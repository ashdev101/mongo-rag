import json
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from SemanticDictionaryProcessor import SemanticDictionaryProcessor

class RoutingEmbeddingBuilder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model = SentenceTransformer(model_name)

    def generate_embeddings(self, routing_data: List[Dict]):
        result = {}

        for item in routing_data:
            collection = item["collection_name"]
            keywords = " ".join(item["routing_keywords"])
            embedding = self.model.encode(keywords).tolist()

            result[collection] = {
                "keywords": item["routing_keywords"],
                "embedding": embedding
            }

        return result
    
    def generate_embeddings_extra_context(self, routing_data: List[Dict]):
        result = {}

        for item in routing_data:
            collection = item["collection_name"]

            # Safely extract lists, fallback to empty list
            routing_keywords = item.get("routing_keywords", [])
            synonyms = item.get("synonyms", [])
            key_fields = item.get("key_fields", [])
            intent_patterns = item.get("intent_patterns", [])

            # Merge all routing-related text
            combined_text = " ".join(
                routing_keywords +
                synonyms +
                key_fields +
                intent_patterns
            )

            print("Combined Text:", combined_text)

            # Generate embedding
            embedding = self.model.encode(combined_text).tolist()

            # Store result
            result[collection] = {
                "routing_keywords": routing_keywords,
                "synonyms": synonyms,
                "key_fields": key_fields,
                "intent_patterns": intent_patterns,
                "embedding": embedding
            }

        return result


    def save_embeddings(self, data: Dict, file_path: str = "./json_repo/routing_embeddings.json"):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved routing embeddings to: {file_path}")


if __name__ == "__main__":
    processor = SemanticDictionaryProcessor("./json_repo/database_summary.json")
    # routing_data = processor.get_collection_routing_list()
    routing_data = processor.get_collection_embedding_list()
    # print("Synonym to Collection Mapping:" , json.dumps(routing_data, indent=2))

    builder = RoutingEmbeddingBuilder()
    embeddings = builder.generate_embeddings_extra_context(routing_data)
    builder.save_embeddings(embeddings)
