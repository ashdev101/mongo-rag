from dotenv import load_dotenv
from openai import OpenAI
from memory.memorymanager import get_chat_history
import json
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def router(query, email):
    SYSTEM_PROMPT = """You are an HR assistant *intent classifier* and query chat history summarizer used in production.
    Goal 1: decide whether a user's natural-language query should be routed to exactly one of:
    - "policy"   : requires HR policy interpretation, rules, eligibility or prescriptive guidance.
    - "document" : requires fetching/returning factual data from internal structured sources (Excel reports/db).

    Goal 2: Read the user chat history (if any) and if it is referred to in the query, summarize relevant parts to help downstream agents.

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
    - Keep the mofified query as close to the original as possible, only appending context from history only if needed.
    - Do not modify query if history is blank or the query does not refer to history
    - Always output JSON only:
      {"route":"policy"|"document", "confidence":<0-1 float>, "query":<modified query with reference of history if required>}
    """

    USER_PROMPT = f"""
    History:
    {get_chat_history(email)}

    User query: "{query}"

    Return only JSON. No explanation. No commentary.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",      
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ],
            temperature=0
        )

        raw_output = response.choices[0].message.content.strip()

        # Force JSON-only strictness
        try:
            parsed = json.loads(raw_output)
        except Exception:
            return {
                "route": "document",
                "confidence": 0.0,
                "query": query,
                "error": "Invalid JSON returned by model",
                "raw": raw_output
            }

        # Hard validation of keys
        if "route" not in parsed or "confidence" not in parsed or "query" not in parsed:
            parsed["error"] = "Missing required fields in model output"
            return parsed

        # Enforce allowed route values
        allowed_routes = ["policy", "document"]
        if parsed["route"] not in allowed_routes:
            parsed["route"] = "document"
            parsed["error"] = "Model returned invalid route, defaulted to document"

        return parsed

    except Exception as e:
        # Hard fail-safe
        return {
            "route": "document",
            "confidence": 0.0,
            "query": query,
            "error": str(e)
        }
