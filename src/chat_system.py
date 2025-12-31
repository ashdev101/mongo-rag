CHAT_SYSTEM_PROMPT = """
You are Tata Play’s HR virtual assistant.

You can:
- Greet users politely
- Respond to thanks
- Engage in light, professional conversation

You cannot:
- Access employee data
- Answer policy or HR record questions
- Explain internal systems

If a question is outside casual conversation, politely guide the user back. But avoid giving resolutions or access instructions.
"""
from llm.LLMFactory import LLMFactory
from memory.memorymanager import get_chat_history

def chat_system(query , email):
    llm = LLMFactory(
        provider="bedrock",
        model="qwen.qwen3-235b-a22b-2507-v1:0",
    ).create()
    history = get_chat_history(email)
    system_message = CHAT_SYSTEM_PROMPT
    user_message = f"""User query: "{query}" , Conversation history : "{history}" """
    response = llm.invoke([{"role": "system", "content": system_message}, {"role": "user", "content": user_message}])
    return response.content

if __name__ == "__main__":
    user_query = "Can i kick my manager?"
    print(chat_system(user_query, "Shayanta.Chaudhuri@tataplay.com"))