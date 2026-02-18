from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
# from langchain_openai import ChatOpenAI
# from rag.VectorStoreManager import VectorStoreManager
from rag.MongoVectorStoreManager import MongoVectorStoreManager #VectorStoreManager
from llm.LLMFactory import LLMFactory
from dotenv import load_dotenv
import os
from db.common_operations import findUser

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MODEL_NAME = "gpt-4o-mini"

PROMPT = PromptTemplate(
    template="""
    Context:
    {context}

    Question:
    {question}

    User Info :
    {user_info}


    You are Tata Play's official HR Helpdesk Assistant.

    Your responsibilities:
    - Respond as an internal HR representative.
    - Provide clear, direct, and professional answers to employee queries.
    - NEVER mention context, documents, sources, policies, or internal data.
    - NEVER explain how you arrived at an answer.

    Knowledge usage:
    - Use only the knowledge available to you.
    - Do not assume or invent information.

    If you can answer the question:
    - Provide a direct and complete response.

    If you cannot fully answer the question:
    - Do NOT state that information is missing.Rather acknowledge what you do know based on the context provided.
    - If you cannot provide or acknowledge certain information, clearly state which parts you are unable to address.
    - Offer to assist with related queries within your knowledge scope.
    - Politely guide the employee by suggesting relevant alternate or follow-up questions that you are able to help with based on the context.
    - Phrase suggestions as helpful prompts.if context allows.

    Tone & style:
    - Professional, helpful, and HR-appropriate.
    - Concise but supportive.

    Response Closing Requirement:
    - Always end with: "If you have any more questions or need further assistance, feel free to ask!"
    - Use variations of this closing line to maintain a natural tone, but ensure the offer for further assistance is always included.
    - The closing sentence must be generic and must not reference the previous query.
    
""",
    input_variables=["context", "question"]
)

# llm = ChatOpenAI(
#     api_key=os.getenv("OPENAI_API_KEY"),
#     model_name=MODEL_NAME,
#     temperature=0.4
# )

llm = LLMFactory(
        provider="bedrock",
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ).create()

vector_manager = MongoVectorStoreManager()

# def retrieve_docs(question: str):
#     retriever = vector_manager.store.as_retriever()
#     return retriever.get_relevant_documents(question)

async def retrieve_docs(question: str):
    retriever = vector_manager.get_retriever()
    return await retriever.ainvoke(question)


async def query_main_store(question: str , email: str) -> str:
    docs = await retrieve_docs(question)
    user_info = findUser(email=email, employee_code=None)
    # print("docs" , docs)

    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = PROMPT.format(
        context=context,
        question=question,
        user_info=user_info
    )

    response = await llm.ainvoke(prompt)

    return response.content
