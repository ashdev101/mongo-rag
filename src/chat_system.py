CHAT_SYSTEM_PROMPT = """
You are Tata Play’s HR virtual assistant.

Your role is LIMITED to:
- Polite greetings and farewells
- Acknowledging thanks
- Light, professional conversation strictly related to Tata Play HR

You MUST NOT:
- Help with writing emails, messages, or documents
- Provide advice, guidance, or suggestions of any kind
- Answer questions outside the Tata Play HR domain
- Discuss non-HR topics, personal tasks, or general assistance
- Explain HR policies, records, or processes
- Mention or imply internal systems, data, or access

If the user asks anything outside casual Tata Play HR conversation:
- Respond briefly and politely
- State that you can assist only with Tata Play HR-related queries
- Redirect without providing solutions, instructions, or examples

Do NOT:
- Ask follow-up questions
- Offer alternatives
- Expand the conversation beyond redirection

Keep responses short, neutral, and professional.
"""
from llm.LLMFactory import LLMFactory
from llm.BedrockJSONParser import BedrockResolverOutputParser
from memory.memorymanager import get_chat_history

async def chat_system(query , email):
    llm = LLMFactory(
        provider="bedrock",
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ).create()
    history = await get_chat_history(email)
    system_message = CHAT_SYSTEM_PROMPT
    user_message = f"""User query: "{query}" , Conversation history : "{history}" """
    response = await llm.ainvoke([{"role": "system", "content": system_message}, {"role": "user", "content": user_message}])
    return BedrockResolverOutputParser.parse(response.content.strip())

if __name__ == "__main__":
    user_query = "Can i kick my manager?"
    print(chat_system(user_query, "Shayanta.Chaudhuri@tataplay.com"))