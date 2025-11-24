"""
MongoDB Schema Extractor (Standalone)
------------------------------------
This script connects to a MongoDB database, samples documents from
each collection, and infers:

- field names
- field types
- required fields
- sample counts

Install requirements:
    pip install pymongo python-dateutil

Usage:
    python mongodb_schema_extractor.py
"""
import os
from pymongo import MongoClient
from dateutil import parser as date_parser
from typing import Any, Dict, List, Union

from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'

# ---------------------------------------
# Helpers
# ---------------------------------------

def infer_primitive_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        try:
            date_parser.parse(value)
            return "date"
        except Exception:
            return "string"
    return type(value).__name__


# ---------------------------
# Recursive inspectors
# ---------------------------

def infer_schema_value(value) -> Dict[str, Any]:
    """Return schema description for ANY value (object, array, primitive)."""
    
    # ---- OBJECT ----
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": infer_schema_object(value)
        }

    # ---- ARRAY ----
    if isinstance(value, list):
        return infer_schema_array(value)

    # ---- PRIMITIVE ----
    return {"type": infer_primitive_type(value)}


def infer_schema_array(values: List[Any]) -> Dict[str, Any]:
    """Infer array element types and nested schemas."""
    element_types = []
    element_schemas = []

    for v in values:
        schema = infer_schema_value(v)
        element_schemas.append(schema)
        element_types.append(schema["type"])

    element_types = list(set(element_types))  # unique types

    if not values:
        return {"type": "array", "items": {"type": "unknown"}}

    # Merge schemas if objects inside the array
    if len(element_schemas) > 1 and all(s["type"] == "object" for s in element_schemas):
        merged = merge_object_schemas([s["properties"] for s in element_schemas])
        return {"type": "array", "items": {"type": "object", "properties": merged}}

    return {"type": "array", "items": {"type": element_types[0]}}


def infer_schema_object(obj: dict) -> Dict[str, Any]:
    """Extract schema for dictionary fields recursively."""
    schema = {}

    for key, value in obj.items():
        schema[key] = infer_schema_value(value)

    return schema


def merge_object_schemas(list_of_dicts: List[Dict[str, Any]]):
    """Merge multiple object schemas from an array of objects."""
    merged = {}

    for d in list_of_dicts:
        for k, v in d.items():
            if k not in merged:
                merged[k] = v
            else:
                # merge only when types match
                if merged[k]["type"] == v["type"] == "object":
                    merged[k]["properties"] = merge_object_schemas(
                        [merged[k]["properties"], v["properties"]]
                    )

    return merged


# ---------------------------
# Main extraction
# ---------------------------

def extract_db_schema():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    final_schema = {}

    for coll_name in db.list_collection_names():
        coll = db[coll_name]
        docs = list(coll.find({}, limit=1))

        if not docs:
            continue

        # initial schema from first doc
        base_schema = infer_schema_value(docs[0])["properties"]
        required_fields = set(docs[0].keys())

        # merge with rest
        for doc in docs[1:]:
            required_fields &= set(doc.keys())  # fields present in ALL docs
            new_schema = infer_schema_value(doc)["properties"]
            base_schema = merge_object_schemas([base_schema, new_schema])

        final_schema[coll_name] = {
            "schema": base_schema,
            # "required_fields": list(required_fields),
            # "sampled_docs": len(docs)
        }

    return final_schema




# print(json.dumps(extract_db_schema(), indent=2))

