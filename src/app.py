import gradio as gr
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store     # <-- update to your real module

# =====================================================================
# Existing processor
# =====================================================================
processor = QueryProcessor()

def run_query(email, question):
    try:
        output = processor.process(email.strip(), question.strip())
        status = output["status"]
        agent_output = output["agent_output"]
        mql = output["mql"]
        db_results = output["db_results"]

        # format agent output string safely
        try:
            import json
            agent_out_str = json.dumps(agent_output, indent=2, default=str)
        except Exception:
            agent_out_str = str(agent_output)

        return status, agent_out_str, mql, db_results
    except Exception as e:
        return "Error", str(e), None, None


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
# Gradio UI with Tabs
# =====================================================================
with gr.Blocks(title="MQL Access Agent UI (robust)") as demo:
    gr.Markdown("# 🚀 Natural Language → MQL Query + Policy Q&A")

    with gr.Tabs() as tabs:

        # =============================================================
        # TAB 1 — MQL Access Agent UI
        # =============================================================
        with gr.Tab("MQL Agent"):
            gr.Markdown("### Enter your email and natural language query.")

            with gr.Row():
                email_in = gr.Textbox(label="Email", placeholder="your.email@company.com")
                query_in = gr.Textbox(label="Natural Language Query", lines=2,
                                      value="give me the name of the people who have resigned in the year 2022 in march?")

            run_btn = gr.Button("Run Query")

            with gr.Row():
                status_out = gr.Textbox(label="Decision (Allowed / Denied / Error)")
                mql_out = gr.Textbox(label="Generated MQL Query")

            with gr.Accordion("Agent Raw Output (JSON-ish)", open=False):
                agent_out = gr.Textbox(lines=8, label="")

            db_out = gr.Textbox(label="Database Results / Converter Output", lines=12)

            run_btn.click(
                run_query,
                inputs=[email_in, query_in],
                outputs=[status_out, agent_out, mql_out, db_out]
            )


        # =============================================================
        # TAB 2 — Policy Documentation Q&A
        # =============================================================
        with gr.Tab("Policy Docs"):
            gr.Markdown("### Ask a question about policy documents.")

            policy_question = gr.Textbox(
                label="Policy Question",
                placeholder="Example: What are the responsibilities of managers in the performance review process?",
                lines=2,
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
