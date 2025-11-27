import io
import contextlib
from Mongo import NaturalLanguageToMQL
from langchain_core.messages import HumanMessage, AIMessage
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
            "needs_clarification": False,
            "clarification_question": "",
            "email": email,
            "employee_code": 0,
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
        print("Access Agent Result:" , result)

        needs_clarification = result.get("needs_clarification")
        clarification_question = result.get("clarification_question")
        decision = result.get("decision")
        modified_query = result.get("modified_query")
        print("modified query" , modified_query)

        # Save conversation to chat history for future context
        try:
            from memorymanager import push_convo_pair
            # Get the conversation messages
            messages = result.get("messages", [])
            if messages:
                user_msg = None
                assistant_msg = None
                for msg in reversed(messages):
                    if (hasattr(msg, 'type') and msg.type == "human") or isinstance(msg, HumanMessage):
                        if not user_msg:
                            user_msg = msg.content
                    elif (hasattr(msg, 'type') and msg.type == "ai") or isinstance(msg, AIMessage):
                        if not assistant_msg:
                            assistant_msg = msg.content
                
                if user_msg:
                    # Use memorymanager's push_convo_pair function
                    push_convo_pair(email, user_msg, assistant_msg or clarification_question or "")
        except Exception as e:
            print(f"Warning: Could not save chat history: {e}")

        if needs_clarification:
            return {
                "status": "Needs Clarification",
                "agent_output": result,
                "mql": result.get("clarification_question"),
                "db_results": clarification_question
            }
        if decision != "Allowed":
            return {
                "status": "Access Denied",
                "agent_output": result,
                "mql": modified_query or result.get("question"),
                "db_results": "Access Denied"
            }

        # Convert to MQL + Execute
        nl_for_converter = modified_query if modified_query else result.get("question")

        # Some converter implementations expect convert_to_mql_and_execute_query to accept None or empty strings:
        try:
            self.converter.convert_to_mql_and_execute_query(nl_for_converter)
        # except TypeError:
        #     # fallback - try calling with no args (if library differs)
        #     try:
        #         self.converter.convert_to_mql_and_execute_query()
        #     except Exception as e:
        #         return {
        #             "status": "Error",
        #             "agent_output": result,
        #             "mql": nl_for_converter,
        #             "db_results": f"Converter execution failed: {e}"
        #         }
        except Exception as e:
            return {
                "status": "Error",
                "agent_output": result,
                "mql": nl_for_converter,
                "db_results": f"Converter execution failed: {e}"
            }

        # obtain results robustly
        db_output = get_converter_results(self.converter)

        output =  {
            "status": "Allowed",
            "agent_output": result,
            "mql": nl_for_converter,
            "db_results": db_output
        }
        print("Final Output:" , output)
        return output
    

# querProcessor = QueryProcessor()

# ans = querProcessor.process("ashwinit@tatasky.com" , "what is the dob of vikram kaushik")
# print(ans)