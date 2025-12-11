import io
import contextlib
from Mongo import NaturalLanguageToMQL
from langchain_core.messages import HumanMessage, AIMessage
from langgraph_sample import access_agent, get_session_state, update_session_state, summarization_agent_node

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
    return "<Unable to retrieve results from NaturalLanguageToMQL. Check implementation.>"

class QueryProcessor:

    def __init__(self):
        self.converter = None  # Will be initialized per query with the actual user query

    def process(self, email: str, nl_query: str, user_profile: dict = None, needs_routing: bool = False):
        """
        Runs the access agent (LangGraph workflow with unified agent node), checks permission,
        and converts the natural language query into MQL.
        Returns a dict with status, agent_output, generated_mql and db_results (string).
        
        Args:
            email: User email
            nl_query: Natural language query
            user_profile: Optional user profile dict (to avoid duplicate fetch)
            needs_routing: Whether routing is needed (True for Combined tab, False for MQL Agent tab)
        """
        # Fetch user_profile if not provided (unified_agent_node will also fetch, but we need it for state initialization)
        if not user_profile:
            from langgraph_sample import fetch_user_profile
            user_profile = fetch_user_profile(email)
        
        # Use user_profile if available, otherwise set defaults
        if user_profile:
            employee_code = user_profile.get("employee_code", 0)
            designation = user_profile.get("designation", "")
            department = user_profile.get("department", "")
            region = user_profile.get("region", "")
        else:
            # Fallback: set defaults (unified_agent_node will fetch)
            employee_code = 0
            designation = ""
            department = ""
            region = ""
        
        # Load session state (automatically clears previous email's state if email changed)
        session_state = get_session_state(email)
        
        # Load chat history from MongoDB only if not cached (first time or cleared)
        # Otherwise use cached version (faster, no MongoDB read)
        chat_history_messages = session_state.get("chat_history_messages")
        if not chat_history_messages:
            from memory.memorymanager import get_chat_history_as_messages
            chat_history_messages = get_chat_history_as_messages(email) or []
            session_state["chat_history_messages"] = chat_history_messages
        
        # Ensure chat_history_messages is a list (not None)
        if not chat_history_messages:
            chat_history_messages = []
        
        # Check chat history cache for exact or very similar query (strict matching to avoid hallucinations)
        cached_answer = None
        if chat_history_messages:
            current_query_lower = nl_query.lower().strip()
            # Check last 10 messages for exact match (most recent first)
            for msg in reversed(chat_history_messages[-10:]):
                user_msg = msg.get("user", "").lower().strip()
                # Exact match (strict - no fuzzy matching to avoid hallucinations)
                if user_msg == current_query_lower:
                    cached_answer = msg.get("assistant", "")
                    print(f"✅ Found cached answer in chat history for query: {nl_query}")
                    break
        
        # If cached answer found, return it immediately (no agent call needed)
        if cached_answer:
            return {
                "status": "Allowed",
                "agent_output": {
                    "needs_clarification": False,
                    "final_clarified_query": nl_query,
                    "decision": "Allowed",
                    "cached": True
                },
                "mql": nl_query,
                "db_results": cached_answer,
                "questions": []  # No questions for cached responses
            }
        
        # Initialize state for LangGraph workflow
        state = {
            "needs_clarification": False,
            "clarification_question": "",
            "email": email,
            "employee_code": employee_code,
            "designation": designation,
            "department": department,
            "region": region,
            "question": nl_query,
            "original_query": nl_query,  # Preserve original query for summarization agent
            "intent": "",
            "decision": "",
            "messages": [HumanMessage(content=nl_query)],
            "modified_query": "",
            "chat_history_loaded": True,  # Always true now (either from cache or MongoDB)
            "chat_history_messages": chat_history_messages,
            "clarification_progress": session_state.get("clarification_progress", {
                "original_query": "",
                "pending_ambiguities": {},
                "resolved_ambiguities": {}
            }),
            "final_clarified_query": "",
            "user_profile": user_profile or session_state.get("user_profile"),
            "needs_routing": needs_routing,
            "route": None,
            "questions": []
        }

        # invoke the access agent (LangGraph workflow with unified agent node)
        result = access_agent.invoke(state)
        print("Access Agent Result:" , result)

        # Save session state for next turn
        # Note: chat_history_messages is updated in app.py via update_chat_history() after each turn
        update_session_state(email,
            clarification_progress=result.get("clarification_progress", session_state.get("clarification_progress", {})),
            user_profile=result.get("user_profile", session_state.get("user_profile"))
        )

        # Check for errors first
        if result.get("error"):
            error_msg = result.get("decision") or result.get("error") or "An error occurred. Please try again."
            return {
                "status": "Error",
                "agent_output": result,
                "mql": error_msg,
                "db_results": error_msg,
                "questions": []  # No questions for errors
            }

        needs_clarification = result.get("needs_clarification", False)
        clarification_question = result.get("clarification_question", "")
        decision = result.get("decision", "")
        modified_query = result.get("modified_query", "")
        route = result.get("route")  # For Combined tab
        
        # If clarification needed, return early
        if needs_clarification:
            questions = result.get("questions", [])
            if len(questions) == 1:
                clarification_text = questions[0]
            else:
                clarification_text = "Please clarify the following:\n\n"
                for i, q in enumerate(questions, 1):
                    clarification_text += f"{i}. {q}\n"
            
            return {
                "status": "Needs Clarification",
                "agent_output": {**result, "questions": questions},  # Ensure questions are in agent_output
                "mql": clarification_text,
                "db_results": clarification_text,
                "questions": questions,  # Return questions as separate field for app.py
                "route": route
            }
        
        # FIX: Check access denied BEFORE applying RBAC (don't waste time on RBAC if access denied)
        if decision != "Allowed":
            # Extract access denied reason from decision if available
            access_denied_reason = decision if decision else "Access Denied"
            return {
                "status": "Access Denied",
                "agent_output": result,
                "mql": modified_query or result.get("question", nl_query),
                "db_results": access_denied_reason,
                "questions": []  # No questions for access denied
            }
        
        # ===== PHASE 8B: RBAC (Applied at MongoDB Aggregation Level) =====
        # Get user_profile from result (set by unified_agent_node)
        user_profile = result.get("user_profile")
        # Priority: final_clarified_query (from unified_agent_node, already enhanced) > modified_query > question
        final_clarified_query = result.get("final_clarified_query") or modified_query or result.get("question") or nl_query
        
        # Phase 7 (Query Enhancement) already added employee_code in unified_agent_node
        # So we use final_clarified_query directly (it's already enhanced)
        nl_for_converter = final_clarified_query
        
        # Note: RBAC is currently applied via query text modification (rbac_tool.apply_rbac)
        # TODO: Future enhancement - apply RBAC at MongoDB aggregation level using AggregationRBAC class
        # For now, keep current approach for HR users
        if (user_profile and 
            user_profile.get("department", "").lower() in ["human resources", "hr", "human resource"]):
            # Fetch RBAC permissions only now (lazy loading - only when needed)
            from langgraph_sample import fetch_rbac_permissions
            rbac_permissions = fetch_rbac_permissions(user_profile.get("employee_code", 0))
            
            if rbac_permissions and rbac_permissions.get("allowed_regions"):
                from rbac_tool import apply_rbac
                try:
                    rbac_result = apply_rbac.invoke({
                        "question": nl_for_converter,
                        "allowed_regions": rbac_permissions["allowed_regions"],
                        "allowed_grades": rbac_permissions["allowed_grades"],
                        "department_exceptions": rbac_permissions["department_exceptions"]
                    })
                    nl_for_converter = rbac_result["final_query"]
                    print(f"✅ Applied RBAC constraints to query (Phase 8B)")
                except Exception as e:
                    print(f"⚠️ Error applying RBAC: {e}, using original query")
        
        print(f"Final query for MongoDB Agent: {nl_for_converter[:100]}...")

        # Update state with final query (after RBAC and employee_code addition)
        # Preserve original_query for summarization agent
        result["final_clarified_query"] = nl_for_converter
        result["original_query"] = result.get("original_query") or nl_query  # Ensure original_query is set
        
        # Check if this is a formatting request (skip MongoDB Agent)
        skip_mongo_agent = result.get("skip_mongo_agent", False)
        
        # Initialize variables (will be set in if/else blocks below)
        db_results = ""
        is_summarized = False
        agg_pipeline = None
        
        if skip_mongo_agent:
            # Formatting request detected - workflow already handled summarization
            # db_results is already reformatted by summarization_agent_node in workflow
            # Just read the results from workflow (no MongoDB execution needed)
            print("Formatting request - workflow already handled summarization, skipping MongoDB Agent")
            
            # Read results from workflow (already summarized)
            db_results = result.get("db_results", "")
            is_summarized = result.get("is_summarized", False)
            agg_pipeline = None  # No MongoDB query for formatting requests
        else:
            # ===== QA TESTING MODE: MOCK MONGODB AGENT =====
            # MongoDB Agent execution commented out for QA testing
            # Returns simple "Access Granted" message instead of executing actual MongoDB query
            print("QA MODE: Returning Access Granted (MongoDB Agent skipped)")
            
            # Mock response - simple "Access Granted" message
            db_results = "Access Granted"
            is_summarized = False  # No summarization in mock mode
            agg_pipeline = None  # No actual pipeline in mock mode
            
            # Update result with mock MongoDB results
            result["db_results"] = db_results
            result["agg_pipeline"] = agg_pipeline
            
            # ===== ORIGINAL CODE (COMMENTED FOR QA TESTING) =====
            # # Normal query - Execute MongoDB Agent with updated query (after RBAC/employee_code)
            # print(f"🔄 Executing MongoDB Agent with query: {nl_for_converter[:100]}...")
            # 
            # # Initialize converter with current query to generate relevant example
            # self.converter = NaturalLanguageToMQL(user_query=nl_for_converter)
            #
            # # Some converter implementations expect convert_to_mql_and_execute_query to accept None or empty strings:
            # try:
            #     self.converter.convert_to_mql_and_execute_query(nl_for_converter)
            # except Exception as e:
            #     return {
            #         "status": "Error",
            #         "agent_output": result,
            #         "mql": nl_for_converter,
            #         "db_results": f"Converter execution failed: {e}",
            #         "questions": []  # No questions for errors
            #     }
            #
            # # obtain results robustly
            # db_output = get_converter_results(self.converter)
            #
            # # default agg pipeline
            # agg_pipeline = None
            #
            # # If converter returned structured data, extract fields
            # if isinstance(db_output, dict):
            #     # unmasked_output may be present
            #     db_results = db_output.get("unmasked_output") or db_output
            #     agg_pipeline = db_output.get("agg_pipeline")
            # else:
            #     # fallback: string result
            #     db_results = db_output
            #     # try to get pipeline directly from converter's db wrapper if available
            #     try:
            #         agg_pipeline = getattr(self.converter.db_wrapper, "last_agg_pipeline", None)
            #     except Exception:
            #         agg_pipeline = None
            # 
            # # Update result with MongoDB results
            # result["db_results"] = db_results
            # result["agg_pipeline"] = agg_pipeline
        
        # ===== QA TESTING MODE: SKIP SUMMARIZATION AGENT =====
        # Summarization Agent execution commented out for QA testing
        # Using mock db_results directly without summarization
        print("QA MODE: Skipping Summarization Agent")
        
        # ===== ORIGINAL CODE (COMMENTED FOR QA TESTING) =====
        # # Execute Summarization Agent only for normal queries (formatting requests already summarized in workflow)
        # if not skip_mongo_agent:
        #     # Normal query - summarization happens here in QueryProcessor
        #     print(f"🔄 Executing Summarization Agent...")
        #     summarization_state = {**result, "original_query": result.get("original_query") or nl_query}
        #     summarization_result = summarization_agent_node(summarization_state)
        #     result.update(summarization_result)
        # else:
        #     # Formatting request - summarization already done in workflow, just use existing results
        #     print(f"⏭️ Skipping Summarization Agent (already handled in workflow for formatting request)")
        
        print("Final Result (after MongoDB/Summarization):" , result)

        # Read final results from state (summarization may have updated them for normal queries)
        # For formatting requests: use values already set from workflow
        # For normal queries: use values updated by summarization_agent_node
        final_db_results = result.get("db_results", db_results)
        final_is_summarized = result.get("is_summarized", is_summarized)
        # agg_pipeline is already set correctly above (None for formatting requests, actual pipeline for normal queries)

        output = {
            "status": "Allowed",
            "agent_output": result,
            "mql": nl_for_converter,
            "db_results": final_db_results,  # This is the FINAL result (summarized for normal queries, or from workflow for formatting requests)
            "agg_pipeline": agg_pipeline,  # From MongoDB execution (None for formatting requests)
            "questions": [],  # No questions for successful queries
            "is_summarized": final_is_summarized  # Indicates if summarization was applied
        }
        print("Final Output:" , output)
        return output
    

# querProcessor = QueryProcessor()

# ans = querProcessor.process("mehaboobb@tataplay.com" , "when should I wish my manager")
# print(ans)