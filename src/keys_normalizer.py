import json
import os
import openai
from schema_generator import extract_db_schema
from langchain_openai import ChatOpenAI
import re
# -------------------------
# CONFIG
# -------------------------
MODEL = "gpt-5"  # or gpt-4o-mini if you want cheaper
llm = ChatOpenAI(model=MODEL) 

# -------------------------
# LLM AGENT FUNCTION
# -------------------------
def generate_field_mapping(schema_text: str):
    """
    Takes in a schema (JSON or descriptive text).
    Returns canonical mapping with similarities and normalized field names.
    """

    prompt = f"""
You are a schema normalization assistant.

The user will give you a full MongoDB schema.

Your job:
1. Identify all fields across collections.
2. Find fields that refer to the same concept (synonyms).
3. Produce a JSON mapping where:
   - KEY = canonical normalized field name
   - VALUE = list of all raw field names that belong to that concept

Normalization rules for canonical keys:
- lowercase
- only letters and numbers
- words separated by a single space
- no underscores, no hyphens, no punctuation

Example:
"employeeCode", "employee_code", "Employee-Code" → "employee code"

Now analyze the following schema and produce ONLY JSON:

----- SCHEMA START -----
{schema_text}
----- SCHEMA END -----

Output ONLY a JSON object like:
{{
  "canonical field": ["raw1", "raw2", "raw3"]
}}
    """

    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are a schema normalization assistant."
                    "Your response MUST be only valid JSON. "
                    "No markdown, no comments, no backticks."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response.content.strip())


# -------------------------
# EXECUTION
# -------------------------
if __name__ == "__main__":
    schema = extract_db_schema()
    schema_text = json.dumps(schema, indent=2)
    mapping_json = generate_field_mapping(schema_text)

    print("\n=== GENERATED MAPPING ===")
    print(mapping_json)

    with open("canonical_mapping.json", "w") as out:
        out.write(json.dumps(mapping_json, indent=2))

    print("\nSaved → canonical_mapping.json\n")
