from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from MongoSchemaInferer import extract_db_schema
import json

ONTOLOGY_GENERATOR_PROMPT = """
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
"""

schema = extract_db_schema()
raw_schema_json = json.dumps(schema, indent=2)

def generate_semantic_dictionary(raw_schema):
    llm = ChatOpenAI(model="gpt-4o-mini")  # or your model

    prompt = ChatPromptTemplate.from_template(ONTOLOGY_GENERATOR_PROMPT)

    messages = prompt.format_messages(schema=json.dumps(raw_schema, indent=2))

    response = llm(messages)

    return json.loads(response.content)

semantic_dictionary = generate_semantic_dictionary(raw_schema_json)
with open("semantic_dictionary.json", "w") as f:
    json.dump(semantic_dictionary, f, indent=2)
print("Semantic dictionary saved to semantic_dictionary.json")

