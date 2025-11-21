import gradio as gr
import json
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store
from feedback.lander import lander 

# =====================================================================
# Existing processor
# =====================================================================
processor = QueryProcessor()

def run_query(email, question):
    """
    Wrapper for running the main processor.
    """
    try:
        output = processor.process(email.strip(), question.strip())
        
        status = output["status"]
        agent_output = output["agent_output"]
        mql = output["mql"]
        db_results = output["db_results"]
        agg_pipeline = output.get("agg_pipeline")
        print("===="*10,"app.py","===="*10)
        print("User Question:",agent_output["question"])
        # print("NLQ:\n",output["question"])
        # Safe JSON formatting
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
# Feedback handler
# =====================================================================
def submit_feedback(choice, feedback_data):
    print("\n===== FEEDBACK RECEIVED =====")
    print("agg_pipeline:",feedback_data["agg_pipeline"])
    print("query:",feedback_data["query"])
    msg = lander(choice,feedback_data)
    
    return msg


# =====================================================================
# UI
# =====================================================================
with gr.Blocks(title="MQL Access Agent UI (robust)") as demo:

    gr.Markdown("# 🚀 Natural Language → MQL Query + Policy Q&A")

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

            # Hidden store for agg_pipeline nad user_query
            agg_pipeline_store = gr.Textbox(label="_agg_pipeline_store", visible=False)
            query_store = gr.Textbox(label="_query_store", visible=False)


            # =============================================================
            # Feedback Section
            # =============================================================
            gr.Markdown("### Was this result correct?")

            with gr.Row():
                yes_btn = gr.Button("Yes", interactive=False)
                no_btn = gr.Button("No", interactive=False)

            feedback_output = gr.Textbox(label="Feedback Status", interactive=False)

            # =================== RUN QUERY AND ENABLE FEEDBACK ===================
            def run_query_and_enable(email, question):
                status, agent_out_str, mql, db_results, agg_pipeline = run_query(email, question)

                return (
                    status,
                    agent_out_str,
                    mql,
                    db_results,
                    gr.update(value=json.dumps(agg_pipeline, default=str), visible=False),
                    gr.update(value=question, visible=False),
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                    ""
                )

            run_btn.click(
                run_query_and_enable,
                inputs=[email_in, query_in],
                outputs=[status_out, agent_out, mql_out, db_out, agg_pipeline_store, query_store,
                         yes_btn, no_btn, feedback_output]
            )

            # =================== RESET FEEDBACK ===================
            def reset_feedback():
                return gr.update(interactive=False), gr.update(interactive=False), ""

            email_in.change(reset_feedback, None, [yes_btn, no_btn, feedback_output])
            query_in.change(reset_feedback, None, [yes_btn, no_btn, feedback_output])

            # =================== FEEDBACK CALLBACKS ===================
            def yes_feedback_action(agg_pipeline,query_value):
                msg = submit_feedback("Yes", {"agg_pipeline": agg_pipeline, "query": query_value})
                return msg, gr.update(interactive=False), gr.update(interactive=False)

            def no_feedback_action(agg_pipeline,query_value):
                msg = submit_feedback("No", {"agg_pipeline": agg_pipeline, "query": query_value})
                return msg, gr.update(interactive=False), gr.update(interactive=False)

            yes_btn.click(
                yes_feedback_action,
                inputs=[agg_pipeline_store,query_store],
                outputs=[feedback_output, yes_btn, no_btn]
            )

            no_btn.click(
            no_feedback_action,
            inputs=[agg_pipeline_store, query_store],
            outputs=[feedback_output, yes_btn, no_btn]
            )

        # =============================================================
        # TAB 2 — Policy Documentation Q&A
        # =============================================================
        with gr.Tab("Policy Docs"):
            gr.Markdown("### Ask a question about policy documents.")

            policy_question = gr.Textbox(
                label="Policy Question",
                lines=2
            )

            policy_btn = gr.Button("Ask Policy Engine")
            policy_output = gr.Textbox(label="Answer", lines=10)

            policy_btn.click(
                run_policy_query,
                inputs=policy_question,
                outputs=policy_output
            )

if __name__ == "__main__":
    demo.launch()
