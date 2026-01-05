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

    Instructions:
    - Answer strictly using only the information provided in the Context.
    - Do NOT add assumptions, interpretations, or external knowledge.
    - Do NOT mention document names, policy titles, sources, or internal references.
    - If the Context does not contain sufficient information to answer the question, respond with:
    "I don’t have enough information in the provided context to answer this question."
    - Keep the answer concise, factual, and neutral in tone.
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

def query_main_store(question):
    store = vector_manager.get_default_store()

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=store.as_retriever(),
        chain_type_kwargs={"prompt": PROMPT}
    )

    return qa.run(question)
