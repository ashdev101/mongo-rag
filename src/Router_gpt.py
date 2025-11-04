
##############################################################################################
                # V2 - With Functional Enforcement and (only 2 staged routing/)
##############################################################################################

# #!/usr/bin/env python3
# """
# Router_gpt.py

# Classifies a user query into one of two routes:
#   - POLICY   : Queries about company rules, procedures, HR, compliance, legal, or eligibility.
#   - DOCUMENT : Queries that require data lookup or analysis from company XLS/XLSX documents.

# This version enforces that the final route is strictly one of the two categories
# (functional enforcement). It keeps .env loading unchanged.
# """

# import os
# import re
# import json
# import time
# import openai
# from enum import Enum
# from typing import Tuple, Dict, Any, Optional
# from dotenv import load_dotenv

# # Load from your .env file (keeps exactly as before)
# load_dotenv("./.env")

# # ----------------------------- CONFIG ---------------------------------
# DEFAULT_MODEL = "gpt-3.5-turbo"
# MAX_RETRIES = 3
# BACKOFF_BASE = 1.5
# TIMEOUT = 20
# # ----------------------------------------------------------------------

# class RouteType(str, Enum):
#     POLICY = "policy"
#     DOCUMENT = "document"

# # ------------------------ FALLBACK KEYWORDS ----------------------------
# POLICY_KEYWORDS = [
#     "policy", "policies", "compliance", "procedure", "guideline",
#     "eligibility", "law", "legal", "regulation", "entitlement",
#     "disciplinary", "grievance", "confidentiality", "privacy", "appeal",
#     "escalate", "approval", "how should", "can i", "do i have to", "notice period",
#     "severance", "probation", "maternity", "paternity", "benefits", "reimbursement",
#     "leave policy", "attendance policy", "termination", "resignation", "promotion policy"
# ]

# DOCUMENT_KEYWORDS = [
#     "report", "show", "list", "rows", "find", "get", "give me", "count",
#     "employee", "person number", "emp code", "classroom", "attendance",
#     "pms", "pip", "leave", "transaction", "goal", "status", "requests",
#     "xls", "xlsx", "csv", "table", "data", "value", "document", "balance", "payroll",
#     "performance", "manager email", "person number", "assigned on", "start date", "end date"
# ]
# # ----------------------------------------------------------------------

# # ------------------------- DETAILED SYSTEM PROMPT -------------------------------
# SYSTEM_PROMPT = """You are an HR assistant *intent classifier* used in production.
# Goal: decide whether a user's natural-language query should be routed to exactly one of:
#  - "policy"   : Questions that require HR policy interpretation, rules, eligibility, legal/compliance reasoning, or prescriptive guidance.
#  - "document" : Questions that require looking up, fetching, or returning factual data from internal structured sources (Excel sheets, reports, DBs). This includes checking internal tables for contact info, team lists, leave balances, PIP transactions, etc.

# Important operational constraints:
# - The system using you will accept ONLY "policy" or "document" as a final route.
# - If the user asks anything that requires consulting internal documents (employee lists, team contacts, person numbers, leave transactions, etc.), classify as "document".
# - If the user asks about rules, eligibility, how-to procedures, interpretations, or requests normative guidance (what should I do, am I eligible, how many days required, resignation process), classify as "policy".
# - If the user's question touches both (e.g., "Show my leave balance and what's the encashment policy?"), treat as POLICY (conservative).
# - Always respond with valid JSON only (no extra text), using exactly:
#   {"route":"policy"|"document", "confidence":<0-1 float>, "reason":"short justification"}

# Examples:
# - "What is the leave policy for probation employees?" -> policy
# - "Am I eligible for maternity leave?" -> policy
# - "How many notice days are required for resignation?" -> policy
# - "Show me my leave balance" -> document
# - "Get PIP transaction details for employee 1045" -> document
# - "Who is the manager for person number 293?" -> document
# - "How do I apply for reimbursement?" -> policy
# - "My laptop is broken - who do I contact to fix it?" -> document (because contact / IT support should be looked up in internal contact lists)
# - "Can I appeal a PIP decision and show me my PIP entries?" -> policy (conservative when combined)
# - "Hi / Hello / Thank you" -> policy (non-data conversational queries should be handled by policy/advice flow in our system)

# Be deterministic (temperature=0.0) and concise. Provide confidence as a float 0.0-1.0.
# """
# # ----------------------------------------------------------------------

# USER_PROMPT_TEMPLATE = """User query:
# "{query}"

# Classify according to the SYSTEM instructions above. Return only JSON.
# """

# # ------------------------ UTILITIES -----------------------------------

# def _parse_json_safe(text: str) -> Optional[Dict[str, Any]]:
#     """Try to parse JSON, with a tolerant extraction of the first {...} block."""
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         m = re.search(r"(\{.*\})", text, re.DOTALL)
#         if m:
#             try:
#                 return json.loads(m.group(1))
#             except Exception:
#                 return None
#     return None

# def keyword_scores(query: str) -> Tuple[int, int]:
#     q = query.lower()
#     pol_score = sum(1 for kw in POLICY_KEYWORDS if kw in q)
#     doc_score = sum(1 for kw in DOCUMENT_KEYWORDS if kw in q)
#     return pol_score, doc_score

# def keyword_fallback_decision(query: str) -> Tuple[RouteType, float, str]:
#     """Stronger fallback that incorporates multi-intent detection and conservative bias."""
#     pol_score, doc_score = keyword_scores(query)
#     if pol_score == 0 and doc_score == 0:
#         # No strong signals — default conservatively to policy
#         return RouteType.POLICY, 0.55, "Fallback: neutral query; defaulting to policy."
#     # If both present -> complex/multi-intent -> conservative policy
#     if pol_score > 0 and doc_score > 0:
#         return RouteType.POLICY, 0.75, "Fallback: detected both policy & document cues; choosing policy for safety."
#     if pol_score > doc_score:
#         return RouteType.POLICY, 0.7 + 0.02 * (pol_score - doc_score), "Fallback: keyword-based policy detection."
#     else:
#         return RouteType.DOCUMENT, 0.7 + 0.02 * (doc_score - pol_score), "Fallback: keyword-based document detection."

# # ------------------------ ENFORCEMENT helpers --------------------------

# def enforce_binary_decision_with_model(client: Any, query: str, model: str) -> Optional[Tuple[RouteType, float, str]]:
#     """
#     Secondary LLM call that is forced to return ONLY 'policy' or 'document'.
#     This is used when the primary classification returns an out-of-band category.
#     Returns None on failure.
#     """
#     system = (
#         "You MUST RETURN ONLY the single word 'policy' or 'document' (lowercase), "
#         "and nothing else. The caller will enforce the final mapping. "
#         "Interpret 'document' as 'requires checking internal structured data (reports/excel/dbs)'. "
#         "Interpret 'policy' as 'requires rules/eligibility/process interpretation'."
#     )
#     user = f"Decide for query: \"{query}\". Reply only with policy or document."
#     try:
#         resp = client.chat.completions.create(
#             model=model,
#             messages=[{"role":"system","content":system},{"role":"user","content":user}],
#             temperature=0.0,
#             max_tokens=10,
#             timeout=TIMEOUT,
#         )
#         content = resp.choices[0].message.content.strip().lower()
#         if content in ("policy","document"):
#             # assign high confidence (model asked to commit)
#             return (RouteType.POLICY, 0.95, "Enforced via binary LLM step.") if content == "policy" else (RouteType.DOCUMENT, 0.95, "Enforced via binary LLM step.")
#     except Exception:
#         return None
#     return None

# # ------------------------ classify_query (core) ------------------------

# def classify_query(
#     query: str,
#     model: str = DEFAULT_MODEL,
#     api_key: Optional[str] = None,
# ) -> Tuple[RouteType, float, str]:
#     """
#     Classify query intent into RouteType.POLICY or RouteType.DOCUMENT.
#     This function enforces final route to only be one of the two categories.
#     """
#     # basic validation
#     if not query or not query.strip():
#         return RouteType.POLICY, 0.0, "Empty query; defaulting to policy."

#     # fetch api key
#     if not api_key:
#         api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         # no API key -> strong keyword fallback
#         return keyword_fallback_decision(query)

#     # initialize new OpenAI client (keeps compatible with openai>=1.0.0)
#     from openai import OpenAI
#     client = OpenAI(api_key=api_key)

#     system_msg = SYSTEM_PROMPT
#     user_msg = USER_PROMPT_TEMPLATE.format(query=query)

#     primary_model_data = None
#     for attempt in range(1, MAX_RETRIES + 1):
#         try:
#             resp = client.chat.completions.create(
#                 model=model,
#                 messages=[{"role":"system","content":system_msg},{"role":"user","content":user_msg}],
#                 temperature=0.0,
#                 max_tokens=200,
#                 timeout=TIMEOUT,
#             )
#             content = resp.choices[0].message.content.strip()
#             parsed = _parse_json_safe(content)
#             if not parsed:
#                 # treat as non-fatal: try again (or fallback later)
#                 raise ValueError("Model did not return valid JSON.")
#             route_raw = str(parsed.get("route","")).lower()
#             confidence = float(parsed.get("confidence", 0.6))
#             reason = str(parsed.get("reason","")).strip()
#             primary_model_data = (route_raw, confidence, reason, content)
#             # If model already returned exactly one of the two -> accept
#             if route_raw in ("policy","document"):
#                 return (RouteType.POLICY, round(max(0.0, min(1.0, confidence)),3), reason) if route_raw=="policy" else (RouteType.DOCUMENT, round(max(0.0, min(1.0, confidence)),3), reason)
#             # else run enforcement chain below
#             break
#         except Exception as e:
#             # retry with backoff
#             if attempt < MAX_RETRIES:
#                 time.sleep(BACKOFF_BASE * (2 ** (attempt-1)))
#                 continue
#             # failed primary attempts -> fallback to keyword-based decision
#             return keyword_fallback_decision(query)

#     # At this point, either model returned something out-of-band (e.g., "general") or parsing ambiguous.
#     # Step 1: quick keyword multi-intent detection
#     pol_score, doc_score = keyword_scores(query)
#     if pol_score > 0 and doc_score > 0:
#         # multi-intent -> conservative policy
#         return RouteType.POLICY, 0.85, "Detected both document & policy cues; choosing policy for safety."

#     # Step 2: attempt enforced binary decision with a second LLM call
#     try:
#         enforced = enforce_binary_decision_with_model(client, query, model)
#         if enforced is not None:
#             return enforced
#     except Exception:
#         pass

#     # Step 3: deterministic keyword fallback mapping
#     return keyword_fallback_decision(query)

# # --------------------------- CLI ENTRYPOINT ----------------------------
# if __name__ == "__main__":
#     print("\nQuery Router — Determine if query is POLICY or DOCUMENT (enforced).")
#     user_q = input("Enter your query (or press ENTER to use a sample): ").strip()
#     if not user_q:
#         user_q = "What is the procedure for leave encashment?"

#     key = None  # use env by default
#     route, confidence, reason = classify_query(user_q, api_key=key)
#     print("\n--- Classification Result ---")
#     print(f"Query      : {user_q}")
#     print(f"Route      : {route.value.upper()}")
#     print(f"Confidence : {confidence}")
#     print(f"Reason     : {reason}")

#     if route == RouteType.POLICY:
#         print("\n→ Run: policy_handler(query)")
#     else:
#         print("\n→ Run: document_retrieval_handler(query)")



##############################################################################################
                # V3 - With 3 Functional Direct Enforcement Routes
##############################################################################################

#!/usr/bin/env python3
"""
Router_gpt.py

Updated router with support for three outcome routes:
 - policy
 - document
 - both   (both document + policy) — in which case router returns two sub-queries:
           (doc_query, policy_query)

Everything else from your core pipeline is preserved; .env loading is unchanged.
"""

import os
import re
import json
import time
from enum import Enum
from typing import Tuple, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv("./.env")

# Use new OpenAI client API
from openai import OpenAI

# ----------------------------- CONFIG ---------------------------------
DEFAULT_MODEL = "gpt-3.5-turbo"
MAX_RETRIES = 3
BACKOFF_BASE = 1.5
TIMEOUT = 20
# ----------------------------------------------------------------------

class RouteType(str, Enum):
    POLICY = "policy"
    DOCUMENT = "document"
    BOTH = "both"

# ------------------------ FALLBACK KEYWORDS ----------------------------
POLICY_KEYWORDS = [
    "policy", "policies", "compliance", "procedure", "guideline",
    "eligibility", "law", "legal", "regulation", "entitlement",
    "disciplinary", "grievance", "confidentiality", "privacy", "appeal",
    "escalate", "approval", "how should", "can i", "do i have to", "notice period",
    "severance", "probation", "maternity", "paternity", "benefits", "reimbursement",
    "leave policy", "attendance policy", "termination", "resignation", "promotion policy"
]

DOCUMENT_KEYWORDS = [
    "report", "show", "list", "rows", "find", "get", "give me", "count",
    "employee", "person number", "emp code", "classroom", "attendance",
    "pms", "pip", "leave", "transaction", "goal", "status", "requests",
    "xls", "xlsx", "csv", "table", "data", "value", "document", "balance", "payroll",
    "performance", "manager email", "assigned on", "start date", "end date"
]
# ----------------------------------------------------------------------

# ------------------------- PRIMARY PROMPT ------------------------------
SYSTEM_PROMPT = """You are an HR assistant *intent classifier* used in production.
Goal: decide whether a user's natural-language query should be routed to exactly one of:
 - "policy"   : requires HR policy interpretation, rules, eligibility or prescriptive guidance.
 - "document" : requires fetching/returning factual data from internal structured sources (Excel reports/db).
 - "both"     : the query legitimately requires both a document lookup AND policy reasoning; in that case the system needs two separate sub-queries (one for docs, one for policy).

Operational rules (enforced in code):
- Final allowed routes: policy, document, both.
- If the user request includes explicit instructions to fetch records or IDs, prefer document.
- If the request asks for rules/eligibility/what-to-do, prefer policy.
- If the request requires both factual lookup and rule interpretation (e.g., "Show my leave balance and tell me if I can encash unused leaves"), mark BOTH.
- Always output JSON only:
  {"route":"policy"|"document"|"both", "confidence":<0-1 float>, "reason":"short justification"}

Examples:
- "What is the leave policy for probation employees?" -> policy
- "Show me my leave balance" -> document
- "Show my leave balance and tell me if unused leaves can be encashed" -> both
- "Who is the manager for person number 293?" -> document
- "How do I apply for reimbursement?" -> policy

Be deterministic (temperature=0.0), concise and return JSON only.
"""
USER_PROMPT_TEMPLATE = """User query:
"{query}"

Classify according to the SYSTEM instructions above. Return only JSON.
"""
# ----------------------------------------------------------------------

# ------------------------ Utilities & Fallbacks -------------------------

def _parse_json_safe(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None

def keyword_scores(query: str) -> Tuple[int, int]:
    q = query.lower()
    pol_score = sum(1 for kw in POLICY_KEYWORDS if kw in q)
    doc_score = sum(1 for kw in DOCUMENT_KEYWORDS if kw in q)
    return pol_score, doc_score

def keyword_fallback_decision(query: str) -> Tuple[RouteType, float, str, Optional[str], Optional[str]]:
    """
    Deterministic fallback to return (route, confidence, reason, doc_query, policy_query)
    doc_query/policy_query only set in BOTH route; else None.
    Conservative: multi-intent -> BOTH (since user asked to split now).
    """
    pol_score, doc_score = keyword_scores(query)
    # thresholds
    if pol_score == 0 and doc_score == 0:
        # nothing clear -> default policy (conservative)
        return RouteType.POLICY, 0.55, "Fallback: no strong keywords; defaulting to policy.", None, None

    if pol_score > 0 and doc_score > 0:
        # clearly both
        doc_q, pol_q = fallback_split_queries_by_keywords(query)
        return RouteType.BOTH, 0.8, "Fallback: both policy & document cues present.", doc_q, pol_q

    if pol_score > doc_score:
        return RouteType.POLICY, 0.75, "Fallback: keyword-based policy detection.", None, None
    else:
        return RouteType.DOCUMENT, 0.75, "Fallback: keyword-based document detection.", None, None

def fallback_split_queries_by_keywords(query: str) -> Tuple[str, str]:
    """
    Basic heuristic to split the original query into a doc_query and policy_query.
    This is a fallback if LLM split generation fails.
    """
    q = query.strip()
    # try extract phrase likely referring to document lookups
    doc_phrases = []
    policy_phrases = []
    # split by conjunctions common in nested queries
    parts = re.split(r"\band\b|\bthen\b|\b, and\b|\b;|\bor\b", q, flags=re.IGNORECASE)
    for p in parts:
        pl = p.strip()
        # if contains document keywords -> doc
        if any(kw in pl.lower() for kw in DOCUMENT_KEYWORDS):
            doc_phrases.append(pl)
        elif any(kw in pl.lower() for kw in POLICY_KEYWORDS):
            policy_phrases.append(pl)
        else:
            # ambiguous -> attach to both (so both handlers see it)
            doc_phrases.append(pl)
            policy_phrases.append(pl)
    doc_q = " ; ".join(doc_phrases) if doc_phrases else q
    pol_q = " ; ".join(policy_phrases) if policy_phrases else q
    return doc_q, pol_q

# ------------------------ Secondary LLM helpers -------------------------

def enforce_binary_decision_with_model(client: OpenAI, query: str, model: str) -> Optional[Tuple[RouteType, float, str]]:
    """
    Secondary, strict decision for policy/document only.
    Returns (RouteType, confidence, reason) or None.
    """
    system = ("RETURN ONLY the single word 'policy' or 'document' (lowercase). "
              "Interpret 'document' as requiring internal structured-data lookup. "
              "Interpret 'policy' as requiring normative HR policy interpretation.")
    user = f"Decide for query: \"{query}\". Reply only with policy or document."
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.0,
            max_tokens=6,
            timeout=TIMEOUT,
        )
        content = resp.choices[0].message.content.strip().lower()
        if content == "policy":
            return (RouteType.POLICY, 0.95, "Enforced binary LLM: policy")
        if content == "document":
            return (RouteType.DOCUMENT, 0.95, "Enforced binary LLM: document")
    except Exception:
        return None
    return None

def generate_split_queries_with_model(client: OpenAI, query: str, model: str) -> Optional[Tuple[str, str]]:
    """
    Ask the model to produce two short sub-queries as JSON:
      {"doc_query":"...", "policy_query":"..."}
    Both strings should be concise and focused for their respective handlers.
    Returns None on failure.
    """
    system = ("You will rewrite the user's single nested query into exactly two concise sub-queries in JSON. "
              "Return ONLY valid JSON with keys 'doc_query' and 'policy_query'. "
              "doc_query should be a short instruction for the document retrieval script (e.g., 'Show leave transactions for employee 4598'). "
              "policy_query should be a short instruction for the policy reasoning script (e.g., 'Explain leave encashment policy for probation employees').")
    user = f"Original query: \"{query}\". Produce JSON {{\"doc_query\":\"...\",\"policy_query\":\"...\"}}."
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.0,
            max_tokens=200,
            timeout=TIMEOUT,
        )
        content = resp.choices[0].message.content.strip()
        parsed = _parse_json_safe(content)
        if parsed and "doc_query" in parsed and "policy_query" in parsed:
            dq = parsed["doc_query"].strip()
            pq = parsed["policy_query"].strip()
            return dq, pq
    except Exception:
        return None
    return None

# ------------------------ CLASSIFICATION CORE ---------------------------

def classify_query(
    query: str,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> Tuple[RouteType, float, str, Optional[str], Optional[str]]:
    """
    Classify query into one of (policy, document, both).
    Return tuple: (route, confidence, reason, doc_query, policy_query)
    doc_query and policy_query are only set when route == BOTH, else None.
    """
    if not query or not query.strip():
        return RouteType.POLICY, 0.0, "Empty query; defaulting to policy.", None, None

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # no API key -> fallback returns also possible BOTH with split queries
        route, conf, reason, doc_q, pol_q = keyword_fallback_decision(query)
        return route, conf, reason, doc_q, pol_q

    client = OpenAI(api_key=api_key)

    # primary LLM classification
    system_msg = SYSTEM_PROMPT
    user_msg = USER_PROMPT_TEMPLATE.format(query=query)

    primary_parsed = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system_msg},{"role":"user","content":user_msg}],
                temperature=0.0,
                max_tokens=200,
                timeout=TIMEOUT,
            )
            content = resp.choices[0].message.content.strip()
            parsed = _parse_json_safe(content)
            if not parsed:
                raise ValueError("Model did not return valid JSON.")
            route_raw = str(parsed.get("route","")).lower()
            confidence = float(parsed.get("confidence", 0.6))
            reason = str(parsed.get("reason","")).strip()
            primary_parsed = (route_raw, confidence, reason, content)
            # If model returned one of the allowed outputs directly -> accept
            if route_raw in ("policy","document","both"):
                if route_raw == "both":
                    # need to generate split queries
                    # attempt LLM-based split
                    split = generate_split_queries_with_model(client, query, model)
                    if split:
                        doc_q, pol_q = split
                        return RouteType.BOTH, round(max(0.0, min(1.0, confidence)),3), reason or "Model indicated both intents", doc_q, pol_q
                    # fallback: keyword-based split
                    doc_q, pol_q = fallback_split_queries_by_keywords(query)
                    return RouteType.BOTH, round(max(0.0, min(1.0, confidence)),3), reason or "Model indicated both intents (fallback split used)", doc_q, pol_q
                else:
                    # policy or document accepted
                    return (RouteType.POLICY, round(max(0.0, min(1.0, confidence)),3), reason, None, None) if route_raw=="policy" else (RouteType.DOCUMENT, round(max(0.0, min(1.0, confidence)),3), reason, None, None)
            # else break to enforcement chain
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue
            # primary classification failed completely -> fallback
            route, conf, reason, doc_q, pol_q = keyword_fallback_decision(query)
            return route, conf, reason, doc_q, pol_q

    # enforcement chain: handle ambiguous or out-of-band primary responses
    pol_score, doc_score = keyword_scores(query)
    # strict multi-intent detection thresholds:
    if pol_score >= 1 and doc_score >= 1:
        # explicitly mark BOTH
        # try model generation of sub-queries first
        split = None
        try:
            split = generate_split_queries_with_model(client, query, model)
        except Exception:
            split = None
        if split:
            doc_q, pol_q = split
        else:
            doc_q, pol_q = fallback_split_queries_by_keywords(query)
        return RouteType.BOTH, 0.9, "Detected both policy & document cues; routing to BOTH.", doc_q, pol_q

    # If one side strongly outweighs the other, try a strict binary LLM enforcement
    try:
        enforced = enforce_binary_decision_with_model(client, query, model)
        if enforced is not None:
            rtype, conf, reason = enforced
            return rtype, conf, reason, None, None
    except Exception:
        pass

    # final deterministic fallback
    route, conf, reason, doc_q, pol_q = keyword_fallback_decision(query)
    return route, conf, reason, doc_q, pol_q

# --------------------------- CLI ENTRYPOINT ----------------------------
if __name__ == "__main__":
    print("\nQuery Router — Determine if query is POLICY, DOCUMENT or BOTH (with split queries).")
    user_q = input("Enter your query (or press ENTER to use a sample): ").strip()
    if not user_q:
        user_q = "Show my leave balance and tell me if unused leaves can be encashed at year-end."

    key = None  # use .env API key by default
    route, confidence, reason, doc_q, pol_q = classify_query(user_q, api_key=key)

    print("\n--- Classification Result ---")
    print(f"Query      : {user_q}")
    print(f"Route      : {route.value.upper()}")
    print(f"Confidence : {confidence}")
    print(f"Reason     : {reason}")
    if route == RouteType.BOTH:
        print("\n--- Generated sub-queries ---")
        print(f"Document query : {doc_q}")
        print(f"Policy query   : {pol_q}")
        # print("\n→ Action: run document handler on the Document query and policy handler on the Policy query; merge outputs in pipeline.")
    elif route == RouteType.POLICY:
        print("\n→ Run: policy_handler(query)")
    else:
        print("\n→ Run: document_retrieval_handler(query)")
