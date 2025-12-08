import json
from pymongo import MongoClient
from openai import OpenAI
import os
# -------------------------------
# 1. CONFIG
# -------------------------------
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))
from MongoSchemaInferer import extract_db_schema
from  SemanticDictionaryProcessor import SemanticDictionaryProcessor

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
MODEL_NAME = "gpt-5-nano" 

client_ai = OpenAI()

def build_summary_document(collection_synonyms_json, user_query):
    prompt = f"""
COLLECTION SYNONYMS DATA:
{json.dumps(collection_synonyms_json, indent=2)}

Your task:
Identify ALL collections whose synonyms match or relate semantically to the user query.

Important rules:
- Return every collection that may be relevant. Not just one.
- If multiple collections match, include all of them.
- Use semantic understanding, not exact keyword match only.
- If nothing matches strongly, return an empty list.
- Do NOT return synonyms, scores, or explanations.
- Output only JSON in the following format:

{{
  "matched_collections": ["collection_name_1", "collection_name_2"]
}}

User Query: "{user_query}"
"""
    response = client_ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a collection router. Respond in strict JSON only."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content





processor = SemanticDictionaryProcessor("./json_repo/database_summary.json")
collections = processor.get_collection_routing_list()
# print("Collections for routing:")
# print(json.dumps(collections, indent=2))
collection = build_summary_document(collections, "Who is my reviewer?")
print(collection)