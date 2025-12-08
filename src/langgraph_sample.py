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
from SummarizationAgent import SummarizationAgent
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

class AccessState(TypedDict, total=False):
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
    # Summarization Agent fields (all Optional for backward compatibility)
    original_query: str  # Original user query (preserved for summarization agent)
    db_results: str  # Raw results from MongoDB Agent
    agg_pipeline: Any  # Aggregation pipeline from MongoDB Agent
    mongo_query_executed: bool  # Whether MongoDB query was executed
    is_summarized: bool  # Whether summarization was applied
    summarization_error: str  # Error message if summarization failed
    skip_mongo_agent: bool  # Flag to skip MongoDB Agent for formatting requests

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
# Formatting Request Detection
# ============================================================================

def detect_formatting_request(query: str, chat_history: List[Dict[str, str]]) -> tuple[bool, str]:
    """
    Hybrid approach: Programmatic detection + LLM fallback for formatting requests.
    Detects if query is a formatting/reformatting request referring to previous result.
    Returns (is_formatting_request, previous_result) tuple.
    
    This is called FIRST (PHASE 0) to skip MongoDB Agent for formatting requests.
    """
    if not query or not chat_history:
        return False, ""
    
    query_lower = query.lower().strip()
    
    # Formatting keywords (expanded list)
    formatting_keywords = [
        "structure", "format", "reformat", "organize", "arrange",
        "make it", "convert to", "change to", "turn into", "instead of",
        "bulleted", "bullet", "list", "table", "narrative", "summary",
        "as a", "as an", "in a", "in an", "show as", "display as",
        "present as", "put in", "arrange as"
    ]
    
    # Reference keywords (expanded - includes pronouns and context references)
    reference_keywords = [
        "this", "that", "it", "them", "these", "those",
        "the above", "the previous", "the last", "the result",
        "this info", "this data", "this result", "this information",
        "that info", "that data", "that result", "that information",
        "the info", "the data", "the result", "the information"
    ]
    
    # PROGRAMMATIC DETECTION (Fast path)
    # Check if query contains formatting keywords
    has_formatting = any(kw in query_lower for kw in formatting_keywords)
    
    # Check if query contains reference keywords OR is very short (likely referring to previous)
    has_reference = any(kw in query_lower for kw in reference_keywords)
    is_short_formatting_query = len(query_lower.split()) <= 8 and has_formatting  # Short queries with formatting keywords are likely formatting requests
    
    # Get previous result for validation
    previous_result = ""
    for msg_dict in reversed(chat_history):
        bot_msg = msg_dict.get("assistant", "").strip()
        if bot_msg and bot_msg.lower() not in ["allowed", "not allowed", "unclear intent"]:
            previous_result = bot_msg
            break
    
    # If both formatting and reference keywords present, OR short formatting query with previous result
    if previous_result and ((has_formatting and has_reference) or is_short_formatting_query):
        return True, previous_result
    
    # LLM FALLBACK (if programmatic detection is uncertain but formatting keywords exist)
    # Use LLM to determine if this is a formatting request when we have formatting keywords
    # but no clear reference, or when query structure suggests formatting intent
    if has_formatting and previous_result:
        # Check for patterns that suggest formatting even without explicit reference
        formatting_patterns = [
            "format it", "format this", "format that",
            "make it", "make this", "make that",
            "convert it", "convert this", "convert that",
            "change it", "change this", "change that",
            "instead of", "rather than", "as a", "as an"
        ]
        
        if any(pattern in query_lower for pattern in formatting_patterns):
            return True, previous_result
    
    return False, ""


# ============================================================================
# Continuation Detection (Hybrid Approach)
# ============================================================================

def detect_continuation_rule_based(query: str, chat_history: List[Dict[str, str]]) -> tuple[str, bool]:
    """
    Fast rule-based continuation detection for common cases.
    Detects if current query is a continuation of previous query (without pronouns).
    
    Examples:
    - "my manager name" → "email" → "my manager email" ✅
    - "my status" → "reviewer" → "my reviewer" ✅
    - "employees in IT" → "count" → "count of employees in IT" ✅
    
    Args:
        query: Current user query
        chat_history: List of message dicts with "user" and "assistant" keys
    
    Returns:
        Tuple of (resolved_query, is_confident):
        - resolved_query: Resolved query with context (or original if not continuation)
        - is_confident: True if confident it's a continuation, False otherwise
    """
    if not query or not chat_history or len(chat_history) == 0:
        return query, False
    
    query_lower = query.lower().strip()
    query_words = query_lower.split()
    
    # Rule 1: Very short queries (1-2 words) are likely continuations
    # Common continuation patterns: single field names, single entities
    if len(query_words) <= 2:
        # Check last user query for entity context
        for msg in reversed(chat_history[-5:]):  # Check last 5 messages
            user_msg = msg.get("user", "").lower().strip()
            if not user_msg:
                continue
            
            # Look for entity patterns in previous query
            entity_patterns = {
                "manager": ["manager", "my manager"],
                "reviewer": ["reviewer", "my reviewer"],
                "employee": ["employee", "employees", "my employee"],
                "department": ["department", "my department", "in department"]
            }
            
            # Check if previous query contains entity context
            for entity_type, patterns in entity_patterns.items():
                if any(pattern in user_msg for pattern in patterns):
                    # Current query is likely asking about same entity
                    # Resolve: "email" → "my manager email" (if previous was about manager)
                    if entity_type == "manager":
                        resolved = f"my manager {query}"
                        print(f"✅ Rule-based continuation detection (manager): '{query}' → '{resolved}'")
                        return resolved, True
                    elif entity_type == "reviewer":
                        resolved = f"my reviewer {query}"
                        print(f"✅ Rule-based continuation detection (reviewer): '{query}' → '{resolved}'")
                        return resolved, True
                    elif entity_type == "employee":
                        # Check if previous query was about "my employee" or just "employee"
                        if "my employee" in user_msg or "my employees" in user_msg:
                            resolved = f"my employee {query}"
                        else:
                            resolved = f"employee {query}"
                        print(f"✅ Rule-based continuation detection (employee): '{query}' → '{resolved}'")
                        return resolved, True
                    elif entity_type == "department":
                        resolved = f"{query} in my department"
                        print(f"✅ Rule-based continuation detection (department): '{query}' → '{resolved}'")
                        return resolved, True
    
    # Rule 2: Check if query is a single field/info request that could continue previous context
    # Common fields: email, name, number, code, id, status, reviewer, manager
    common_fields = ["email", "name", "number", "code", "id", "status", "reviewer", "manager", "designation", "department"]
    if len(query_words) == 1 and query_words[0] in common_fields:
        # Check last assistant message for entity context
        for msg in reversed(chat_history[-3:]):  # Check last 3 messages
            assistant_msg = msg.get("assistant", "").lower()
            if not assistant_msg:
                continue
            
            # Skip clarification questions
            if any(phrase in assistant_msg for phrase in ["do you mean", "which", "please clarify", "?"]):
                continue
            
            # Look for entity mentions in assistant response
            if "manager" in assistant_msg and ("name" in assistant_msg or "is" in assistant_msg):
                resolved = f"my manager {query}"
                print(f"✅ Rule-based continuation detection (from assistant context): '{query}' → '{resolved}'")
                return resolved, True
            elif "reviewer" in assistant_msg and ("name" in assistant_msg or "is" in assistant_msg):
                resolved = f"my reviewer {query}"
                print(f"✅ Rule-based continuation detection (from assistant context): '{query}' → '{resolved}'")
                return resolved, True
    
    # Not a continuation (or not confident) → let LLM handle
    return query, False


# ============================================================================
# Pronoun Resolution (Hybrid Approach)
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
    # IMPORTANT: Only resolve pronouns that are clearly referring to entities, not relative pronouns
    if entity_type == "manager":
        # Resolve possessive pronouns (his, her, their) - these are always entity references
        resolved_query = re.sub(r'\bhis\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bher\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\btheir\b', "my manager's", resolved_query, flags=re.IGNORECASE)
        # Resolve object pronouns (him) - these are entity references
        resolved_query = re.sub(r'\bhim\b', "my manager", resolved_query, flags=re.IGNORECASE)
        # Resolve subject pronouns (he, she, they) - but only if followed by verb or at end
        resolved_query = re.sub(r'\bhe\b(?=\s+(?:is|has|was|will|can|should|email|name|number|code))', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bshe\b(?=\s+(?:is|has|was|will|can|should|email|name|number|code))', "my manager", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthey\b(?=\s+(?:are|have|were|will|can|should|email|name|number|code))', "my manager", resolved_query, flags=re.IGNORECASE)
        # Resolve "it" only when followed by possessive or specific patterns (not relative pronoun)
        resolved_query = re.sub(r'\bit\b(?=\s+(?:is|has|was|will|email|name|number|code|\'))', "my manager", resolved_query, flags=re.IGNORECASE)
        # Resolve "this" only when it's clearly a pronoun (not relative pronoun)
        resolved_query = re.sub(r'\bthis\b(?=\s+(?:is|has|was|will|email|name|number|code|$))', "my manager", resolved_query, flags=re.IGNORECASE)
        # Only resolve "that" if it's NOT a relative pronoun
        # Relative pronoun pattern: "that" followed by subject pronoun (I/you/we/they/he/she/it) + verb
        # Check if "that" is followed by subject pronoun + verb (relative pronoun) - if so, DON'T resolve
        # Simple check: if "that" is followed by "I", "you", "we", "they", "he", "she", "it" within next few words, it's likely a relative pronoun
        if not re.search(r'\bthat\s+(?:I|you|we|they|he|she|it)\s+', query, flags=re.IGNORECASE):
            # Not a relative pronoun pattern, safe to resolve
            resolved_query = re.sub(r'\bthat\b(?=\s+(?:is|has|was|will|email|name|number|code|$))', "my manager", resolved_query, flags=re.IGNORECASE)
    elif entity_type == "reviewer":
        # Resolve possessive pronouns (his, her, their) - these are always entity references
        resolved_query = re.sub(r'\bhis\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bher\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\btheir\b', "my reviewer's", resolved_query, flags=re.IGNORECASE)
        # Resolve object pronouns (him) - these are entity references
        resolved_query = re.sub(r'\bhim\b', "my reviewer", resolved_query, flags=re.IGNORECASE)
        # Resolve subject pronouns (he, she, they) - but only if followed by verb or at end
        resolved_query = re.sub(r'\bhe\b(?=\s+(?:is|has|was|will|can|should|email|name|number|code))', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bshe\b(?=\s+(?:is|has|was|will|can|should|email|name|number|code))', "my reviewer", resolved_query, flags=re.IGNORECASE)
        resolved_query = re.sub(r'\bthey\b(?=\s+(?:are|have|were|will|can|should|email|name|number|code))', "my reviewer", resolved_query, flags=re.IGNORECASE)
        # Resolve "it" only when followed by possessive or specific patterns (not relative pronoun)
        resolved_query = re.sub(r'\bit\b(?=\s+(?:is|has|was|will|email|name|number|code|\'))', "my reviewer", resolved_query, flags=re.IGNORECASE)
        # Resolve "this" only when it's clearly a pronoun (not relative pronoun)
        resolved_query = re.sub(r'\bthis\b(?=\s+(?:is|has|was|will|email|name|number|code|$))', "my reviewer", resolved_query, flags=re.IGNORECASE)
        # Only resolve "that" if it's NOT a relative pronoun
        # Relative pronoun pattern: "that" followed by subject pronoun (I/you/we/they/he/she/it) + verb
        # Check if "that" is followed by subject pronoun + verb (relative pronoun) - if so, DON'T resolve
        if not re.search(r'\bthat\s+(?:I|you|we|they|he|she|it)\s+', query, flags=re.IGNORECASE):
            # Not a relative pronoun pattern, safe to resolve
            resolved_query = re.sub(r'\bthat\b(?=\s+(?:is|has|was|will|email|name|number|code|$))', "my reviewer", resolved_query, flags=re.IGNORECASE)
    
    # Only log if resolution actually happened
    if resolved_query != query:
        print(f"✅ Rule-based pronoun resolution ({entity_type}): '{query}' → '{resolved_query}' (confident: {is_confident})")
    
    return resolved_query, is_confident


# ============================================================================
# Rule-Based Intent Detection (Hybrid Approach)
# ============================================================================

def detect_intent_rule_based(query: str, user_profile: dict) -> tuple[str, bool, bool]:
    """
    Fast rule-based intent detection for obvious sensitive info requests.
    Catches cases like "when should I wish my manager" → intent="others" → DENY immediately.
    
    Args:
        query: User query (may be resolved from continuation/pronoun resolution)
        user_profile: User profile dict with designation, department, etc.
    
    Returns:
        Tuple of (intent, should_deny, is_confident):
        - intent: "others" if detected, None if not confident
        - should_deny: True if should immediately deny (non-HR + others + sensitive), False otherwise
        - is_confident: True if confident about intent classification, False to let LLM handle
    """
    if not query:
        return None, False, False
    
    query_lower = query.lower().strip()
    
    # Check if user is HR (HR users have full access)
    is_hr = user_profile.get("designation", "").lower() in ["hr", "human resources", "hr manager", "hr executive"]
    if is_hr:
        # HR users have full access - let LLM handle (no immediate deny)
        return None, False, False
    
    # Check if query is about manager/reviewer
    is_about_manager = "manager" in query_lower and ("my manager" in query_lower or "manager's" in query_lower or "manager " in query_lower)
    is_about_reviewer = "reviewer" in query_lower and ("my reviewer" in query_lower or "reviewer's" in query_lower or "reviewer " in query_lower)
    
    # Check if query mentions explicit person name (e.g., "John's birthday", "John's salary")
    # Pattern: word ending with 's followed by sensitive info
    explicit_person_pattern = r"\b\w+'s\s+(?:birthday|dob|date of birth|salary|age|compensation|pay|earnings|ssn|social security|wage|income)"
    has_explicit_person = bool(re.search(explicit_person_pattern, query_lower))
    
    is_about_others = is_about_manager or is_about_reviewer or has_explicit_person
    
    if not is_about_others:
        # Not about manager/reviewer/other person - let LLM handle intent classification
        return None, False, False
    
    # Explicit sensitive info patterns
    explicit_sensitive = [
        "birthday", "dob", "date of birth", "salary", "age", "compensation", 
        "pay", "earnings", "ssn", "social security", "wage", "income"
    ]
    
    # Implicit sensitive info patterns (birthday/DOB)
    implicit_birthday_patterns = [
        "when should i wish", "when to wish", "what gift for", "when to celebrate",
        "when is the birthday", "birthday date", "birth date"
    ]
    
    # Implicit sensitive info patterns (salary)
    implicit_salary_patterns = [
        "how much does", "how much do", "what is", "what are", "earn", "paid", 
        "compensation of", "salary of", "wage of", "income of"
    ]
    
    # Implicit sensitive info patterns (age)
    implicit_age_patterns = [
        "how old is", "how old are", "what age is", "what age are", "age of"
    ]
    
    # Check for explicit sensitive info
    has_explicit_sensitive = any(pattern in query_lower for pattern in explicit_sensitive)
    
    # Check for implicit sensitive info
    has_implicit_birthday = any(pattern in query_lower for pattern in implicit_birthday_patterns)
    has_implicit_salary = any(pattern in query_lower for pattern in implicit_salary_patterns)
    has_implicit_age = any(pattern in query_lower for pattern in implicit_age_patterns)
    
    has_sensitive_info = has_explicit_sensitive or has_implicit_birthday or has_implicit_salary or has_implicit_age
    
    if has_sensitive_info:
        # Query is about manager/reviewer AND requesting sensitive info → intent="others"
        # For non-HR users, this should be denied immediately
        print(f"🚫 Rule-based intent detection: '{query}' → intent='others' (sensitive info request about manager/reviewer)")
        return "others", True, True  # should_deny=True for non-HR users
    
    # Check if query is requesting ONLY allowed info (name, email, code, number, id)
    allowed_info = ["name", "email", "code", "number", "id", "employee code", "employee id", "contact", "phone"]
    has_allowed_info = any(info in query_lower for info in allowed_info)
    
    # If query is about manager/reviewer but only requesting allowed info → intent="self" (let LLM confirm)
    if has_allowed_info and not has_sensitive_info:
        # This is likely intent="self" but let LLM confirm (not confident enough to skip LLM)
        return None, False, False
    
    # If about manager/reviewer but unclear what info → let LLM handle
    return None, False, False


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
    
    # Get original_query from state (set by QueryProcessor), fallback to current_query
    original_query = state.get("original_query", current_query)
    
    # ===== PHASE 0: FORMATTING REQUEST DETECTION (FIRST - BEFORE EVERYTHING) =====
    # Check for formatting/reformatting requests (referring to previous results)
    # This handles cases like "format it as table", "make it bulleted", "convert to list"
    # If detected, skip MongoDB Agent and go directly to Summarization Agent
    chat_history_messages = state.get("chat_history_messages", [])
    formatting_request, previous_result = detect_formatting_request(current_query, chat_history_messages)
    
    if formatting_request and previous_result:
        # This is a formatting request - skip MongoDB query, go directly to Summarization Agent
        print(f"✅ Detected formatting request: '{current_query}' - will reformat previous result")
        return {
            "needs_clarification": False,
            "decision": "Allowed",
            "final_clarified_query": current_query,  # Use current query as final (it's a formatting instruction)
            "db_results": previous_result,  # Use previous result as db_results
            "original_query": original_query or current_query,  # Preserve original_query, fallback to current
            "skip_mongo_agent": True,  # Flag to skip MongoDB Agent
            "intent": "self"  # Default intent for formatting requests
        }
    
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
    
    # ===== PHASE 1: CONTINUATION DETECTION (Hybrid: Rule-based first, LLM validates/fallback) =====
    # Detect if current query is a continuation of previous query (without pronouns)
    # Examples: "my manager name" → "email" → "my manager email"
    continuation_query, continuation_confident = detect_continuation_rule_based(current_query, chat_history_messages)
    
    # ===== PHASE 2: PRONOUN RESOLUTION (Hybrid: Rule-based first, LLM validates/fallback) =====
    # Resolve pronouns in query (or continuation-resolved query)
    # Use continuation-resolved query if continuation was detected, otherwise use original
    query_for_pronoun_resolution = continuation_query if continuation_confident else current_query
    resolved_query, pronoun_confident = resolve_pronouns_rule_based(query_for_pronoun_resolution, chat_history_messages)
    
    # Determine final query for LLM
    # If either continuation or pronoun resolution was confident, use resolved query
    # Otherwise, pass original to LLM for full processing
    is_confident = continuation_confident or pronoun_confident
    query_for_llm = resolved_query if is_confident else current_query
    
    # ===== PHASE 3: RULE-BASED INTENT DETECTION (BEFORE LLM - IMMEDIATE DENY FOR OBVIOUS CASES) =====
    # Check for obvious sensitive info requests about manager/reviewer
    # If detected → immediately deny for non-HR users (skip LLM call)
    rule_based_intent, should_deny, intent_confident = detect_intent_rule_based(query_for_llm, user_profile)
    
    if should_deny and intent_confident:
        # Obvious sensitive info request about manager/reviewer → immediately deny
        print(f"🚫 Rule-based access denial: '{query_for_llm}' → intent='others' → ACCESS_DENIED (non-HR user requesting sensitive manager/reviewer info)")
        return {
            "needs_clarification": False,
            "status": "access_denied",
            "decision": f"ACCESS_DENIED: You do not have permission to access sensitive information about your manager or reviewer (e.g., birthday, salary, age). Only name, email, and employee code are allowed.",
            "intent": "others",
            "clarification_progress": {
                "original_query": current_query,
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    # Log processing steps
    if continuation_confident:
        print(f"✅ Continuation detected: '{current_query}' → '{continuation_query}'")
    if pronoun_confident and resolved_query != query_for_pronoun_resolution:
        print(f"✅ Pronoun resolved: '{query_for_pronoun_resolution}' → '{resolved_query}'")
    if not is_confident:
        print(f"ℹ️ Rule-based couldn't resolve, LLM will handle continuation/pronouns: '{current_query}'")
    
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
    
    # CRITICAL FIX: Skip clarification if no ambiguous terms present AND no pending ambiguities
    # Only ask clarification for terms in ambiguous_terms list
    pending_ambiguities = clarification_progress.get("pending_ambiguities", {}) if clarification_progress else {}
    has_pending_ambiguities = len(pending_ambiguities) > 0
    has_ambiguous_terms = len(filtered_ambiguous_terms) > 0
    
    if not has_ambiguous_terms and not has_pending_ambiguities:
        # No ambiguous terms in query and no pending ambiguities → Skip clarification, go straight to ready
        print(f"✅ No ambiguous terms found in query and no pending ambiguities → Skipping clarification, proceeding to ready status")
        # Use rule-based intent if available, otherwise default to "self"
        default_intent = rule_based_intent if intent_confident else "self"
        # Build a minimal result to proceed without clarification
        result = {
            "status": "ready",
            "intent": default_intent,  # Use rule-based intent if confident, otherwise default
            "decision": "Allowed",
            "final_clarified_query": query_for_llm,  # Use current query as final
            "clarification_progress": {
                "original_query": query_for_llm,
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    else:
        # Call clarify_query with optimizations (TOON format used internally)
        # Pass query_for_llm to LLM:
        # - If rule-based resolved with confidence → LLM validates/corrects if needed
        # - If rule-based didn't resolve → LLM resolves from scratch
        # LLM has all context (chat history) and will handle edge cases
        # Pass filtered_ambiguous_terms (only terms present in query)
        # Pass rule-based results for validation (including intent detection)
        rule_based_results = {
            "original_query": current_query,  # Original query before rule-based processing
            "continuation_detected": continuation_confident,  # Whether continuation was detected
            "continuation_resolved": continuation_query if continuation_confident else "",  # Resolved continuation query
            "continuation_confident": continuation_confident,  # Whether continuation detection was confident
            "pronoun_resolved": resolved_query if pronoun_confident else "",  # Resolved pronoun query
            "pronoun_confident": pronoun_confident,  # Whether pronoun resolution was confident
            "intent_detected": rule_based_intent if intent_confident else None,  # Rule-based intent ("others" or None)
            "intent_confident": intent_confident,  # Whether intent detection was confident
        }
        result = clarify_query(
            query_for_llm, structure["collections"], filtered_ambiguous_terms,
            chat_history=format_chat_history_compact(chat_history_messages),
            clarification_progress=clarification_progress,
            user_profile=user_profile, needs_routing=state.get("needs_routing", False),
            rule_based_results=rule_based_results
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

def summarization_agent_node(state: AccessState) -> Dict[str, Any]:
    """
    Summarize database results if needed.
    Uses LLM to analyze original_query, final_clarified_query, and db_results.
    Fast path: Skips summarization if not needed (preserves good answers).
    """
    # Get original_query from state (preserved from initial query)
    # Fallback to question if original_query not set (backward compatibility)
    original_query = state.get("original_query") or state.get("question", "")
    final_clarified_query = state.get("final_clarified_query", "")
    db_results = state.get("db_results", "")
    user_profile = state.get("user_profile")
    
    # Skip if no results
    if not db_results:
        return {
            "db_results": "",
            "is_summarized": False
        }
    
    # Skip if error occurred in MongoDB Agent
    if state.get("error") or "Error" in db_results:
        return {
            "db_results": db_results,
            "is_summarized": False
        }
    
    try:
        summarizer = SummarizationAgent()
        summarized_result = summarizer.summarize(
            original_query=original_query,
            final_clarified_query=final_clarified_query,
            db_results=db_results,
            user_context=user_profile
        )
        
        # Check if summarization changed the result (to track if it was summarized)
        was_summarized = (summarized_result != db_results)
        
        return {
            "db_results": summarized_result,
            "is_summarized": was_summarized
        }
        
    except Exception as e:
        # Fallback to raw results on error
        print(f"⚠️ Summarization Agent error: {e}, using raw results")
        return {
            "db_results": db_results,
            "is_summarized": False,
            "summarization_error": str(e)
        }


def response_node(state: AccessState):
    # Use db_results if available (from summarization agent), otherwise use decision
    db_results = state.get("db_results", "")
    decision = state.get("decision", "")
    
    # Prefer db_results over decision (db_results is the final answer)
    content = db_results if db_results else decision
    msg = AIMessage(content=content)
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
workflow.add_node("summarization_agent", summarization_agent_node)  # Result summarization node
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
    elif state.get("skip_mongo_agent", False):
        # Formatting request detected - skip MongoDB Agent, go directly to Summarization Agent
        # db_results is already set from previous result
        return "summarization_agent"
    else:
        # Normal query or access denied - go to response
        # MongoDB execution happens in QueryProcessor, not in workflow
        # Summarization will be called from QueryProcessor after MongoDB execution
        return "response"

workflow.add_conditional_edges(
    "unified_agent",
    unified_agent_condition,
    {
        "ask_clarification": "ask_clarification",
        "summarization_agent": "summarization_agent",  # Route directly to Summarization Agent for formatting requests
        "response": "response"
    }
)

workflow.add_edge("ask_clarification", END)  # User will respond in next query
# workflow.add_edge("modify_query", "check_access")  # COMMENTED: Nodes removed from flow
# workflow.add_edge("check_access", "response")  # COMMENTED: Nodes removed from flow
workflow.add_edge("summarization_agent", "response")  # After summarization, go to response
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


