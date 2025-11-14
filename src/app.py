import io
import gradio as gr
import contextlib
from Mongo import NaturalLanguageToMQL
from langchain_core.messages import HumanMessage
from langgraph_sample import access_agent

# =====================================================================
# Helper: safely get results from converter.print_results()
# =====================================================================
def get_converter_results(converter):
    """
    Try multiple ways to obtain results from NaturalLanguageToMQL instance:
      1. converter.print_results(return_output=True)  -- preferred
      2. capture stdout of converter.print_results()
      3. converter.results   -- fallback attribute if present
    Returns a string (human readable).
    """
    # 1) Preferred: method returns data
    try:
        out = converter.print_results(return_output=True)
        # If it returned a non-string (e.g., list/dict), stringify safely
        if isinstance(out, (list, dict)):
            import json
            return json.dumps(out, indent=2, default=str)
        return str(out)
    except TypeError:
        # method exists but doesn't accept that kwarg -> fall back to capturing stdout
        pass
    except Exception as e:
        # Some other issue when calling with kwarg
        pass

    # 2) Capture printed output
    try:
        sio = io.StringIO()
        with contextlib.redirect_stdout(sio):
            # call without kwargs
            converter.print_results()
        captured = sio.getvalue()
        if captured.strip():
            return captured
    except Exception:
        pass

    # 3) look for a results attribute
    try:
        if hasattr(converter, "results"):
            res = getattr(converter, "results")
            import json
            try:
                return json.dumps(res, indent=2, default=str)
            except Exception:
                return str(res)
    except Exception:
        pass

    # 4) nothing worked
    return "<Unable to retrieve results from NaturalLanguageToMQL. Check implementation.>"

# =====================================================================
# Core Processor Class
# =====================================================================
class QueryProcessor:

    def __init__(self):
        self.converter = NaturalLanguageToMQL()

    def process(self, email: str, nl_query: str):
        """
        Runs the access agent, checks permission,
        and converts the natural language query into MQL.
        Returns a dict with status, agent_output, generated_mql and db_results (string).
        """
        state = {
            "email": email,
            "designation": "",
            "department": "",
            "region": "",
            "question": "",
            "intent": "",
            "decision": "",
            "messages": [HumanMessage(content=nl_query)],
            "modified_query": ""
        }

        # invoke the access agent
        result = access_agent.invoke(state)

        decision = result.get("decision")
        modified_query = result.get("modified_query")

        if decision != "Allowed":
            return {
                "status": "Access Denied",
                "agent_output": result,
                "mql": modified_query or result.get("question"),
                "db_results": "Access Denied by agent"
            }

        # Convert to MQL + Execute
        nl_for_converter = modified_query if modified_query else result.get("question")

        # Some converter implementations expect convert_to_mql_and_execute_query to accept None or empty strings:
        try:
            self.converter.convert_to_mql_and_execute_query(nl_for_converter)
        except TypeError:
            # fallback - try calling with no args (if library differs)
            try:
                self.converter.convert_to_mql_and_execute_query()
            except Exception as e:
                return {
                    "status": "Error",
                    "agent_output": result,
                    "mql": nl_for_converter,
                    "db_results": f"Converter execution failed: {e}"
                }
        except Exception as e:
            return {
                "status": "Error",
                "agent_output": result,
                "mql": nl_for_converter,
                "db_results": f"Converter execution failed: {e}"
            }

        # obtain results robustly
        db_output = get_converter_results(self.converter)

        return {
            "status": "Allowed",
            "agent_output": result,
            "mql": nl_for_converter,
            "db_results": db_output
        }


# =====================================================================
# Gradio glue
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

with gr.Blocks(title="MQL Access Agent UI (robust)") as demo:
    gr.Markdown("# 🚀 Natural Language → MQL Query System (robust)")
    gr.Markdown("Enter your email and natural language query.")

    with gr.Row():
        email_in = gr.Textbox(label="Email", placeholder="your.email@company.com")
        query_in = gr.Textbox(label="Natural Language Query", lines=2, value="give me the name of the people who have resigned in the year 2022 in march?")

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

if __name__ == "__main__":
    demo.launch()
