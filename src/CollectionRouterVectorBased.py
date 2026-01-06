import json
import numpy as np
from typing import Dict, List
from sentence_transformers import SentenceTransformer


class CollectionRouterVectorBased:
    def __init__(self, embedding_file="./json_repo/routing_embeddings.json", model_name="./models/BAAI.bge-small-en-v1.5"):
        self.model = SentenceTransformer(model_name)
        self.collection_data = self._load_embeddings(embedding_file)

    @staticmethod
    def _load_embeddings(file_path: str):
        with open(file_path, "r") as f:
            return json.load(f)

    @staticmethod
    def cosine_similarity(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def top_k_collections(self, query: str, k: int = 3) -> List[Dict]:
        query_emb = self.model.encode(query)
        scores = []

        for name, data in self.collection_data.items():
            score = self.cosine_similarity(query_emb, data["embedding"])
            scores.append({"collection_name": name, "score": score})

        return sorted(scores, key=lambda x: x["score"], reverse=True)[:k]
    

if __name__ == "__main__":
    router = CollectionRouterVectorBased(embedding_file="routing_embeddings.json")

    results = router.top_k_collections(
        query="people joined the commercial department this year?"
    )

    print("Top match:", results)
