import os
from llm.LLMFactory import LLMFactory
from llm.BedrockJSONParser import BedrockResolverOutputParser
from memory.memorymanager import get_chat_history
import json
import asyncio


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
  "query": "<final query text>"
}

If you violate any rule above, the output is invalid.
"""

async def resolve_conversation(query, email):
    llm = LLMFactory(
        provider="bedrock",
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ).create()
    history = await get_chat_history(email)
    system_message = CONVERSATION_RESOLVER_PROMPT
    user_message = f"""History:\n{history}\nUser query:\n{query}"""
    response = await llm.ainvoke([{"role": "system", "content": system_message}, {"role": "user", "content": user_message}])
    return BedrockResolverOutputParser.parse(response.content.strip())["query"]

if __name__ == "__main__":
    user_query = "Is it correct ?"
    print(resolve_conversation(user_query, "user-email"))

