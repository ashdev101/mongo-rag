from CollectionRouterRuleBased import CollectionRouterRuleBased
from CollectionRouterVectorBased import CollectionRouterVectorBased
from SemanticDictionaryProcessor import SemanticDictionaryProcessor

class CollectionRouterAgent:
    def __init__(self , collectionRouterRuleBased : CollectionRouterRuleBased , collectionRouterVector : CollectionRouterVectorBased  ) :
        self.collectionRouterRuleBased = collectionRouterRuleBased
        self.collectionRouterVector = collectionRouterVector
    
    def route_query(self, user_query: str, include_default_collection: bool = True):
        """
        Returns ALL collections that match the user query based on routing keywords.

        If include_default_collection=True:
            Appends the default collection list from the schema.
        Output:
            ["collection1", "collection2", ...]
        """
        # First use rule-based routing
        matched_collections = self.collectionRouterRuleBased.route_query(user_query, include_default_collection)

        # If collections matched size is 1, use vector-based routing as fallback
        if not matched_collections or len(matched_collections) == 1:
            print("Using vector-based routing as fallback...")
            vector_match = self.collectionRouterVector.top_k_collections(user_query)
            if vector_match:
                for match in vector_match:
                    if match["collection_name"] not in matched_collections:
                        matched_collections.append(match["collection_name"])

        return matched_collections
    
def get_collection(query : str):
    processor = SemanticDictionaryProcessor("./json_repo/database_summary.json")
    defualt_collections = processor.get_default_collections()
    collections = processor.get_collection_routing_list()
    collectionRouterRuleBased = CollectionRouterRuleBased(collections , defualt_collections)
    collectionRouterVectorBased = CollectionRouterVectorBased()
    router = CollectionRouterAgent(collectionRouterRuleBased , collectionRouterVectorBased)
    return router.route_query(query)
    
if __name__ == "__main__":
    matches = get_collection("Show me my performance rating for this year")
    print(matches)