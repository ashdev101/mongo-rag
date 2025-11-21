from .MongoDBEmbeddingStore import MongoDBEmbeddingStore   # adjust import to your file path
from pymongo.errors import DuplicateKeyError
from .hashing import md5_hash_string
from .cleaner import clean_text
def lander(choice, feedback_data):
    """
    feedback_data: {
        "agg_pipeline": <string or dict>,
        "query": <string>
    }
    """

    try:
        if choice == "Yes":
            # raw_query = feedback_data.get("query").lower().strip()
            raw_query = feedback_data.get("query")
            agg_pipeline = feedback_data.get("agg_pipeline")
            cleaned_query = clean_text(raw_query)
            print("=======================lander.py=========================")
            print("agg_pipeline:",agg_pipeline)
            md5 = md5_hash_string(cleaned_query)
            if not raw_query:
                return "Query is missing. Cannot store feedback."

            store = MongoDBEmbeddingStore(
                database_name="test-saptarshi",
                collection_name="feedback-vector"
            )

            # Generate embedding ONLY for query
            embedding = store.generate_embedding(cleaned_query)
            agg_list = eval(agg_pipeline)
            # Build document exactly as required
            doc = {
                "hash": md5,
                "query": raw_query,
                "db_results": agg_list[-1],
                "agg_pipeline": agg_list[:-2],
                "collection_name": agg_list[-2],
                "embedding": embedding
            }

            store.collection.insert_one(doc)      
            store.close()

        return "Your feedback has been recorded. Thank You!"
    
    except DuplicateKeyError as e:

        if "E11000" in str(e):
            return "This feedback has already been recorded. Thank You!"
        else:
            print(e)
            return f"Error processing feedback: {e}"
        
    except Exception as e:
        return f"Error processing feedback: {e}"
    finally:       
        store.close()
