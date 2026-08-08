import json
from typing import Any, Dict, List
from aggregation.AggregationRBAC import AggregationRBAC
from MongoDbDatabseLocalContextAndPiiMasking import MongoDBDatabasePIIToolkit
import os
from pymongo import MongoClient
# Load environment variables from .env file
from dotenv import load_dotenv
from db.mongo import mongoClient
from datetime import date, datetime, timezone
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv("MONGODB_DATABASE")

client = mongoClient
db = client[DB_NAME]

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

class MongoDBToolExecutor:
    """
    Executes MongoDB tool calls.
    RBAC REMOVED.
    PII + aggregation enforcement delegated to existing toolkit.
    """

    def __init__(self, db_wrapper : MongoDBDatabasePIIToolkit , aggregationRBAC: AggregationRBAC):
        self.db = db_wrapper
        self.aggregationRBAC = aggregationRBAC
        self.schema_cache = {}

    
    def normalize_dates(obj):
        if isinstance(obj, dict):
            if set(obj.keys()) == {"$date"}:
                return datetime.fromisoformat(
                    obj["$date"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)

            return {k: MongoDBToolExecutor.normalize_dates(v) for k, v in obj.items()}

        elif isinstance(obj, list):
            return [MongoDBToolExecutor.normalize_dates(i) for i in obj]

        return obj


    def list_collections(self) -> str:
        try:
            collections = self.db.get_usable_collection_names()
            print("Fetched collections:", collections)
            return json.dumps(
                {"collections": collections, "count": len(collections)}, indent=2
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_collection_schema(self, collection_name: str, sample_size: int = 3) -> str:
        try:
            if not collection_name :
                raise ValueError("Collection name must be provided")
            print("Using collection for schema:", collection_name)
            schema = self.db._get_collection_schema(collection_name)
            sample_docs = self.db._get_sample_docs(collection_name)
            print("Fetched schema:", schema)
            # self.schema_cache[collection_name] = schema
            fetched_schema = json.dumps(schema, indent=2)
            fetched_sample_docs = json.dumps(sample_docs, indent=2)
            result = {
                "collection": collection_name,
                "schema": fetched_schema,
                "sample docs" : fetched_sample_docs
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def run_aggregation(self, collection_name: str, pipeline: List[Dict]) -> str:
        """Run an aggregation pipeline on a collection with RBAC enforcement"""
        try:
            if collection_name not in self.db.get_usable_collection_names():
                return json.dumps(
                    {"error": f"Collection '{collection_name}' does not exist"}
                )

            # collection = [collection_name]
            print("Original pipeline:", pipeline)
            print("Using collection:", collection_name)
            original_pipeline = pipeline.copy()

            # Normalize dates
            pipeline = MongoDBToolExecutor.normalize_dates(pipeline)

            # Enforce RBAC on the pipeline
            print("Enforcing RBAC on pipeline...")
            pipeline = self.aggregationRBAC.enforce(pipeline)
            print("RBAC-enforced pipeline:", pipeline)


            # Execute aggregation with (possibly modified) pipeline
            results = await db[collection_name].aggregate(pipeline).to_list(length=None)

            print("Aggregation results:", results)

            return json.dumps(
                {
                    "collection": collection_name,
                    "pipeline": original_pipeline, 
                    "result_count": len(results),
                    "results": results,           
                },
                indent=2,
                cls=DateTimeEncoder
            )
        except Exception as e:
            return json.dumps(
                {"error": str(e), "collection": collection_name, "pipeline": pipeline}
            )

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        print("Executing tool:", tool_name)
        if tool_name == "list_collections":
            return self.list_collections()
        elif tool_name == "get_collection_schema":
            return self.get_collection_schema(
                tool_input["collection_name"],
                tool_input.get("sample_size", 3),
            )
        elif tool_name == "run_aggregation":
            return await self.run_aggregation(
                tool_input["collection_name"],
                tool_input["pipeline"],
            )
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        

