import os
import re
import json
import time
from typing import TypedDict, Annotated, Dict, Any, Optional, List
from langgraph.graph.message import add_messages, AnyMessage
from langchain_core.messages import AIMessage , HumanMessage
from langgraph.graph import StateGraph, END
from pymongo import MongoClient
from langchain_openai import ChatOpenAI
from SemanticDictionaryProcessor import SemanticDictionaryProcessor
from CollectionRouter import CollectionRouterAgent
from clarifying_agent2 import clarify_query, format_ambiguous_terms_toon, format_semantic_context_toon
from memory.memorymanager import get_chat_history, push_convo_pair, get_chat_history_as_messages, push_clarification_turns_async
# Load environment variables from .env file
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MONGODB_URI = os.getenv('MONGODB_URI')

# Initialize SemanticDictionaryProcessor once at module level (singleton pattern)
# This avoids reloading the JSON file on every clarification check
_semantic_processor = None
def get_semantic_processor():
    global _semantic_processor
    if _semantic_processor is None:
        # Construct path relative to project root (where database_summary.json is located)
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database_summary.json")
        _semantic_processor = SemanticDictionaryProcessor(json_path)
    return _semantic_processor

# ============================================================================
# Session-level state storage (persists clarification_progress between turns)
# ============================================================================
_session_state = {}  # email -> {clarification_progress, chat_history_messages, user_profile}
_last_email = None  # Track last email to detect email changes (single session assumption)

def get_session_state(email: str) -> Dict[str, Any]:
    """Get or initialize session state for an email. Creates fresh state for new email."""
    global _last_email
    
    # If email changed, clear previous session state
    if _last_email is not None and _last_email != email and _last_email in _session_state:
        del _session_state[_last_email]
    
    _last_email = email
    
    # Create fresh state for new email
    if email not in _session_state:
        _session_state[email] = {
            "clarification_progress": {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            },
            "chat_history_messages": [],
            "user_profile": None
        }
    return _session_state[email]

def update_session_state(email: str, **updates):
    """Update session state for an email."""
    state = get_session_state(email)
    state.update(updates)

def update_chat_history(email: str, user_msg: str, bot_msg: str):
    """
    Update chat_history_messages in session state (synchronously, in-memory).
    Also saves to MongoDB asynchronously.
    This ensures next turn has immediate access to latest history without MongoDB read.
    """
    # Filter out access check messages
    if bot_msg and bot_msg.strip().lower() in ["allowed", "not allowed", "unclear intent"]:
        return
    
    # Update session state synchronously (in-memory, immediate)
    state = get_session_state(email)
    state["chat_history_messages"].append({
        "user": user_msg.strip() if user_msg else "",
        "assistant": bot_msg.strip() if bot_msg else ""
    })
    
    # Keep only last 10 turns in memory (matches MongoDB limit)
    state["chat_history_messages"] = state["chat_history_messages"][-10:]
    
    # Save to MongoDB asynchronously (fire-and-forget, doesn't block)
    push_convo_pair(email=email, user_msg=user_msg, bot_msg=bot_msg)

def clear_session_state(email: str = None):
    """Clear session state when email changes or session ends."""
    global _last_email
    if email:
        if email in _session_state:
            del _session_state[email]
    else:
        # Clear all if no email specified
        _session_state.clear()
    _last_email = None

class AccessState(TypedDict):
    needs_clarification: bool
    clarification_question: str
    email: str
    employee_code : int  # fetched from MongoDB
    designation: str  # fetched from MongoDB
    department : str  # fetched from MongoDB
    region : str  # fetched from MongoDB
    question: str
    intent: str
    decision: str
    messages: Annotated[list, add_messages]
    modified_query : str
    # New fields for chat history and clarification tracking
    chat_history_loaded: bool  # Flag to track if chat history loaded
    chat_history_messages: list  # Previous messages from MongoDB (last 10)
    clarification_progress: dict  # Track clarification state
    final_clarified_query: str  # Final query when all ambiguities resolved
    # Unified agent fields
    user_profile: dict  # User profile (employee_code, designation, department, region)
    rbac_permissions: dict  # RBAC permissions (allowed_regions, allowed_grades, department_exceptions)
    route: str  # Route decision (document/policy) for Combined tab
    needs_routing: bool  # Whether routing is needed (True for Combined tab)
    questions: list  # Clarification questions array

# llm = ChatOpenAI(model="gpt-4o-mini")  # lightweight but smart

def is_hr_department(department: str) -> bool:
    """
    Check if department is HR (case-insensitive, handles variations).
    Handles: "Human Resources", "HR", "hr", "human resources", etc.
    """
    if not department:
        return False
    dept_lower = department.lower().strip()
    # Handle variations
    hr_variations = ["human resources", "hr", "human resource"]
    return dept_lower in hr_variations

# ============================================================================
# Compact Chat History Format (Token Optimization)
# ============================================================================

def format_chat_history_compact(chat_history_messages: list) -> str:
    """
    Format chat history in compact format to reduce tokens.
    Uses "U:" and "A:" instead of "User:" and "Assistant:".
    """
    if not chat_history_messages:
        return ""
    
    parts = []
    for msg_dict in chat_history_messages[-10:]:  # Last 10 messages
        user_msg = msg_dict.get("user", "").strip()
        bot_msg = msg_dict.get("assistant", "").strip()
        
        # Skip "Allowed" messages
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            if user_msg:
                parts.append(f"U: {user_msg}")
            if bot_msg:
                parts.append(f"A: {bot_msg}")
    
    return "\n".join(parts)

# ============================================================================
# Access Control (Now handled entirely by LLM in clarifying_agent2.py)
# ============================================================================
# Removed: check_sensitive_field_access() - Now handled entirely by LLM
# LLM performs: pronoun resolution → intent detection → access control check
# This ensures pronouns are resolved from chat history before intent is determined

# ============================================================================
# Fetch User Profile (with retries)
# ============================================================================

def fetch_user_profile(email: str, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
    """Fetch user profile from hr.base_report collection with retries. Returns default profile if not found."""
    if not MONGODB_URI:
        print("Error: MONGODB_URI not set")
        return {"employee_code": 0, "designation": "unknown", "department": "unknown", "region": None}
    
    for attempt in range(max_retries):
        try:
            client = MongoClient(MONGODB_URI)
            record = client["hr"]["base_report"].find_one(
                {"primary email": email},
                {"_id": 0, "employee code": 1, "designation": 1, "region": 1, "department": 1}
            )
            client.close()
            
            if record:
                return {
                    "employee_code": record.get("employee code", 0),
                    "designation": record.get("designation", "").lower() if record.get("designation") else "unknown",
                    "department": record.get("department", "") or "unknown",
                    "region": record.get("region", None)
                }
            # Record not found - return default profile
            return {"employee_code": 0, "designation": "unknown", "department": "unknown", "region": None}
        except Exception as e:
            print(f"Error fetching user profile (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                # Return default profile on final failure instead of None
                return {"employee_code": 0, "designation": "unknown", "department": "unknown", "region": None}
    return {"employee_code": 0, "designation": "unknown", "department": "unknown", "region": None}

# ============================================================================
# Fetch RBAC Permissions
# ============================================================================

def fetch_rbac_permissions(employee_code: int) -> Optional[Dict[str, Any]]:
    """Fetch RBAC permissions from access_record.json. Returns None if not found."""
    if employee_code == 0:
        return None
    try:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "access_record.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            for record in json.load(f):
                if record.get("Emp Code") == employee_code:
                    return {
                        "allowed_regions": record.get("Region", []),
                        "allowed_grades": record.get("Grade", []),
                        "department_exceptions": record.get("Department_exception", [])
                    }
    except Exception as e:
        print(f"Error fetching RBAC permissions: {e}")
    return None

# ============================================================================
# Pronoun Resolution (Inline - Hybrid Approach)
# ============================================================================

def resolve_pronouns_rule_based(query: str, chat_history: List[Dict[str, str]]) -> tuple[str, bool]:
    """
    Fast rule-based pronoun resolution for common cases (Hybrid Approach - Option C).
    Handles all pronouns: his, her, their, he, she, they, it, this, that, him.
    Focuses on insensitive info: email, number, name, code, id for manager/reviewer.
    
    Args:
        query: User query that may contain pronouns
        chat_history: List of message dicts with "user" and "assistant" keys
    
    Returns:
        Tuple of (resolved_query, is_confident):
        - resolved_query: Resolved query (or original if couldn't resolve)
        - is_confident: True if resolution is confident (clear entity match), False otherwise
    """
    if not query or not chat_history:
        return query, False
    
    # All pronouns to handle (comprehensive list)
    pronouns = ["his", "her", "their", "he", "she", "they", "it", "this", "that", "him"]
    # Insensitive info that can be asked about
    insensitive_info = ["email", "number", "name", "code", "id", "contact", "phone", "mobile"]
    
    query_lower = query.lower()
    has_pronoun = any(pronoun in query_lower for pronoun in pronouns)
    
    # If no pronouns, return original (no resolution needed)
    if not has_pronoun:
        return query, False
    
    # Search last 10 messages (not just 3) for better context
    # Skip clarification questions, prioritize answers
    last_answer_msg = ""
    for msg in reversed(chat_history[-10:]):  # Check last 10 messages
        assistant_msg = msg.get("assistant", "").lower()
        if not assistant_msg:
            continue
        
        # Skip clarification questions (they don't contain entity info)
        if any(phrase in assistant_msg for phrase in ["do you mean", "which", "please clarify", "?"]):
            continue
        
        # Look for answer patterns (contains entity mentions)
        if "manager" in assistant_msg or "reviewer" in assistant_msg:
            # Check if it's an answer (contains name, email, or entity info)
            if any(pattern in assistant_msg for pattern in ["name is", "is", "email", "number", "your"]):
                last_answer_msg = assistant_msg
                break  # Found a good answer, use it
    
    if not last_answer_msg:
        # No clear answer found → let LLM handle (not confident)
        return query, False
    
    # Determine entity type from answer message
    entity_type = None
    is_confident = False
    
    # Manager patterns - check for clear manager mentions
    if "manager" in last_answer_msg:
        # Check if it's clearly about manager (not ambiguous)
        if any(pattern in last_answer_msg for pattern in ["your manager", "manager's", "manager is", "manager name"]):
            entity_type = "manager"
            is_confident = True
    
    # Reviewer patterns - check for clear reviewer mentions
    if "reviewer" in last_answer_msg and not entity_type:
        # Check if it's clearly about reviewer (not ambiguous)
        if any(pattern in last_answer_msg for pattern in ["your reviewer", "reviewer's", "reviewer is", "reviewer name"]):
            entity_type = "reviewer"
            is_confident = True
    
    # If no clear entity found, let LLM handle
    if not entity_type:
        return query, False
    
    # Resolve pronouns based on entity type
    resolved_query = query
    
    # Map pronouns to entity-specific replacements
    if entity_type == "manager":
        # Resolve all pronouns to "my manager's" or "my manager" depending on context
        resolved_query = re.sub(r'\bhis\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bher\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\btheir\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bhim\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bhe\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bshe\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthey\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bit\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthis\b', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthat\b', "my manager", resolved_query, flags=re.IGNORECASE)
    elif entity_type == "reviewer":
        # Resolve all pronouns to "my reviewer's" or "my reviewer" depending on context
        resolved_query = re.sub(r'\bhis\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bher\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\btheir\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bhim\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bhe\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bshe\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthey\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bit\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthis\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthat\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
    
    # Only log if resolution actually happened
    if resolved_query != query:
        print(f"✅ Rule-based pronoun resolution ({entity_type}): '{query}' → '{resolved_query}' (confident: {is_confident})")
    
    return resolved_query, is_confident


# ============================================================================
# Unified Agent Node (LangGraph Node)
# ============================================================================

def unified_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified agent: Clarification → Enhancement → Routing → Access Control (LLM-based).
    Access control is handled by LLM in clarify_query() which performs:
    pronoun resolution → intent detection → access control check.
    RBAC permissions are fetched here but applied AFTER clarification in QueryProcessor.py (line 153-170).
    """
    # Extract query and email
    messages = state.get("messages", [])
    if not messages or not state.get("email"):
        return {"error": "No messages or email in state", "needs_clarification": False, 
                "decision": "Error: Invalid request. Please try again."}
    
    current_query = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
    email = state["email"]
    
    # OPTIMIZATION: Use user_profile from state (already fetched in QueryProcessor or data_preparation_node)
    # No duplicate fetch - use session state memory
    user_profile = state.get("user_profile")
    if not user_profile:
        # Fallback: fetch only if not in state (shouldn't happen, but handle gracefully)
        print(f"⚠️ WARNING: user_profile not in state, fetching now (should be cached)")
        user_profile = fetch_user_profile(email)
        # Cache in session state for next turn
        session_state = get_session_state(email)
        session_state["user_profile"] = user_profile
    if not user_profile:
        # Final fallback: create default profile
        user_profile = {"employee_code": 0, "designation": "unknown", "department": "unknown", "region": None}
    
    # Access control is now handled entirely by LLM in clarify_query()
    # LLM performs: pronoun resolution → intent detection → access control check
    # This ensures pronouns are resolved from chat history before intent is determined
    
    # OPTION C: Hybrid Approach - Rule-based fast path, LLM validates/fallback
    # Preserve clarification_progress - let LLM handle new query detection (it has better context)
    clarification_progress = state.get("clarification_progress", {"original_query": "", "pending_ambiguities": {}, "resolved_ambiguities": {}})
    
    # PHASE 1: Pronoun Resolution (Hybrid: Rule-based first, LLM validates/fallback)
    # Fast rule-based for common cases, LLM handles edge cases and validates
    chat_history_messages = state.get("chat_history_messages", [])
    resolved_query, is_confident = resolve_pronouns_rule_based(current_query, chat_history_messages)
    
    # If rule-based resolved with confidence, use resolved query
    # If not confident, pass original query to LLM (LLM will resolve and validate)
    query_for_llm = resolved_query if is_confident else current_query
    
    # Log if we're using LLM fallback
    if not is_confident and resolved_query != current_query:
        print(f"⚠️ Rule-based resolved but not confident, passing to LLM for validation: '{resolved_query}'")
    elif not is_confident:
        print(f"ℹ️ Rule-based couldn't resolve pronouns, LLM will handle: '{current_query}'")
    
    # Prepare context for clarification (use query_for_llm for routing - may be resolved or original)
    processor = get_semantic_processor()
    collections = processor.get_collection_routing_list()
    default_collections = processor.get_default_collections()
    collection = CollectionRouterAgent(collections, default_collections).route_query(query_for_llm)
    structure = processor.get_clarification_agent_structure(allowed_collections=collection)
    
    # HYBRID APPROACH: Filter ambiguous_terms by query content (code-level filtering)
    # Only include ambiguous_terms that actually appear in the query
    # This prevents LLM from seeing irrelevant ambiguous_terms (e.g., "reviewer" when query is "manager name")
    query_lower = query_for_llm.lower()
    filtered_ambiguous_terms = [
        term_data for term_data in structure["ambiguous_terms"]
        if term_data.get("term", "").lower() in query_lower
    ]
    
    # Log filtering for debugging
    if len(filtered_ambiguous_terms) != len(structure["ambiguous_terms"]):
        filtered_terms = [t.get("term", "") for t in filtered_ambiguous_terms]
        all_terms = [t.get("term", "") for t in structure["ambiguous_terms"]]
        print(f"🔍 Filtered ambiguous_terms: {all_terms} → {filtered_terms} (query: '{query_for_llm}')")
    
    # Call clarify_query with optimizations (TOON format used internally)
    # Pass query_for_llm to LLM:
    # - If rule-based resolved with confidence → LLM validates/corrects if needed
    # - If rule-based didn't resolve → LLM resolves from scratch
    # LLM has all context (chat history) and will handle edge cases
    # Pass filtered_ambiguous_terms (only terms present in query)
    result = clarify_query(
        query_for_llm, structure["collections"], filtered_ambiguous_terms,
        chat_history=format_chat_history_compact(chat_history_messages),
        clarification_progress=clarification_progress,
        user_profile=user_profile, needs_routing=state.get("needs_routing", False)
    )
    
    # Build state updates
    status = result.get("status", "")
    needs_clarification = status == "needs_clarification"
    access_denied = status == "access_denied"
    
    # FIX: Use state.get() as fallback for intent (was causing NameError)
    intent = result.get("intent", state.get("intent", ""))
    
    # Debug: Print what LLM returned
    print(f"🔍 LLM Result: status={status}, needs_clarification={needs_clarification}, access_denied={access_denied}, final_query={result.get('final_clarified_query', 'N/A')[:50]}")
    
    updates = {
        "user_profile": user_profile,
        "employee_code": user_profile.get("employee_code", 0),
        "designation": user_profile.get("designation", ""),
        "department": user_profile.get("department", ""),
        "region": user_profile.get("region", ""),
        "intent": intent,
        "clarification_progress": result.get("clarification_progress", {})
        # OPTIMIZATION: RBAC permissions removed from here - will be fetched lazily in QueryProcessor
        # only when needed (after clarification, if HR user)
    }
    
    # FIX: Handle access_denied status first
    if access_denied:
        updates.update({
            "needs_clarification": False,
            "decision": result.get("decision", "Access Denied"),
            "questions": []
        })
        return updates
    
    # Handle needs_clarification
    if needs_clarification:
        questions = result.get("questions", [])
        updates.update({
            "needs_clarification": True,
            "clarification_question": questions[0] if len(questions) == 1 else \
                "Please clarify the following:\n\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)),
            "questions": questions,
            "decision": ""  # No decision yet, waiting for clarification
        })
        return updates
    
    # Handle ready status (all clear, access allowed)
    if status == "ready":
        final_query = result.get("final_clarified_query", current_query)
        updates.update({
            "needs_clarification": False,
            "final_clarified_query": final_query, 
            "question": final_query,
            "decision": "Allowed"  # Set decision so QueryProcessor knows query is ready
        })
        if state.get("needs_routing"):
            updates["route"] = result.get("route", "document")
        return updates
    
    # Unknown status - log warning and default to error
    print(f"⚠️ WARNING: Unknown status from LLM: {status}")
    updates.update({
        "error": f"Unknown status from LLM: {status}",
        "decision": "Error: Unknown status from LLM",
        "needs_clarification": False
    })
    return updates

def normalize_clarification_state(state: AccessState) -> dict:
    """
    Auto-fix inconsistencies in clarification state.
    Returns corrected state updates.
    """
    updates = {}
    
    needs_clarification = state.get("needs_clarification", False)
    clarification_question = state.get("clarification_question", "").strip()
    
    # Rule 1: If needs_clarification=True, clarification_question must exist
    if needs_clarification and not clarification_question:
        # Auto-fix: Clear the flag if no question
        updates["needs_clarification"] = False
        print("⚠️ Auto-fixed: needs_clarification=True but no question. Clearing flag.")
    
    # Rule 2: If clarification_question exists, needs_clarification should be True
    if clarification_question and not needs_clarification:
        # Auto-fix: Set the flag if question exists
        updates["needs_clarification"] = True
        print("⚠️ Auto-fixed: clarification_question exists but flag is False. Setting flag.")
    
    # Rule 3: If needs_clarification=False, clear the question
    if not needs_clarification and clarification_question:
        updates["clarification_question"] = ""
    
    return updates

def initialize_chat_history_node(state: AccessState):
    """
    Load chat history from MongoDB once at session start and store in state.
    This node should run before input_node on the first query.
    """
    # Check if already loaded
    if state.get("chat_history_loaded", False):
        return {}  # Already loaded, no update needed
    
    email = state.get("email", "")
    if not email:
        return {"chat_history_loaded": True, "chat_history_messages": []}
    
    # Load chat history from MongoDB
    chat_history_messages = get_chat_history_as_messages(email)
    
    # Initialize clarification progress if not exists
    clarification_progress = state.get("clarification_progress", {
        "original_query": "",
        "clarified_terms": [],
        "pending_terms": []
    })
    
    return {
        "chat_history_loaded": True,
        "chat_history_messages": chat_history_messages,
        "clarification_progress": clarification_progress
    }

def input_node(state: AccessState):
    print(state)
    # Get the last human message (user's query - already clarified at UI level)
    last_msg = state["messages"][-1].content
    
    # Simple intent detection (since clarification is handled at UI level)
    # Check if query contains "my", "I", "me" for self intent
    query_lower = last_msg.lower()
    if any(word in query_lower for word in ["my ", " i ", " me ", "myself"]):
        intent = "self"
    elif any(word in query_lower for word in ["'s", "his ", "her ", "their "]):
        intent = "others"
    else:
        # Default to self if no explicit subject
        intent = "self"
    
    # Check if this is a clarification response (there's an AI message before the last human message)
    if len(state["messages"]) > 1:
        # Check if the previous message was an AI message (clarification question)
        prev_msg = state["messages"][-2]
        is_ai_message = (hasattr(prev_msg, 'type') and prev_msg.type == "ai") or isinstance(prev_msg, AIMessage)
        
        if is_ai_message:
            # This is a clarification response - get original query from clarification_progress (persisted in session state)
            clarification_progress = state.get("clarification_progress", {})
            original_question = clarification_progress.get("original_query", "")
            
            # Fallback: If not in clarification_progress, try to find it in messages
            if not original_question:
                for msg in reversed(state["messages"][:-2]):  # Skip last 2 (AI + current human)
                    if (hasattr(msg, 'type') and msg.type == "human") or isinstance(msg, HumanMessage):
                        original_question = msg.content
                        break
            
            # If we found an original question, merge it with the clarification response
            if original_question:
                # Enhanced merge logic: Detect if user is providing answers to clarification questions
                original_lower = original_question.lower()
                last_msg_lower = last_msg.lower()
                
                # Check if the clarification response already contains the original question
                # This means user provided a complete, clarified query
                if original_lower in last_msg_lower:
                    # User provided complete query (e.g., "my performance status and performance reviewer")
                    combined_question = last_msg
                elif last_msg_lower in original_lower:
                    # Original contains the response (unlikely but handle it)
                    combined_question = original_question
                else:
                    # User provided answers to clarification questions
                    # Try to intelligently merge by replacing ambiguous terms in original with specific answers
                    # Example: "my status and reviewer" + "employee status and offboarding reviewer" 
                    #          → "my employee status and offboarding reviewer"
                    
                    # Check if original has ambiguous terms that might be answered in last_msg
                    # Common patterns: "status", "reviewer", "leaves", "manager"
                    combined_question = original_question
                    
                    # If original has "status" and last_msg has qualified status (e.g., "employee status", "performance status")
                    if "status" in original_lower:
                        # Look for qualified status terms in last_msg
                        status_patterns = [
                            r'\b(employee|performance|goal-setting|offboarding)\s+status\b',
                            r'\bstatus\s+(employee|performance|goal-setting|offboarding)\b'
                        ]
                        for pattern in status_patterns:
                            match = re.search(pattern, last_msg_lower, re.IGNORECASE)
                            if match:
                                qualified_status = match.group(0)
                                # Replace "status" in original with qualified status
                                combined_question = re.sub(r'\bstatus\b', qualified_status, combined_question, flags=re.IGNORECASE)
                                break
                    
                    # If original has "reviewer" and last_msg has qualified reviewer
                    if "reviewer" in original_lower:
                        reviewer_patterns = [
                            r'\b(offboarding|performance|goal-setting)\s+reviewer\b',
                            r'\breviewer\s+(offboarding|performance|goal-setting)\b'
                        ]
                        qualified_reviewer = None
                        for pattern in reviewer_patterns:
                            match = re.search(pattern, last_msg_lower, re.IGNORECASE)
                            if match:
                                qualified_reviewer = match.group(0)
                                break
                        
                        # Smart inference: If "performance status" mentioned, infer "performance reviewer"
                        if not qualified_reviewer and "performance" in last_msg_lower and "status" in last_msg_lower:
                            qualified_reviewer = "performance reviewer"
                        
                        if qualified_reviewer:
                            combined_question = re.sub(r'\breviewer\b', qualified_reviewer, combined_question, flags=re.IGNORECASE)
                    
                    # If no intelligent merge happened, append the clarification response
                    if combined_question == original_question:
                        combined_question = f"{original_question} {last_msg}".strip()
                
                print(f"Merged question: {original_question} + {last_msg} = {combined_question}")
                return {"question": combined_question, "intent": intent}
    
    return {"question": last_msg, "intent": intent}

# fetch_role_node removed - user_profile is now passed from unified agent to avoid duplicate fetch
# classify_query_node and query_clarifying_agent_node removed - functionality moved to unified_agent_node
# Intent classification is now done in the combined LLM call in clarify_query

def ask_for_clarification_node(state: AccessState):
    # Store the clarification question and preserve the original question
    # When user responds, their response will be in the next message
    # CRITICAL: Preserve clarification_progress so it persists in session state
    return {
        "messages": [
            AIMessage(content=state["clarification_question"])
        ],
        # Preserve the original question so we can merge it with clarification response
        "question": state.get("question", ""),
        # CRITICAL: Preserve clarification_progress so it's saved to session state
        "clarification_progress": state.get("clarification_progress", {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        })
    }
    # return {
    #     "messages": [
    #         AIMessage(content=state["clarification_question"])
    #     ]
    # }
def clarification_condition(state: AccessState):
    if state.get("needs_clarification", False):
        return "ask_clarification"   # pause + ask user
    else:
        return "modify_query"        # continue normally (skip fetch_role)

# COMMENTED OUT: modify_query_node - Redundant, unified_agent_node already enhances query
# def modify_query_node(state: dict):
#     """
#     Modify query by adding employee_code for self queries.
#     RBAC constraints are already applied by rbac_tool in app.py, so we don't handle region constraints here.
#     """
#     question = state["question"]
#     intent = state["intent"]
#     employee_code = state.get("employee_code", 0)
#     
#     # Check if employee_code is already in the query (unified agent may have added it)
#     employee_code_already_present = (
#         "employee code" in question.lower() or 
#         (employee_code and f"employee code is {employee_code}" in question.lower())
#     )
#     
#     # Only add employee_code for self queries if not already present
#     # RBAC constraints are already applied by rbac_tool in app.py
#     if intent == "self" and employee_code and not employee_code_already_present:
#         modified_query = f"{question} . My employee code is {employee_code}"
#     else:
#         modified_query = question
# 
#     return {"modified_query": modified_query}

# COMMENTED OUT: check_access_node - Redundant, unified_agent_node already checks access early
# def check_access_node(state: AccessState):
#     """
#     Check access permissions based on department, intent, and sensitive fields.
#     
#     Rules:
#     - HR users: Can access anyone (self OR others), but RBAC restricts by region
#     - Non-HR users: 
#       * Can access self queries for non-sensitive info (name, email, manager name/email, etc.)
#       * Cannot access sensitive info even for self (DOB, salary, etc.) - only HR can
#       * Cannot access others' info at all
#     """
#     department = state["department"]
#     intent = state["intent"]
#     question = state.get("question", "").lower()
#     
#     # Check for sensitive fields (even in self queries, non-HR cannot access these)
#     sensitive_fields = ["date of birth", "dob", "birth date", "salary", "compensation", "pay", "ssn", "social security"]
#     has_sensitive_field = any(field in question for field in sensitive_fields)
#     
#     # Use case-insensitive HR check
#     if is_hr_department(department):
#         # HR users: Can access anyone (self OR others), but RBAC restricts by region
#         decision = "Allowed"
#     else:
#         # Non-HR users
#         if intent == "self":
#             # Self queries: allowed for non-sensitive info, denied for sensitive info
#             if has_sensitive_field:
#                 decision = "Not allowed"  # Even self queries for sensitive info are denied for non-HR
#             else:
#                 decision = "Allowed"  # Non-sensitive self queries are allowed
#         elif intent == "others":
#             decision = "Not allowed"  # Non-HR cannot access others' info
#         else:
#             decision = "Unclear intent"
# 
#     return {"decision": decision}

def response_node(state: AccessState):
    msg = AIMessage(content=state["decision"])
    return {"messages": [msg]}


workflow = StateGraph(AccessState)

# def hr_conditional_path(state: dict):
#     # If HR, go to 'modify_query'; else, skip to 'check_access'
#     if state["department"] == "Human Resources":
#         return "modify_query"
#     else:
#         return "check_access"

workflow.add_node("initialize_chat_history", initialize_chat_history_node)
workflow.add_node("input", input_node)
workflow.add_node("unified_agent", unified_agent_node)  # NEW: Unified agent node (replaces query_clarifying_agent)
workflow.add_node("ask_clarification", ask_for_clarification_node)
# workflow.add_node("modify_query", modify_query_node)  # COMMENTED: Redundant - unified_agent_node already enhances query
# workflow.add_node("check_access", check_access_node)  # COMMENTED: Redundant - unified_agent_node already checks access
workflow.add_node("response", response_node)


workflow.set_entry_point("initialize_chat_history")
workflow.add_edge("initialize_chat_history", "input")
workflow.add_edge("input", "unified_agent")  # NEW: Go to unified agent after input

# Conditional: If clarification needed, ask user; otherwise continue
def unified_agent_condition(state: AccessState):
    # Check for errors first
    if state.get("error"):
        return "response"  # Return error message
    if state.get("needs_clarification", False):
        return "ask_clarification"
    elif state.get("decision"):  # Early access denied or error
        return "response"
    else:
        return "response"  # Skip modify_query and check_access - unified_agent_node already did everything

workflow.add_conditional_edges(
    "unified_agent",
    unified_agent_condition,
    {
        "ask_clarification": "ask_clarification",
        "response": "response"  # Removed "modify_query" - unified_agent_node already enhanced query
    }
)

workflow.add_edge("ask_clarification", END)  # User will respond in next query
# workflow.add_edge("modify_query", "check_access")  # COMMENTED: Nodes removed from flow
# workflow.add_edge("check_access", "response")  # COMMENTED: Nodes removed from flow
workflow.add_edge("response", END)

access_agent = workflow.compile()

# state = {
#     "needs_clarification": False,
#     "clarification_question": "",
#     "email": "lynetted@tataplay.com",
#     "designation": "",
#     "department" : "",
#     "region" : "",
#     "question": "",
#     "intent": "",
#     "decision": "",
#     "messages": [HumanMessage(content="Whos my reviewer?")],
#     "modified_query" : ""
# }

# result = access_agent.invoke(state)
# print(result)
# print(result["decision"])


