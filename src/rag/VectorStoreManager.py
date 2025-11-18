import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

CHROMA_BASE_DIR = "chroma_store"
DEFAULT_COLLECTION = "documents"  # one single vectorstore

class VectorStoreManager:
    def __init__(self, persist_base=CHROMA_BASE_DIR, default_collection=DEFAULT_COLLECTION):
        self.persist_base = persist_base
        self.default_collection = default_collection
        self.embeddings = OpenAIEmbeddings()

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
