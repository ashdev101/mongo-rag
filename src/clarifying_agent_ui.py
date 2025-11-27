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
            "chat_history_messages": [],
            "clarification_progress": {
                "original_query": "",
                "clarified_terms": [],
                "pending_terms": []
            }
        }
    
    state = _clarification_state[session_id]
    
    # Load chat history once per session
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
    
    if all_history_parts:
        chat_history_text = "\n\n".join(all_history_parts)
    
    # Call clarifying agent
    result = clarify_query(
        question,
        structure["collections"],
        structure["ambiguous_terms"],
        chat_history=chat_history_text
    )
    
    # Extract results
    needs_clarification = result.get("status") == "needs_clarification"
    intent = result.get("intent", "self")
    clarification_progress = result.get("clarification_progress", {})
    
    # Update session state
    if clarification_progress:
        # If this is first clarification, store original query
        if not state["clarification_progress"].get("original_query"):
            state["clarification_progress"]["original_query"] = clarification_progress.get("original_query", question)
        # Update progress
        state["clarification_progress"].update(clarification_progress)
    
    if needs_clarification:
        questions = result.get("questions", [])
        return {
            "needs_clarification": True,
            "questions": questions,
            "intent": intent,
            "clarification_progress": state["clarification_progress"]
        }
    else:
        # All clarified - get final query
        final_clarified_query = result.get("final_clarified_query", question)
        
        # Save clarification conversation to MongoDB (async) if there was a clarification process
        original_query = state["clarification_progress"].get("original_query", "")
        if original_query and original_query != question:
            # There was a clarification process - save it
            clarification_turns = [
                {
                    "user": original_query,
                    "assistant": ""  # Will be filled from questions if available
                },
                {
                    "user": question,  # User's answer/clarified response
                    "assistant": ""  # Empty, will be filled by final response later
                }
            ]
            # Async save
            push_clarification_turns_async(email, clarification_turns)
            print(f"✅ Saved clarification conversation to MongoDB (async)")
        
        # Reset clarification progress for next query
        state["clarification_progress"] = {
            "original_query": "",
            "clarified_terms": [],
            "pending_terms": []
        }
        
        return {
            "needs_clarification": False,
            "final_clarified_query": final_clarified_query,
            "intent": intent,
            "clarification_progress": {}
        }

def clear_clarification_state(session_id: str):
    """Clear clarification state for a session"""
    if session_id in _clarification_state:
        del _clarification_state[session_id]

