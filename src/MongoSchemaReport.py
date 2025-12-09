import json
from pymongo import MongoClient
from langchain_mongodb.agent_toolkit import (
    MongoDBDatabase
)
from MongoSchemaInferer import MongoSchemaInferer

from pymongo import MongoClient
from bson import json_util

class MongoSchemaReport:
    def __init__(self, client: MongoClient, mongoSchemaInferer : MongoSchemaInferer , db_name: str, sample_docs_in_collection_info: int = 3):
        """
        client  = MongoClient instance
        db_name = database name
        """
        self.client = client
        self.db = client[db_name]
        self.sample_docs_in_collection_info = sample_docs_in_collection_info
        self.mongoSchemaInferer = mongoSchemaInferer

    def get_collections(self):
        """Return list of all collection names in the database."""
        return self.db.list_collection_names()

    def get_sample_documents(self, collection_name: str):
        """
        Get sample documents from a collection
        """
        collection = self.db[collection_name]
        samples_cursor = collection.find().limit(self.sample_docs_in_collection_info)
        return list(samples_cursor)

    def get_indexes(self, collection_name: str):
        """
        Get index information from a collection
        """
        collection = self.db[collection_name]
        return collection.index_information()

    def build_collection_report(self, collection_name: str):
        raw_schema = self.mongoSchemaInferer.extract_schema(collection_name)  # returns {collection: schema}
        schema = raw_schema[collection_name]             # ← extract only inner dict

        samples = self.get_sample_documents(collection_name)

        try:
            indexes = self.get_indexes(collection_name)
        except Exception:
            indexes = []    

        return {
            "fields": schema,    
            "indexes": indexes,
            "samples": samples
        }

    def build_full_report(self):
        """
        Build schema report for all collections.
        """
        report = {}
        for name in self.get_collections():
            report[name] = self.build_collection_report(name)
        return report
    
    def build_full_fields_report(self):
        report = {}
        for name in self.get_collections():
            report[name] = self.build_collection_report(name)["fields"]
        return report

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    app_dir = os.path.join(os.getcwd())
    load_dotenv(os.path.join(app_dir, ".env"))
  
    MONGODB_URI = os.getenv('MONGODB_URI')

    client = MongoClient(MONGODB_URI)
    db_name = "hr-cleaned"
    mongoSchemaInferer = MongoSchemaInferer(client, db_name=db_name)
    util = MongoSchemaReport(client, mongoSchemaInferer,db_name=db_name, sample_docs_in_collection_info=2)
    schema_report = util.build_full_report()
    ##save to file
    with open("./json_repo/mongo_schema_report.json", "w") as f:
        f.write(json_util.dumps(schema_report, indent=2))
