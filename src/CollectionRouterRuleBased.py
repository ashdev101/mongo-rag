import json
import re
from SemanticDictionaryProcessor import SemanticDictionaryProcessor

class CollectionRouterRuleBased:
    def __init__(self, json_file: dict , default_collections: list = []):
        """
        Initialize the agent with the JSON file containing:
        [
            {
                "collection_name": "...",
                "routing_keywords": ["keyword1", "keyword2", ...]
            },
            ...
        ]
        """
        self.collection_synonyms = json_file
        self.default_collections = default_collections

        # For multi-match routing:
        # { "reviewer": ["performance", "goals", "offboarding"] }
        self.keywords_collections = {}

        for item in self.collection_synonyms:
            collection_name = item["collection_name"]

            for keyword in item["routing_keywords"]:
                keyword = keyword.lower()
                if keyword not in self.keywords_collections:
                    self.keywords_collections[keyword] = []
                self.keywords_collections[keyword].append(collection_name)

    def normalize_text(self, text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.lower())

    def route_query(self, user_query: str, include_default_collection: bool = True):
        """
        Returns ALL collections that match the user query based on routing keywords.

        If include_default_collection=True:
            Appends the default collection list from the schema.
        
        Output:
            ["collection1", "collection2", ...]
        """

        query_norm = self.normalize_text(user_query)
        matched_collections = set()

        # Match keywords → list of collections
        for keyword, collection_list in self.keywords_collections.items():
            if keyword in query_norm:
                for col in collection_list:
                    matched_collections.add(col)

        # If default list is not requested → return early
        if not include_default_collection:
            return list(matched_collections)

        # Include default collections from schema
        default_list = getattr(self, "default_collections", [])

        # Union matched + default
        final_set = matched_collections.union(default_list)

        return sorted(list(final_set))




# ================================
# Example Usage
# ================================

if __name__ == "__main__":
    processor = SemanticDictionaryProcessor("./json_repo/database_summary.json")
    collections = processor.get_collection_routing_list()
    defualt_collections = processor.get_default_collections()
    router = CollectionRouterRuleBased(collections , defualt_collections)

    queries = [
        "Show me my performance rating for this year",
        "I want the list of employees in IT",
        "Get my appraisal score"
    ]

    # for q in queries:
    collection = router.route_query("education details of employees in grade m2 and m4 working in HR and finance departments in east and west regions")
    print(f"Routed Collection: {collection}\n")
    # result = processor.get_clarification_agent_structure(
    #     allowed_collections=collection
    # )

    # print(json.dumps(result, indent=2))
