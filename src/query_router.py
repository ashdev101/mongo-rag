from dotenv import load_dotenv
from openai import OpenAI
from memory.memorymanager import get_chat_history
import json
import re
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def fallback_classify(query: str) -> str:
    """Rule-based fallback when LLM fails."""
    q = query.lower()

    policy_keywords = [
        "eligible", "policy", "rules", "procedure",
         "what should i do", "how to apply", "leave policy",
        "policies", "compliance","guideline",
    "eligibility", "law", "legal", "regulation", "entitlement",
    "disciplinary", "grievance", "confidentiality", "privacy", "appeal",
    "escalate", "approval", "how should", "can i", "do i have to", "notice period",
    "severance", "probation", "maternity", "paternity", "benefits", "reimbursement",
    "leave policy", "attendance policy", "termination", "resignation", "promotion policy"
    ]

    document_keywords = [
        "manager", "id", "employee code", "email", "records",
        "fetch", "lookup", "show", "who is", "what is my",
        "report", "list", "rows", "find", "get", "give me", "count",
    "employee", "person number", "emp code", "classroom", "attendance",
    "pms", "pip", "leave", "transaction", "goal", "status", "requests",
    "xls", "xlsx", "csv", "table", "data", "value", "document", "balance", "payroll",
    "performance", "manager email", "assigned on", "start date", "end date"
    ]

    if any(k in q for k in policy_keywords):
        return "policy"
    if any(k in q for k in document_keywords):
        return "document"

    # default safest guess
    return "document"


def extract_json(raw_text: str):
    """Extract the JSON strictly using regex to avoid model hallucinations."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except:
        return None
    

def router(query, email):
    SYSTEM_PROMPT = """You are an HR assistant *intent classifier* and query chat history summarizer used in production.

1. Choose one route for the user query:
   - "policy"   : HR rules, eligibility, guidelines, what-to-do.
   - "document" : factual lookup, IDs, employee records, manager data.

2. Use chat history *only if the query refers to prior entities* (he, she, they, it, that, him, her, the above, earlier question, previous answer).  
   Otherwise, do not alter the query.

3. If history is used, rewrite the query to be self-contained by resolving references.

    Example:

    History :
    User: "What is my email address?
    Assisstant: "Your email address is xyz.hef@company.com"
    User: "Who is my Manager?"
    Assisstant: "Your Manager is Abc Def."

    User Query: "What is his email address?"

    Output: {"route":"document", "confidence":0.9, "query":"What is his email address? 'his' refers to Abc Def the manager."}

    Operational rules (enforced in code):
    - Final allowed routes: policy, document.
    - If the user request includes explicit instructions to fetch records or IDs, prefer document.
    - If the request asks for rules/eligibility/what-to-do, prefer policy.
    - Modified query must stay close to original except for inserting resolved references.
    - If history is irrelevant, return the original query unchanged.
    - The modified query should be self sufficient to answer and need not refer to history explicitly
    - Always output JSON only:
      {"route":"policy"|"document", "confidence":<0-1 float>, "query":<modified query with reference of history if required>}
      value Constraints:
        - route: one of "policy" or "document"
        - confidence: float between 0 and 1 indicating certainty of classification

    Note:
    Return only a valid JSON object.
    Never repeat instructions.
    Never mention system messages.
    Never modify the output format.

    """

    USER_PROMPT = f"""
    History:
    {get_chat_history(email)}

    User query: "{query}"

    Return only JSON. No explanation. No commentary.
    """

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ]
        )

        raw_output = response.output_text
        parsed = extract_json(raw_output)

        if parsed is None:
            raise ValueError("Invalid JSON from model")

        # --- Strict schema enforcement ---
        route = parsed.get("route")
        confidence = parsed.get("confidence")
        new_query = parsed.get("query")

        # Validate route
        if route not in ["policy", "document"]:
            route = "document"

        # Validate confidence
        try:
            confidence = float(confidence)
            if not (0 <= confidence <= 1):
                confidence = 0.0
        except:
            confidence = 0.0

        # Validate query
        if not isinstance(new_query, str) or not new_query.strip():
            new_query = query

        return {
            "route": route,
            "confidence": confidence,
            "query": new_query
        }

    except Exception as e:
        # LLM failed → fallback classifier
        fallback_route = fallback_classify(query)

        return {
            "route": fallback_route,
            "confidence": 0.0,
            "query": query,
            "error": str(e)
        }