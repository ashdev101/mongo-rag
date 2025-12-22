import os
# from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

CHROMA_BASE_DIR = "chroma_store"
DEFAULT_COLLECTION = "documents"  # one single vectorstore

class VectorStoreManager:
    def __init__(self, persist_base=CHROMA_BASE_DIR, default_collection=DEFAULT_COLLECTION):
        self.persist_base = persist_base
        self.default_collection = default_collection
        self.embeddings = BedrockEmbeddings(
                            model_id = "amazon.titan-embed-text-v2:0",
                            region_name = os.getenv("AWS_REGION")
                        )

    def get_default_store(self):
        dir_path = os.path.join(self.persist_base, self.default_collection)
        os.makedirs(dir_path, exist_ok=True)

        return Chroma(
            persist_directory=dir_path,
            embedding_function=self.embeddings
        )

    def add_texts(self, texts):
        store = self.get_default_store()
        store.add_texts(texts)
        store.persist()
        return store
