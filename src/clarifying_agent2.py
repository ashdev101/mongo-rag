import json
import re
from langchain_openai import ChatOpenAI
import os
from SemanticDictionaryProcessor import SemanticDictionaryProcessor
from CollectionRouter import CollectionRouterAgent
# -------------------------------
# 1. CONFIG
# -------------------------------
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))
# schema_generator import removed - not used in this file
# from schema_generator import extract_db_schema

llm = ChatOpenAI(model="gpt-4o")  # or "gpt-4o-mini" etc.

# Chat history is now managed by memorymanager.py
# Import functions from memorymanager instead of managing MongoDB directly
from memory.memorymanager import get_chat_history, push_convo_pair


# -------------------------------
# TOON Format Converter
# -------------------------------

def format_semantic_context_toon(semantic_context: dict) -> str:
    """
    Convert semantic_context dict to TOON format for token reduction.
    Reduces tokens by 50-60% compared to JSON.
    """
    if not semantic_context or not isinstance(semantic_context, dict):
        return "None"
    
    lines = []
    collections = semantic_context.get("collections", {})
    
    for entity_name, entity_data in collections.items():
        if not isinstance(entity_data, dict):
            continue
        
        for sub_entity, sub_data in entity_data.items():
            if not isinstance(sub_data, dict):
                continue
            
            collection = sub_data.get("collection", "")
            key_fields = sub_data.get("key_fields", [])
            routing_keywords = sub_data.get("routing_keywords", [])
            
            # Format: entity[sub_entity]{collection,key_fields,routing_keywords}
            key_fields_str = ",".join(key_fields) if key_fields else ""
            keywords_str = ",".join(routing_keywords) if routing_keywords else ""
            
            lines.append(f"{entity_name}[{sub_entity}]{{collection,key_fields,routing_keywords}}:")
            lines.append(f"  {collection}")
            lines.append(f"  {key_fields_str}")
            lines.append(f"  {keywords_str}")
            lines.append("")  # Empty line between entities
    
    return "\n".join(lines).strip()

def format_ambiguous_terms_toon(ambiguous_terms: list) -> str:
    """
    Convert ambiguous_terms list to TOON (Token-Oriented Object Notation) format.
    This reduces token count by 50-60% compared to JSON while maintaining readability.
    
    Args:
        ambiguous_terms: List of ambiguous term dictionaries with collection-aware structure
    
    Returns:
        TOON formatted string
    """
    if not ambiguous_terms:
        return "None"
    
    lines = []
    for term_data in ambiguous_terms:
        term = term_data.get("term", "")
        collections = term_data.get("collections", {})
        ask_user = term_data.get("ask_user", "")
        
        if not term:
            continue
        
        # Format: term[collection|field|short_name|keywords]
        term_lines = [f"{term}:"]
        
        for collection_name, collection_info in collections.items():
            # Handle both single field and multiple fields (for rating, leavers)
            if "fields" in collection_info:
                # Multiple fields in same collection (e.g., rating has self and manager)
                for field_info in collection_info["fields"]:
                    field = field_info.get("field", "")
                    short_name = field_info.get("short_name", "")
                    keywords = ",".join(field_info.get("keywords", []))
                    term_lines.append(f"  [{collection_name}|{field}|{short_name}|{keywords}]")
            else:
                # Single field per collection
                field = collection_info.get("field", "")
                short_name = collection_info.get("short_name", "")
                keywords = ",".join(collection_info.get("keywords", []))
                term_lines.append(f"  [{collection_name}|{field}|{short_name}|{keywords}]")
        
        if ask_user:
            term_lines.append(f"  ask: \"{ask_user}\"")
        
        lines.append("\n".join(term_lines))
    
    return "\n\n".join(lines)


# You are a MongoDB Query Clarification Agent. 
# Your ONLY job is to interpret the user’s request and ask ONE short clarifying question ONLY when the database query cannot be constructed without it.

# CRITICAL RULES (MUST FOLLOW):

# 1. Strictly make NO assumptions about the database.
#    - You may ONLY use fields, metrics, entities, and meanings that appear in the semantic_context or ambiguous_terms provided to you.
#    - If it is not in semantic_context → it does NOT exist.
#    - Never invent fields, filters, collections, metrics, or attributes.

# 2. Strictly make NO assumptions about the user's intent.
#    - Only use exactly what the user said.
#    - Never “guess” their intent or add extra interpretation.

# 3. Ask a question ONLY when:
#    - The user uses an ambiguous term (from ambiguous_terms) AND the ambiguity corresponds to different known database attributes.
#    - Required query components are missing AND they exist in semantic_context (entity, metric, time_range, filters).

# 4. NEVER ask about anything unrelated to generating a MongoDB query.
#    - No conversational questions.
#    - No HR-style questions.
#    - No business questions unless directly mapped to database fields.

# 5. NEVER ask for anything the database CANNOT store.
#    - If the field or concept is not listed in semantic_context, you must NOT ask about it.
#    - Example: If “appraisal_cycle” is not in semantic_context, do NOT ask about it or include it.

# 6. NEVER ask about anything the user already provided.

# 7. ONE QUESTION ONLY.
#    - Must be short, human, and easy to answer.
#    - No technical words: no “schema”, “fields”, “collections”, “documents”.

# 8. The question asked must be directly relevant to user intent .

# You are given:
# 1) semantic_context (database concepts and collections)
# {json.dumps(semantic_context, indent=2)}
# 2) ambiguous_terms (terms with multiple database meanings)
# {json.dumps(ambiguous_terms, indent=2)}

# Ask a clarifying question ONLY when:
# - The user uses an ambiguous term (from ambiguous_terms) AND the possible meanings map to different database fields or collections.
# - The request is incomplete in a way that prevents generating the MongoDB query.
# - A required database dimension is missing (metric, subtype, time_range, or scope).

# If the user request already maps cleanly to one entity, one metric, and optional time_range → DO NOT ASK.

# Your clarifying question must:
# - Be ONE sentence.
# - Be simple and easy to answer.
# - Refer ONLY to details needed for the database query.
# - Never include technical words like “field”, “schema”, “collection”, or “document”.

# If ambiguous_terms defines a question → use that as your ONLY question, but rephrase it to be short and human.

# Examples:
# 1. User: “my leaves”
#    → Ask: “Do you want pending leaves or total leaves?” 
#    (because these map to different database fields)

# 2. User: “my manager”
#    → Ask: “Do you want your manager’s name or email?”
#    (database has multiple manager attributes)

# 3. User: “attendance”
#    → Ask: “Do you want your attendance count or a day-wise breakdown?”
#    (different database metrics)

# 4. User: “leaves this month”
#    → No question (entity + time are clear)

# 5. User: “manager’s email”
#    → No question (specific database attribute)

# 6. User: “team attendance last week”
#    → No question (intent, scope, time all clear)

# OUTPUT FORMAT:

# If clarification is needed:
# {{
#   "status": "needs_clarification",
#   "questions": ["<one short database-relevant question>"],
#   "missing": ["metric", "time_range", ...]
# }}

# If everything is clear:
# {{
#   "status": "ready",
#   "structured_query": {{
#     "entity": "...",
#     "metric": "...",
#     "filters": {...},
#     "time_range": "...",
#     "collection": "..."
#   }}
# }}

# User Query: "{user_query}"

# -------------------------------
# 2. Clarification Agent
# -------------------------------

# Chat history functions removed - now using memorymanager.py
# Use push_convo_pair() and get_chat_history() from memorymanager module


def validate_clarification_progress(result: dict, user_query: str, clarification_progress: dict) -> dict:
    """
    Validate and fix clarification_progress structure.
    Light validation: Only fix structure, don't try to infer missing logic.
    If LLM fails to set fields, we can't programmatically fix the logic,
    but we can ensure the structure is valid to prevent crashes.
    """
    # Ensure clarification_progress exists
    if "clarification_progress" not in result:
        result["clarification_progress"] = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
    
    cp = result["clarification_progress"]
    
    # Structure validation only (not logic validation)
    if not isinstance(cp, dict):
        cp = {}
        result["clarification_progress"] = cp
    
    # Ensure required keys exist with correct types
    if "original_query" not in cp or not isinstance(cp.get("original_query"), str):
        cp["original_query"] = clarification_progress.get("original_query", "") if clarification_progress else "" or user_query
    
    if "pending_ambiguities" not in cp or not isinstance(cp.get("pending_ambiguities"), dict):
        cp["pending_ambiguities"] = {}
    
    if "resolved_ambiguities" not in cp or not isinstance(cp.get("resolved_ambiguities"), dict):
        cp["resolved_ambiguities"] = {}
    
    # If LLM failed to set pending_ambiguities but asked questions, log warning
    if result.get("status") == "needs_clarification" and result.get("questions") and not cp.get("pending_ambiguities"):
        print("⚠️ WARNING: LLM asked questions but didn't set pending_ambiguities - structure fixed but logic may be incomplete")
        # We can't programmatically infer which terms are pending, so we leave it empty
        # The next turn will handle it (user will answer, we'll detect continuation)
    
    # If status="ready" but pending_ambiguities is not empty, clear it
    if result.get("status") == "ready" and cp.get("pending_ambiguities"):
        cp["pending_ambiguities"] = {}
        print("⚠️ WARNING: LLM returned status='ready' but pending_ambiguities was not empty - cleared it")
    
    result["clarification_progress"] = cp
    return result


def clarify_query(user_query: str , semantic_context: dict , ambiguous_terms: dict, chat_history: str = "", clarification_progress: dict = None, user_profile: dict = None, needs_routing: bool = False, rule_based_results: dict = None):
    """
    Unified agent: Clarification + Enhancement + Routing + Query Modification
    
    Args:
        user_query: the question from the user (may be rule-based resolved query)
        semantic_context: the semantic JSON document produced by build_summary_document()
        ambiguous_terms: dictionary of ambiguous terms and their possible meanings
        chat_history: formatted string of previous conversation (last 10 messages)
        clarification_progress: current clarification progress from state (optional)
        user_profile: dict with employee_code, designation, department, region (optional)
        needs_routing: whether to perform routing (True for Combined tab, False for MQL Agent tab)
        rule_based_results: dict with rule-based processing results for validation (optional)
            {
                "original_query": str,  # Original user query before rule-based processing
                "continuation_detected": bool,  # Whether continuation was detected
                "continuation_resolved": str,  # Resolved continuation query (if detected)
                "continuation_confident": bool,  # Whether continuation detection was confident
                "pronoun_resolved": str,  # Resolved pronoun query (if resolved)
                "pronoun_confident": bool,  # Whether pronoun resolution was confident
            }
    """
    # ===== EDGE CASE VALIDATION =====
    # Validate user_query
    if not user_query or not isinstance(user_query, str):
        return {
            "status": "error",
            "error": "Invalid query: Query must be a non-empty string",
            "intent": "self",
            "decision": "Error: Please provide a valid query.",
            "clarification_progress": {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    # Trim and validate query length
    user_query = user_query.strip()
    if not user_query:
        return {
            "status": "error",
            "error": "Empty query provided",
            "intent": "self",
            "decision": "Error: Query cannot be empty. Please provide a question.",
            "clarification_progress": {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    # Validate query length (prevent extremely long queries)
    if len(user_query) > 2000:
        return {
            "status": "error",
            "error": f"Query too long: {len(user_query)} characters (max 2000)",
            "intent": "self",
            "decision": "Error: Query is too long. Please provide a shorter, more focused question.",
            "clarification_progress": {
                "original_query": user_query[:2000],  # Store truncated version
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    # Validate semantic_context
    if not semantic_context or not isinstance(semantic_context, dict):
        return {
            "status": "error",
            "error": "Invalid semantic_context: Must be a non-empty dictionary",
            "intent": "self",
            "decision": "Error: System configuration error. Please contact support.",
            "clarification_progress": {
                "original_query": user_query,
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    
    # Validate ambiguous_terms
    if ambiguous_terms is None:
        ambiguous_terms = []
    if not isinstance(ambiguous_terms, list):
        ambiguous_terms = []
    
    # Validate chat_history
    if chat_history is None:
        chat_history = ""
    if not isinstance(chat_history, str):
        chat_history = ""
    
    # Validate user_profile
    if user_profile is not None and not isinstance(user_profile, dict):
        user_profile = None
    
    # Validate rule_based_results
    if rule_based_results is None:
        rule_based_results = {}
    if not isinstance(rule_based_results, dict):
        rule_based_results = {}
    
    # Extract rule-based results for prompt
    original_query_rb = rule_based_results.get("original_query", user_query)
    continuation_detected = rule_based_results.get("continuation_detected", False)
    continuation_resolved = rule_based_results.get("continuation_resolved", "")
    continuation_confident = rule_based_results.get("continuation_confident", False)
    pronoun_resolved = rule_based_results.get("pronoun_resolved", "")
    pronoun_confident = rule_based_results.get("pronoun_confident", False)
    
    # Initialize clarification_progress if not provided
    if clarification_progress is None:
        clarification_progress = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
    
    # Validate clarification_progress structure
    if not isinstance(clarification_progress, dict):
        clarification_progress = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
    
    # Ensure required keys exist with correct types
    if "original_query" not in clarification_progress or not isinstance(clarification_progress.get("original_query"), str):
        clarification_progress["original_query"] = ""
    if "pending_ambiguities" not in clarification_progress or not isinstance(clarification_progress.get("pending_ambiguities"), dict):
        clarification_progress["pending_ambiguities"] = {}
    if "resolved_ambiguities" not in clarification_progress or not isinstance(clarification_progress.get("resolved_ambiguities"), dict):
        clarification_progress["resolved_ambiguities"] = {}
    
    # Format clarification progress for prompt
    pending_count = len(clarification_progress.get("pending_ambiguities", {}))
    resolved_count = len(clarification_progress.get("resolved_ambiguities", {}))
    # Get original_query from clarification_progress, or indicate it's first query
    original_query = clarification_progress.get("original_query", "") if clarification_progress else ""
    if not original_query:
        original_query = "(first query - will be stored as original_query)"
    
    pending_list = "\n".join([f"- {term}: {info.get('question', 'needs clarification')}" for term, info in clarification_progress.get("pending_ambiguities", {}).items()]) if clarification_progress.get("pending_ambiguities") else "None"
    resolved_list = "\n".join([f"- {term}: resolved to '{info.get('resolved_to', 'unknown')}'" for term, info in clarification_progress.get("resolved_ambiguities", {}).items()]) if clarification_progress.get("resolved_ambiguities") else "None"
    
    # Format user profile for prompt
    if user_profile:
        user_profile_text = f"""Employee Code: {user_profile.get('employee_code', 0)}
Designation: {user_profile.get('designation', 'unknown')}
Department: {user_profile.get('department', 'unknown')}
Region: {user_profile.get('region', 'None')}"""
    else:
        user_profile_text = "Not available"
    
    # Format routing requirement
    if needs_routing:
        routing_text = "YES - You must classify the query as 'document' or 'policy' and return the route in your response."
    else:
        routing_text = "NO - Skip routing, this is for MQL Agent tab (always document queries)."

    # Build chat history section for prompt
    chat_history_section = ""
    if chat_history and chat_history.strip():
        chat_history_section = f"""

═══════════════════════════════════════════════════════════════════════════════
CHAT HISTORY:
═══════════════════════════════════════════════════════════════════════════════
{chat_history}

**Use chat history for:**
- Pronoun resolution (check most recent first)
- Context inference (qualify terms from previous topics)
- Continuation detection (check if answering previous questions)
- Entity extraction (add manager/reviewer names to query)

"""
    
    # Extract rule-based intent results
    intent_detected = rule_based_results.get("intent_detected") if rule_based_results else None
    intent_confident = rule_based_results.get("intent_confident", False) if rule_based_results else False
    
    # Build rule-based results section for validation (only if results exist)
    rule_based_section = ""
    has_pronoun = pronoun_resolved and pronoun_resolved.strip() and pronoun_resolved != user_query
    has_rule_based_results = rule_based_results and (continuation_detected or has_pronoun or intent_confident)
    
    if has_rule_based_results:
        # Only show relevant information
        continuation_info = f"Continuation: '{continuation_resolved}' (confident: {continuation_confident})" if continuation_detected else ""
        pronoun_info = f"Pronoun: '{pronoun_resolved}' (confident: {pronoun_confident})" if has_pronoun else ""
        intent_info = f"Intent: '{intent_detected}' (confident: {intent_confident})" if intent_confident else ""
        
        rule_based_section = f"""

═══════════════════════════════════════════════════════════════════════════════
RULE-BASED PROCESSING (VALIDATE):
═══════════════════════════════════════════════════════════════════════════════
Original: "{original_query_rb}" → Current: "{user_query}"
{continuation_info}
{pronoun_info}
{intent_info}

**Validate:** If CORRECT → use it. If INCORRECT → override. If NOT confident → re-process.

"""
    
    prompt = f"""
You are a MongoDB Query Clarification Agent for an HR system. Identify ambiguities and request clarifications when the database query cannot be constructed without them.

{rule_based_section}

{chat_history_section}

═══════════════════════════════════════════════════════════════════════════════
SENSITIVE INFO PATTERNS (REFERENCE):
═══════════════════════════════════════════════════════════════════════════════
**Explicit sensitive info:** birthday, DOB, date of birth, salary, age, compensation, pay, earnings, SSN
**Implicit sensitive info patterns:**
- Birthday/DOB: "when should I wish [X]", "when to wish [X]", "what gift for [X]", "when to celebrate [X]"
- Salary: "how much does [X] earn", "what is [X] paid", "compensation of [X]"
- Age: "how old is [X]", "what age is [X]"
**Allowed info for manager/reviewer/others:** name, email, code, number, employee_id, employee_code

═══════════════════════════════════════════════════════════════════════════════
PROCESSING PIPELINE (Execute in order):
═══════════════════════════════════════════════════════════════════════════════

**STEP 1: CONTINUATION DETECTION** (FIRST - before pronoun resolution)
- **IF rule-based detected continuation:** Validate against chat history (use if correct, override if incorrect)
- **IF pending_ambiguities exist:**
  * Check if current query answers them (qualified terms match) → CONTINUATION
  * **Answer Pattern Recognition:** Detect multi-selection patterns: "all", "all of them", "both", "all 3", "all [number]", "yes to all", "everything", or explicit enumeration like "performance and goal", "performance, goal, employee"
  * **Multi-Value Resolution:** If multi-selection detected → expand to list of all possible values from ambiguous_terms for that term. Example: "all 3 status" → resolve to ["performance status", "goal-setting status", "employee status"]
  * Move answered terms to resolved_ambiguities (store as list if multi-selection, single value if single selection)
  * If ALL answered → status="ready", merge into original_query
  * Use merged query for subsequent steps
- **IF no pending_ambiguities and no rule-based continuation:**
  * Check if current query is a continuation of previous query (even without pronouns)
  * Examples of continuation WITHOUT pronouns:
    * "my manager name" → "email" → Resolve to "my manager email"
    * "employees in IT" → "count" → Resolve to "count of employees in IT"
    * "my status" → "reviewer" → Resolve to "my reviewer"
  * If continuation detected → Merge with previous context from chat history
  * If semantically different from original_query → NEW QUERY (reset clarification_progress)
  * IF same topic → FOLLOW-UP (preserve context, use chat history)

**STEP 2: PRONOUN RESOLUTION** (if pronouns exist: he/she/they/his/her/their/it/this/that)
- **IF rule-based resolved pronouns:** Validate against chat history (use if correct, override if incorrect)
- **IF pronouns not resolved by rule-based:**
  * If already resolved (e.g., "my manager's email", "my manager email") → validate and use
  * If unresolved (e.g., "his email") → resolve from chat history (most recent first)
  * Extract entity type from last Assistant message → update query
  * Handle continuation without pronouns (e.g., "email" after "my manager name")
- **Use RESOLVED query for all subsequent steps**

**STEP 3: ACCESS CONTROL** (use RESOLVED query from STEP 2)

1. **INTENT CLASSIFICATION (VALIDATE RULE-BASED IF PROVIDED):**
   - **IF rule-based intent provided:** Validate it (use if correct, override if incorrect)
   - **IF no rule-based intent or not confident:**
     a) Identify requested info (explicit or implicit - see SENSITIVE INFO PATTERNS above)
     b) If query about manager/reviewer + sensitive info → intent="others"
     c) If query about manager/reviewer + ONLY allowed info (name/email/code/number/id) → intent="self"
     d) If own info → intent="self"
     e) If other person → intent="others"
   
2. **ACCESS DECISION:**
   - IF HR → ACCESS ALLOWED
   - IF NON-HR + "self": ALL own info → ALLOWED | Manager/reviewer: ONLY name/email/code/number/id → ALLOWED
   - IF NON-HR + "others": ONLY name/email/code/number/id → ALLOWED | All other info → DENIED

**If ACCESS DENIED, return immediately:**
{{
  "status": "access_denied",
  "decision": "ACCESS_DENIED: [reason]",
  "intent": "[detected intent]",
  "clarification_progress": {{"original_query": "", "pending_ambiguities": {{}}, "resolved_ambiguities": {{}}}}
}}

═══════════════════════════════════════════════════════════════════════════════
CORE RULES:
═══════════════════════════════════════════════════════════════════════════════

**RULE 1: Default Subject**
- No explicit subject → assume "self" (NEVER ask "for whom?" or "whose?")
- Only ask about subject if query explicitly mentions another person/entity

**RULE 2: Ambiguous Terms Check** (in order)
1. Is ambiguous_terms list empty? → status="ready", NO questions
2. Are terms qualified? (e.g., "manager name", "performance status") → status="ready"
3. Can context infer? (e.g., "performance status and reviewer" → infer "performance reviewer") → status="ready"
4. Else → ask questions for unqualified terms

**RULE 3: Qualified Terms = Resolved**
- Qualified: "performance status", "offboarding reviewer", "total leaves", "current manager", "manager name"
- Unqualified: "status", "reviewer", "leaves" (only if in ambiguous_terms)
- Once qualified → DONE, do NOT ask follow-up questions

**RULE 4: Ask All Questions At Once (CRITICAL)**
- Identify ALL ambiguities in the query, return ALL questions in one response
- If query has 2 ambiguous terms → return 2 questions, if 5 → return 5 questions
- DO NOT skip any ambiguous terms - ask about EVERY unqualified ambiguous term found in the query
- Check ALL ambiguous_terms provided - if any match the query, include them in questions

**RULE 5: Query Enhancement** (when status="ready")
- Extract entities from chat history (manager/reviewer names, employee IDs)
- Resolve pronouns to entities (e.g., "his email" → "my manager's email")
- Add entity context: "Tell me his email" + History: "manager name is [Name]" → "Tell me my manager's email. My manager name is [Name]"
- If resolved_ambiguities contains lists (multiple values) → build query with "and" connectors. Example: resolved_to: ["performance status", "goal status"] → "performance status and goal status"
- Add employee_code for self queries: "My employee code is {{employee_code}}"
- Add field mappings if needed: "employee ID (field: employee_code)"
- Preserve original query structure (connectors, order, "my"/"I" pronouns)

**RULE 6: Routing** (ONLY if needs_routing=True)
- "document": IDs, records, data lookups
- "policy": Rules, eligibility, guidelines, what-to-do
- Default: "document"

═══════════════════════════════════════════════════════════════════════════════
VALIDATION & EDGE CASES:
═══════════════════════════════════════════════════════════════════════════════

**Before asking questions, verify:**
- ambiguous_terms empty? → status="ready"
- Terms qualified? → status="ready"
- Context can infer? → infer → status="ready"
- Already answered in chat history? → use answer, mark as resolved
- ALL terms qualified? → status="ready"

**NEVER ask about:**
- Subject/employee (unless explicitly mentioned like "John's")
- Qualified terms (e.g., "performance status", "manager name")
- Things already answered in chat history
- Things not in semantic_context
- Pronouns if chat history provides context (resolve automatically)
- Granular details about qualified terms

**Edge Cases:**
- Empty query → Return error (handled by validation)
- Very long query → Return error (handled by validation)
- Team queries (e.g., "team attendance") → Process normally, assume self scope unless specified
- Multiple subjects (e.g., "John's and Mary's emails") → "others" intent
- Time-based queries (e.g., "leaves this month") → Time already specified, process normally
- Aggregations (e.g., "total leaves", "sum of ratings") → Process normally


═══════════════════════════════════════════════════════════════════════════════
KEY EXAMPLES:
═══════════════════════════════════════════════════════════════════════════════

**Simple Queries:**
- "my manager name" → NO questions (qualified, no ambiguities) → status="ready"
- "total leaves" → NO question (qualified term, assume self) → status="ready"
- "offboarding reviewer" → NO question (qualified term, assume self) → status="ready"

**Pronoun Resolution & Continuation:**
- "give his email" + History: "manager name is [Name]" → Resolve "his" = manager → "my manager's email" → status="ready"
- "my manager name" → "email" → Continuation detected → "my manager email" → status="ready"
- "employees in IT" → "count" → Continuation detected → "count of employees in IT" → status="ready"

**Access Control:**
- "tell me my salary" → ALLOWED (self, own info)
- "my manager's dob" → DENIED (self, manager's sensitive - only name/email/code allowed)
- "my manager's birthday" → DENIED (self, manager's sensitive - only name/email/code allowed)
- "my manager's salary" → DENIED (self, manager's sensitive - only name/email/code allowed)
- "when should I wish my manager" → DENIED (self, implicit birthday request - only name/email/code allowed)
- "how much does my manager earn" → DENIED (self, implicit salary request - only name/email/code allowed)
- "how old is my manager" → DENIED (self, implicit age request - only name/email/code allowed)
- "my manager's email" → ALLOWED (self, manager's allowed: name/email/code only)
- "my manager's name" → ALLOWED (self, manager's allowed: name/email/code only)
- "John's email" → ALLOWED (others, email allowed)
- "John's salary" → DENIED (others, deny all except name/email/code/number)
- "John's birthday" → DENIED (others, deny all except name/email/code/number)

**Clarification:**
- "my leaves" → Ask: "Do you want pending leaves or total leaves?" (1 question)
- "my status and reviewer" → Ask: ["Which status?", "Which reviewer?"] (2 questions)

**Continuation:**
- Previous: "my status and reviewer" → Questions: ["Which status?", "Which reviewer?"]
- Current: "performance status and performance reviewer" → ALL answered → status="ready"
- Final: "my performance status and performance reviewer"

**Context Inference:**
- "performance status and reviewer" → Infer "performance reviewer" → status="ready" (NO questions)

═══════════════════════════════════════════════════════════════════════════════
DATABASE CONTEXT:
═══════════════════════════════════════════════════════════════════════════════

**Rules:**
- Use ONLY entities/fields/metrics in semantic_context (never invent)
- Time_range is OPTIONAL unless query is about historical data
- Employee identification: Use Employee Code OR Primary Email (with OR condition, handle variations)
- Only "ACTIVE" employees unless otherwise specified
- Leave types: Sick Leave, Casual Leave, Paid Leave (sum all for total leaves)
- MongoDB agent handles field lookups and cross-collection joins automatically

**Collections:**
- base_report: Employee details, manager info, personal information
- leave_transaction: Leave records (Sick/Casual/Paid)
- offboarding_checklist: Exit formalities status
- performance_goal_report_2025_2026: Performance goals with weights
- goal_setting_status: Goal setting status and reviewers
- performance_rating_report_year_2025_2026: Performance ratings

**Semantic Context (TOON format):**
{format_semantic_context_toon(semantic_context)}

**Ambiguous Terms (TOON format):**
{format_ambiguous_terms_toon(ambiguous_terms)}



OUTPUT FORMAT:

If clarification is needed (MUST return ALL questions at once):
{{
  "status": "needs_clarification",
  "questions": ["<question 1>", "<question 2>", "<question 3>", ...],
  "intent": "self" or "others",
  "clarification_progress": {{
    "original_query": "<original user query from first interaction>",
    "pending_ambiguities": {{
      "<term1>": {{
        "term": "<term1>",
        "question": "<question asked for this term>",
        "possible_meanings": ["<meaning1>", "<meaning2>"]
      }},
      "<term2>": {{
        "term": "<term2>",
        "question": "<question asked for this term>",
        "possible_meanings": ["<meaning1>", "<meaning2>"]
      }}
    }},
    "resolved_ambiguities": {{
      "<term>": {{
        "term": "<term>",
        "resolved_to": "<resolved value>",
        "collection": "<collection name if applicable>"
      }}
    }}
  }}
}}
**CRITICAL REQUIREMENTS:**
- "questions" array MUST contain ALL questions for ALL ambiguous terms found in the query (if 2 ambiguities → 2 questions, if 5 → 5 questions)
- DO NOT skip any ambiguous terms - if an ambiguous term from ambiguous_terms appears in the query and is unqualified, you MUST ask about it
- If FIRST clarification → set original_query to current user_query
- If status="needs_clarification" → set pending_ambiguities (dict) with ALL ambiguous terms found in the query
- If status="ready" → clear pending_ambiguities (empty dict), populate resolved_ambiguities (dict)
- clarification_progress must be: {{"original_query": str, "pending_ambiguities": dict, "resolved_ambiguities": dict}}

If everything is clear (no clarification needed):
{{
  "status": "ready",
  "intent": "self" or "others",
  "route": "document" or "policy" (ONLY if needs_routing=True, otherwise omit),
  "final_clarified_query": "<natural language query with all ambiguities resolved, enhanced with context, modified with employee_code/region if needed>",
  "clarification_progress": {{
    "original_query": "<original user query>",
    "pending_ambiguities": {{}},  # Empty when ready
    "resolved_ambiguities": {{
      "<term1>": {{
        "term": "<term1>",
        "resolved_to": "<resolved value>",
        "collection": "<collection name if applicable>"
      }},
      "<term2>": {{
        "term": "<term2>",
        "resolved_to": "<resolved value>",
        "collection": "<collection name if applicable>"
      }}
    }}
  }}
}}
**FINAL QUERY BUILDING** (when status="ready"):
1. Start with original_query from clarification_progress
2. Replace ambiguous terms with resolved values from resolved_ambiguities
   - If resolved_to is a list → join with "and": "performance status and goal status and employee status"
   - If resolved_to is a string → replace directly as before
3. Preserve structure (order, connectors "and"/"or", "my"/"I" pronouns)
4. Add entity context from chat history if pronouns were resolved
5. Add field mappings if needed: "employee ID (field: employee_code)"
6. NOTE: employee_code is already added in RULE 5 (Query Enhancement) - DO NOT add again
7. DO NOT add extra phrases like "for my role" or explanatory text

**Examples:**
- Original: "department, status and reviewer" + Resolved: {{"department": "IT", "status": "performance status", "reviewer": "performance reviewer"}}
  → Final: "IT department, performance status and performance reviewer"
- Original: "my status and reviewer" + Resolved: {{"status": "performance status", "reviewer": "performance reviewer"}}
  → Final: "my performance status and performance reviewer. My employee code is 1045"
- Original: "my status" + Resolved: {{"status": ["performance status", "goal-setting status", "employee status"]}}
  → Final: "my performance status and goal-setting status and employee status. My employee code is 1045"

**INTENT CLASSIFICATION:**
- CONTINUATION: Use intent from ORIGINAL query
- STANDALONE: "self" (default) OR "others" (explicit other person)
- Manager/reviewer info → "self" intent

User Query: "{user_query}"

═══════════════════════════════════════════════════════════════════════════════
USER PROFILE:
═══════════════════════════════════════════════════════════════════════════════
{user_profile_text}

═══════════════════════════════════════════════════════════════════════════════
ROUTING REQUIREMENT:
═══════════════════════════════════════════════════════════════════════════════
{routing_text}

═══════════════════════════════════════════════════════════════════════════════
CURRENT CLARIFICATION PROGRESS:
═══════════════════════════════════════════════════════════════════════════════
Original Query: {original_query}

Pending Ambiguities: {pending_count} term(s)
{pending_list}

Resolved Ambiguities: {resolved_count} term(s)
{resolved_list}

**IMPORTANT**: 
- If user's current query answers any pending ambiguities, move them from pending_ambiguities to resolved_ambiguities
- If ALL pending_ambiguities are resolved, return status="ready"
- Use the resolved_ambiguities to build the final_clarified_query
    """
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are a MongoDB Query Clarification Agent. "
                    "CRITICAL RULES (MUST FOLLOW): "
                    "1. NEVER ask 'for whom?' or 'for yourself or someone else?' - always assume self if no explicit subject. "
                    "2. Qualified terms (e.g., 'performance status', 'current manager', 'offboarding reviewer') are FULLY RESOLVED - do NOT ask ANY questions about them. "
                    "3. If user answers previous questions with qualified terms, those are RESOLVED - do NOT ask follow-up questions. "
                    "4. Once a term is qualified, it's COMPLETE and READY for query - no further clarification needed. "
                    "5. Ask ALL necessary questions at once in the questions array. "
                    "6. If ALL terms in current query are qualified → return status='ready' immediately. "
                    "7. ACCESS CONTROL: If rule-based intent provided, validate it. Otherwise, classify intent based on requested info (see SENSITIVE INFO PATTERNS). For 'others' intent, ONLY allow name/email/code/number/id, DENY everything else. "
                    "Your response MUST be only valid JSON. No markdown, no comments, no backticks."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )
    
    # Parse JSON response, handling potential markdown code blocks
    response_text = response.content.strip()
    
    # Debug: Print raw LLM response
    print(f"\n=== RAW LLM RESPONSE ===")
    print(response_text[:500])  # First 500 chars
    print("=======================\n")
    
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        # Extract JSON from markdown code block
        lines = response_text.split("\n")
        response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])
    
    try:
        result = json.loads(response_text)
        # Validate that questions is a list
        if result.get("status") == "needs_clarification":
            questions = result.get("questions", [])
            if not isinstance(questions, list):
                # If questions is not a list, wrap it
                result["questions"] = [questions] if questions else []
            else:
                # Log how many questions were returned
                print(f"LLM returned {len(questions)} question(s): {questions}")
        
        # Ensure intent is always present (default to "self" if missing)
        if "intent" not in result:
            result["intent"] = "self"  # Default assumption
            print("WARNING: Intent not in LLM response, defaulting to 'self'")
        else:
            # Sanitize intent
            intent = result["intent"].lower()
            if "self" in intent:
                result["intent"] = "self"
            elif "other" in intent:
                result["intent"] = "others"
            else:
                result["intent"] = "unknown"
                print(f"WARNING: Unrecognized intent: {intent}, setting to 'unknown'")
        
        # Validate route if present (only when needs_routing=True and status="ready")
        if result.get("status") == "ready" and needs_routing:
            if "route" not in result:
                # Default to "document" if route not provided
                result["route"] = "document"
                print("WARNING: Route not in LLM response, defaulting to 'document'")
            else:
                # Sanitize route
                route = result["route"].lower()
                if route in ["document", "policy"]:
                    result["route"] = route
                else:
                    result["route"] = "document"
                    print(f"WARNING: Invalid route '{route}', defaulting to 'document'")
        elif result.get("status") == "ready" and not needs_routing:
            # MQL Agent tab - no routing needed, but set route to "document" for consistency
            result["route"] = "document"
        
        # Ensure clarification_progress is present with new structure
        if "clarification_progress" not in result:
            result["clarification_progress"] = {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        
        # Ensure pending_ambiguities and resolved_ambiguities are dicts
        if "pending_ambiguities" not in result["clarification_progress"]:
            result["clarification_progress"]["pending_ambiguities"] = {}
        if "resolved_ambiguities" not in result["clarification_progress"]:
            result["clarification_progress"]["resolved_ambiguities"] = {}
        
        # CRITICAL: Always ensure original_query is set on first clarification
        if result.get("status") == "needs_clarification":
            # If original_query is not set, this is the first clarification - store current query
            if not result["clarification_progress"].get("original_query"):
                result["clarification_progress"]["original_query"] = user_query
                print(f"✅ Stored original_query: {user_query}")
            # Also check if we have original_query from previous state (continuation scenario)
            elif clarification_progress and clarification_progress.get("original_query"):
                # Preserve original_query from state (don't overwrite)
                result["clarification_progress"]["original_query"] = clarification_progress["original_query"]
        
        # If needs_clarification, ensure pending_ambiguities are set
        if result.get("status") == "needs_clarification":
            # If pending_ambiguities is empty but we have questions, infer from questions
            if not result["clarification_progress"].get("pending_ambiguities") and questions:
                # Try to infer pending terms from questions and ambiguous_terms
                pending_ambiguities = {}
                for q in questions:
                    # Match questions to ambiguous terms
                    for amb_term in ambiguous_terms:
                        term_name = amb_term.get("term", "")
                        if term_name and term_name.lower() in q.lower():
                            pending_ambiguities[term_name] = {
                                "term": term_name,
                                "question": q,
                                "possible_meanings": amb_term.get("possible_meanings", [])
                            }
                if pending_ambiguities:
                    result["clarification_progress"]["pending_ambiguities"] = pending_ambiguities
        
        # Ensure final_clarified_query is present if ready
        if result.get("status") == "ready":
            if "final_clarified_query" not in result or not result.get("final_clarified_query"):
                # Build final query from original + resolved ambiguities
                original = result["clarification_progress"].get("original_query", "")
                resolved = result["clarification_progress"].get("resolved_ambiguities", {})
                
                # If we have original_query and resolved ambiguities, merge them
                if original and resolved:
                    # Merge: replace ambiguous terms in original with resolved values
                    final_query = original
                    for term, info in resolved.items():
                        if isinstance(info, dict):
                            resolved_value = info.get("resolved_to", term)
                        else:
                            resolved_value = str(info)
                        
                        # Handle list-based resolved values (multi-selection)
                        if isinstance(resolved_value, list):
                            # Join list with "and" connector
                            resolved_value = " and ".join(resolved_value)
                        else:
                            resolved_value = str(resolved_value)
                        
                        # Replace term in original query with resolved value
                        # Use word boundaries to avoid partial matches
                        # Replace whole word matches (case-insensitive)
                        pattern = r'\b' + re.escape(term) + r'\b'
                        final_query = re.sub(pattern, resolved_value, final_query, flags=re.IGNORECASE)
                    
                    result["final_clarified_query"] = final_query
                    print(f"✅ Built final query from original: '{original}' → '{final_query}'")
                elif original:
                    # Have original but no resolved (shouldn't happen, but handle it)
                    result["final_clarified_query"] = original
                    print(f"WARNING: No resolved ambiguities, using original_query: {original}")
                else:
                    # No original_query, use current user_query
                    result["final_clarified_query"] = user_query
                    print(f"WARNING: No original_query found, using user_query: {user_query}")
        
        # Validate and fix clarification_progress structure (hybrid validation)
        result = validate_clarification_progress(result, user_query, clarification_progress)
        
        return result
    except json.JSONDecodeError as e:
        print(f"ERROR: Error parsing JSON response: {e}")
        print(f"Response text: {response_text[:1000]}")  # Print first 1000 chars for debugging
        # Return error status - do NOT proceed with unclarified query
        return {
            "status": "error",
            "error": f"Failed to parse LLM response: {str(e)}",
            "intent": "self",
            "decision": "Error: Unable to process query. Please try again.",
            "clarification_progress": {
                "original_query": user_query,
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }
    except Exception as e:
        print(f"ERROR: Unexpected error in clarify_query: {e}")
        import traceback
        traceback.print_exc()
        # Return error status
        return {
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "intent": "self",
            "decision": "Error: An unexpected error occurred. Please try again.",
            "clarification_progress": {
                "original_query": user_query,
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }
        }


# -------------------------------
# 3. TEST CODE (only runs if file is executed directly)
# -------------------------------

if __name__ == "__main__":
    processor = SemanticDictionaryProcessor("database_summary.json")
    collections = processor.get_collection_routing_list()
    defualt_collections = processor.get_default_collections()
    router = CollectionRouterAgent(collections , defualt_collections)

    queries = [
        "Show me my performance rating for this year",
        "I want the list of employees in IT",
        "Get my appraisal score"
    ]

    # for q in queries:
    query = "my status"
    collection = router.route_query(query)
    print(f"Routed Collection: {collection}\n")
    result = processor.get_clarification_agent_structure(
        allowed_collections=collection
    )

    # print(json.dumps(result, indent=2))
    res = clarify_query(query, result["collections"], result["ambiguous_terms"])
    print(res)
    print(query)