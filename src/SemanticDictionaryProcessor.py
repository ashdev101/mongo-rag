import json
from typing import List, Dict, Any

class SemanticDictionaryProcessor:
    def __init__(self, semantic_dict_path: str):
        """
        Initialize the processor with the path to the semantic dictionary JSON.
        """
        with open(semantic_dict_path, "r") as f:
            self.semantic_dict = json.load(f)

    def get_collection_routing_list(self, max_routing_keywords_per_entity: int = 20 , include_default_collection: bool = True) -> list:
        """
        Returns a list of dictionaries:
        [
            {
                "collection_name": "<collection_name>",
                "routing_keywords": ["keyword1", "keyword2", ...]
            },
            ...
        ]
        Deduplicates and limits the number of routing keywords per collection.
        """
        collection_routing_list = []

        for entity_name, entity_data in self.semantic_dict.get("entities", {}).items():
            collection_name = entity_data.get("collection")
            routing_keywords = entity_data.get("routing_keywords", [])

            # Deduplicate and normalize
            seen = set()
            _routing_keywords = []
            for s in _routing_keywords:
                s_norm = s.lower().strip()
                if s_norm not in seen:
                    seen.add(s_norm)
                    _routing_keywords.append(s_norm)
                if len(_routing_keywords) >= max_routing_keywords_per_entity:
                    break  # limit number of routing keywords per collection

            collection_routing_list.append({
                "collection_name": collection_name,
                "routing_keywords": routing_keywords
            })

        return collection_routing_list

    def get_clarification_agent_structure(
        self,
        allowed_collections: list = None,
    ) -> dict:
        """
        Returns a dictionary formatted for the Clarification Agent:

        {
            "collections": {
                "<collection_name>": {
                    "<Entity Name>": {
                        "collection": "<collection_name>",
                        "key_fields": [ ... ]
                    }
                }
            },
            "ambiguous_terms": [...],
            "default_reports": [...]
        }

        Params:
        - allowed_collections: list[str] or None
            → If provided, only include entities from these collections.
        - include_default_collection: bool
            → Includes the default_reports list from schema.
        """

        collections_output = {}

        # NORMALIZE allowed collections (None → all allowed)
        allowed_set = set(allowed_collections) if allowed_collections else None

        # Iterate through entities in schema
        for entity_name, entity_data in self.semantic_dict.get("entities", {}).items():

            collection_name = entity_data.get("collection")
            key_fields = entity_data.get("key_fields", [])

            # Filter by allowed collections if provided
            if allowed_set is not None and collection_name not in allowed_set:
                continue

            # Add collection bucket if not exists
            if collection_name not in collections_output:
                collections_output[collection_name] = {}

            # Add entity to the correct collection group
            collections_output[collection_name][entity_name] = {
                "collection": collection_name,
                "key_fields": key_fields
            }

        # Build final structure
        result = {
            "collections": collections_output,
            "ambiguous_terms": self.semantic_dict.get("ambiguous_terms", [])
        }

        return result

    def get_default_collections(self) -> list:
        """
        Returns the default collections list from the semantic dictionary.
        """
        return self.semantic_dict.get("default_collections", [])

    def save_synonym_mapping(self, output_path: str):
        mapping = self.get_synonym_collection_mapping()
        with open(output_path, "w") as f:
            json.dump(mapping, f, indent=2)
        print(f"Synonym mapping saved to {output_path}. Total synonyms: {len(mapping)}")

    def save_clarification_input(self, output_path: str):
        data = self.get_clarification_agent_input()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Clarification agent input saved to {output_path}.")


# ==========================
# Example Usage
# ==========================

if __name__ == "__main__":
    processor = SemanticDictionaryProcessor("database_summary.json")
    collections = processor.get_clarification_agent_structure(
        allowed_collections=["performance_rating_report_year_2025_2026"]
    )
    print("Synonym to Collection Mapping:" , json.dumps(collections, indent=2))    

    # # 1. Save synonym -> collection mapping
    # processor.save_synonym_mapping("synonym_collection_mapping.json")

    # # 2. Save collection -> key_fields + ambiguous_terms
    # processor.save_clarification_input("clarification_agent_input.json")
