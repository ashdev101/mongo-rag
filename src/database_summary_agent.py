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
from MongoSchemaInferer import MongoSchemaInferer
from MongoSchemaReport import MongoSchemaReport

MONGO_URI = os.getenv('MONGODB_URI')
# DB_NAME = 'hr'
MODEL_NAME = "gpt-5" 

client_ai = OpenAI()

def build_summary_document(schema_json , database_explanation):
    prompt = f"""
      You are a Semantic Dictionary Generator Agent.

      Your job:
      Given the MongoDB database schema and database explanation, produce a BUSINESS-ORIENTED ROUTING DICTIONARY.

      The dictionary must include: entity_name, collection, key_fields, synonyms, intent_patterns, ambiguous_fields, routing_keywords.

      SYNONYM MINIMIZATION RULE:
      Generate only 3–6 high-signal synonyms per entity.
      It should cover the Key Fields in varoius synonym manner
      Include ONLY:
      1) the main business term (singular+plural),
      2) 1–2 common user terms,
      3) 1–2 widely-used business alternatives.
      Avoid long lists or rare variations.

      INTENT PATTERN RULE:
      Keep intent patterns short, natural-language, and as much as possible as this will also be going to be used for semantic based routing , covering all the key fields in different dimensions .

      Ambiguous Terms (global)**  
        - At the end of the dictionary, create a single top-level object `ambiguous_terms`.
        - Include only fields that are ambiguous across the database (e.g., status, reviewer, department, location, rating, goal, weight, name, leavers, top/bottom N).
        - Each term object must include:
          - term: the ambiguous keyword
          - possible_meanings: all possible meanings across any collection
          - disambiguation_keywords: words that may help infer correct meaning
          - ask_user: concise question to clarify if needed in natural language.
        - Example:
          {{
            "term": "reviewer",
            "possible_meanings": ["goal-setting reviewer", "performance reviewer", "offboarding reviewer"],
            "disambiguation_keywords": [],
            "ask_user": "Use goal-setting reviewer, performance reviewer, or offboarding reviewer?"
          }}

      OUTPUT FORMAT:
      {{
        "entities":{{
          "<entity_name>": {{
            "collection": "<collection_name>",
            "key_fields": { ... },
            "synonyms": [...],
            "intent_patterns": [...],
            "routing_keywords": [...]
          }}
        }},
          "ambiguous_terms": [ ... ]
      }}

      Database Schema:
      {json.dumps(schema_json, indent=2)}

      Database explanation :
      {database_explanation}
      """
    response = client_ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a Semantic Dictionary Generator Agent. Respond in strict JSON only."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content



if __name__ == "__main__":
  from dotenv import load_dotenv
  app_dir = os.path.join(os.getcwd())
  load_dotenv(os.path.join(app_dir, ".env"))
  
  MONGODB_URI = os.getenv('MONGODB_URI')
  print("Extracting MongoDB schema...")
  db_name = "hr-cleaned"
  client = MongoClient(MONGODB_URI)
  mongoSchemaInferer = MongoSchemaInferer(client, db_name=db_name , sample_docs=2)
  mongoSchemaReport = MongoSchemaReport(client,mongoSchemaInferer=mongoSchemaInferer, db_name=db_name , sample_docs_in_collection_info=2)

  schema = mongoSchemaReport.build_full_fields_report()

  # print(json.dumps(schema, indent=2))

  from data_context import DataContext

  print("Generating database summary using LLM...")
  summary = build_summary_document(schema , DataContext)

  # If summary is already a JSON string, convert it to a dict
  try:
      summary_dict = json.loads(summary)
  except json.JSONDecodeError:
      # If summary is not valid JSON, wrap it as a string
      summary_dict = {"summary": summary}

  # Save as properly formatted JSON
  with open("./json_repo/database_summary.json", "w") as f:
      json.dump(summary_dict, f, indent=4)

  print("\nSaved to ./json_repo/database_summary.json with proper indentation")
