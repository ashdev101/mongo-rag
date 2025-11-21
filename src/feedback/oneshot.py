from .MongoDBEmbeddingStore import MongoDBEmbeddingStore   # adjust import
from .cleaner import clean_text
def oneshot_example(query: str):
    try:
        # clean query
        if " . My email is" in query:
            query = query[:query.rfind(" . My email is")]
        query = clean_text(query)

        print("++++++++Received Query:", query, "+++++++++++++++++++++")

        # Init store
        store = MongoDBEmbeddingStore(
            database_name="test-saptarshi",
            collection_name="feedback-vector"
        )

        # Perform similarity search – return top 1 result
        results = store.search(
            query_text=query,
            limit=1
        )

        store.close()
        # print("++++similarity search result:",results,"+++++++++++++++++++++")
        if results[0]['score']>0.75:
            print("Similarity Score:",results[0]['score'])
            return f"""query: {results[0]['query']}\nagg_pipeline: {results[0]['agg_pipeline']}\ncollection_name: {results[0]['collection_name']}"""
        if not results:
            return None  # or "No similar query found"

        # Return the closest matched document
        return results[0]
    except:
        return "Example Not Available"
