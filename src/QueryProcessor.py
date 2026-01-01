import io
import contextlib
from Mongo import NaturalLanguageToMQL
from langchain_core.messages import HumanMessage, AIMessage
from langgraph_sample import access_agent
from CollectionRouter import get_collection
from aggregation.AggregationRBAC import AggregationRBAC

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
    # 1) Preferred: method returns structured data
    try:
        out = converter.print_results(return_output=True)
        print("===="*10,"QueryProcessor.py",'===='*10)
        print("Out:",out)
        # If it returned a dict/list, return it as-is for callers to inspect
        if isinstance(out, (list, dict)):
            return out
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
    return "Sorry , I am unable to process your request at the moment."

class QueryProcessor:

    def __init__(self):
        self.converter = None  # Will be initialized per query with the actual user query

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
        "designation": "",
        "department" : "",
        "region" : "",
        "isSpecialHRUser" : False,
        "department_exception" : [],
        "grade_allowed" : [],
        "region_access" : [],
        "requested_region" : [],
        "requested_grade" : [],
        "requested_department" : [],
        "access_denied" : False,
        "access_denied_regions" : [],
        "access_denied_grades" : [],
        "access_denied_departments" : [],
        "access_message" : "",
        "question": "",
        "intent": "",
        "decision": "",
        "messages": [HumanMessage(content= nl_query)],
        "modified_query" : ""
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
            #from memorymanager import push_convo_pair
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
                
                # if user_msg:
                #     # Use memorymanager's push_convo_pair function
                #     #push_convo_pair(email, user_msg, assistant_msg or clarification_question or "")
        except Exception as e:
            print(f"Warning: Could not save chat history: {e}")

        if needs_clarification:
            return {
                "status": "Needs Clarification",
                "agent_output": result,
                "mql": result.get("clarification_question"),
                "db_results": clarification_question
            }
        if decision != "Access Granted":
            return {
                "status": "Access Denied",
                "agent_output": result,
                "mql": modified_query or result.get("question"),
                "db_results": result["access_message"]
            }

        # Convert to MQL + Execute
        nl_for_converter = modified_query if modified_query else result.get("question")

        # know which collections to use to resolve the query
        collections = get_collection(nl_for_converter , use_rule_based_first=False)
        print("Collections to use for query:", collections)
        aggregationRBAC = AggregationRBAC(
                            user={
                                    "isHR" : result["department"] == "Human Resources",
                                    "employeeCode" : result["employee_code"],
                                    "region" : result.get("requested_region" , []),
                                    "department" : result.get("requested_department" , []),
                                    "grades" : result.get("requested_grade" , [])
                                }
                            )
        # Initialize converter with current query to generate relevant example
        self.converter = NaturalLanguageToMQL(user_query=nl_for_converter, include_collections = collections , aggregationRBAC= aggregationRBAC , userid=result["employee_code"])

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

        # Debug info: show what we received and whether the db wrapper holds a pipeline
        # author: saptarshi-> can delete the following used to debug
        # try:
        #     print("DEBUG: get_converter_results returned type:", type(db_output))
        #     if isinstance(db_output, dict):
        #         print("DEBUG: db_output keys:", list(db_output.keys()))
        #         print("DEBUG: db_output['agg_pipeline']:", db_output.get("agg_pipeline"))
        #     else:
        #         print("DEBUG: db_output (string preview):", str(db_output)[:200])
        # except Exception as e:
        #     print("DEBUG: error while printing db_output info:", e)

        # try:
        #     last_pipe = getattr(self.converter.db_wrapper, "last_agg_pipeline", None)
        #     print("DEBUG: converter.db_wrapper.last_agg_pipeline:", last_pipe)
        # except Exception as e:
        #     print("DEBUG: error getting converter.db_wrapper.last_agg_pipeline:", e)

        # default agg pipeline
        agg_pipeline = None

        # If converter returned structured data, extract fields
        if isinstance(db_output, dict):
            # unmasked_output may be present
            db_results = db_output.get("unmasked_output") or db_output
            agg_pipeline = db_output.get("agg_pipeline")
        else:
            # fallback: string result
            db_results = db_output
            # try to get pipeline directly from converter's db wrapper if available
            try:
                agg_pipeline = getattr(self.converter.db_wrapper, "last_agg_pipeline", None)
            except Exception:
                agg_pipeline = None

        output =  {
            "status": "Allowed",
            "agent_output": result,
            "mql": nl_for_converter,
             "db_results": db_results,
            "agg_pipeline": agg_pipeline,
        }
        print("Final Output:" , output)
        return output
    
if __name__ == "__main__":
    querProcessor = QueryProcessor()

    ans = querProcessor.process("Shayanta.Chaudhuri@tataplay.com" , "give me the people who have resigned in the year 2025 with m1 , m2 grades")
    print(ans)