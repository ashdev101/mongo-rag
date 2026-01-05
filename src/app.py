import json
import re
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store
from query_router import router as query_router
from memory.memorymanager import push_convo_pair
from onepager.pdf_generator import generate_one_pager
from rbac_onepager import rbac_onepager
from OnePager import OnePager
from backend.config import get_settings
from meta_system import meta_system
from chat_system import chat_system
from conversation_resolver import resolve_conversation

# =====================================================================
# Existing processor
# =====================================================================
processor = QueryProcessor()


def run_query(email, question):
    """
    Wrapper for running the main processor.
    """
    try:
        # Validate email is provided
        if not email or not email.strip():
            return "Error", "Please provide a valid email address", None, "Email is required to fetch your employee information and process the query."
        
        output = processor.process(email.strip(), question.strip())
        
        status = output["status"]
        agent_output = output["agent_output"]
        mql = output["mql"]
        db_results = output["db_results"]
        agg_pipeline = output.get("agg_pipeline")

        print("===="*10,"app.py","===="*10)
        print("User Question:",agent_output["question"])
        print("Generated Output:",output["db_results"])

        try:
            agent_out_str = json.dumps(agent_output, indent=2, default=str)
        except Exception:
            agent_out_str = str(agent_output)

        return status, agent_out_str, mql, db_results, agg_pipeline

    except Exception as e:
        return "Error", str(e), None, None, None


# =====================================================================
# Policy Q&A function
# =====================================================================
def run_policy_query(question):
    try:
        response = query_main_store(question)
        return str(response)
    except Exception as e:
        return f"Error: {e}"


# =====================================================================
# Combined Router
# =====================================================================
def router(question):
    """
    Decide whether to call:
    - run_query (MQL agent)
    - run_policy_query (policy engine)
    """

    q_lower = question.lower()

    try:
        if "policy" in q_lower or "regulation" in q_lower:
            result = run_policy_query(question)
            return f"[ROUTED TO POLICY ENGINE]\n\n{result}"

        else:
            status, agent_out_str, mql, db_results, agg_pipeline = run_query("combined@auto", question)

            return (
                "[ROUTED TO MQL AGENT]\n\n"
                f"Status: {status}\n\n"
                f"MQL:\n{mql}\n\n"
                f"DB Results:\n{db_results}\n\n"
                f"Agent Output:\n{agent_out_str}"
            )

    except Exception as e:
        return f"Routing Error: {e}"


# =====================================================================
# Combined Flow Function
# =====================================================================
import os
import json
import re
import gradio as gr

def combined_execute(email, question):
    """
    Returns:
    1. router_output (text)
    2. final_text (Textbox OR hidden)
    3. final_file (File OR hidden)
    """

    def safe_json(v):
        try:
            return json.dumps(v, indent=2, default=str)
        except Exception:
            return str(v)

    try:
        # ===== /onepager COMMAND =====
        onepager_match = re.search(r'/onepager\s+@(\d+)', question.strip(), re.IGNORECASE)

        if onepager_match:
            employee_code = onepager_match.group(1)
            onepager = OnePager()

            try:
                access_granted = rbac_onepager(email , employee_code)

                if not access_granted:
                    router_out_str = safe_json({
                        "route": "onepager",
                        "command": f"/onepager @{employee_code}",
                        "employee_code": employee_code
                    })
                    error_msg = "Access denied for onepager report"
                    return (
                        router_out_str,
                        gr.update(visible=True, value=error_msg),
                        gr.update(visible=False, value=None)
                    )
                report = onepager.generate_report_aggregation(employee_code, email)

                router_out_str = safe_json({
                    "route": "onepager",
                    "command": f"/onepager @{employee_code}",
                    "employee_code": employee_code
                })

                if report.get("status") == "success":
                    final_output = generate_one_pager(report)  
                    # ⬆️ could be TEXT or FILE PATH

                    # Save history (text only)
                    try:
                        if isinstance(final_output, str) and not os.path.isfile(final_output):
                            push_convo_pair(email, question, final_output)
                    except Exception as e:
                        print("History save failed:", e)

                    # ===== FILE OUTPUT =====
                    if isinstance(final_output, str) and os.path.isfile(final_output):
                        return (
                            router_out_str,
                            gr.update(visible=False, value=None),
                            gr.update(visible=True, value=final_output)
                        )

                    # ===== TEXT OUTPUT =====
                    return (
                        router_out_str,
                        gr.update(visible=True, value=final_output),
                        gr.update(visible=False, value=None)
                    )

                else:
                    error_msg = report.get("message", "Error generating report")
                    return (
                        router_out_str,
                        gr.update(visible=True, value=error_msg),
                        gr.update(visible=False, value=None)
                    )

            finally:
                onepager.close()

        # ===== REGULAR ROUTING =====
        resolve_conversation_result = resolve_conversation(question, email)
        route_result = query_router(resolve_conversation_result, email)
        router_out_str = safe_json(route_result)

        route = route_result.get("route")
        query = route_result.get("query", "")

        final_output = ""

        if route == "document":
            status, agent_out_str, mql, db_results, agg_pipeline = run_query(email, query)
            final_output = db_results

        elif route == "policy":
            final_output = run_policy_query(query)
        
        elif route == "chat":
            final_output = chat_system(query , email)

        elif route == "meta":
            final_output = meta_system(query)

        else:
            final_output = "Sorry , I am unable to process your request at the moment."

        # Save history
        try:
            push_convo_pair(email, question, final_output)
        except Exception as e:
            print("History save failed:", e)

        # ===== FILE VS TEXT DETECTION =====
        if isinstance(final_output, str) and os.path.isfile(final_output):
            return (
                router_out_str,
                gr.update(visible=False, value=None),
                gr.update(visible=True, value=final_output)
            )

        return (
            router_out_str,
            gr.update(visible=True, value=str(final_output)),
            gr.update(visible=False, value=None)
        )

    except Exception as e:
        err = safe_json({"error": str(e)})
        return (
            err,
            gr.update(visible=True, value=err),
            gr.update(visible=False, value=None)
        )
    

# ===================================================================== 
# Combined Execute for api

import json
import os
import re
from fastapi import HTTPException
from typing import Any, Literal, Optional 
from pydantic import BaseModel


class APIResponse(BaseModel):
    type: Literal["text","file"]  # "text" | "file"
    content: str  # text OR absolute file path

def combined_execute_api(email: str, question: str):
    """
    Returns:
    {
        "type": "text" | "file",
        "content": str   # text OR absolute file path
    }
    """

    def safe_json(v):
        try:
            return json.dumps(v, indent=2, default=str)
        except Exception:
            return str(v)

    try:
        # ===== DEVELOPMENT MODE: EXTRACT EMAIL FROM INPUT =====
        settings = get_settings()
        if settings.ENVIRONMENT == "development":
            useemail_match = re.search(r'/useemail\s+@([\w.@+-]+)\s*\.\s*(.+)', question.strip(), re.IGNORECASE | re.DOTALL)
            if useemail_match:
                email = useemail_match.group(1)
                question = useemail_match.group(2).strip()
                # print(f"[DEV MODE] Extracted email: {email}")
                # print(f"[DEV MODE] Extracted message: {question}")
        # ===== /onepager COMMAND =====
        onepager_match = re.search(r'/onepager\s+@(\d+)', question.strip(), re.IGNORECASE)

        if onepager_match:
            employee_code = onepager_match.group(1)
            onepager = OnePager()

            try:
                access_granted = rbac_onepager(email, employee_code)

                if not access_granted:
                    return APIResponse(
                        type="text",
                        content="Access denied for onepager report"
                    )

                report = onepager.generate_report_aggregation(employee_code, email)

                if report.get("status") != "success":
                    error_msg = report.get("message", "Error generating report")
                    return APIResponse(
                        type="text",
                        content=error_msg
                    )

                final_output = generate_one_pager(report)

                # Save history (TEXT ONLY)
                if isinstance(final_output, str) and not os.path.isfile(final_output):
                    try:
                        push_convo_pair(email, question, final_output)
                    except Exception:
                        pass

                # ===== FILE OUTPUT =====
                if isinstance(final_output, str) and os.path.isfile(final_output):
                    return APIResponse(
                        type="file",
                        content=final_output
                    )

                # ===== TEXT OUTPUT =====
                return APIResponse(
                    type="text",
                    content=final_output
                )

            finally:
                onepager.close()

        # ===== REGULAR ROUTING =====
        resolve_conversation_result = resolve_conversation(question, email)
        route_result = query_router(resolve_conversation_result, email)
        route = route_result.get("route")
        query = route_result.get("query", "")

        if route == "document":
            _, _, _, db_results, _ = run_query(email, query)
            final_output = db_results

        elif route == "policy":
            final_output = run_policy_query(query)
        
        elif route == "chat":
            final_output = chat_system(query , email)

        elif route == "meta":
            final_output = meta_system(query)

        else:
            final_output = "Sorry , I am unable to process your request at the moment."

        # Save history
        try:
            push_convo_pair(email, question, final_output)
        except Exception:
            pass

        # FILE VS TEXT
        if isinstance(final_output, str) and os.path.isfile(final_output):
            return APIResponse(
                type="file",
                content=final_output
            )

        return APIResponse(
            type="text",
            content=str(final_output)
        )

    except Exception as e:
        return APIResponse(
            type="text",
            content=str("Sorry , we are unable to process this query .")
        )
