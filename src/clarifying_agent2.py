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


def clarify_query(user_query: str , semantic_context: dict , ambiguous_terms: dict, chat_history: str = "", clarification_progress: dict = None, user_profile: dict = None, needs_routing: bool = False):
    """
    Unified agent: Clarification + Enhancement + Routing + Query Modification
    
    Args:
        user_query: the question from the user
        semantic_context: the semantic JSON document produced by build_summary_document()
        ambiguous_terms: dictionary of ambiguous terms and their possible meanings
        chat_history: formatted string of previous conversation (last 10 messages)
        clarification_progress: current clarification progress from state (optional)
        user_profile: dict with employee_code, designation, department, region (optional)
        needs_routing: whether to perform routing (True for Combined tab, False for MQL Agent tab)
    """
    # Initialize clarification_progress if not provided
    if clarification_progress is None:
        clarification_progress = {
            "original_query": "",
            "pending_ambiguities": {},
            "resolved_ambiguities": {}
        }
    
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
CHAT HISTORY (Previous Conversation):
═══════════════════════════════════════════════════════════════════════════════
{chat_history}

**IMPORTANT - CHAT HISTORY ANALYSIS (CRITICAL - CHECK THIS FIRST):**
1. **Context from Previous Queries:**
   - If chat history shows a previous query about a specific topic (e.g., "goal setting status information")
   - And the current query references the same topic (e.g., "My goal setting reviewer")
   - Then use the context from the previous query to resolve ambiguities
   - Example: If previous query was about "goal setting status", then "goal setting reviewer" is CLEAR from context → NO question needed

2. **Continuation Detection (CRITICAL - MOST IMPORTANT):**
   - If you see a previous Assistant message with clarification questions (e.g., "Which status?", "Which reviewer?")
   - And the current user query contains answers to those questions (e.g., "performance status", "performance reviewer", "current manager")
   - Then this is a CONTINUATION - the user is answering your previous questions
   - **CRITICAL RULES FOR CONTINUATION:**
     - If user answers with QUALIFIED terms (e.g., "performance status", "current manager") → Those terms are FULLY RESOLVED
     - Mark ALL answered terms as clarified in clarification_progress
     - Remove ALL answered terms from pending_ambiguities
     - **If ALL questions are answered with qualified terms → return status="ready" IMMEDIATELY**
     - **Do NOT ask follow-up questions about already-qualified terms**
     - Use the original_query from the first interaction (preserve it in clarification_progress)
     - Preserve the intent from the original query (if original had "my", intent is "self")
   
   **CRITICAL - MERGING ORIGINAL QUERY WITH ANSWERS:**
   - When continuation detected, you MUST merge user's answers back into the original_query structure
   - Map each answer to its corresponding ambiguous term in original_query
   - Replace the ambiguous term with the resolved value
   - Preserve all other parts of original query (connectors, order, context)
   
   **Example:**
   - Original: "department, status and reviewer"
   - Questions: ["Which department?", "Which status?", "Which reviewer?"]
   - User answers: "IT department, performance status, performance reviewer"
   - Mapping:
     * "department" → "IT department"
     * "status" → "performance status"
     * "reviewer" → "performance reviewer"
   - Final: "IT department, performance status and performance reviewer"
   - **CRITICAL**: Preserve the "and" connector and structure from original
   
   - **Example**: 
     * Previous: "Which status? Which reviewer? Which manager?"
     * Current: "1. Performance status, 2. performance reviewer, 3. current manager"
     * → ALL terms QUALIFIED → ALL RESOLVED → status="ready" (NO questions)
     * → Final query: Merge answers into original query structure

3. **Pronoun Resolution from Chat History (CRITICAL - CHECK MOST RECENT FIRST):**
   - If current query uses pronouns (he, she, they, his, her, their, it, this, that):
     * **MANDATORY**: Check chat history in REVERSE ORDER (most recent first) to find the IMMEDIATELY PRECEDING mention of a person/entity
     * **PRIORITY RULE**: The most recent entity mentioned in chat history takes precedence over older mentions
     * **RESOLUTION LOGIC**:
       1. Look at the LAST Assistant message in chat history
       2. Extract any person/entity name mentioned there (manager, reviewer, employee, etc.)
       3. If found, resolve the pronoun to that entity
       4. If not found, check the second-to-last message, and so on
     * Example: 
       - Last message: "Your manager's name is Pramatesh V. Kumar."
       - Current query: "what is his email"
       - Resolution: "his" = manager (from most recent message) → "what is my manager's email"
     * Example: 
       - Last message: "Your performance reviewer's name is Ashwin Shukla."
       - Current query: "what is his email"
       - Resolution: "his" = performance reviewer → "what is my performance reviewer's email"
   - **NEVER ask "Whose email?" or "Who are you referring to?" if chat history provides the context**
   - If chat history clearly identifies the entity, resolve the pronoun and enhance the query - NO clarification needed

4. **Context-Aware Term Resolution:**
   - If previous conversation mentioned "goal setting" → "goal setting reviewer" is QUALIFIED and CLEAR
   - If previous conversation mentioned "performance" → "performance reviewer" is QUALIFIED and CLEAR
   - If previous conversation mentioned "offboarding" → "offboarding reviewer" is QUALIFIED and CLEAR
   - Use chat history to automatically qualify terms that appear in current query
   - Example: History shows "goal setting status" → Current query "My goal setting reviewer" → "goal setting reviewer" is clear from context → NO question

4. **Qualified Term Recognition (CRITICAL):**
   - When user provides qualified terms in their answer, recognize them as COMPLETE
   - "Performance status" = qualified, complete, ready → NO questions
   - "Performance reviewer for current month" = qualified, complete, ready → NO questions
   - "Current manager" = qualified, complete, ready → NO questions
   - Do NOT ask for "exact information", "specific details", or "which type" about qualified terms

# ============================================================================
# OLD PROMPT SECTIONS (COMMENTED OUT - FOR REFERENCE/REVERT IF NEEDED)
# ============================================================================
# **CRITICAL - CHAT HISTORY ANALYSIS (MUST CHECK BEFORE ASKING QUESTIONS):**
# 
# **MANDATORY CHAT HISTORY ANALYSIS (DO THIS FIRST):**
# 
# 1. **Extract Previous Clarification Questions:**
#    - Look for Assistant messages in chat history that contain clarification questions
#    - Identify what questions were asked (e.g., "Which status?", "Which reviewer?")
# 
# 2. **Extract User's Answers from Current Query:**
#    - Check if current query contains answers to previous questions
#    - Map each answer to its corresponding question:
#      * If previous question: "Which status?" → Look for answer in current query (e.g., "employee status", "performance status", "goal-setting status")
#      * If previous question: "Which reviewer?" → Look for answer in current query (e.g., "offboarding reviewer", "performance reviewer", "goal-setting reviewer")
#      * If previous question: "Do you want pending leaves or total leaves?" → Look for answer (e.g., "pending", "total")
# 
# 3. **Continuation Detection:**
#    - If chat history shows:
#      * Previous query: "my status and reviewer"
#      * Previous clarification: "Which status? Which reviewer?"
#      * Current query: "employee status and offboarding reviewer"
#    - Then this is a CONTINUATION. The user is ANSWERING previous questions.
#    - Extract answers: "employee status" (answers "Which status?") and "offboarding reviewer" (answers "Which reviewer?")
#    - Merge with original: "my employee status and offboarding reviewer"
#    - Return status: "ready" (all ambiguities resolved)
#    - Intent: Use intent from ORIGINAL query (if original had "my", intent is "self")
# 
# 4. **Resolve Ambiguities from History:**
#    - If user previously said "performance status" → treat "status" in current query as "performance status"
#    - If user previously said "goal-setting reviewer" → treat "reviewer" as "goal-setting reviewer"
#    - Apply previous answers to current query automatically
# 
# 5. **Only Ask About NEW Ambiguities:**
#    - If ALL previous questions are answered → return status: "ready" (no questions needed)
#    - If SOME questions answered → ask ONLY about unanswered ones
#    - NEVER ask questions that were already answered in chat history
# 
# 6. **Context Merging:**
#    - If current query is a continuation (e.g., user answering clarification), merge it with the original query from history
#    - Example: History shows "my status" → User says "performance status" → Treat as "my performance status"
# 
# **CRITICAL - QUALIFIED TERMS ARE NOT AMBIGUOUS (HIGHEST PRIORITY - CHECK THIS FIRST):**
# 
# Before checking if a term is ambiguous, FIRST check if it's QUALIFIED:
# 
# **QUALIFIED TERMS (NOT ambiguous - DO NOT ASK QUESTIONS):**
# - "performance status" → QUALIFIED → NOT ambiguous → NO question
# - "offboarding reviewer" → QUALIFIED → NOT ambiguous → NO question
# - "goal-setting reviewer" → QUALIFIED → NOT ambiguous → NO question
# - "performance reviewer" → QUALIFIED → NOT ambiguous → NO question
# - "employee status" → QUALIFIED → NOT ambiguous → NO question
# - "pending leaves" → QUALIFIED → NOT ambiguous → NO question
# - "total leaves" → QUALIFIED → NOT ambiguous → NO question
# 
# **UNQUALIFIED TERMS (ambiguous - ASK QUESTIONS):**
# - "status" → UNQUALIFIED → ambiguous → ASK question
# - "reviewer" → UNQUALIFIED → ambiguous → ASK question
# - "leaves" → UNQUALIFIED → ambiguous → ASK question
# 
# **RULE (MANDATORY):**
# 1. If you see a QUALIFIED term (has a prefix like "performance", "offboarding", "goal-setting", "employee", "pending", "total"), 
#    DO NOT ask about it. Treat it as SPECIFIC and RESOLVED.
# 
# 2. Check for qualified terms BEFORE checking ambiguous_terms dictionary.
# 
# 3. Examples:
#    - Query: "my performance status" → "performance status" is QUALIFIED → NOT ambiguous → NO question → status: "ready"
#    - Query: "offboarding reviewer" → "offboarding reviewer" is QUALIFIED → NOT ambiguous → NO question → status: "ready"
#    - Query: "my status" → "status" is UNQUALIFIED → ambiguous → ASK question
#    - Query: "my reviewer" → "reviewer" is UNQUALIFIED → ambiguous → ASK question
# ============================================================================

"""
    
    prompt = f"""
You are a MongoDB Query Clarification Agent. Your job is to ask ALL necessary clarifying questions in ONE response when the database query cannot be constructed without them.

{chat_history_section}

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE RULES (MUST FOLLOW - NO EXCEPTIONS):
═══════════════════════════════════════════════════════════════════════════════

**RULE 1: DEFAULT SUBJECT (HIGHEST PRIORITY - NEVER VIOLATE):**
   - If query has NO explicit subject (e.g., "John's", "team's") → ALWAYS assume user means THEMSELVES
   - NEVER ask "for whom?", "for yourself or someone else?", or "whose?"
   - Examples: "leaves" → self, "total leaves" → self, "offboarding reviewer" → self, "reviewer" → self
   - Only ask about subject if query explicitly mentions another person/entity (e.g., "John's leaves")

**RULE 2: QUALIFIED TERMS ARE NOT AMBIGUOUS (CHECK FIRST - CRITICAL):**
   - If term has a qualifier prefix → it's FULLY RESOLVED, DO NOT ask ANY questions about it
   - Qualified terms are COMPLETE and READY for query - no further clarification needed
   - Qualified: "performance status", "offboarding reviewer", "total leaves", "pending leaves", "employee status", "goal-setting reviewer", "current manager"
   - Unqualified: "status", "reviewer", "leaves", "manager" → these ARE ambiguous
   - Check qualified terms BEFORE checking ambiguous_terms dictionary
   - **CRITICAL**: Once a term is qualified (e.g., "performance status"), it's DONE. Do NOT ask for:
     * "What exact information do you need about performance status?" → NO, it's already clear
     * "Which performance status?" → NO, "performance status" is already specific
     * "Current or historical?" → NO, if user said "performance status", that's enough

**RULE 3: ASK ALL QUESTIONS AT ONCE:**
   - Identify ALL ambiguities and missing components
   - Return ALL questions in one response (if 2 ambiguities → 2 questions, if 5 → 5 questions)

**RULE 4: USE CHAT HISTORY AND TRACK PROGRESS (CRITICAL):**
   - If previous questions were asked and answered in current query → use those answers
   - If continuation detected → merge with original query, use original intent
   - NEVER ask questions already answered in chat history
   - Track which terms have been clarified and which are still pending in clarification_progress
   - When continuation detected: mark previously pending terms as clarified in clarification_progress
   - **CRITICAL**: If user answers with qualified terms (e.g., "performance status", "performance reviewer"), those terms are RESOLVED
   - **CRITICAL**: Do NOT ask follow-up questions about already-qualified terms. Once qualified = ready to query

**RULE 5: BUILD FINAL QUERY WHEN READY (CRITICAL - PRESERVE ORIGINAL STRUCTURE):**
   - When all ambiguities are resolved (status="ready"), build final_clarified_query by:
   
   1. **Start with Original Query Structure:**
      - Use the original_query from clarification_progress as the base
      - Preserve the original word order, connectors ("and", "or", commas), and structure
      - If original_query is not in clarification_progress, use current user_query as base
   
   2. **Replace Ambiguous Terms with Resolved Values:**
      - For each term in resolved_ambiguities, replace it in the original query
      - Example: Original "department, status and reviewer"
        * resolved_ambiguities: {{"department": {{"resolved_to": "IT department"}}, "status": {{"resolved_to": "performance status"}}, "reviewer": {{"resolved_to": "performance reviewer"}}}}
        * Final: "IT department, performance status and performance reviewer"
   
   3. **Preserve All Parts:**
      - If original had 3 items, final must have 3 items
      - If original had "my", preserve it: "my department, status and reviewer" → "my IT department, performance status and performance reviewer"
      - Don't lose any parts of the original query
      - Preserve connectors: "and", "or", commas
   
   4. **Examples:**
      - Original: "department, status and reviewer"
        Answers: "IT department, performance status, performance reviewer"
        Final: "IT department, performance status and performance reviewer"
      
      - Original: "my status and reviewer"
        Answers: "performance status, performance reviewer"
        Final: "my performance status and performance reviewer"
      
      - Original: "department of an hr email_id, status and reviewer"
        Answers: "IT department, performance status, performance reviewer"
        Final: "IT department of an hr email_id, performance status and performance reviewer"

**RULE 6: QUERY ENHANCEMENT (AFTER CLARIFICATION):**
   - Extract entities from chat history (manager name, employee_id, department, region, etc.)
   - Resolve pronouns (he/she/they/his/her/their) to specific entities from chat history
   - Add context from previous queries to make query self-contained
   - Example: "Tell me his email_id" + History: "manager name is Abc Def" → "Tell me my manager's email_id. My manager name is Abc Def"

**RULE 7: ROUTING (ONLY IF needs_routing=True):**
   - Classify query as "document" (factual lookup, employee records) or "policy" (HR rules, guidelines)
   - "document": IDs, employee records, manager data, database queries
   - "policy": HR rules, eligibility, guidelines, what-to-do questions
   - Default to "document" if unclear

**RULE 8: QUERY MODIFICATION:**
   - Add employee_code for self queries: "My employee code is {{employee_code}}"
   - For HR users with regions: Apply region constraints (see HR Region Rules below)
   - Preserve natural language flow

═══════════════════════════════════════════════════════════════════════════════
QUERY ENHANCEMENT (APPLY AFTER CLARIFICATION WHEN status="ready"):
═══════════════════════════════════════════════════════════════════════════════

**1. Entity Extraction from Chat History:**
   - Extract entities mentioned in previous queries/results:
     * Manager name (e.g., "manager name is Abc Def")
     * Employee IDs (e.g., "employee_id is 123")
     * Departments, regions, designations
     * Any specific values from previous query results
   - Use these entities to enhance the query

**2. Pronoun Resolution (CRITICAL - ALWAYS RESOLVE FROM CHAT HISTORY - CHECK MOST RECENT FIRST):**
   - If query uses pronouns (he, she, they, his, her, their, it, this, that):
     * **MANDATORY**: Check chat history in REVERSE ORDER (most recent first) to resolve the pronoun
     * **PRIORITY RULE**: The IMMEDIATELY PRECEDING conversation turn takes highest priority
     * **RESOLUTION STEPS**:
       1. Check the LAST Assistant message in chat history for any person/entity name
       2. If found, resolve pronoun to that entity (e.g., "manager", "reviewer", "employee")
       3. If not found, check the second-to-last message, and so on
       4. Once resolved, enhance the query with the resolved entity
     * Example: 
       - Last message: "Your manager's name is Pramatesh V. Kumar."
       - Current query: "what is his email"
       - Resolution: "his" = manager (from most recent) → "what is my manager's email"
     * Example: 
       - Last message: "Your performance reviewer's name is Ashwin Shukla."
       - Current query: "what is his email"
       - Resolution: "his" = performance reviewer → "what is my performance reviewer's email"
   - **NEVER ask "Whose email?" or "Who are you referring to?" if chat history provides the context**
   - If chat history clearly identifies the entity, resolve the pronoun and enhance the query automatically

**3. Context Addition:**
   - Build a self-contained query that includes:
     * Original query intent
     * Resolved pronouns/references
     * Relevant entities from chat history
     * User's employee_code (if self query)
     * **Explicit field mappings and lookup instructions** (for MongoDB agent):
       - If field name differs from natural language, specify: "(field: actual_field_name)"
       - If data requires lookup to another collection, specify: "(requires lookup to collection_name using join_field to get target_field)"
       - This helps MongoDB agent generate correct queries with all fields and proper $lookup operations

**4. Example Enhancement:**
   - Input: "Tell me his email_id"
   - Chat History: "User: What is my manager name? Assistant: Your manager name is Abc Def"
   - Enhanced: "Tell me my manager's email (requires lookup to base_report collection using manager name to get primary email field). My manager name is Abc Def. My employee code is 123"
   - **IMPORTANT**: Only add lookup instructions when the user explicitly requests a field that requires lookup
   - Do NOT retrieve all information upfront - only add context for what is explicitly asked
   - Do NOT add lookup instructions for fields that are already available in the current collection
   - Use generic patterns: determine target collection and join fields dynamically based on the field being requested (not hardcoded to specific fields)
   
**5. Field Mapping Examples (generic patterns - apply to any field):**
   - If field name differs: "field_name" → "field_name (field: actual_database_field_name)"
   - If lookup needed: "field_name" → "field_name (requires lookup to target_collection using join_field to get target_field)"
   - Multiple fields: "field1 and field2" → "field1 (field: actual_field1) and field2 (requires lookup to collection using join_field to get target_field)"
   - **CRITICAL - Generic Lookup Pattern (apply to ANY field that needs lookup):**
     * When a field requires data from another collection, add: "field_name (requires lookup to target_collection using join_field to get target_field)"
     * Only add lookup instructions when the user explicitly requests that specific field - do not add them proactively
     * Determine the target collection and join fields based on the field being requested and the collections available
     * Use generic patterns: "entity_name's field_name (requires lookup to target_collection using entity_name to get target_field_name)"

═══════════════════════════════════════════════════════════════════════════════
ROUTING (ONLY IF needs_routing=True):
═══════════════════════════════════════════════════════════════════════════════

**Route Classification:**
   - "document": Factual lookup, IDs, employee records, manager data, database queries
     * Examples: "What is my email?", "Show me employees", "List managers"
   - "policy": HR rules, eligibility, guidelines, what-to-do questions
     * Examples: "What is the leave policy?", "How to apply for leave?", "Eligibility for promotion"
   
**Rules:**
   - If query asks for rules/eligibility/what-to-do → "policy"
   - If query asks for records/IDs/data → "document"
   - Default to "document" if unclear
   - Only perform routing when needs_routing=True (Combined tab)

═══════════════════════════════════════════════════════════════════════════════
QUERY MODIFICATION (APPLY WHEN status="ready"):
═══════════════════════════════════════════════════════════════════════════════

**1. Employee Code Addition:**
   - For self queries (intent="self"): Add "My employee code is {{employee_code}}" (use the actual employee_code from user profile)
   - Example: "my performance status" → "my performance status. My employee code is 123"

**2. HR Region Constraints (ONLY for HR users with regions):**
   - If user is HR (department="Human Resources") AND has region(s):
     
     **Self Queries (intent="self"):**
     - If query refers to HR themselves ("I", "my", "me") → Do NOT append region
     - Only add employee_code
     
     **Other Queries (intent="others"):**
     - If user has SINGLE region:
       * Append "in [Region Name] region" to query
       * Example: "Show employees" → "Show employees in Mumbai region"
     
     - If user has MULTIPLE regions:
       * If query mentions NO region → Append "in all allowed regions"
       * If query mentions region AND it's allowed → Replace with "[Region Name] region"
       * If query mentions region AND it's NOT allowed → Override to "in all allowed regions"
       * Always append word "region" after region name(s)
     
     **Examples:**
     - HR with region="Mumbai", query="Show employees" → "Show employees in Mumbai region"
     - HR with regions=["Mumbai", "Delhi"], query="Show employees in Pune" → "Show employees in all allowed regions" (Pune not allowed)
     - HR with region="Mumbai", query="What is my manager name?" → "What is my manager name? My employee code is 123" (self query, no region)

**3. Natural Language Preservation:**
   - Keep query natural and readable
   - Don't make it too verbose
   - Preserve original query structure

═══════════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST (DO THIS BEFORE ASKING ANY QUESTION):
═══════════════════════════════════════════════════════════════════════════════

Before asking, verify:
- Subject clear? → If no explicit subject, assume self (DO NOT ask about subject)
- Term qualified? → If qualified (e.g., "performance status", "current manager"), it's FULLY resolved (DO NOT ask ANY questions)
- Already answered? → Check chat history, if answered → use that answer, mark as clarified
- All ambiguities identified? → List ALL, not just one
- **CRITICAL CHECK**: If ALL terms in current query are qualified → status="ready", NO questions
- **CRITICAL CHECK**: If user answered previous questions with qualified terms → those are RESOLVED, do NOT ask for more details

═══════════════════════════════════════════════════════════════════════════════
NEVER ASK ABOUT:
═══════════════════════════════════════════════════════════════════════════════

- Subject/employee (unless explicitly mentioned like "John's")
- Qualified terms (e.g., "total leaves", "performance status", "offboarding reviewer", "current manager", "performance reviewer")
- Things already answered in chat history
- Things not in semantic_context
- Conversational/HR/policy questions unrelated to MongoDB query
- **CRITICAL**: Do NOT ask for granular details about already-qualified terms:
  * "What exact information do you need about [qualified term]?" → NO
  * "Which [qualified term]?" → NO (it's already qualified)
  * "Current or historical [qualified term]?" → NO (if user said "performance status", that's enough)
  * "Specific [qualified term] or all [qualified term]?" → NO (qualified = ready)
- **CRITICAL - Pronoun Resolution:**
  * "Whose email?" or "Who are you referring to?" → NO (if chat history provides context)
  * "What is his email" + History: "manager name is Nitin Mittal" → Resolve "his" = manager → NO question needed
  * Always check chat history FIRST before asking about pronouns

═══════════════════════════════════════════════════════════════════════════════
WHEN TO ASK QUESTIONS:
═══════════════════════════════════════════════════════════════════════════════

Ask ONLY when:
- Unqualified ambiguous term exists (e.g., "status", "reviewer", "leaves")
- Required component missing AND exists in semantic_context
- Multiple ambiguities → ask ALL at once

═══════════════════════════════════════════════════════════════════════════════
KEY EXAMPLES:
═══════════════════════════════════════════════════════════════════════════════

CORRECT: "my leaves" → Ask: "Do you want pending leaves or total leaves?" (DO NOT ask "for whom?")
CORRECT: "total leaves" → NO question (qualified term, assume self) → status: "ready"
CORRECT: "offboarding reviewer" → NO question (qualified term, assume self) → status: "ready"
CORRECT: "my status and reviewer" → Ask: ["Which status?", "Which reviewer?"] (2 questions)
CORRECT: "employee status and offboarding reviewer" (continuation) → NO questions (both qualified, use original intent) → status: "ready"
WRONG: "total leaves" → DO NOT ask "for yourself or someone else?" (violates Rule 1)
WRONG: "offboarding reviewer" → DO NOT ask "for whom?" (violates Rule 1)

═══════════════════════════════════════════════════════════════════════════════
DATABASE CONSTRAINTS:
═══════════════════════════════════════════════════════════════════════════════

- Use ONLY entities/fields/metrics in semantic_context (never invent)
- Time_range is OPTIONAL unless query is about historical data (e.g., "leaves this year" needs time)
- For leaves: time period is usually optional (can query all-time leaves)

You are given:
1) semantic_context (database concepts and collections)
{json.dumps(semantic_context, indent=2)}

2) ambiguous_terms (terms with multiple database meanings - TOON format):
{format_ambiguous_terms_toon(ambiguous_terms)}

Important database context to keep in mind:
Database Context:
  -Some documents may use Employee Code or Primary Email to uniquely identify an employee.
  -Other documents may contain these identifiers in different forms, such as Person ID, Employee Email Address, or similar variations.
  -In certain documents, either the Employee Code or Primary Email may be missing.
  -Therefore, always use both fields together—in all their possible variations—with an OR condition to reliably identify an employee.
  
  - Collection Name: base_report
    - This collection contains employee details such as employee code, name, email, designation,grade , department, region, date of joining, managers info and other personal information.
    - Employees can be identified as "ACTIVE" or "INACTIVE" based on their status in the "assignment status type" field.This means that wether the employee is currently working in the organization or not.
    - **Important**: Only "ACTIVE" employees should be considered for queries unless otherwise specified. 

  - Collection Name: leave_transaction
    - Each employee can have three types of leaves:
      - Sick Leave
      - Casual Leave
      - Paid Leave
    - When a user asks for the total number of leaves taken by an employee, you must sum up all three types of leaves (Sick Leave, Casual Leave, and Paid Leave) for that employee.
    - If u did't find the records for the employee, that means the employee has not taken any leaves yet.

  - Collection Name: offboarding_checklist
    - when "status.all task status" is "Completed" , it means all the exit formalities are done for the employee.
    - when "status.all task status" is "Pending" , it means some exit formalities are still pending for the employee.
    - to know which exit checklist formaities are pending for an employee, you can check which all feilds are marked as "Pending" in "the "status" field.

  - Collection Name: performance_goal_report_2025_2026
    - This collection contains performance goals entry for employees for the year 2025-2026.
    - It has got goal plan name , weight and description of the goals of the employees.
    - One employee can have multiple goals assigned to them , with different weightages. The total weightage of all goals for an employee is sum up to 100.

  - Collection Name: goal_setting_status
    - This collection contains information about employees' performance goal setting status .
    - This contains information about whether employees have set their goals for the review period or not , and who is the reviewer assigned to them.
    - The goal setting status can be "Approved" or "CANCELLED".

  - Collection Name: permormance_rating_report_year_2025_2026
    - This collection contains performance ratings for employees for the year 2025-2026.
    - It has got feild "final status" as "Submitted" , "Completed" , "In progress" , etc


═══════════════════════════════════════════════════════════════════════════════
DETAILED EXAMPLES:
═══════════════════════════════════════════════════════════════════════════════

Example 1: "my leaves"
  → Subject: "my" → self (DO NOT ask "for whom?")
  → Term: "leaves" → unqualified → ambiguous
  → Ask: "Do you want pending leaves or total leaves?"

Example 2: "total leaves" (continuation from "my leaves")
  → Subject: No explicit subject → assume self (DO NOT ask "for whom?")
  → Term: "total leaves" → QUALIFIED → NOT ambiguous
  → Status: "ready" (no questions needed)

Example 3: "offboarding reviewer"
  → Subject: No explicit subject → assume self (DO NOT ask "for whom?")
  → Term: "offboarding reviewer" → QUALIFIED → NOT ambiguous
  → Status: "ready" (no questions needed)

Example 4: "my status and reviewer"
  → Subject: "my" → self (DO NOT ask "for whom?")
  → Terms: "status" (unqualified) + "reviewer" (unqualified) → both ambiguous
  → Ask: [
      "Which status do you need: performance, goal-setting, offboarding, or employee status?",
      "Do you mean goal-setting reviewer, performance reviewer, or offboarding reviewer?"
  ]

Example 5: "employee status and offboarding reviewer" (continuation)
  → Both terms QUALIFIED → NOT ambiguous
  → Use intent from original query ("my status and reviewer" → "self")
  → Status: "ready" (no questions needed)

Example 6: "1. Performance status, 2. performance reviewer for current month and 3. current manager" (continuation)
  → ALL terms QUALIFIED: "performance status", "performance reviewer", "current manager"
  → ALL terms are RESOLVED → NO questions needed
  → Status: "ready" (build final query immediately)

Example 7: "Current Performance status" (continuation)
  → Term QUALIFIED: "Current Performance status" → RESOLVED
  → Do NOT ask "What exact information?" or "Current or historical?" → It's already clear
  → Status: "ready"

Example 8: CONTINUATION SCENARIO (CRITICAL - FOLLOW THIS EXACTLY):
  Previous query: "My status, reviewer and manager name"
  Previous questions: ["Which status?", "Which reviewer?", "Which manager?"]
  Current query: "1. Performance status, 2. performance reviewer for current month and 3. current manager"
  → ALL terms are QUALIFIED: "performance status", "performance reviewer", "current manager"
  → ALL terms are RESOLVED → NO questions needed
  → Status: "ready", questions: [], final_clarified_query: "My performance status, performance reviewer for current month, and current manager name"
  → **DO NOT** ask "What exact information about performance status?" or "Which performance reviewer?" → They're already qualified

Example 9: PRONOUN RESOLUTION FROM CHAT HISTORY (CRITICAL - MOST RECENT TAKES PRIORITY):
  Chat History (in order, most recent last):
    - "User: performance reviewer's name?"
    - "Assistant: Your performance reviewer's name is Ashwin Shukla."
    - "User: my manager's name"
    - "Assistant: Your manager's name is Pramatesh V. Kumar."  ← MOST RECENT MESSAGE
  Current query: "what is his email"
  → **STEP 1**: Check MOST RECENT message first: "Your manager's name is Pramatesh V. Kumar."
  → **STEP 2**: Extract entity: "manager" (Pramatesh V. Kumar)
  → **STEP 3**: Resolve pronoun: "his" = "manager" (from most recent message)
  → Enhanced query: "what is my manager's email (requires lookup to base_report collection using manager name to get primary email field). My manager name is Pramatesh V. Kumar"
  → Status: "ready" (NO question "Whose email?" needed - context is clear from most recent history)
  → **DO NOT** ask "Whose email are you referring to?" → Chat history provides the context
  → **IMPORTANT**: Do NOT resolve to "performance reviewer" even though it was mentioned earlier - most recent takes priority
  → **NOTE**: Lookup instruction is added only because user explicitly asked for "email" - if user had asked for "manager name", no lookup would be needed
  → **GENERIC PATTERN**: Apply this same logic to ANY field (not just email) - determine lookup requirements dynamically based on the field requested

Example 9: CONTINUATION SCENARIO (WRONG vs CORRECT):
  Previous: "My status and reviewer"
  Previous questions: ["Which status?", "Which reviewer?"]
  Current: "1. Current Performance status, 2. performance reviewer for current month and 3. current manager"
  
  WRONG Response:
  {{
    "status": "needs_clarification",
    "questions": ["What exact information about performance status?", "Which performance reviewer?"]
  }}
  
  CORRECT Response:
  {{
    "status": "ready",
    "final_clarified_query": "My current performance status, performance reviewer for current month, and current manager name",
    "clarification_progress": {{
      "original_query": "My status and reviewer",
      "resolved_ambiguities": {{
        "status": {{"term": "status", "resolved_to": "current performance status"}},
        "reviewer": {{"term": "reviewer", "resolved_to": "performance reviewer for current month"}}
      }},
      "pending_ambiguities": {{}}
    }}
  }}

═══════════════════════════════════════════════════════════════════════════════
COMMON MISTAKES TO AVOID:
═══════════════════════════════════════════════════════════════════════════════

WRONG: "total leaves" → Ask "for yourself or someone else?"
CORRECT: "total leaves" → NO question (qualified term, assume self)

WRONG: "offboarding reviewer" → Ask "for whom?"
CORRECT: "offboarding reviewer" → NO question (qualified term, assume self)

WRONG: "my leaves" → Ask only "Do you want pending or total?" (missing time period)
CORRECT: "my leaves" → Ask "Do you want pending leaves or total leaves?" (time is optional for leaves)

WRONG: User answers "performance status" → Ask "What exact information do you need about performance status?"
CORRECT: User answers "performance status" → It's qualified, resolved → status="ready"

WRONG: User answers "performance reviewer for current month" → Ask "Which performance reviewer?" or "For which period?"
CORRECT: User answers "performance reviewer for current month" → It's qualified, resolved → status="ready"

WRONG: User answers "current manager" → Ask "Do you mean current manager's name, role, or details?"
CORRECT: User answers "current manager" → It's qualified, resolved → status="ready"

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
**CRITICAL**: 
- The "questions" array MUST contain ALL necessary questions. If there are 2 ambiguities, return 2 questions. If there are 5, return 5. NEVER return just one question when multiple are needed.
- **ORIGINAL QUERY STORAGE (MANDATORY):**
  * If this is the FIRST clarification (no original_query in clarification_progress), you MUST set original_query to the current user_query
  * Store it in clarification_progress.original_query
  * This is CRITICAL for building the final query later
- **CONTINUATION DETECTION (MOST IMPORTANT):**
  * If chat history shows you asked questions (e.g., "Which status?", "Which reviewer?")
  * And current query contains qualified answers (e.g., "performance status", "performance reviewer", "current manager")
  * Then this is a CONTINUATION - user is answering your questions
  * **ACTION**: Move answered terms from pending_ambiguities to resolved_ambiguities, and if ALL are answered → return status="ready" with NO questions
  * **DO NOT** ask follow-up questions about already-qualified terms
- If this is a continuation (user answering previous questions), update clarification_progress:
  * Move answered terms from pending_ambiguities to resolved_ambiguities (e.g., "status" → resolved with "performance status")
  * Remove answered terms from pending_ambiguities
  * Keep original_query from the first interaction (DO NOT overwrite it)
  * **If ALL pending_ambiguities are now resolved → status="ready", questions=[]**
  * **CRITICAL**: Build final_clarified_query by merging original_query with resolved values (preserve structure)
- If this is the first clarification, set original_query to current user_query and add all ambiguous terms to pending_ambiguities

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
**IMPORTANT - FINAL QUERY BUILDING (CRITICAL):**
- When status is "ready", you MUST provide a "final_clarified_query" that is a complete, unambiguous natural language query.
- **MANDATORY STEPS:**
  1. Get original_query from clarification_progress (the first query from user)
  2. Get resolved_ambiguities (terms that were clarified)
  3. Replace each ambiguous term in original_query with its resolved value
  4. Preserve the original structure (order, connectors, context)
  5. Include ALL parts from original query (don't lose any items)
  6. **ADD EXPLICIT FIELD INSTRUCTIONS** (for MongoDB agent to generate correct queries):
     * For fields that need lookup to another collection: Add explicit instruction in parentheses
     * For fields where field name differs from natural language: Mention the actual field name
     * Format: "(field: actual_field_name)" or "(requires lookup to collection_name using join_field to get target_field)"
     * This helps MongoDB agent include ALL requested fields and use proper $lookup operations
  
- **Examples:**
  - Original: "department, status and reviewer"
    Resolved: {{"department": "IT department", "status": "performance status", "reviewer": "performance reviewer"}}
    Final: "IT department, performance status and performance reviewer" (preserves "and" connector)
  
  - Original: "my status and reviewer"
    Resolved: {{"status": "performance status", "reviewer": "performance reviewer"}}
    Final: "my performance status and performance reviewer" (preserves "my" and "and")
  
  - Original: "department of an hr email_id, status and reviewer"
    Resolved: {{"department": "IT department", "status": "performance status", "reviewer": "performance reviewer"}}
    Final: "IT department of an hr email_id, performance status and performance reviewer" (preserves all parts)
  
  - Original: "field1 and field2"
    Final: "field1 (field: actual_field1_name) and field2 (requires lookup to target_collection using join_field to get target_field)"
  
- This query should be self-contained and ready to be passed to the MongoDB query generator.
- **Include explicit field mappings and lookup instructions** so MongoDB agent can generate queries with all requested fields.
- Preserve the original intent (e.g., if original had "my", include it).
- Make it natural and complete, preserving the original query structure.

═══════════════════════════════════════════════════════════════════════════════
INTENT CLASSIFICATION:
═══════════════════════════════════════════════════════════════════════════════

**If CONTINUATION (answers previous questions):**
  → Use intent from ORIGINAL query in chat history
  → Example: Original "my status" → Current "employee status" → intent: "self" (from original)

**If STANDALONE:**
  → "self": User's own details, manager's/reviewer's non-sensitive info
  → "others": Another person's info or sensitive data (salary, DOB, etc.)
  → Default: If no explicit subject → intent: "self"

Examples:
- "my leaves" → "self"
- "total leaves" → "self" (no subject, assume self)
- "offboarding reviewer" → "self" (no subject, assume self)
- "John's leaves" → "others" (explicit subject)

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
            
            # Ensure pending_ambiguities is empty when ready
            if "pending_ambiguities" not in result["clarification_progress"]:
                result["clarification_progress"]["pending_ambiguities"] = {}
            # Ensure resolved_ambiguities is populated
            if "resolved_ambiguities" not in result["clarification_progress"]:
                result["clarification_progress"]["resolved_ambiguities"] = {}
        
        return result
    except json.JSONDecodeError as e:
        print(f"ERROR: Error parsing JSON response: {e}")
        print(f"Response text: {response_text}")
        # Return a fallback response with default intent and user_query as final_clarified_query
        return {
            "status": "ready",
            "intent": "self",
            "final_clarified_query": user_query,  # Use original query as fallback
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