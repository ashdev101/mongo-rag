# full_rbac_with_llm_normalization.py
# --------------------------------------------------------
# Imports
# --------------------------------------------------------
import json
import re
import os
from typing import Optional, Dict, Any

from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

# --------------------------------------------------------
# State Definition
# --------------------------------------------------------
class State(BaseModel):
    user_question: Optional[str] = None
    cleaned_query: Optional[str] = None
    rbac_result: Optional[str] = None
    tool_request: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# --------------------------------------------------------
# Master lists (from user)
# --------------------------------------------------------
CANONICAL_GRADES = ['M0','M1','M2','M3','M4','M5','M6']

CANONICAL_DEPARTMENTS = [
  'B2B','Business Development','Commercial','Communications','Content',
  'Customer Operations','Executive Office','Facilities','Field Service Delivery',
  'Field Services','Finance','Human Resources','IT','Interactive Services','Legal',
  'Marketing','Sales','Sales & Service','Service','Strategy','Technical','Technology'
]

CANONICAL_REGIONS = ['Central','Corporate','East','North','South','West','PAN INDIA']

# --------------------------------------------------------
# Region Hierarchy (used for allowing suffix suppression)
# you can expand this mapping as needed
# --------------------------------------------------------
REGION_HIERARCHY = {
    "pan india": ["central", "corporate", "east", "north", "south", "west", "pan india", "india", "all india"],
    # optionally more mappings can be added
    "corporate": ["corporate"],
    "north": ["north"],
    "south": ["south"],
    "east": ["east"],
    "west": ["west"],
    "central": ["central"]
}

# --------------------------------------------------------
# Tool Schema
# --------------------------------------------------------
class RBACInput(BaseModel):
    question: str
    allowed_regions: list[str]
    allowed_grades: list[str]
    department_exceptions: list[str]


class RBACOutput(BaseModel):
    final_query: str


# --------------------------------------------------------
# RBAC Logic (applies sanitization + builds suffix)
# - expects `question` to be the rewritten neutral question (e.g., "list ...")
# - uses the normalized fields (if present) to decide whether to append suffixes
# --------------------------------------------------------
def normalize_str(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    return x.strip()

def normalize_key(s: str) -> str:
    return s.strip().lower()

def is_region_allowed(user_region: str, allowed_regions: list[str]) -> bool:
    if not user_region:
        return False
    ur = normalize_key(user_region)
    allowed_norm = [normalize_key(a) for a in allowed_regions]

    # direct equality
    if ur in allowed_norm:
        return True

    # check hierarchy: if any allowed region's hierarchy contains user region
    for allowed in allowed_norm:
        if allowed in REGION_HIERARCHY:
            if ur in REGION_HIERARCHY[allowed]:
                return True

    # also check if user region is a superset of allowed (user asked pan india while allowed corporate)
    for allowed in allowed_norm:
        if allowed in REGION_HIERARCHY and allowed == ur:
            return True

    return False

def is_grade_allowed(user_grade: Optional[str], allowed_grades: list[str]) -> bool:
    if not user_grade:
        return False
    return user_grade.upper() in [g.upper() for g in allowed_grades]

def is_dept_forbidden(user_department: Optional[str], department_exceptions: list[str]) -> bool:
    if not user_department:
        return False
    ud = normalize_key(user_department)
    exc = [normalize_key(e) for e in department_exceptions]
    return ud in exc

def apply_rbac_logic(question, allowed_regions, allowed_grades, department_exceptions,
                     normalized_region=None, normalized_grade=None, normalized_department=None):
    """
    question: rewritten neutral question from normalization step (string)
    normalized_*: canonical values (or None) from LLM normalization step
    """

    # Track whether user explicitly requested an allowed canonical value
    region_allowed_by_user = False
    grade_allowed_by_user = False
    dept_specified_and_forbidden = False

    # REGION logic
    if normalized_region:
        if is_region_allowed(normalized_region, allowed_regions):
            region_allowed_by_user = True
        else:
            # user requested a disallowed region -> sanitize by removing region mention from question
            # (the normalization step should have produced a canonical token; remove the raw token if present)
            question = re.sub(re.escape(normalized_region), "", question, flags=re.IGNORECASE).strip()

    # GRADE logic
    if normalized_grade:
        if is_grade_allowed(normalized_grade, allowed_grades):
            grade_allowed_by_user = True
        else:
            question = re.sub(re.escape(normalized_grade), "", question, flags=re.IGNORECASE).strip()

    # DEPARTMENT logic
    if normalized_department:
        if is_dept_forbidden(normalized_department, department_exceptions):
            # remove department mention and mark forbidden
            question = re.sub(re.escape(normalized_department), "", question, flags=re.IGNORECASE).strip()
            dept_specified_and_forbidden = True

    # Build suffixes:
    suffix_parts = []

    # Region suffix: only add if user did not specify an allowed region
    if not region_allowed_by_user:
        if allowed_regions:
            suffix_parts.append(f"in regions ({', '.join(allowed_regions)})")

    # Grade suffix: only add if user did not specify an allowed grade
    if not grade_allowed_by_user:
        if allowed_grades:
            suffix_parts.append(f"with grades ({', '.join(allowed_grades)})")

    # Department suffix rules:
    # - If user explicitly requested a forbidden department, we removed it above and it's already sanitized.
    # - We still append the global exclusions unless user explicitly requested a department that is allowed and not in exceptions.
    if department_exceptions:
        suffix_parts.append(f"excluding departments ({', '.join(department_exceptions)})")

    suffix = " ".join(suffix_parts).strip()
    final = f"{question.strip()} {suffix}".strip()
    # Cleanup double spaces
    final = re.sub(r"\s{2,}", " ", final)
    return final


# --------------------------------------------------------
# Tool Definition
# --------------------------------------------------------
@tool("apply_rbac", args_schema=RBACInput)
def apply_rbac(question, allowed_regions, allowed_grades, department_exceptions):
    """
    apply_rbac tool expects the normalized fields to be attached in the question string
    OR passed separately by the pipeline. For compatibility, we'll accept them via question
    if embedded JSON is present, otherwise we only use question text and RBAC lists.
    """
    # For compatibility with our pipeline, we expect the pipeline to already embed the final query,
    # or pass normalized fields via a special JSON suffix. But to keep the tool simple, here it just
    # runs a safe pass-through that builds the final query if the pipeline provided normalized metadata.
    # In our pipeline we will call this tool with precomputed args, so this function will mostly
    # construct the final query using the same helper apply_rbac_logic when necessary.

    # If the question accidentally contains JSON with normalized fields, parse it
    normalized_region = None
    normalized_grade = None
    normalized_department = None

    # Try to extract JSON metadata if present at the end of question: {...}
    m = re.search(r"(\{.*\})\s*$", question)
    if m:
        try:
            payload = json.loads(m.group(1))
            normalized_region = payload.get("normalized_region")
            normalized_grade = payload.get("normalized_grade")
            normalized_department = payload.get("normalized_department")
            # remove the JSON payload from the visible question text
            question = question[:m.start(1)].strip()
        except Exception:
            # ignore parsing error
            pass

    final = apply_rbac_logic(
        question,
        allowed_regions,
        allowed_grades,
        department_exceptions,
        normalized_region=normalized_region,
        normalized_grade=normalized_grade,
        normalized_department=normalized_department,
    )

    return RBACOutput(final_query=final).model_dump()


# --------------------------------------------------------
# LLM (used for normalization)
# --------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([apply_rbac])


# --------------------------------------------------------
# Utility: robustly extract JSON object from LLM text
# --------------------------------------------------------
def extract_json_from_text(text: str) -> dict:
    """
    Try to find the first {...} JSON object in text. If none found, try to clean loose JSON-like text.
    """
    if not text:
        return {}
    # simple search for first JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        substring = text[start:end+1]
        try:
            return json.loads(substring)
        except Exception:
            pass

    # fallback: try to interpret lines like 'region: PAN India' into a dict
    result = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip().lower()] = v.strip()
    return result


# --------------------------------------------------------
# LLM Normalization Node (extract canonical fields + produce neutral rewrite)
# --------------------------------------------------------
NORMALIZER_SYSTEM_PROMPT = f"""
You are an assistant that extracts canonical HR selectors from noisy user text and rewrites the user's
request into a neutral HR-style query.

Rules:
- You MUST NOT execute any data retrieval.
- You MUST return (or embed) JSON with the keys exactly: "normalized_region", "normalized_grade", "normalized_department", "rewritten_query".
- normalized_region / normalized_grade / normalized_department must be one of the canonical values listed below, or null if none found.
- rewritten_query must start with one of: "give me", "show me", "list", "fetch" and be a short neutral query equivalent to the user's intent.
- Be tolerant of typos, abbreviations, and synonyms. Map them to the canonical lists when possible.

Canonical lists (choose one of these values when possible; otherwise return null):
REGIONS: {CANONICAL_REGIONS}
GRADES: {CANONICAL_GRADES}
DEPARTMENTS: {CANONICAL_DEPARTMENTS}

Return the JSON object either as a standalone JSON block, or a short explanation followed by the JSON block.
"""

def llm_normalize_and_rewrite(user_question: str) -> dict:
    """
    Calls the LLM to normalize and rewrite the user question.
    Returns a dict with keys:
      - normalized_region (str|null)
      - normalized_grade (str|null)
      - normalized_department (str|null)
      - rewritten_query (str)
    """
    messages = [
        SystemMessage(content=NORMALIZER_SYSTEM_PROMPT),
        HumanMessage(content=f"User question: \"{user_question}\"")
    ]

    response = llm.invoke(messages)
    # the model response text will be in response.output (or response.content depending on sdk)
    # We'll try to get the assistant text:
    assistant_text = ""
    if hasattr(response, "content") and response.content:
        # older style
        assistant_text = response.content
    else:
        # try other fields
        assistant_text = getattr(response, "output", "") or str(response)

    # Extract JSON payload
    payload = extract_json_from_text(assistant_text)
    # Normalize keys to expected names
    normalized_region = payload.get("normalized_region") or payload.get("region") or payload.get("normalizedRegion")
    normalized_grade = payload.get("normalized_grade") or payload.get("grade") or payload.get("normalizedGrade")
    normalized_department = payload.get("normalized_department") or payload.get("department") or payload.get("normalizedDepartment")
    rewritten_query = payload.get("rewritten_query") or payload.get("query") or payload.get("rewrittenQuery")

    # fallback: if rewritten_query missing, attempt a minimal neutral rewrite
    if not rewritten_query:
        # try minimal rewrite heuristics
        q = user_question.strip()
        if not q.lower().startswith(("give me", "show me", "list", "fetch")):
            rewritten_query = "list " + q
        else:
            rewritten_query = q

    return {
        "normalized_region": normalize_str(normalized_region),
        "normalized_grade": normalize_str(normalized_grade),
        "normalized_department": normalize_str(normalized_department),
        "rewritten_query": rewritten_query.strip()
    }


# --------------------------------------------------------
# Node 1: Normalize query & construct tool_request (calls normalization LLM)
# --------------------------------------------------------
def normalize_node(state: State, config):
    if not state.user_question:
        return {"error": "No user question provided."}

    cfg = config["configurable"]
    normalization = llm_normalize_and_rewrite(state.user_question)

    # Build a question string that includes the rewritten query and an embedded JSON with normalized fields.
    # We'll embed the normalized fields as JSON at the end of the question so the apply_rbac tool can pick them up if needed.
    metadata = {
        "normalized_region": normalization["normalized_region"],
        "normalized_grade": normalization["normalized_grade"],
        "normalized_department": normalization["normalized_department"]
    }

    # use rewritten query as the main question, and append the JSON metadata to help the tool
    question_for_tool = f"{normalization['rewritten_query']} {json.dumps(metadata)}"

    # Build tool_request dict (the rbac node will invoke the tool)
    tool_request = {
        "name": "apply_rbac",
        "args": {
            "question": question_for_tool,
            "allowed_regions": cfg.get("allowed_regions", []),
            "allowed_grades": cfg.get("allowed_grades", []),
            "department_exceptions": cfg.get("department_exceptions", [])
        },
        "type": "tool_call"
    }

    return {"tool_request": tool_request, "cleaned_query": normalization['rewritten_query']}


# --------------------------------------------------------
# Node 2: Run RBAC tool
# --------------------------------------------------------
def rbac_node(state: State, config):
    if state.tool_request is None:
        return {"error": "No tool request found."}

    tool_name = state.tool_request.get("name")
    tool_args = state.tool_request.get("args")

    if tool_name != "apply_rbac":
        return {"error": "Unexpected tool call."}

    result = apply_rbac.invoke(tool_args)
    return {"rbac_result": result["final_query"]}


# --------------------------------------------------------
# Graph Definition
# --------------------------------------------------------
graph = StateGraph(State)

graph.add_node("normalize", normalize_node)
graph.add_node("rbac", rbac_node)

graph.set_entry_point("normalize")

graph.add_edge("normalize", "rbac")
graph.add_edge("rbac", END)

app = graph.compile()


# --------------------------------------------------------
# RUN QUERY FUNCTION
# --------------------------------------------------------
def run_query(user_question, allowed_regions, allowed_grades, department_exceptions):
    initial_state = State(user_question=user_question)

    result = app.invoke(
        initial_state,
        config={
            "configurable": {
                "allowed_regions": allowed_regions,
                "allowed_grades": allowed_grades,
                "department_exceptions": department_exceptions,
            }
        },
    )

    return result


# --------------------------------------------------------
# TEST RUNS
# --------------------------------------------------------
# if __name__ == "__main__":
    # Example 1: correct behavior - user requests Corporate while allowed is PAN INDIA
    # res1 = run_query(
    #     user_question="people resigned in 2025 from Corporate region",
    #     allowed_regions=["PAN INDIA"],                  # user has PAN INDIA access
    #     allowed_grades=["M3", "M4", "M5"],
    #     department_exceptions=["HR", "Facilities"],
    # )
    # print("TEST 1:", res1)

    # Example 2: noisy user text -> LLM should normalize to PAN INDIA
    # res2 = run_query(
    #     user_question="people resigned in 2025 from PAAN indai",  # typo 'indai'
    #     allowed_regions=["Corporate"],                           # user only has Corporate access
    #     allowed_grades=["M3", "M4", "M5"],
    #     department_exceptions=["HR", "Facilities"],
    # )
    # print("TEST 2:", res2)

    # Example 3: user explicitly requests a disallowed grade
    # res3 = run_query(
    #     user_question="resigners for my region , my region is north for m6 and hr department",
    #     allowed_regions=["Corporate", "West", "Central"],
    #     allowed_grades=["M3", "M4", "M5"],   # M6 not allowed
    #     department_exceptions=["HR", "Facilities"],
    # )
    # print("TEST 3:", res3)
