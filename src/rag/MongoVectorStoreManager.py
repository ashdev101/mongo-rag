import os
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DATABASE_VECTOR")
COLLECTION_NAME = "Sample_Vector"
INDEX_NAME = "vector-test"

class MongoVectorStoreManager:
    def __init__(self):
        self.embeddings = BedrockEmbeddings(
                            model_id = "amazon.titan-embed-text-v2:0",
                            region_name = os.getenv("AWS_REGION")
                        )
        # self.embeddings = OpenAIEmbeddings()

        self.client = MongoClient(os.getenv("MONGODB_URI"))
        self.collection = self.client[DB_NAME][COLLECTION_NAME]

        self.store = MongoDBAtlasVectorSearch(
            collection=self.collection,
            embedding=self.embeddings,
            index_name="vector-test"
        )

    def add_texts(self, texts, metadatas=None):
        return self.store.add_texts(texts=texts, metadatas=metadatas)


    def get_retriever(self, k=5):
        chunks =  self.store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": k,
                "score_threshold": 0.15
            }
        )

        print("chunks" , chunks)
        return chunks


    def similarity_search(self, query, k=5):
        return self.store.similarity_search(query, k=k)
