import json
import re
from QueryProcessor import QueryProcessor
from rag.queryengine import query_main_store
from query_router import router as query_router
from memory.memorymanager import push_convo_pair
from onepager.pdf_generator import generate_one_pager

from OnePager import OnePager

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
def combined_execute(email, question):
    """
    1. Check for special commands (/onepager)
    2. Call router for regular queries
    3. Execute the actual target agent
    4. Store conversation history
    5. Return router output + executed result
    """

    def safe_json(v):
        try:
            return json.dumps(v, indent=2, default=str)
        except Exception:
            return str(v)

    try:
        # Check for /onepager @<employee_code> command (e.g., /onepager @1001)
        onepager_match = re.search(r'/onepager\s+@(\d+)', question.strip(), re.IGNORECASE)
        
        if onepager_match:
            employee_code = onepager_match.group(1)
            
            # Generate OnePager report
            onepager = OnePager()
            try:
                report = onepager.generate_report_aggregation(employee_code, email)
                
                # Format output
                router_out_str = safe_json({
                    "route": "onepager",
                    "command": f"/onepager @{employee_code}",
                    "employee_code": employee_code
                })
                
                if report.get("status") == "success":
                    # Format as text
                    final_output_string = generate_one_pager(report)
                    #final_output_string = onepager.format_report_text(report)
                    
                    # Save to conversation history
                    try:
                        push_convo_pair(
                            email=email,
                            user_msg=question,
                            bot_msg=final_output_string
                        )
                    except Exception as e:
                        print("Failed to push conversation history:", e)
                    
                    return router_out_str, final_output_string
                else:
                    error_msg = report.get("message", "Error generating report")
                    return router_out_str, error_msg
                    
            finally:
                onepager.close()
        
        # Regular query routing
        route_result = query_router(question, email)
        router_out_str = safe_json(route_result)

        route = route_result.get("route")
        query = route_result.get("query", "")

        # ===== EXECUTE TARGET ENGINE =====
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
        final_output_string = ""
        try:
            if route == "document":
                push_convo_pair(
                    email=email,
                    user_msg=question,
                    bot_msg=final_output_dict.get("db_results")
                )
                final_output_string = final_output_dict.get("db_results")

            elif route == "policy":
                push_convo_pair(
                    email=email,
                    user_msg=question,
                    bot_msg=final_output_dict.get("policy_answer")
                )
                final_output_string = final_output_dict.get("policy_answer")

        except Exception as e:
            print("Failed to push conversation history:", e)

        return router_out_str, final_output_string

    except Exception as e:
        err = safe_json({"error": str(e)})
        return err, err
