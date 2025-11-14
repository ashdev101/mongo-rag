from src.app import QueryProcessor
processor = QueryProcessor()

def run_query(email, question):
    """
    Function used by Gradio UI.
    """
    try:
        output = processor.process(email, question)

        status = output["status"]
        agent_output = output["agent_output"]
        mql = output["mql"]
        db_results = output["db_results"]

        return (
            status,
            str(agent_output),
            mql,
            db_results if db_results else "No results / Access Denied"
        )

    except Exception as e:
        return ("Error", str(e), None, None)


# =====================================================================
# 3. Gradio UI
# =====================================================================
with gr.Blocks(title="MQL Access Agent UI") as demo:

    gr.Markdown("# 🚀 Natural Language → MQL Query System")
    gr.Markdown("Enter your email and natural language query.")

    with gr.Row():
        email_in = gr.Textbox(label="Email", placeholder="your.email@company.com")
        query_in = gr.Textbox(label="Natural Language Query", lines=2)

    run_btn = gr.Button("Run Query")

    with gr.Row():
        status_out = gr.Textbox(label="Decision (Allowed / Denied)")
        mql_out = gr.Textbox(label="Generated MQL Query")

    agent_out = gr.Textbox(label="Agent Raw Output", lines=5)
    db_out = gr.Textbox(label="Database Results", lines=5)

    run_btn.click(
        run_query,
        inputs=[email_in, query_in],
        outputs=[status_out, agent_out, mql_out, db_out]
    )

# Launch
demo.launch()