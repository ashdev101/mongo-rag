import os
from llm.LLMFactory import LLMFactory
from memory.memorymanager import get_chat_history


CONVERSATION_RESOLVER_PROMPT = """
You are a STRICT conversation resolver for an HR assistant.

You are NOT an answering agent.
You are a query normalizer ONLY.

Your task:
- Determine whether the user query depends on prior chat history
  due to pronouns or implicit references.
- If yes, rewrite the query to be self-contained by resolving
  references ONLY to abstract roles (manager, reviewer, employee, HR).
- If no, return the query EXACTLY as provided.

ABSOLUTE RULES (HARD CONSTRAINTS):
- You MUST NOT answer the question.
- You MUST NOT use chat history to supply facts, numbers, or conclusions.
- You MUST NOT infer or assume missing information.
- You MUST NOT say that data exists or does not exist.
- You MUST NOT explain, justify, or add commentary.
- You MUST NOT rephrase statements into answers.
- You MUST NOT mention systems, records, balances, discrepancies, or actions.
- You MUST NOT include names, emails, IDs, or any PII.

Input handling rules:
- If the input is a statement, reaction, or opinion → return it unchanged.
- If the input is a question AND does not reference prior entities → return it unchanged.
- If the input references history AND required context is NOT present →
  return the query unchanged and mark it unresolved.

Output format (STRICT JSON ONLY):

{
  "resolved": true | false,
  "query": "<final query text>"
}

Definitions:
- resolved = true → query was rewritten using chat history
- resolved = false → no rewrite was needed or possible

If you violate any rule above, the output is invalid.
"""

def resolve_conversation(query, email):
    llm = LLMFactory(
        provider="bedrock",
        model="qwen.qwen3-vl-235b-a22b",
    ).create()
    history = get_chat_history(email)
    system_message = CONVERSATION_RESOLVER_PROMPT
    user_message = f"""History:\n{history}\nUser query:\n{query}"""
    response = llm.invoke([{"role": "system", "content": system_message}, {"role": "user", "content": user_message}])
    return response.content

if __name__ == "__main__":
    sample_chat_history_document = {
  "_id": {
    "$oid": "6955127b77165e96d0a46f68"
  },
  "email": "Shayanta.Chaudhuri@tataplay.com",
  "history": [
    {
      "user": "how many leaves i have in balance",
      "assistant": "Based on the records in the system, there are no leave balance records found for your employee code (7011). This could mean that you have not taken any leaves yet, or the leave balance data has not been recorded in the system.\n\nPlease contact your HR team to get updated information about your leave balance.",
      "ts": {
        "$date": "2025-12-31T17:39:30.708Z"
      }
    },
    {
      "user": "i think i do have taken the leaves ",
      "assistant": "Based on the search results, **no leave records were found** for your employee code (7011) in the leave transaction system.\n\nThis means either:\n- You have not applied for any leaves yet, or\n- Your leave applications may not have been recorded in the system\n\nIf you believe you have taken leaves, I would recommend reaching out to your HR team to verify your leave records.",
      "ts": {
        "$date": "2025-12-31T18:01:17.827Z"
      }
    },
    {
      "user": "tell me about my pending leaves ",
      "assistant": "Based on the query results, you currently have **no pending leaves**.\n\nThis means there are no leave requests with \"SUBMITTED\" status or \"AWAITING\" approval status associated with your employee code (7011). \n\nIf you have recently applied for leave, it may have already been approved or processed. Would you like me to check your leave history or leave balance instead?",
      "ts": {
        "$date": "2025-12-31T18:05:39.378Z"
      }
    },
    # {
    #   "user": "who approves it ",
    #   "assistant": "The HR SPOC or the Reviewer approves it, depending on the approval stage.",
    #   "ts": {
    #     "$date": "2025-12-31T18:06:14.755Z"
    #   }
    # },
    # {
    #   "user": "what is the name of my reviewer",
    #   "assistant": "Your reviewer's name is **Ashwin Shukla**.",
    #   "ts": {
    #     "$date": "2025-12-31T18:07:47.929Z"
    #   }
    # },
    # {
    #   "user": "what is his email address",
    #   "assistant": "Your email address is: **Shayanta.Chaudhuri@tataplay.com**",
    #   "ts": {
    #     "$date": "2025-12-31T18:10:01.187Z"
    #   }
    # }
  ],
  "updated_at": {
    "$date": "2025-12-31T18:10:01.187Z"
  }
}
    chat_history = """User: "Tell me about my goal status and reviewer?
    Assistant: "Your goal status is APPROVED , and your review is amit sing "
    User: "Any leaves taken so far by me?"
    Assistant: "You have in total 10 leaves taken"."""
    user_query = "Is it correct ?"
    print(resolve_conversation(user_query, sample_chat_history_document["history"]))

