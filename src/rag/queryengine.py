from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
# from langchain_openai import ChatOpenAI
from rag.VectorStoreManager import VectorStoreManager
from llm.LLMFactory import LLMFactory
from dotenv import load_dotenv
import os

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MODEL_NAME = "gpt-4o-mini"

PROMPT = PromptTemplate(
    template="""
    Context:
    {context}

    Question:
    {question}

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

vector_manager = VectorStoreManager()

def retrieve_docs(question: str):
    store = vector_manager.get_default_store()
    retriever = store.as_retriever()
    return retriever.get_relevant_documents(question)

async def query_main_store(question: str) -> str:
    docs = retrieve_docs(question)

    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = PROMPT.format(
        context=context,
        question=question
    )

    response = await llm.ainvoke(prompt)

    return response.content
