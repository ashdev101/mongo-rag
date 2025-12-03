import gradio as gr
import json
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store
from query_router import router as query_router
from memory.memorymanager import push_convo_pair
from clarifying_agent_ui import add_session_turn
from clarifying_agent_ui import run_clarifying_agent

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
        # ===== STEP 1: UNIFIED AGENT (FIRST) =====
        # needs_routing=False for MQL Agent tab (always document queries)
        clarification_result = run_clarifying_agent(email, question, needs_routing=False)
        
        # If clarification needed, return questions to UI
        if clarification_result.get("needs_clarification", False):
            questions = clarification_result.get("questions", [])
            if len(questions) == 1:
                clarification_text = questions[0]
            else:
                clarification_text = "I need a few clarifications:\n\n"
                for i, q in enumerate(questions, 1):
                    clarification_text += f"{i}. {q}\n"
            
            # Return format compatible with MQL Agent UI
            # For MQL Agent tab, we'll show clarification in the db_out field
            clarification_json = safe_json({
                "status": "needs_clarification",
                "questions": questions
            })
            return "Needs Clarification", clarification_json, None, clarification_text
        
        # ===== STEP 2: EXECUTE MQL QUERY DIRECTLY =====
        final_clarified_query = clarification_result.get("final_clarified_query", question)
        status, agent_out_str, mql, db_results, agg_pipeline = run_query(email, final_clarified_query)
        
        # ===== AUTO-SAVE CHAT HISTORY =====
        # Save exactly what the user sees in UI: user's current input → bot's current output
        # Filter out "Allowed"/"Not allowed" messages
        try:
            # Check if there was a clarification process
            # If original_query exists and differs from current question, user provided clarification answer
            # In that case, save current question (clarification answer) → final response
            # Otherwise, save current question (original query) → final response
            original_query = clarification_result.get("original_query", "")
            if original_query and original_query != question:
                # There was clarification - save user's clarification answer → final response
                user_msg_to_save = question  # User's clarification answer
            else:
                # No clarification - save user's original query → final response
                user_msg_to_save = question  # User's original query
            
            if db_results and db_results.strip().lower() not in ["allowed", "not allowed", "unclear intent"]:
                print(f"💾 Saving chat history to MongoDB: user_msg='{user_msg_to_save[:50]}...', bot_msg length={len(db_results)}")
                # Save to MongoDB (async) - save what user sees: their input → bot's output
                push_convo_pair(
                    email=email,
                    user_msg=user_msg_to_save,
                    bot_msg=db_results
                )
                # Also add to current session state for immediate context
                add_session_turn(email, user_msg_to_save, db_results)
            else:
                print(f"⚠️ Skipping save: db_results is empty or access check message")
        except Exception as e:
            print(f"❌ Failed to push conversation history: {e}")
        
        return status, agent_out_str, mql, db_results
    
    except Exception as e:
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
        # ===== STEP 1: UNIFIED AGENT (FIRST) =====
        # needs_routing=True for Combined tab (routes to document/policy)
        clarification_result = run_clarifying_agent(email, question, needs_routing=True)
        
        # If clarification needed, return questions to UI
        if clarification_result.get("needs_clarification", False):
            questions = clarification_result.get("questions", [])
            if len(questions) == 1:
                clarification_text = questions[0]
            else:
                clarification_text = "I need a few clarifications:\n\n"
                for i, q in enumerate(questions, 1):
                    clarification_text += f"{i}. {q}\n"
            
            # Return format compatible with UI (two string outputs)
            clarification_json = safe_json({
                "status": "needs_clarification",
                "questions": questions
            })
            return clarification_json, clarification_text
        
        # ===== STEP 2: USE ROUTE FROM UNIFIED AGENT =====
        final_clarified_query = clarification_result.get("final_clarified_query", question)
        route = clarification_result.get("route", "document")  # Default to document if not provided
        
        # Create router output format (for UI display)
        route_result = {
            "route": route,
            "confidence": 1.0,
            "query": final_clarified_query
        }
        router_out_str = safe_json(route_result)
        
        query = final_clarified_query

        # ===== STEP 3: EXECUTE TARGET ENGINE =====
        if route == "document":
            status, agent_out_str, mql, db_results, agg_pipeline = run_query(email, query)
            final_output_dict = {
                "status": status,
                "mql": mql,
                "db_results": db_results,
                "agent_output": agent_out_str
            }
            final_output = safe_json(final_output_dict)

        elif route == "policy":
            policy_ans = run_policy_query(query)
            final_output_dict = {"policy_answer": policy_ans}
            final_output = safe_json(final_output_dict)

        else:
            final_output_dict = {"error": "Router returned invalid route"}
            final_output = safe_json(final_output_dict)

        # ===== AUTO-SAVE CHAT HISTORY =====
        # Save exactly what the user sees in UI: user's current input → bot's current output
        # Filter out "Allowed"/"Not allowed" messages - they're access checks, not conversation
        final_output_string = ""
        try:
            # Check if there was a clarification process
            # If original_query exists and differs from current question, user provided clarification answer
            # In that case, save current question (clarification answer) → final response
            # Otherwise, save current question (original query) → final response
            original_query = clarification_result.get("original_query", "")
            if original_query and original_query != question:
                # There was clarification - save user's clarification answer → final response
                user_msg_to_save = question  # User's clarification answer
            else:
                # No clarification - save user's original query → final response
                user_msg_to_save = question  # User's original query
            
            if route == "document":
                bot_response = final_output_dict.get("db_results", "")
                # Filter out access check messages
                if bot_response and bot_response.strip().lower() not in ["allowed", "not allowed", "unclear intent"]:
                    print(f"💾 Saving chat history to MongoDB: user_msg='{user_msg_to_save[:50]}...', bot_msg length={len(bot_response)}")
                    # Save to MongoDB (async) - save what user sees: their input → bot's output
                    push_convo_pair(
                        email=email,
                        user_msg=user_msg_to_save,
                        bot_msg=bot_response
                    )
                    # Also add to current session state for immediate context
                    add_session_turn(email, user_msg_to_save, bot_response)
                else:
                    print(f"⚠️ Skipping save: bot_response is empty or access check message")
                final_output_string = bot_response

            elif route == "policy":
                bot_response = final_output_dict.get("policy_answer", "")
                # Filter out access check messages
                if bot_response and bot_response.strip().lower() not in ["allowed", "not allowed", "unclear intent"]:
                    print(f"💾 Saving chat history to MongoDB: user_msg='{user_msg_to_save[:50]}...', bot_msg length={len(bot_response)}")
                    # Save to MongoDB (async) - save what user sees: their input → bot's output
                    push_convo_pair(
                        email=email,
                        user_msg=user_msg_to_save,
                        bot_msg=bot_response
                    )
                    # Also add to current session state for immediate context
                    add_session_turn(email, user_msg_to_save, bot_response)
                else:
                    print(f"⚠️ Skipping save: bot_response is empty or access check message")
                final_output_string = bot_response

        except Exception as e:
            print(f"❌ Failed to push conversation history: {e}")

        return router_out_str, final_output_string

    except Exception as e:
        err = safe_json({"error": str(e)})
        return err, err


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
            final_output = gr.Textbox(label="Final Result (Executed Output)", lines=6)

            combined_btn.click(
                combined_execute,
                inputs=[combined_email, combined_question],
                outputs=[router_output, final_output]
            )


if __name__ == "__main__":
    demo.launch()
