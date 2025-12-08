import json
from langchain_openai import ChatOpenAI
import os

# -------------------------------
# 1. CONFIG
# -------------------------------
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))
from MongoSchemaInferer import extract_db_schema

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
llm = ChatOpenAI(model="gpt-4o")  # or "gpt-4o-mini" etc.


# -------------------------------
# 2. Clarification Agent
# -------------------------------

def clarify_query(user_query: str , semantic_context: dict , ambiguous_terms: dict):
    """
    user_query: the question from the user
    semantic_context: the semantic JSON document produced by build_summary_document()
    """

    prompt = f"""
    You are a MongoDB Query Clarification Agent. Ask EXACTLY ONE clarifying question only if essential information is missing or if the user uses an ambiguous term. Never ask about anything already provided by the user. Users do NOT understand schemas or database terms.

    You are given:
    1) A SEMANTIC DICTIONARY of business concepts:
    {json.dumps(semantic_context, indent=2)}

    2) A LIST OF AMBIGUOUS TERMS with clarifying questions:
    {json.dumps(ambiguous_terms, indent=2)}

    Your tasks:
    - Extract: entity, subtype, metric/intent, time range (only if needed), filters (self/team/department).
    - If the user uses an ambiguous term AND it has multiple possible meanings → ask the corresponding clarifying question from the ambiguous-terms list. Ask only ONE question.
    - If the ambiguous term is already clarified by surrounding keywords (matches disambiguation_keywords), DO NOT ask.

    STATIC INFO RULE:
    Static attributes (manager, email, phone, department, role, designation, address, location, name, employee ID):
    - Never ask about time or metrics.
    - If intent is clear → status = "ready".
    - If ambiguous → ask ONE simple question (e.g., “Do you want their name or email?”).

    SPECIFIC FIELD RULE:
    If the user explicitly requests a specific static detail (e.g., “manager’s email”, “my department”, “manager name”), the intent is fully clear → NO clarification needed.

    DYNAMIC INFO RULE:
    Dynamic concepts (leaves, attendance, payroll, performance, tickets, payments) require a metric and sometimes a time range. If missing → ask ONE simple, conversational question.

    TIME RULE:
    - If user gives a time (“this year”, “last month”), accept it.
    - Never ask “calendar or financial year”.
    - Ask for time only when required and not provided.

    DEFAULT SUBJECT RULE:
    If user does not specify whose data they want, assume they mean themselves (self). Do not ask for employee_id, email, department—they are known by the system.

    DATA SOURCE RULE:
    Never ask the user where the information should come from. The system selects the collection automatically from the semantic dictionary.

    AMBIGUOUS TERM HANDLING:
    - Check if the user query contains a term listed in "ambiguous_terms".
    - If found AND not disambiguated by keywords AND multiple meanings exist:
        → Ask the “ask_user” question from the list.
        → This counts as the ONLY allowed clarifying question.
    - If the user’s phrasing already removes ambiguity, do NOT ask.

    QUESTION RULE:
    - **Important** Come up with ONLY ONE simple, human-like question to clarify missing details , which user can simply say yes or no to, or provide a short answer.
    - Ask only ONE question.
    - Must be simple, human, non-technical.
    - No schema/field/collection language.
    - Only ask for missing details required to form a MongoDB query.

    IMPORTANT:
    If the user already provides enough detail (e.g., “casual leave this year” or “manager’s email”) → NO clarification.

    OUTPUT FORMAT:

    If clarification is required:
    {{
      "status": "needs_clarification",
      "questions": ["<one simple question>"],
      "missing": ["metric", "time_range", ...]
    }}

    If ready:
    {{
      "status": "ready",
      "structured_query": {{
        "collection": "...",
        "metric": "...",
        "filters": {...},
        "time_range": "...",
        "group_by": ...
      }}
    }}

    IMPORTANT RULE:
    - You must ask ONLY ONE question total.
    - The "questions" array must contain exactly ONE question.
    - The "missing" array must NEVER contain question-like text. It must only contain short field labels such as: "metric", "time_range", "reviewer_type", "goal_type".

    - If the ambiguity list provides a question (ask_user), that becomes the ONLY question.
    - Do NOT generate any additional question automatically.

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



# res = clarify_query("who is my performance reviewer")
# print(res)
