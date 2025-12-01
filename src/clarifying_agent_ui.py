"""
Standalone Clarifying Agent for UI Level
Handles multi-turn clarification before routing
"""
import os
from typing import Dict, Any, Optional
from SemanticDictionaryProcessor import SemanticDictionaryProcessor
from CollectionRouter import CollectionRouterAgent
from clarifying_agent2 import clarify_query
from memory.memorymanager import get_chat_history_as_messages, push_clarification_turns_async
from langchain_core.messages import HumanMessage, AIMessage

# Initialize SemanticDictionaryProcessor once (singleton pattern)
_semantic_processor = None

def get_semantic_processor():
    global _semantic_processor
    if _semantic_processor is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database_summary.json")
        _semantic_processor = SemanticDictionaryProcessor(json_path)
    return _semantic_processor

# Session-level state storage (in-memory, per user session)
_clarification_state = {}

def run_clarifying_agent(email: str, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Standalone clarifying agent at UI level.
    Handles multi-turn clarification with state management.
    
    Args:
        email: User email
        question: User query or clarification response
        session_id: Optional session ID for state management (defaults to email)
    
    Returns:
        {
            "needs_clarification": bool,
            "questions": [...],  # if needs_clarification
            "final_clarified_query": "...",  # if ready
            "intent": "self" or "others",
            "clarification_progress": {...}
        }
    """
    # Use email as session_id if not provided
    if session_id is None:
        session_id = email
    
    # Initialize or get session state
    if session_id not in _clarification_state:
        _clarification_state[session_id] = {
            "chat_history_loaded": False,
            "chat_history_messages": [],  # MongoDB history (previous sessions)
            "current_session_turns": [],  # Current session conversation turns (query/answer pairs)
            "clarification_progress": {
                "original_query": "",
                "pending_ambiguities": {},  # Track ambiguities that need clarification
                "resolved_ambiguities": {}  # Track ambiguities that have been resolved
            }
        }
    
    state = _clarification_state[session_id]
    
    # Load chat history once per session (from MongoDB - previous sessions)
    if not state["chat_history_loaded"]:
        state["chat_history_messages"] = get_chat_history_as_messages(email)
        state["chat_history_loaded"] = True
    
    # Get semantic processor
    processor = get_semantic_processor()
    collections = processor.get_collection_routing_list()
    default_collections = processor.get_default_collections()
    
    # Route query to get relevant collections
    router = CollectionRouterAgent(collections, default_collections)
    collection = router.route_query(question)
    
    # Get clarification structure
    structure = processor.get_clarification_agent_structure(
        allowed_collections=collection
    )
    
    # Build chat history text from state
    # Include: MongoDB history (previous sessions) + Current session turns (recent conversation)
    chat_history_text = ""
    all_history_parts = []
    
    # Add MongoDB history from state (previous sessions)
    for msg_dict in state["chat_history_messages"]:
        user_msg = msg_dict.get("user", "").strip()
        bot_msg = msg_dict.get("assistant", "").strip()
        # Skip "Allowed" messages
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            if user_msg or bot_msg:
                all_history_parts.append(f"User: {user_msg}\nAssistant: {bot_msg}")
    
    # Add current session conversation turns (most recent context)
    # This includes queries/answers from the current session that haven't been saved to MongoDB yet
    for turn in state.get("current_session_turns", []):
        user_msg = turn.get("user", "").strip()
        bot_msg = turn.get("assistant", "").strip()
        # Skip "Allowed" messages
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            if user_msg or bot_msg:
                all_history_parts.append(f"User: {user_msg}\nAssistant: {bot_msg}")
    
    if all_history_parts:
        chat_history_text = "\n\n".join(all_history_parts)
    
    # Pass current clarification progress to clarifying agent
    current_progress = state.get("clarification_progress", {})
    
    # Call clarifying agent
    result = clarify_query(
        question,
        structure["collections"],
        structure["ambiguous_terms"],
        chat_history=chat_history_text,
        clarification_progress=current_progress
    )
    
    # Extract results
    needs_clarification = result.get("status") == "needs_clarification"
    intent = result.get("intent", "self")
    clarification_progress = result.get("clarification_progress", {})
    
    # Update session state with clarification progress
    if clarification_progress:
        # If this is first clarification, store original query
        if not state["clarification_progress"].get("original_query"):
            state["clarification_progress"]["original_query"] = clarification_progress.get("original_query", question)
        
        # Update pending_ambiguities and resolved_ambiguities
        if "pending_ambiguities" in clarification_progress:
            state["clarification_progress"]["pending_ambiguities"] = clarification_progress["pending_ambiguities"]
        if "resolved_ambiguities" in clarification_progress:
            # Merge resolved ambiguities (don't overwrite, merge)
            current_resolved = state["clarification_progress"].get("resolved_ambiguities", {})
            current_resolved.update(clarification_progress.get("resolved_ambiguities", {}))
            state["clarification_progress"]["resolved_ambiguities"] = current_resolved
    
    if needs_clarification:
        questions = result.get("questions", [])
        
        # ===== SAVE CLARIFICATION QUESTIONS IMMEDIATELY =====
        # Format questions nicely for chat history
        if questions:
            if len(questions) == 1:
                clarification_text = questions[0]
            else:
                clarification_text = "I need a few clarifications:\n\n"
                for i, q in enumerate(questions, 1):
                    clarification_text += f"{i}. {q}\n"
            
            # Get the original query from state (already stored at line 131)
            # Use original query, not current question (which might be a continuation answer)
            original_query = state["clarification_progress"].get("original_query", question)
            
            # Save original query → clarification questions to MongoDB (async)
            # This ensures clean chat history with no empty assistant fields
            push_clarification_turns_async(email, [{
                "user": original_query,
                "assistant": clarification_text
            }])
            print(f"✅ Saved clarification questions to MongoDB (async)")
        
        return {
            "needs_clarification": True,
            "questions": questions,
            "intent": intent,
            "clarification_progress": state["clarification_progress"]
        }
    else:
        # All clarified - get final query
        final_clarified_query = result.get("final_clarified_query", question)
        
        # NOTE: We don't save anything here anymore
        # Clarification questions were already saved when needs_clarification was True
        # Final response will be saved in app.py after query execution
        
        # Reset clarification progress for next query
        state["clarification_progress"] = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
        
        return {
            "needs_clarification": False,
            "final_clarified_query": final_clarified_query,
            "intent": intent,
            "clarification_progress": {}
        }

def add_session_turn(email: str, user_query: str, bot_response: str, session_id: Optional[str] = None):
    """
    Add a conversation turn to the current session state.
    This allows the clarifying agent to see recent conversation context.
    
    Args:
        email: User email
        user_query: User's query
        bot_response: Bot's response (final answer, not "Allowed")
        session_id: Optional session ID (defaults to email)
    """
    if session_id is None:
        session_id = email
    
    # Initialize state if needed
    if session_id not in _clarification_state:
        _clarification_state[session_id] = {
            "chat_history_loaded": False,
            "chat_history_messages": [],
            "current_session_turns": [],
            "clarification_progress": {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    state = _clarification_state[session_id]
    
    # Add turn to current session (keep last 10 turns)
    if "current_session_turns" not in state:
        state["current_session_turns"] = []
    
    # Filter out "Allowed" messages
    if bot_response and bot_response.strip().lower() not in ["allowed", "not allowed", "unclear intent"]:
        state["current_session_turns"].append({
            "user": user_query,
            "assistant": bot_response
        })
        # Keep only last 10 turns to avoid memory bloat
        state["current_session_turns"] = state["current_session_turns"][-10:]

def clear_clarification_state(session_id: str):
    """Clear clarification state for a session"""
    if session_id in _clarification_state:
        del _clarification_state[session_id]

