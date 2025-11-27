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
from schema_generator import extract_db_schema

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
MODEL_NAME = "gpt-5" 

client_ai = OpenAI()

def build_summary_document(schema_json):
    prompt = f"""
You are an Ontology Generator Agent.

You will receive a FULL MongoDB schema that may be large and detailed.
Your job is to convert it into a SMALL, HUMAN-ORIENTED semantic dictionary
that can be used by a Clarifying Agent.

RULES:
1. DO NOT include more than 6–10 fields per collection.
2. DO NOT include nested objects or low-level details.
3. DO NOT expose internal database naming conventions.
4. DO NOT show sensitive fields.
5. Create business-friendly names for collections:
   - "users" → "customer"
   - "payments" → "payment"
   - "orders" → "order"
6. Identify field categories:
   - date
   - amount/number
   - status
   - reference (ObjectId)
7. Produce useful synonyms:
   - "customer", "user", "client" → users
   - "order", "purchase" → orders
   - "payment", "transaction" → payments
8. Produce a compact structure like:

{{
  "entities": {{
     "customer": {{
        "collection": "users",
        "key_fields": {{
            "created_at": "date",
            "status": "status",
            "email": "string"
        }},
        "synonyms": ["user", "client", "account"]
     }},
     "order": {{
        "collection": "orders",
        "key_fields": {{
            "order_date": "date",
            "status": "status",
            "total": "amount"
        }},
        "synonyms": ["purchase", "transaction"]
     }}
  }}
}}

Keep the output small, abstract, and strictly business-focused.
### Schema:
{json.dumps(schema_json, indent=2)}

"""
    response = client_ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an Ontology Generator Agent. Respond in strict JSON only."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content






print("Extracting MongoDB schema...")
schema = extract_db_schema()

print("Generating database summary using LLM...")
summary = build_summary_document(schema)

print("\n=== DATABASE SUMMARY ===\n")
# print(summary)

with open("database_summary10.txt", "w") as f:
    f.write(summary)

print("\nSaved to database_summary.txt")
