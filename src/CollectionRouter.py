from CollectionRouterRuleBased import CollectionRouterRuleBased
from CollectionRouterVectorBased import CollectionRouterVectorBased
from SemanticDictionaryProcessor import SemanticDictionaryProcessor

class CollectionRouterAgent:
    def __init__(self , semanticDictionaryProcessor : SemanticDictionaryProcessor , collectionRouterRuleBased : CollectionRouterRuleBased , collectionRouterVector : CollectionRouterVectorBased , use_rule_based_first : bool = True , include_default_collection : bool = True) :
        self.semanticDictionaryProcessor = semanticDictionaryProcessor
        self.collectionRouterRuleBased = collectionRouterRuleBased
        self.collectionRouterVector = collectionRouterVector
        self.use_rule_based_first = use_rule_based_first
        self.include_default_collection = include_default_collection
    
    async def route_query(self, user_query: str):
        """
        Returns ALL collections that match the user query based on routing keywords.

        If include_default_collection=True:
            Appends the default collection list from the schema.
        Output:
            ["collection1", "collection2", ...]
        """

        # Get default collections
        matched_collections = [] if not self.include_default_collection else self.semanticDictionaryProcessor.get_default_collections()
        
        # First use rule-based routing
        if self.use_rule_based_first:
            matched_collections = self.collectionRouterRuleBased.route_query(user_query, include_default_collection = False)

        # If collections matched size is 1, use vector-based routing as fallback
        if not matched_collections or len(matched_collections) <= 1:
            print("Using vector-based routing as fallback...")
            vector_match = await self.collectionRouterVector.top_k_collections(user_query)
            if vector_match:
                for match in vector_match:
                    if match["collection_name"] not in matched_collections:
                        matched_collections.append(match["collection_name"])

        return matched_collections
    
async def get_collection(query : str , use_rule_based_first : bool = True) -> list:
    processor = SemanticDictionaryProcessor("./json_repo/database_summary.json")
    defualt_collections = processor.get_default_collections()
    collections = processor.get_collection_routing_list()
    collectionRouterRuleBased = CollectionRouterRuleBased(collections , defualt_collections)
    collectionRouterVectorBased = CollectionRouterVectorBased()
    router = CollectionRouterAgent(processor , collectionRouterRuleBased , collectionRouterVectorBased , use_rule_based_first)
    return await router.route_query(query)
    
if __name__ == "__main__":
    matches = get_collection("last promotion date for ashish" , use_rule_based_first=False)
    print(matches)