import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dateutil import parser as date_parser
from typing import Any, Dict, List
import json
from dotenv import load_dotenv

app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))


# ---------------------------------------
# Helpers
# ---------------------------------------

from typing import Any, Dict, List
from pymongo import MongoClient
from bson import ObjectId
from dateutil import parser as date_parser
from datetime import datetime
import json


class MongoSchemaInferer:
    def __init__(self, client: MongoClient, db_name: str, sample_docs: int = 100):
        self.client = client
        self.db = client[db_name]
        self.sample_docs = sample_docs

    # --------------------------- PRIMITIVE TYPE INFERENCE ---------------------------
    @staticmethod
    def infer_primitive_type(value):
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Boolean"
        if isinstance(value, int):
            return "Number"
        if isinstance(value, float):
            return "Number"
        if isinstance(value, ObjectId):
            return "ObjectId"
        if isinstance(value, datetime):
            return "Timestamp"
        if isinstance(value, str):
            try:
                date_parser.parse(value)
                return "Timestamp"
            except Exception:
                return "String"
        return "Unknown"

    # --------------------------- RECURSIVE SCHEMA RESOLUTION ---------------------------
    @classmethod
    def infer_schema_value(cls, value):
        """Return simplified schema for ANY value (object, array, primitive)."""
        # Object
        if isinstance(value, dict):
            return {k: cls.infer_schema_value(v) for k, v in value.items()}

        # Array
        if isinstance(value, list):
            if not value:
                return ["unknown"]
            element_schemas = [cls.infer_schema_value(v) for v in value]
            uniq = list({json.dumps(s): s for s in element_schemas}.values())
            return uniq

        # Primitive
        return cls.infer_primitive_type(value)
    def normalize_schema(schema: dict) -> dict:
        """
        Convert values from list-of-types to:
        - single string if only one type
        - keep list if multiple types
        """
        normalized = {}

        for k, v in schema.items():
            # Recursively normalize nested objects
            if isinstance(v, dict):
                normalized[k] = MongoSchemaInferer.normalize_schema(v)
            elif isinstance(v, list):
                # Flatten single-type lists
                flat_list = []

                def flatten(x):
                    if isinstance(x, list):
                        for item in x:
                            flatten(item)
                    else:
                        flat_list.append(x)

                flatten(v)

                uniq = list({json.dumps(x): x for x in flat_list}.values())

                if len(uniq) == 1:
                    normalized[k] = uniq[0]  # single type as string
                else:
                    normalized[k] = uniq      # multiple types remain as list
            else:
                normalized[k] = v

        return normalized


    @classmethod
    def merge_object_schemas(cls, dicts: List[Dict[str, Any]]):
        """Merge multiple object schemas into a flattened format."""

        # helper to flatten nested lists
        def flatten(x, flat_list):
            if isinstance(x, list):
                for item in x:
                    flatten(item, flat_list)
            else:
                flat_list.append(x)

        merged = {}

        for d in dicts:
            for k, v in d.items():
                if k not in merged:
                    merged[k] = v
                    continue

                # Recursively merge objects
                if isinstance(merged[k], dict) and isinstance(v, dict):
                    merged[k] = cls.merge_object_schemas([merged[k], v])
                    continue

                # Merge lists
                if isinstance(merged[k], list) and isinstance(v, list):
                    flat_list = []
                    flatten(merged[k], flat_list)
                    flatten(v, flat_list)
                    merged[k] = list({json.dumps(x): x for x in flat_list}.values())
                    continue

                # Handle mismatched primitives (primitive vs primitive OR primitive vs list)
                merged_list = []

                # flatten existing merged value if it is a list
                flatten(merged[k], merged_list) if isinstance(merged[k], list) else merged_list.append(merged[k])

                # flatten new value if it is a list
                flatten(v, merged_list) if isinstance(v, list) else merged_list.append(v)

                # deduplicate
                merged[k] = list({json.dumps(x): x for x in merged_list}.values())

        return merged


    # --------------------------- MAIN EXTRACTION ---------------------------
    def extract_schema(self, collection_name: str = None):
        """
        Return schema for:
        - One collection (if collection_name provided)
        - All collections (if None)
        """
        final_schema = {}

        collections = (
            [collection_name] if collection_name else self.db.list_collection_names()
        )

        for coll_name in collections:
            coll = self.db[coll_name]
            docs = list(coll.find({}, limit=self.sample_docs))

            if not docs:
                continue

            base_schema = self.infer_schema_value(docs[0])

            for doc in docs[1:]:
                base_schema = self.merge_object_schemas(
                    [base_schema, self.infer_schema_value(doc)]
                )

            final_schema[coll_name] = base_schema

        return MongoSchemaInferer.normalize_schema(final_schema)



# ---------------------------
# Run test
# ---------------------------
if __name__ == "__main__":
    MONGO_URI = os.getenv('MONGODB_URI')
    DB_NAME = 'hr-cleaned'
    print(json.dumps(MongoSchemaInferer(MongoClient(MONGO_URI), DB_NAME).extract_schema("historical_ratings_and_other_information"), indent=2))
