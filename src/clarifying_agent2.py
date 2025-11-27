import json
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


def clarify_query(user_query: str , semantic_context: dict , ambiguous_terms: dict, chat_history: str = ""):
    """
    user_query: the question from the user
    semantic_context: the semantic JSON document produced by build_summary_document()
    ambiguous_terms: dictionary of ambiguous terms and their possible meanings
    chat_history: formatted string of previous conversation (last 10 messages)
    """

    # Build chat history section for prompt
    chat_history_section = ""
    if chat_history and chat_history.strip():
        chat_history_section = f"""

═══════════════════════════════════════════════════════════════════════════════
CHAT HISTORY (Previous Conversation):
═══════════════════════════════════════════════════════════════════════════════
{chat_history}

**IMPORTANT - CHAT HISTORY ANALYSIS:**
1. If you see a previous Assistant message with clarification questions (e.g., "Which status?", "Which reviewer?")
2. And the current user query contains answers to those questions (e.g., "employee status", "offboarding reviewer")
3. Then this is a CONTINUATION - the user is answering your previous questions
4. In this case:
   - Mark the answered terms as clarified in clarification_progress
   - Remove them from pending_terms
   - If ALL questions are answered → return status="ready" with final_clarified_query
   - If SOME questions answered → ask ONLY about remaining ambiguities
   - Use the original_query from the first interaction (preserve it in clarification_progress)
   - Preserve the intent from the original query (if original had "my", intent is "self")

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

**RULE 2: QUALIFIED TERMS ARE NOT AMBIGUOUS (CHECK FIRST):**
   - If term has a qualifier prefix → it's RESOLVED, DO NOT ask about it
   - Qualified: "performance status", "offboarding reviewer", "total leaves", "pending leaves", "employee status"
   - Unqualified: "status", "reviewer", "leaves" → these ARE ambiguous
   - Check qualified terms BEFORE checking ambiguous_terms dictionary

**RULE 3: ASK ALL QUESTIONS AT ONCE:**
   - Identify ALL ambiguities and missing components
   - Return ALL questions in one response (if 2 ambiguities → 2 questions, if 5 → 5 questions)

**RULE 4: USE CHAT HISTORY AND TRACK PROGRESS:**
   - If previous questions were asked and answered in current query → use those answers
   - If continuation detected → merge with original query, use original intent
   - NEVER ask questions already answered in chat history
   - Track which terms have been clarified and which are still pending in clarification_progress
   - When continuation detected: mark previously pending terms as clarified in clarification_progress

**RULE 5: BUILD FINAL QUERY WHEN READY:**
   - When all ambiguities are resolved (status="ready"), build a complete natural language query
   - The final_clarified_query should be self-contained, unambiguous, and ready for the router agent
   - Include all resolved terms in the final query (e.g., "Show me my employee status and offboarding reviewer information")
   - If original query had "my" or similar self-reference, preserve it in final_clarified_query
   - Make the final query natural and complete (e.g., "Show me my employee status" not just "employee status")

═══════════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST (DO THIS BEFORE ASKING ANY QUESTION):
═══════════════════════════════════════════════════════════════════════════════

Before asking, verify:
- Subject clear? → If no explicit subject, assume self (DO NOT ask about subject)
- Term qualified? → If qualified (e.g., "total leaves"), it's resolved (DO NOT ask)
- Already answered? → Check chat history, if answered → use that answer
- All ambiguities identified? → List ALL, not just one

═══════════════════════════════════════════════════════════════════════════════
NEVER ASK ABOUT:
═══════════════════════════════════════════════════════════════════════════════

- Subject/employee (unless explicitly mentioned like "John's")
- Qualified terms (e.g., "total leaves", "performance status", "offboarding reviewer")
- Things already answered in chat history
- Things not in semantic_context
- Conversational/HR/policy questions unrelated to MongoDB query

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

═══════════════════════════════════════════════════════════════════════════════
COMMON MISTAKES TO AVOID:
═══════════════════════════════════════════════════════════════════════════════

WRONG: "total leaves" → Ask "for yourself or someone else?"
CORRECT: "total leaves" → NO question (qualified term, assume self)

WRONG: "offboarding reviewer" → Ask "for whom?"
CORRECT: "offboarding reviewer" → NO question (qualified term, assume self)

WRONG: "my leaves" → Ask only "Do you want pending or total?" (missing time period)
CORRECT: "my leaves" → Ask "Do you want pending leaves or total leaves?" (time is optional for leaves)

OUTPUT FORMAT:

If clarification is needed (MUST return ALL questions at once):
{{
  "status": "needs_clarification",
  "questions": ["<question 1>", "<question 2>", "<question 3>", ...],
  "intent": "self" or "others",
  "clarification_progress": {{
    "original_query": "<original user query from first interaction>",
    "clarified_terms": ["<term1> → <resolved_value1>", "<term2> → <resolved_value2>"],  # Terms that have been clarified
    "pending_terms": ["<term1>", "<term2>"]  # List of ambiguous terms still needing clarification
  }}
}}
**CRITICAL**: 
- The "questions" array MUST contain ALL necessary questions. If there are 2 ambiguities, return 2 questions. If there are 5, return 5. NEVER return just one question when multiple are needed.
- If this is a continuation (user answering previous questions), update clarification_progress:
  * Mark answered terms in clarified_terms (e.g., "status → employee status")
  * Remove answered terms from pending_terms
  * Keep original_query from the first interaction
- If this is the first clarification, set original_query to current user_query and list all ambiguous terms in pending_terms

If everything is clear (no clarification needed):
{{
  "status": "ready",
  "intent": "self" or "others",
  "final_clarified_query": "<natural language query with all ambiguities resolved, ready for router>",
  "clarification_progress": {{
    "original_query": "<original user query>",
    "clarified_terms": ["<all resolved terms>"],
    "pending_terms": []  # Empty when ready
  }}
}}
**IMPORTANT**: 
- When status is "ready", you MUST provide a "final_clarified_query" that is a complete, unambiguous natural language query.
- This query should be self-contained and ready to be passed to the router agent.
- Preserve the original intent (e.g., if original had "my", include it: "Show me my employee status" not just "employee status").
- Make it natural and complete: "Show me my employee status and offboarding reviewer information" not just "employee status offboarding reviewer".
- Example: If original was "my status" and user answered "employee status", the final_clarified_query should be "Show me my employee status information" or "my employee status".

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
    """
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are a MongoDB Query Clarification Agent. "
                    "CRITICAL RULES: "
                    "1. NEVER ask 'for whom?' or 'for yourself or someone else?' - always assume self if no explicit subject. "
                    "2. Qualified terms (e.g., 'total leaves', 'offboarding reviewer') are NOT ambiguous - do NOT ask about them. "
                    "3. Ask ALL necessary questions at once in the questions array. "
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
        
        # Ensure clarification_progress is present
        if "clarification_progress" not in result:
            result["clarification_progress"] = {
                "original_query": user_query,
                "clarified_terms": [],
                "pending_terms": []
            }
        
        # If needs_clarification, ensure pending_terms are set
        if result.get("status") == "needs_clarification":
            # If pending_terms is empty but we have questions, infer from questions
            if not result["clarification_progress"].get("pending_terms") and questions:
                # Try to infer pending terms from questions (simple heuristic)
                pending = []
                for q in questions:
                    if "status" in q.lower():
                        pending.append("status")
                    if "reviewer" in q.lower():
                        pending.append("reviewer")
                    if "leave" in q.lower():
                        pending.append("leaves")
                if pending:
                    result["clarification_progress"]["pending_terms"] = list(set(pending))
        
        # Ensure final_clarified_query is present if ready
        if result.get("status") == "ready":
            if "final_clarified_query" not in result or not result.get("final_clarified_query"):
                # Build final query from original + clarified terms
                original = result["clarification_progress"].get("original_query", user_query)
                clarified = result["clarification_progress"].get("clarified_terms", [])
                
                # If we have clarified terms, try to build a better query
                if clarified:
                    # Simple fallback: use original query (it should already be merged by input_node)
                    result["final_clarified_query"] = user_query
                else:
                    # No clarification happened, use user_query as-is
                    result["final_clarified_query"] = user_query
                print(f"WARNING: LLM didn't provide final_clarified_query, using: {result['final_clarified_query']}")
            
            # Ensure pending_terms is empty when ready
            result["clarification_progress"]["pending_terms"] = []
        
        return result
    except json.JSONDecodeError as e:
        print(f"ERROR: Error parsing JSON response: {e}")
        print(f"Response text: {response_text}")
        # Return a fallback response with default intent
        return {"status": "ready", "intent": "self"}


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