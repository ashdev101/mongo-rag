from Mongo import NaturalLanguageToMQL
from langchain_core.messages import HumanMessage
from langgraph_sample import access_agent

email : str = "EMAIL OVER HERE"
NATURAL_LANGUAGE_QUERY : str = "what is my managers email id?"

Response = Router_gpt(query=NATURAL_LANGUAGE_QUERY)

if Response == "DOCUMENT":
    state = {
    "email": email,
    "designation": "",
    "department" : "",
    "region" : "",
    "question": "",
    "intent": "",
    "decision": "",
    "messages": [HumanMessage(content=NATURAL_LANGUAGE_QUERY)],
    "modified_query" : ""
}

    result = access_agent.invoke(state)
    print(result)
    print(result["decision"])

    if(result["decision"] == "Allowed"):
        converter = NaturalLanguageToMQL()
        # converter.convert_to_mql_and_execute_query(result["modified_query"]) if result["modified_query"] else converter.convert_to_mql_and_execute_query(result["question"])
        converter.convert_to_mql_and_execute_query(result["modified_query"])
        converter.print_results()
    else:
        print("Access Denied. Cannot execute the query.")
elif Response == "POLICY":
    print("The query is related to policy. Redirecting to policy agent...")
    # Add logic to handle policy-related queries
else Response == "BOTH":
    print("The query is BOTH")