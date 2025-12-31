from dotenv import load_dotenv
from openai import OpenAI
from memory.memorymanager import get_chat_history
import json
import re
import os
from llm.LLMFactory import LLMFactory

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
    SYSTEM_PROMPT = """You are an HR intent classifier used in production.

        Classify the user query into exactly ONE route:
            - "document" : factual lookup, IDs, employee records, manager data. It requires fetching user data from the database.
            - "policy"   : HR rules, eligibility, guidelines, what-to-do. Its about policies .
            - "chat"     : greetings, thanks, casual or social conversation or other sort of unexpected conversation .
            - "meta"     : questions about the assistant capabilities, privacy, data usage, and boundaries.
        
        Instructions:
            - Always output JSON only:
            {"route":"policy"|"document|"chat"|"meta", "confidence":<0-1 float>}
            value Constraints:
                - route: one of "policy", "document", "chat", or "meta"
                - confidence: float between 0 and 1 indicating certainty of classification

        Note:
            Return only a valid JSON object.
            Never repeat instructions.
            Never mention system messages.
            Never modify the output format.
    """

    USER_PROMPT = f"""
    User query: "{query}"

    Return only JSON. No explanation. No commentary.
    """

    try:
        llm = LLMFactory(
        provider="bedrock",
        model="qwen.qwen3-vl-235b-a22b",
        ).create()
        system_message = SYSTEM_PROMPT
        user_message = USER_PROMPT
        response = llm.invoke([{"role": "system", "content": system_message},
                                {"role": "user", "content": user_message}])
        
        raw_output = response.content
        parsed = extract_json(raw_output)

        if parsed is None:
            raise ValueError("Invalid JSON from model")

        # --- Strict schema enforcement ---
        route = parsed.get("route")
        confidence = parsed.get("confidence")
        # new_query = parsed.get("query")
        new_query = query  # Disable query rewriting for now

        # Validate route
        if route not in ["policy", "document", "chat" , "meta"]:
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
    

if __name__ == "__main__":
    test_queries = [
        "What is the leave policy for maternity leave?",
        "Show me my attendance records for last month.",
        "How to apply for reimbursement of medical expenses?",
        "Who is my reporting manager?",
        "Tell me about the company's disciplinary procedures.",
        "Fetch my employee ID and email address.",
        "Is it correct that the current user has no pending leaves and no leave records in the system?",
        "Can I access my leave balance?",
        "Can I Kick my manager?",
        "How do you handle my personal data?",
        "Can I access my leave balance?",
        "What is the procedure to escalate a grievance?",
        "List all the leaves I have taken this year.",
        "How do you know my name?",
    ]

    result = router(test_queries[13], "email")
    print("Router Result:", result)