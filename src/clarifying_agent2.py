import json
from langchain_openai import ChatOpenAI
import os
from SemanticDictionaryProcessor import  SemanticDictionaryProcessor
from CollectionRouter import CollectionRouterAgent
# -------------------------------
# 1. CONFIG
# -------------------------------
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))
from schema_generator import extract_db_schema

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
llm = ChatOpenAI(model="gpt-4o")  # or "gpt-4o-mini" etc.


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

def clarify_query(user_query: str , semantic_context: dict , ambiguous_terms: dict):
    """
    user_query: the question from the user
    semantic_context: the semantic JSON document produced by build_summary_document()
    """

    prompt = f"""
You are a MongoDB Query Clarification Agent. 
Your ONLY job is to interpret the user’s request and ask ONE short clarifying question ONLY when the database query cannot be constructed without it.
**Important**: If the user request already contains entity, subtype, metric, and time_range, and the default subject rule applies (self), you must NOT ask any question. Treat the query as fully clear.


CRITICAL RULES (MUST FOLLOW):

1. Strictly make NO assumptions about the database.
   - You may ONLY use entities, fields, metrics, attributes, and meanings that appear in semantic_context or ambiguous_terms.
   - If something does NOT appear in semantic_context → it does NOT exist.
   - Never invent fields, filters, collections, metrics, or attributes.

2. Strictly make NO assumptions about the user’s intent.
   - Use ONLY what the user explicitly states.
   - Never guess, infer, or assume additional intent.

3. Ask a question ONLY when:
   - The user uses an ambiguous term (from ambiguous_terms) which maps to multiple known database meanings, OR
   - A REQUIRED query component is missing (entity, metric, subtype, time_range, or filter scope) AND that component exists in semantic_context.

4. NEVER ask about anything unrelated to generating a MongoDB query.
   - No conversational questions.
   - No HR/policy questions.
   - No business questions unless they directly map to known database fields.

5. NEVER ask for anything the database CANNOT store.
   - Only ask about fields and meanings that exist in semantic_context.
   - If a concept is not included there (e.g., “appraisal_cycle”), do NOT reference it or ask about it.

6. NEVER ask for anything the user already provided.
   - Do not repeat or reconfirm details they already stated.

7. ONE QUESTION ONLY.
   - The question must be short, human, and easy to answer.
   - No technical terminology (no “schema”, “fields”, “collections”, “documents”).

8. The question MUST be directly relevant to producing the correct MongoDB query.
   - If a question does not change the structure of the query → do NOT ask it.

9. Default subject:
   - If the user does not specify “who,” assume the user is asking about THEMSELVES.

10. Time interpretation:
   - “This year” must always mean the current calendar year (2025-01-01 to 2025-12-31) unless the user specifies otherwise.

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


Ask a clarifying question ONLY when:
- The user uses an ambiguous term AND the possible meanings map to different database fields or collections.
- The request is incomplete in a way that prevents generating the MongoDB query.
- A required database dimension is missing (metric, subtype, time_range, or scope).

If the user request already maps cleanly to one entity, one metric, and optional time_range → DO NOT ASK.

Your clarifying question must:
- Be ONE sentence.
- Be simple and easy to answer.
- Refer ONLY to details needed for the database query.
- Never include technical words like “field”, “schema”, “collection”, or “document”.

If ambiguous_terms defines a question → use that as your ONLY question, but rephrase it to be short and human.

Examples:
1. User: “my leaves”
   → Ask: “Do you want pending leaves or total leaves?” 
   (because these map to different database fields)

2. User: “my manager”
   → Ask: “Do you want your manager’s name or email?”
   (database has multiple manager attributes)

3. User: “attendance”
   → Ask: “Do you want your attendance count or a day-wise breakdown?”
   (different database metrics)

4. User: “leaves this month”
   → No question (entity + time are clear)

5. User: “manager’s email”
   → No question (specific database attribute)

6. User: “team attendance last week”
   → No question (intent, scope, time all clear)

OUTPUT FORMAT:

If clarification is needed:
{{
  "status": "needs_clarification",
  "questions": ["<one short database-relevant question>"],
  "missing": ["metric", "time_range", ...]
}}

If everything is clear:
{{
  "status": "ready",
  "structured_query": {{
    "entity": "...",
    "metric": "...",
    "filters": {...},
    "time_range": "...",
    "collection": "..."
  }}
}}

User Query: "{user_query}"
    """
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are a MongoDB Query Clarification Agent."
                    "Your response MUST be only valid JSON. "
                    "No markdown, no comments, no backticks."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response.content.strip())


# -------------------------------
# 3. RUN THE CLARIFICATION AGENT
# -------------------------------

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