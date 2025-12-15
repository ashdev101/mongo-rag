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
DB_NAME = 'hr-cleaned'
MODEL_NAME = "gpt-4o"  # Using valid model name

client_ai = OpenAI()

def clean_json_response(response_text):
    """
    Clean the LLM response by removing markdown code blocks if present.
    Handles cases where response is wrapped in ```json ... ``` or ``` ... ```
    """
    response_text = response_text.strip()
    
    # Remove markdown code blocks
    if response_text.startswith("```json"):
        response_text = response_text[7:]  # Remove ```json
    elif response_text.startswith("```"):
        response_text = response_text[3:]  # Remove ```
    
    if response_text.endswith("```"):
        response_text = response_text[:-3]  # Remove trailing ```
    
    return response_text.strip()

def extract_ambiguous_terms(schema_json):
    """
    Extract ONLY ambiguous terms from the database schema.
    Returns ambiguous_terms array in the format matching database_summary.json
    """
    prompt = f"""
You are an Ambiguous Terms Detection Agent.

Your job:
Given the MongoDB database schema, identify ALL ambiguous terms that appear across collections OR within the same collection.

CRITICAL REQUIREMENTS:
1. Extract ALL ambiguous terms - do not miss any. This is a comprehensive extraction, not a summary.
2. **MANDATORY: You MUST include "status" and "reviewer" as ambiguous terms** - these are CRITICAL and cannot be missed.
3. Pay special attention to ambiguous terms WITHIN THE SAME COLLECTION - these are often missed but are very important.
4. Thoroughly scan ALL collections and ALL fields to identify ambiguous terms.

A term is ambiguous if:
1. The same field name appears in multiple collections with different meanings (e.g., "status" in performance vs goal-setting vs offboarding)
2. A field name appears multiple times in the SAME collection with different contexts (e.g., "rating" as "self rating" vs "manager rating" in the same collection)
3. A term can refer to different fields across collections (e.g., "reviewer" in different contexts)
4. **MOST IMPORTANT: A term has multiple related fields in the SAME collection** (e.g., "leavers" referring to "date_of_resignation" vs "date_of_leaving" both in base_report collection)
5. Similar field names in the SAME collection that could be confused (e.g., "office location" vs "work location" in the same collection)
6. Date fields in the SAME collection that might be ambiguous (e.g., "date_of_resignation" vs "date_of_leaving" in base_report)
7. Location-related fields in the SAME collection (e.g., "location", "office location", "work location" all in one collection)
8. Manager-related fields in the SAME collection (e.g., "manager", "reporting manager", "manager number" in same collection)
9. Department-related fields across collections OR within same collection
10. Any other fields in the SAME collection that could cause confusion when users query
11. Terms like "leavers", "joiners", "dates", "locations", "managers" that might refer to multiple fields in the same document/collection

OUTPUT FORMAT - Return ONLY a JSON array of ambiguous terms:
[
  {{
    "term": "reviewer",
    "collections": {{
      "goal_setting_status": {{
        "field": "reviewer name",
        "short_name": "goal-setting reviewer",
        "keywords": ["goal", "goal-setting", "goal setting"]
      }},
      "permormance_rating_report_year_2025_2026": {{
        "field": "reviewer",
        "short_name": "performance reviewer",
        "keywords": ["performance", "rating", "appraisal"]
      }},
      "offboarding_checklist": {{
        "field": "reviewer",
        "short_name": "offboarding reviewer",
        "keywords": ["offboarding", "exit", "clearance"]
      }}
    }},
    "ask_user": "Do you mean goal-setting reviewer, performance reviewer, or offboarding reviewer?"
  }},
  {{
    "term": "rating",
    "collections": {{
      "permormance_rating_report_year_2025_2026": {{
        "fields": [
          {{"field": "self rating", "short_name": "self rating", "keywords": ["self"]}},
          {{"field": "manager rating", "short_name": "manager rating", "keywords": ["manager"]}}
        ]
      }}
    }},
    "ask_user": "Do you mean self rating or manager rating?"
  }},
  {{
    "term": "status",
    "collections": {{
      "permormance_rating_report_year_2025_2026": {{
        "field": "final status",
        "short_name": "performance status",
        "keywords": ["performance", "rating", "appraisal"]
      }},
      "goal_setting_status": {{
        "field": "status",
        "short_name": "goal-setting status",
        "keywords": ["goal", "goal-setting", "goal setting"]
      }},
      "offboarding_checklist": {{
        "field": "status.all task status",
        "short_name": "offboarding status",
        "keywords": ["offboarding", "exit", "clearance"]
      }},
      "base_report": {{
        "field": "assignment status type",
        "short_name": "employee status",
        "keywords": ["employee", "active", "inactive"]
      }}
    }},
    "ask_user": "Which status do you need: performance, goal-setting, offboarding, or employee status?"
  }},
  {{
    "term": "leavers",
    "collections": {{
      "base_report": {{
        "fields": [
          {{"field": "date_of_resignation", "short_name": "resigned (DoR)", "keywords": ["resignation", "resigned"]}},
          {{"field": "date_of_leaving", "short_name": "exited (DoL)", "keywords": ["leaving", "exited"]}}
        ]
      }}
    }},
    "ask_user": "Filter by resignation date or leaving date?"
  }}
]

RULES:
- Extract ALL ambiguous terms - this is a complete extraction, not a summary. Include every ambiguous term you find.
- **MANDATORY INCLUSION: You MUST include "status" and "reviewer" as ambiguous terms** - these are CRITICAL and appear in the examples below. Do not skip them.
- **EXCLUSION RULE: DO NOT include ambiguous terms for "name" or "manager"** - these are excluded from the results
- For each ambiguous term, use "field" if the collection has ONE field, or "fields" (array) if it has MULTIPLE fields in the SAME collection
- **CRITICAL: Pay special attention to terms with multiple fields in the SAME collection** - use "fields" array for these (like "leavers" example)
- Include "short_name" - a human-readable name for disambiguation
- Include "keywords" - words that help identify which meaning is intended
- Create a clear "ask_user" question for each ambiguous term
- Be EXTREMELY THOROUGH - check for ALL ambiguous terms including: **status (MANDATORY)**, **reviewer (MANDATORY)**, rating, department, location, date, employee, goal, weight, leavers, joiners, dates, locations, leaves, etc.
- **IMPORTANT: Include "leaves" if there are multiple leave-related fields in the same collection (e.g., total leaves, pending leaves, sick leaves)**
- Handle nested field paths (e.g., "status.all task status", "core hr.employee id")
- Look for similar field names that could be confused, especially within the same collection
- **DO NOT SKIP ambiguous terms that exist only within a single collection** - these are just as important as cross-collection ambiguities
- **VERIFY: Before finishing, check that you have included "status" and "reviewer" in your output**

Database Schema:
{json.dumps(schema_json, indent=2)}
"""
    response = client_ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an Ambiguous Terms Detection Agent. Respond with ONLY a valid JSON array, no markdown code blocks, no explanations, no other text. Just the raw JSON array starting with [ and ending with ]."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3  # Lower temperature for more consistent results
    )
    return response.choices[0].message.content


print("Extracting MongoDB schema...")
schema = extract_db_schema()

print("Analyzing schema for ambiguous terms...")
ambiguous_terms_json = extract_ambiguous_terms(schema)

# Clean the response (remove markdown code blocks if present)
ambiguous_terms_json = clean_json_response(ambiguous_terms_json)

# Parse the JSON response
try:
    ambiguous_terms = json.loads(ambiguous_terms_json)
    
    # Ensure it's an array
    if not isinstance(ambiguous_terms, list):
        print("Warning: Expected array, got:", type(ambiguous_terms))
        ambiguous_terms = []
    
    # Filter out "name" and "manager" ambiguous terms
    filtered_terms = []
    excluded_terms = []
    for term_obj in ambiguous_terms:
        term = term_obj.get("term", "").lower()
        if term in ["name", "manager"]:
            excluded_terms.append(term_obj.get("term", "unknown"))
        else:
            filtered_terms.append(term_obj)
    
    ambiguous_terms = filtered_terms
    
    if excluded_terms:
        print(f"\n⚠️  Excluded ambiguous terms: {', '.join(excluded_terms)}")
    
    # Validate that critical terms are present
    terms_lower = [term_obj.get("term", "").lower() for term_obj in ambiguous_terms]
    missing_critical = []
    if "status" not in terms_lower:
        missing_critical.append("status")
    if "reviewer" not in terms_lower:
        missing_critical.append("reviewer")
    
    if missing_critical:
        print(f"\n❌ WARNING: Missing CRITICAL ambiguous terms: {', '.join(missing_critical)}")
        print("   These terms should be included. Please check the schema and re-run if needed.")
    
    # Create output structure matching database_summary.json format
    output = {
        "ambiguous_terms": ambiguous_terms
    }
    
    # Save to database_summary2.json
    with open("database_summary2.json", "w") as f:
        json.dump(output, f, indent=4)
    
    print(f"\n✅ Successfully extracted {len(ambiguous_terms)} ambiguous terms (excluding 'name' and 'manager')")
    print("✅ ALL ambiguous terms saved to database_summary2.json (complete extraction, not a summary)")
    
    # Print summary for verification
    print("\n📊 Extracted Ambiguous Terms (for verification):")
    for term_obj in ambiguous_terms:
        term = term_obj.get("term", "unknown")
        collections = term_obj.get("collections", {})
        collections_count = len(collections)
        
        # Check if any collection has multiple fields (same-collection ambiguity)
        has_same_collection_ambiguity = False
        for coll_name, coll_data in collections.items():
            if "fields" in coll_data:  # Multiple fields in same collection
                has_same_collection_ambiguity = True
                fields_count = len(coll_data["fields"])
                print(f"  - {term}: {collections_count} collection(s) | {coll_name} has {fields_count} fields (same-collection ambiguity)")
                break
        
        if not has_same_collection_ambiguity:
            print(f"  - {term}: found in {collections_count} collection(s)")
        
except json.JSONDecodeError as e:
    print(f"❌ Error parsing JSON response: {e}")
    print("\nRaw response:")
    print(ambiguous_terms_json)
    
    # Save raw response for debugging
    with open("database_summary2.json", "w") as f:
        json.dump({"error": "Failed to parse JSON", "raw_response": ambiguous_terms_json}, f, indent=4)
    print("\nRaw response saved to database_summary2.json for debugging")

