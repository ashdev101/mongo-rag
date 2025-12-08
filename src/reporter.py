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

MONGO_URI = os.getenv('MONGODB_URI')
DB_NAME = 'hr'
MODEL_NAME = "gpt-4.1"  # or "gpt-4o-mini" etc.

client_ai = OpenAI()

# -------------------------------
# 2. IMPORT THE DEEP SCHEMA EXTRACTOR
# (paste your deep schema extractor here)
# -------------------------------

from dateutil import parser as date_parser

# (Keep the previous deep schema extractor functions exactly as is)
# infer_primitive_type(), infer_schema_value(), infer_schema_array(), infer_schema_object(),
# merge_object_schemas(), extract_db_schema()


# -------------------------------
# 3. MAKE THE DB SUMMARY FUNCTION
# -------------------------------

def summarize_database(schema_json):
    prompt = f"""
You are a senior database architect. You have been given the complete introspected schema of a MongoDB database.

Analyze the schema and provide:

1. Overall purpose of the database
2. Summary of each collection
3. Important fields per collection
4. Relationships between collections
5. Data quality issues
6. Suggested improvements
7. Possible user queries

### Schema:
{json.dumps(schema_json, indent=2)}
"""

    response = client_ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a world-class database analyst."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


# -------------------------------
# 4. MAIN EXECUTION
# -------------------------------


print("Extracting MongoDB schema...")
schema = extract_db_schema()

print("Generating database summary using LLM...")
summary = summarize_database(schema)

print("\n=== DATABASE SUMMARY ===\n")
print(summary)

with open("database_summary.txt", "w") as f:
    f.write(summary)

print("\nSaved to database_summary.txt")
