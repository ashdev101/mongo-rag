"""
orchestrator.py

A LangGraph orchestrator combining:
- HR pipeline (Mongo + NLP)
- Policy RAG (query_main_store)
- MongoDB-backed chat memory
- LLM intent classifier
- Human-in-the-loop approval
"""

import os
import time
import uuid
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END  # adjust import to your LangGraph SDK
# NOTE: If your SDK uses different names, adapt accordingly.

# For LLM calls - example using OpenAI style. Swap with your SDK.
import openai
from pymongo import MongoClient

from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MONGO_URI = os.getenv('MONGODB_URI')
MONGO_DB = 'chat_orchestrator_db'
#----------------------------
# Mongo helpers
#----------------------------
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
conversations = db["conversations"]        # stores session-level chat history
memories = db["memories"]                  # persistent semantic memories (if needed)
human_tasks = db["human_tasks"]            # tasks for human-in-loop
logs = db["orchestrator_logs"]

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

# ---------------------------
class OrchestratorState(BaseModel):
    input: str
    user_id: str
    session_id: str

    history: List[Dict] = Field(default_factory=list)
    memory_ids: List[str] = Field(default_factory=list)

    intent: Optional[str] = None
    intent_confidence: Optional[float] = None

    role: Optional[str] = None
    modified_query: Optional[str] = None
    access_granted: Optional[bool] = None

    hr_answer: Optional[str] = None
    policy_answer: Optional[str] = None

    needs_approval: Optional[bool] = None
    human_task_id: Optional[str] = None

    answer: Optional[str] = None
    debug: Dict = Field(default_factory=dict)
# ---------------------------

def ensure_session_record(session_id: str, user_id: str):
    doc = conversations.find_one({"session_id": session_id})
    if not doc:
        conversations.insert_one({
            "session_id": session_id,
            "user_id": user_id,
            "history": [],
            "created_at": time.time()
        })

def append_history(session_id: str, from_: str, text: str):
    conversations.update_one(
        {"session_id": session_id},
        {"$push": {"history": {"from": from_, "text": text, "ts": time.time()}}},
        upsert=True
    )

def save_memory(user_id: str, content: Dict[str, Any]) -> str:
    res = memories.insert_one({"user_id": user_id, "content": content, "ts": time.time()})
    return str(res.inserted_id)

def create_human_task(session_id: str, user_id: str, payload: Dict[str, Any]) -> str:
    task = {
        "session_id": session_id,
        "user_id": user_id,
        "payload": payload,
        "created_at": time.time(),
        "status": "pending",   # "pending", "approved", "rejected"
        "result": None
    }
    res = human_tasks.insert_one(task)
    return str(res.inserted_id)

def poll_human_task(task_id: str, timeout_seconds: int = 60*30) -> Optional[Dict[str, Any]]:
    """Polling helper for demo. In production use webhooks or event-driven messages."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        t = human_tasks.find_one({"_id": task_id})
        if not t:
            return None
        if t.get("status") in ("approved", "rejected"):
            return t
        time.sleep(1.0)
    return None

# ---------------------------
# LLM intent classifier node
# ---------------------------
def llm_intent_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls LLM to classify intent. Returns state with 'intent' and 'intent_confidence'.
    You can replace the prompt or use your own classifier model.
    """
    user_text = state["input"]
    prompt = (
        "You are an intent classifier. Given the user message, pick one intent label "
        "from [hr, policy, smalltalk, other]. Respond as a JSON object "
        'like {"intent":"hr","confidence":0.95} and nothing else.\n\n'
        f"Message: '''{user_text}'''"
    )

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # replace with the model you use
            messages=[{"role":"system","content":"You are a strict JSON-only classifier."},
                      {"role":"user","content":prompt}],
            max_tokens=60,
            temperature=0.0
        )
        raw = resp.choices[0].message.content.strip()
        # Best-effort parse JSON from model output
        import json
        parsed = json.loads(raw)
        state["intent"] = parsed.get("intent", "other")
        state["intent_confidence"] = float(parsed.get("confidence", 0.5))
    except Exception as e:
        # fallback heuristic
        txt = user_text.lower()
        if "policy" in txt or "procedure" in txt or "policy" in txt:
            state["intent"] = "policy"
            state["intent_confidence"] = 0.7
        elif "manager" in txt or "performance" in txt or "salary" in txt:
            state["intent"] = "hr"
            state["intent_confidence"] = 0.7
        else:
            state["intent"] = "other"
            state["intent_confidence"] = 0.5
        state.setdefault("debug", {})["llm_error"] = str(e)
    return state

# ---------------------------
# Chat memory node (Mongo-backed)
# ---------------------------
def chat_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append the incoming user message to Mongo conversation history, and retrieve
    the latest N turns as context if desired.
    """
    session_id = state.get("session_id") or str(uuid.uuid4())
    user_id = state.get("user_id", "unknown")
    ensure_session_record(session_id, user_id)
    append_history(session_id, "user", state["input"])
    # attach session info back to state
    state["session_id"] = session_id
    # For simplicity, fetch the last 6 messages
    doc = conversations.find_one({"session_id": session_id})
    recent = (doc or {}).get("history", [])[-6:]
    state["history"] = recent
    return state

# ---------------------------
# HR subgraph nodes (your existing pipeline A)
# ---------------------------
def fetch_role_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example: fetch role info from users collection or an identity provider.
    """
    # Placeholder — in real system fetch from users collection
    user_id = state.get("user_id", "unknown")
    # Example role lookup
    role_doc = db["users"].find_one({"user_id": user_id})
    role = role_doc.get("role") if role_doc else "employee"
    state["role"] = role
    return state

def classify_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify whether HR query needs modification or special handling.
    """
    text = state["input"]
    # simple rule: if contains 'performance', mark as performance
    state.setdefault("debug", {})["classify_query_keywords"] = []
    if "performance" in text.lower():
        state["debug"]["classify_query_keywords"].append("performance")
        state["query_type"] = "performance_review"
    else:
        state["query_type"] = "general_hr"
    return state

def modify_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform or expand query before sending to Mongo/NLP retrieval.
    """
    q = state["input"]
    # e.g. add clarifying context for manager queries
    if state.get("query_type") == "performance_review":
        q = q + " (focus on manager responsibilities and steps in review cycle)"
    state["modified_query"] = q
    return state

def check_access_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check whether user has permission to access requested HR info.
    """
    role = state.get("role", "employee")
    # Example policy: only managers and HR can get certain items
    sensitive = "salary" in state["modified_query"].lower() or "discipline" in state["modified_query"].lower()
    if sensitive and role not in ("hr", "admin", "manager"):
        state["access_granted"] = False
        state["needs_approval"] = True  # escalate to human-in-loop
    else:
        state["access_granted"] = True
    return state

def hr_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute query against HR Mongo/NLP system. Fill hr_answer.
    Replace with your actual DB + NLP retrieval implementation.
    """
    if not state.get("access_granted", False):
        state["hr_answer"] = "Access denied. This request requires approval."
        return state

    # Simulated call: in reality you'd call your NLP retrieval on HR docs:
    # e.g. call `query_hr_store(state["modified_query"], k=5)`
    q = state["modified_query"]
    # Placeholder response:
    state["hr_answer"] = f"[HR ANSWER simulated] For query: '{q}' -> Managers should set clear objectives, provide feedback, document performance, etc."
    return state

def hr_subgraph() -> StateGraph:
    """
    Build HR pipeline as a StateGraph (subgraph)
    """
    g = StateGraph(state_schema=OrchestratorState)
    g.add_node("fetch_role", fetch_role_node)
    g.add_node("classify_query", classify_query_node)
    g.add_node("modify_query", modify_query_node)
    g.add_node("check_access", check_access_node)
    g.add_node("hr_response", hr_response_node)
    # edges
    g.add_edge("fetch_role", "classify_query")
    g.add_edge("classify_query", "modify_query")
    g.add_edge("modify_query", "check_access")
    g.add_edge("check_access", "hr_response")
    g.add_edge("hr_response", END)
    return g

# ---------------------------
# Policy (RAG) subgraph
# ---------------------------
# You should provide query_main_store function in your codebase.
# Example signature: def query_main_store(query: str) -> str
# This placeholder will call that if present.

def policy_rag_node(state: Dict[str, Any]) -> Dict[str, Any]:
    q = state["input"]
    # Use history and memory if available to craft prompt (optional)
    try:
        # call your RAG function
        from your_rag_module import query_main_store  # replace with actual import
        ans = query_main_store(q)
    except Exception:
        # fallback placeholder
        ans = f"[Policy RAG simulated] Relevant responsibilities are: define objectives, follow appraisal policy, keep records. (Query was: {q})"
    state["policy_answer"] = ans
    return state

def policy_subgraph() -> StateGraph:
    g = StateGraph(state_schema=OrchestratorState)
    g.add_node("policy_rag", policy_rag_node)
    g.add_edge("policy_rag", END)
    return g

# ---------------------------
# Human-in-the-loop node
# ---------------------------
def human_in_the_loop_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    If something needs approval, create a human task in Mongo and poll for result.
    In production: send a webhook or push to a task queue and return control to caller.
    """
    if not state.get("needs_approval", False):
        return state

    # create payload for human approver (include relevant context)
    payload = {
        "session_id": state.get("session_id"),
        "user_id": state.get("user_id"),
        "input": state["input"],
        "modified_query": state.get("modified_query"),
        "role": state.get("role"),
        "reason": "sensitive HR access request"
    }
    task_id = create_human_task(state.get("session_id"), state.get("user_id"), payload)
    state["human_task_id"] = task_id

    # Poll for demo purposes. Real system should use webhook or async messaging.
    task_doc = poll_human_task(task_id, timeout_seconds=60*10)  # wait up to 10 minutes for demo
    if not task_doc:
        # timeout or no response -> mark as denied or fallback
        state["access_granted"] = False
        state["answer"] = "This request requires human approval; no decision was recorded."
        state["needs_approval"] = True
        return state

    if task_doc["status"] == "approved":
        state["access_granted"] = True
        state["needs_approval"] = False
        state["debug"] = state.get("debug", {})
        state["debug"]["human_task_result"] = task_doc.get("result")
    else:
        state["access_granted"] = False
        state["needs_approval"] = False
        state["answer"] = "Human reviewer rejected the request."
    return state

# ---------------------------
# Final response node
# ---------------------------
def final_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    out_parts = []
    if state.get("hr_answer"):
        out_parts.append(state["hr_answer"])
    if state.get("policy_answer"):
        out_parts.append(state["policy_answer"])

    if not out_parts and state.get("answer"):
        # already set (like denied)
        final = state["answer"]
    else:
        final = "\n\n".join(out_parts) if out_parts else "I'm not sure how to answer that."

    # Save assistant reply to history
    append_history(state.get("session_id"), "assistant", final)
    state["answer"] = final

    # log for debugging
    logs.insert_one({
        "session_id": state.get("session_id"),
        "user_id": state.get("user_id"),
        "input": state.get("input"),
        "intent": state.get("intent"),
        "answer": final,
        "ts": time.time()
    })

    return state

# ---------------------------
# Assemble top-level orchestrator
# ---------------------------


def build_orchestrator() -> StateGraph:
    orchestrator = StateGraph(state_schema=OrchestratorState)

    # nodes
    orchestrator.add_node("chat_memory", chat_memory_node)
    orchestrator.add_node("classify_intent", llm_intent_classifier_node)
    orchestrator.add_node("hr_flow", hr_subgraph())
    orchestrator.add_node("policy_flow", policy_subgraph())
    orchestrator.add_node("human_check", human_in_the_loop_node)
    orchestrator.add_node("final_response", final_response_node)

    # entry
    orchestrator.set_entry_point("chat_memory")

    orchestrator.add_edge("chat_memory", "classify_intent")

    # conditional routing
    def intent_router(state):
        intent = state.intent or "other"
        if intent == "hr":
            return "hr_flow"
        elif intent == "policy":
            return "policy_flow"
        else:
            return "policy_flow"

    orchestrator.add_conditional_edges(
        source="classify_intent",
        router=intent_router
    )

    orchestrator.add_edge("hr_flow", "human_check")
    orchestrator.add_edge("policy_flow", "human_check")
    orchestrator.add_edge("human_check", "final_response")

    orchestrator.add_edge("final_response", END)

    return orchestrator

# ---------------------------
# Example usage
# ---------------------------
orc = build_orchestrator()

# Example request
initial_state = {
    "input": "What are the responsibilities of the managers in performance review?",
    "user_id": "user-123",
    "session_id": "session-abc-1"
}

# Many LangGraph SDKs use something like orc.run(initial_state)
# Replace with the correct execution call for your version.
res_state = orc.run(initial_state)
print("FINAL ANSWER:")
print(res_state.get("answer"))
