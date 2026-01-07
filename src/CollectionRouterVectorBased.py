import json
import numpy as np
from typing import Dict, List
# from sentence_transformers import SentenceTransformer
from llm.LLMFactory import LLMFactory
from llm.BedrockJSONParser import BedrockResolverOutputParser
import json
import asyncio




# class CollectionRouterVectorBased:
#     def __init__(self, embedding_file="./json_repo/routing_embeddings.json", model_name="BAAI/bge-small-en-v1.5"):
#         self.model = SentenceTransformer(model_name)
#         self.collection_data = self._load_embeddings(embedding_file)

#     @staticmethod
#     def _load_embeddings(file_path: str):
#         with open(file_path, "r") as f:
#             return json.load(f)

#     @staticmethod
#     def cosine_similarity(a, b):
#         a, b = np.array(a), np.array(b)
#         return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

#     def top_k_collections(self, query: str, k: int = 3) -> List[Dict]:
#         query_emb = self.model.encode(query)
#         scores = []

#         for name, data in self.collection_data.items():
#             score = self.cosine_similarity(query_emb, data["embedding"])
#             scores.append({"collection_name": name, "score": score})

#         return sorted(scores, key=lambda x: x["score"], reverse=True)[:k]


class CollectionRouterVectorBased:
    def __init__(self):
        pass


    async def top_k_collections(self, query: str, k: int = 3) -> List[Dict]:

        with open("./json_repo/database_content.json", "r") as f:
            collections_metadata = json.load(f)

        collections_json = json.dumps(collections_metadata, indent=2)
        SYSTEM_PROMPT = """
            You are a database collection routing agent.

            Your task:
            - Determine which database collection(s) are required to answer the user query.
            - Choose ONLY from the provided collections.
            - If multiple collections are required, return all of them.
            - If no collection matches, return ["base_report"].
            - Follow all rules defined in the collection metadata.
            - Return VALID JSON ONLY. No explanations outside JSON.
        """

        prompt = f"""
            Available collections metadata:
            {collections_json}

            User query:
            "{query}"

            Return JSON in the following format:
            {{
            "collections": ["collection_name"],
            "confidence": 0.0,
            "reason": "short explanation"
            }}
        """


        llm = LLMFactory(
            provider="bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.1
        ).create()

        response = await llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])

        result = BedrockResolverOutputParser.parse(response.content.strip())["collections"]
        return [{"collection_name": name} for name in result]

    

if __name__ == "__main__":
    async def test():
        router = CollectionRouterVectorBased()

        results = await router.top_k_collections(
            query="eduation qulatification of sachin and people in pip?"
        )

        print("Top match:", results)

    asyncio.run(test())
