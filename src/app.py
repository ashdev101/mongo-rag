import gradio as gr
import json
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store
from query_router import router as query_router
from langgraph_sample import update_chat_history

def save_conversation_turn(email: str, user_msg: str, bot_msg: str):
    """Helper to save conversation turn with error handling."""
    try:
        update_chat_history(email, user_msg, bot_msg)
    except Exception as e:
        print(f"❌ Failed to update chat history: {e}")
# Import is_hr_department helper (defined in langgraph_sample.py)
# Note: We import it here to avoid circular imports
def is_hr_department(department: str) -> bool:
    """
    Check if department is HR (case-insensitive, handles variations).
    Handles: "Human Resources", "HR", "hr", "human resources", etc.
    """
    if not department:
        return False
    dept_lower = department.lower().strip()
    hr_variations = ["human resources", "hr", "human resource"]
    return dept_lower in hr_variations

# =====================================================================
# Existing processor
# =====================================================================
processor = QueryProcessor()


def run_query(email, question, user_profile=None, needs_routing=False):
    """
    Wrapper for running the main processor.
    
    Args:
        email: User email
        question: Query to process
        user_profile: Optional user profile dict (to avoid duplicate fetch)
        needs_routing: Whether routing is needed (True for Combined tab, False for MQL Agent tab)
    """
    try:
        # Validate email is provided
        if not email or not email.strip():
            return "Error", "Please provide a valid email address", None, "Email is required to fetch your employee information and process the query.", None, []
        
        output = processor.process(email.strip(), question.strip(), user_profile=user_profile, needs_routing=needs_routing)
        
        # Debug: Check if output is None or missing required keys
        if output is None:
            print("❌ ERROR: processor.process() returned None")
            return "Error", "Processor returned None", None, "Internal error: Processor returned None", None, []
        
        if not isinstance(output, dict):
            print(f"❌ ERROR: processor.process() returned non-dict: {type(output)}")
            return "Error", f"Processor returned invalid type: {type(output)}", None, f"Internal error: Invalid output type", None, []
        
        # Check for required keys
        required_keys = ["status", "agent_output", "mql", "db_results"]
        missing_keys = [key for key in required_keys if key not in output]
        if missing_keys:
            print(f"❌ ERROR: Missing keys in output: {missing_keys}")
            print(f"Available keys: {list(output.keys())}")
            return "Error", f"Missing keys: {missing_keys}", None, f"Internal error: Missing output keys", None, []
        
        status = output["status"]
        agent_output = output["agent_output"]
        mql = output["mql"]
        db_results = output["db_results"]
        agg_pipeline = output.get("agg_pipeline")
        questions = output.get("questions", [])  # Get questions as separate field

        print("===="*10,"app.py","===="*10)
        print("User Question:",agent_output.get("question", "") if isinstance(agent_output, dict) else "N/A")
        print("Generated Output:",output["db_results"])

        try:
            agent_out_str = json.dumps(agent_output, indent=2, default=str)
        except Exception as json_err:
            print(f"⚠️ JSON serialization error: {json_err}, using str()")
            agent_out_str = str(agent_output)

        return status, agent_out_str, mql, db_results, agg_pipeline, questions

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ EXCEPTION in run_query: {e}")
        print(f"Traceback:\n{error_trace}")
        return "Error", str(e), None, f"Error: {str(e)}", None, []


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
            status, agent_out_str, mql, db_results, agg_pipeline, questions = run_query("combined@auto", question)

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
# MQL Agent Flow Function (with Clarifying Agent)
# =====================================================================
def mql_execute(email, question):
    """
    1. Call clarifying agent first
    2. If clarified, execute MQL query directly (no router)
    3. Store conversation history
    4. Return results
    """
    
    def safe_json(v):
        try:
            return json.dumps(v, indent=2, default=str)
        except Exception:
            return str(v)
    
    try:
        # ===== UNIFIED AGENT IS NOW IN LANGGRAPH =====
        # QueryProcessor will use LangGraph workflow with unified_agent node
        # needs_routing=False for MQL Agent tab (always document queries)
        status, agent_out_str, mql, db_results, agg_pipeline, questions = run_query(email, question, user_profile=None, needs_routing=False)
        
        # Check if clarification is needed (returned from QueryProcessor)
        if status == "Needs Clarification":
            # Save: Original query → Clarification questions
            save_conversation_turn(email, question, db_results)
            
            # Return clarification questions to UI (use questions array from QueryProcessor)
            clarification_json = safe_json({
                "status": "needs_clarification",
                "questions": questions if questions else []
            })
            return "Needs Clarification", clarification_json, None, db_results
        
        # ===== SAVE FINAL RESPONSE =====
        # Save: Final query → Results
        if db_results:
            save_conversation_turn(email, question, db_results)
        
        return status, agent_out_str, mql, db_results
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ EXCEPTION in mql_execute: {e}")
        print(f"Traceback:\n{error_trace}")
        err = safe_json({"error": str(e)})
        return "Error", err, None, str(e)


# =====================================================================
# Combined Flow Function
# =====================================================================
def combined_execute(email, question):
    """
    1. Call router
    2. Execute the actual target agent
    3. Store conversation history
    4. Return router output + executed result
    """

    def safe_json(v):
        try:
            return json.dumps(v, indent=2, default=str)
        except Exception:
            return str(v)

    try:
        # ===== UNIFIED AGENT IS NOW IN LANGGRAPH =====
        # QueryProcessor will use LangGraph workflow with unified_agent node
        # needs_routing=True for Combined tab (routes to document/policy)
        status, agent_out_str, mql, db_results, agg_pipeline, questions = run_query(email, question, user_profile=None, needs_routing=True)
        
        # Check if clarification is needed
        if status == "Needs Clarification":
            # Save: Original query → Clarification questions
            save_conversation_turn(email, question, db_results)
            
            # Return clarification questions to UI (use questions array from QueryProcessor)
            clarification_json = safe_json({
                "status": "needs_clarification",
                "questions": questions if questions else []
            })
            return clarification_json, "No MQL query (clarification needed)", db_results
        
        # Extract route from agent_output (set by unified_agent_node)
        route = "document"  # Default
        try:
            agent_output = json.loads(agent_out_str) if isinstance(agent_out_str, str) else agent_out_str
            route = agent_output.get("route", "document")
        except:
            pass
        
        # Create router output format (for UI display)
        route_result = {
            "route": route,
            "confidence": 1.0,
            "query": question
        }
        router_out_str = safe_json(route_result)

        # ===== EXECUTE TARGET ENGINE =====
        # For document route, results are already in db_results from run_query
        # For policy route, we need to call policy engine separately
        if route == "policy":
            # Policy queries - call policy engine with clarified query
            # The query should already be clarified by unified agent
            policy_ans = run_policy_query(question)
            final_output = policy_ans
            mql = None  # No MQL for policy queries
        else:
            # Document route - results already in db_results
            final_output = db_results if db_results else "No results"
            mql = mql if mql else "No MQL query generated"

        # ===== SAVE FINAL RESPONSE =====
        # Save: Final query → Results
        bot_response = final_output if isinstance(final_output, str) else str(final_output)
        if bot_response:
            save_conversation_turn(email, question, bot_response)
        
        # Return router output, MQL query, and final output
        mql_output = mql if mql else "No MQL query generated (policy query or error)"
        return router_out_str, mql_output, bot_response

    except Exception as e:
        err = safe_json({"error": str(e)})
        return err, "Error", err


# =====================================================================
# UI
# =====================================================================
with gr.Blocks(title="MQL Access Agent UI (robust)") as demo:

    gr.Markdown("# 🚀 Natural Language → MQL Query + Policy Q&A + Combined Router")

    with gr.Tabs():

        # =============================================================
        # TAB 1 — MQL Access Agent UI
        # =============================================================
        with gr.Tab("MQL Agent"):
            gr.Markdown("### Enter your email and natural language query.")

            with gr.Row():
                email_in = gr.Textbox(label="Email")
                query_in = gr.Textbox(
                    label="Natural Language Query",
                    lines=2,
                    value="give me the name of the people who have resigned in the year 2022 in march?"
                )

            run_btn = gr.Button("Run Query")

            with gr.Row():
                status_out = gr.Textbox(label="Decision (Allowed / Denied / Error)")
                mql_out = gr.Textbox(label="Generated MQL Query")

            with gr.Accordion("Agent Raw Output (JSON-ish)", open=False):
                agent_out = gr.Textbox(lines=8)

            db_out = gr.Textbox(label="Database Results / Converter Output", lines=12)

            # ========== RUN QUERY (with Clarifying Agent) ==========
            run_btn.click(
                mql_execute,
                inputs=[email_in, query_in],
                outputs=[status_out, agent_out, mql_out, db_out]
            )

        # =============================================================
        # TAB 2 — Policy Documentation Q&A
        # =============================================================
        with gr.Tab("Policy Docs"):
            gr.Markdown("### Ask a question about policy documents.")

            policy_question = gr.Textbox(label="Policy Question", lines=2)
            policy_btn = gr.Button("Ask Policy Engine")
            policy_output = gr.Textbox(label="Answer", lines=10)

            policy_btn.click(
                run_policy_query,
                inputs=policy_question,
                outputs=policy_output
            )

        # =============================================================
        # TAB 3 — Combined Router
        # =============================================================
        with gr.Tab("Combined"):
            gr.Markdown("### Unified Query Interface (Router → Document/Policy)")

            with gr.Row():
                combined_email = gr.Textbox(label="Email")
                combined_question = gr.Textbox(label="Your Question", lines=2)

            combined_btn = gr.Button("Run Combined Router")

            router_output = gr.Textbox(label="Router Output (JSON)", lines=6)
            mql_output = gr.Textbox(label="Generated MQL Query", lines=6)
            final_output = gr.Textbox(label="Final Result (Executed Output)", lines=6)

            combined_btn.click(
                combined_execute,
                inputs=[combined_email, combined_question],
                outputs=[router_output, mql_output, final_output]
            )


if __name__ == "__main__":
    demo.launch()
