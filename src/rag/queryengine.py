from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from rag.VectorStoreManager import VectorStoreManager
from dotenv import load_dotenv
import os

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MODEL_NAME = "gpt-4o-mini"

PROMPT = PromptTemplate(
    template="""
Context: {context}

Question: {question}

Provide a concise answer based on the context.
If not enough info, say: "Not enough information in the context."
""",
    input_variables=["context", "question"]
)

llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name=MODEL_NAME,
    temperature=0.4
)

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
