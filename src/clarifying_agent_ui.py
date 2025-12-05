"""
Standalone Clarifying Agent for UI Level
Handles multi-turn clarification before routing
"""
import os
import json
import time
from typing import Dict, Any, Optional
from pymongo import MongoClient
from dotenv import load_dotenv
from SemanticDictionaryProcessor import SemanticDictionaryProcessor
from CollectionRouter import CollectionRouterAgent
from clarifying_agent2 import clarify_query
from memory.memorymanager import get_chat_history_as_messages, push_clarification_turns_async
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

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

def fetch_user_profile(email: str, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
    """
    Fetch user profile from hr.base_report collection with retries.
    
    Args:
        email: User email
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 0.5)
    
    Returns:
        Dictionary with user profile or None if fetch fails after retries
    """
    if not MONGODB_URI:
        print("Error: MONGODB_URI not set")
        return None
    
    for attempt in range(max_retries):
        try:
            client = MongoClient(MONGODB_URI)
            db = client["hr"]
            employees = db["base_report"]
            
            record = employees.find_one(
                {"primary email": email},
                {"_id": 0, "employee code": 1, "designation": 1, "region": 1, "department": 1}
            )
            
            client.close()
            
            if record and "designation" in record:
                return {
                    "employee_code": record.get("employee code", 0),
                    "designation": record.get("designation", "").lower(),
                    "department": record.get("department", ""),
                    "region": record.get("region", None)
                }
            else:
                # User not found in database
                print(f"Warning: User {email} not found in base_report")
                return {
                    "employee_code": 0,
                    "designation": "unknown",
                    "department": "unknown",
                    "region": None
                }
        
        except Exception as e:
            print(f"Error fetching user profile (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print(f"Failed to fetch user profile after {max_retries} attempts")
                return None
    
    return None

def fetch_rbac_permissions(employee_code: int) -> Optional[Dict[str, Any]]:
    """
    Fetch RBAC permissions from access_record.json based on employee_code.
    Returns None if not found or employee_code is 0.
    
    Returns:
        Dictionary with keys: allowed_regions, allowed_grades, department_exceptions
        or None if not found
    """
    if employee_code == 0:
        return None
    
    try:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "access_record.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        for record in records:
            if record.get("Emp Code") == employee_code:
                return {
                    "allowed_regions": record.get("Region", []),
                    "allowed_grades": record.get("Grade", []),
                    "department_exceptions": record.get("Department_exception", [])
                }
        return None
    except Exception as e:
        print(f"Error fetching RBAC permissions: {e}")
        return None

def run_clarifying_agent(email: str, question: str, session_id: Optional[str] = None, needs_routing: bool = False) -> Dict[str, Any]:
    """
    Unified agent at UI level.
    Handles clarification, enhancement, routing, and query modification.
    
    Args:
        email: User email
        question: User query or clarification response
        session_id: Optional session ID for state management (defaults to email)
        needs_routing: Whether to perform routing (True for Combined tab, False for MQL Agent tab)
    
    Returns:
        {
            "needs_clarification": bool,
            "questions": [...],  # if needs_clarification
            "final_clarified_query": "...",  # if ready
            "intent": "self" or "others",
            "route": "document" | "policy",  # if needs_routing=True and ready
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
    
    # Load chat history from MongoDB for each query (ensures we have latest data)
    # This is important because previous queries might have saved new history asynchronously
    try:
        state["chat_history_messages"] = get_chat_history_as_messages(email) or []
        if not state.get("chat_history_loaded", False):
            # Mark as loaded on first successful load (for logging/debugging)
            state["chat_history_loaded"] = True
            print(f"✅ Loaded chat history from MongoDB: {len(state['chat_history_messages'])} messages")
        else:
            # Reloaded for subsequent queries
            print(f"🔄 Reloaded chat history from MongoDB: {len(state['chat_history_messages'])} messages")
    except Exception as e:
        print(f"Warning: Failed to load chat history: {e}")
        if "chat_history_messages" not in state:
            state["chat_history_messages"] = []
        state["chat_history_loaded"] = True  # Mark as attempted to avoid repeated errors
    
    # Fetch user profile (with retries)
    user_profile = fetch_user_profile(email)
    if user_profile is None:
        # Return error response with appropriate route if needed
        route = "document" if needs_routing else None
        return {
            "needs_clarification": False,
            "error": "Failed to fetch user profile. Please try again.",
            "final_clarified_query": question,
            "intent": "self",
            "route": route,
            "user_profile": None,
            "rbac_permissions": None
        }
    
    # Fetch RBAC permissions using employee_code
    rbac_permissions = fetch_rbac_permissions(user_profile.get("employee_code", 0))
    
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
    # Include: MongoDB history (source of truth) + Current session turns (for immediate context)
    # Deduplicate to avoid showing same turn twice
    chat_history_text = ""
    all_history_parts = []
    seen_turns = set()  # Track seen turns to avoid duplicates
    
    # Add MongoDB history from state (source of truth - includes all saved turns)
    for msg_dict in state["chat_history_messages"]:
        user_msg = msg_dict.get("user", "").strip()
        bot_msg = msg_dict.get("assistant", "").strip()
        # Skip "Allowed" messages
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            if user_msg or bot_msg:
                # Create a unique key for this turn (user + assistant)
                turn_key = (user_msg, bot_msg)
                if turn_key not in seen_turns:
                    seen_turns.add(turn_key)
                    all_history_parts.append(f"User: {user_msg}\nAssistant: {bot_msg}")
    
    # Add current session conversation turns (for immediate context - might include unsaved turns)
    # This ensures we have the latest context even if async save hasn't completed yet
    for turn in state.get("current_session_turns", []):
        user_msg = turn.get("user", "").strip()
        bot_msg = turn.get("assistant", "").strip()
        # Skip "Allowed" messages
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            if user_msg or bot_msg:
                # Create a unique key for this turn (user + assistant)
                turn_key = (user_msg, bot_msg)
                if turn_key not in seen_turns:
                    # This turn is not in MongoDB history yet (async save pending or failed)
                    seen_turns.add(turn_key)
                    all_history_parts.append(f"User: {user_msg}\nAssistant: {bot_msg}")
    
    if all_history_parts:
        # Limit total history to last 10 turns to avoid token bloat
        # (MongoDB already limits to 10, current_session_turns to 10, but deduplication might reduce this)
        all_history_parts = all_history_parts[-10:]
        chat_history_text = "\n\n".join(all_history_parts)
    
    # Pass current clarification progress to clarifying agent
    # CRITICAL: Ensure original_query is preserved from state
    current_progress = state.get("clarification_progress", {})
    if current_progress and current_progress.get("original_query"):
        # Original query exists in state - preserve it
        print(f"📌 Passing original_query from state: {current_progress['original_query']}")
    
    # Call unified agent (clarification + enhancement + routing + modification)
    result = clarify_query(
        question,
        structure["collections"],
        structure["ambiguous_terms"],
        chat_history=chat_history_text,
        clarification_progress=current_progress,
        user_profile=user_profile,
        needs_routing=needs_routing
    )
    
    # Extract results
    needs_clarification = result.get("status") == "needs_clarification"
    intent = result.get("intent", "self")
    clarification_progress = result.get("clarification_progress", {})
    
    # Update session state with clarification progress
    if clarification_progress:
        # CRITICAL: Always preserve original_query from state if it exists (continuation scenario)
        # Only set it if this is the first clarification (not in state yet)
        if not state["clarification_progress"].get("original_query"):
            # First clarification - store original query
            state["clarification_progress"]["original_query"] = clarification_progress.get("original_query", question)
            print(f"✅ Stored original_query in state: {state['clarification_progress']['original_query']}")
        else:
            # Continuation - preserve original_query from state, don't overwrite
            # But update it if LLM provided a better one (shouldn't happen, but handle it)
            llm_original = clarification_progress.get("original_query", "")
            if llm_original and llm_original != state["clarification_progress"]["original_query"]:
                # LLM provided different original - use state's version (it's the true original)
                print(f"⚠️ LLM provided different original_query, preserving state version")
        
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
                clarification_text = "Please clarify the following:\n\n"
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
            "route": None,  # No route yet, still clarifying
            "clarification_progress": state["clarification_progress"],
            "user_profile": user_profile,
            "rbac_permissions": rbac_permissions
        }
    else:
        # All clarified - get final query
        final_clarified_query = result.get("final_clarified_query", question)
        
        # NOTE: We don't save anything here anymore
        # Clarification questions were already saved when needs_clarification was True
        # Final response will be saved in app.py after query execution
        
        # Extract original_query BEFORE resetting state (needed for saving final response)
        original_query = state["clarification_progress"].get("original_query", question)
        
        # Reset clarification progress for next query
        state["clarification_progress"] = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
        
        # Extract route if available (only when needs_routing=True and status="ready")
        route = result.get("route", None)
        
        return {
            "needs_clarification": False,
            "final_clarified_query": final_clarified_query,
            "intent": intent,
            "route": route,  # "document" or "policy" (if needs_routing=True)
            "original_query": original_query,  # Include original query for saving final response
            "clarification_progress": {},
            "user_profile": user_profile,
            "rbac_permissions": rbac_permissions
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

