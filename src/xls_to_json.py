import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import re

# --- Helper functions ---

def prettify_key(key: str) -> str:
    """
    Convert messy keys into lowercase, readable keys.
    Example:
        'exit_checklist_-_employee' -> 'exit checklist employee'
    """
    if pd.isna(key):
        return ""
    key = str(key)
    # Replace underscores and hyphens with spaces
    key = key.replace("_", " ").replace("-", " ")
    # Remove punctuation like (), /, ., :
    key = re.sub(r"[()/,.:]+", " ", key)
    # Remove multiple spaces
    key = re.sub(r"\s+", " ", key)
    return key.strip().lower()


def is_date_column(name: str) -> bool:
    """Detect date-like columns by name."""
    date_keywords = [
        "date", "joining", "resignation", "leaving", "dob",
        "date_of_birth", "date_of_joining", "date_of_resignation", "date_of_leaving"
        "start_date", "end_date" ,"doj"
    ]
    return any(k in name.lower() for k in date_keywords)


def convert_to_mongo_date(value):
    """Convert datetime or string to MongoDB Extended JSON date."""
    if pd.isna(value) or value == "":
        return ""
    if isinstance(value, (datetime, pd.Timestamp)):
        return {"$date": value.strftime("%Y-%m-%dT%H:%M:%SZ")}
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d-%b-%Y"):
        try:
            dt = datetime.strptime(str(value), fmt)
            return {"$date": dt.strftime("%Y-%m-%dT%H:%M:%SZ")}
        except ValueError:
            continue
    return value


def excel_to_nested_json(input_path: str, output_path: str):
    """
    Converts Excel with merged or normal headers into nested JSON.
    Converts date-like fields into MongoDB Extended JSON format.
    Keys are cleaned to lowercase, human-readable format.
    """
    input_path = Path(input_path)
    engine = 'xlrd' if input_path.suffix.lower() == '.xls' else 'openpyxl'
    excel = pd.ExcelFile(input_path, engine=engine)
    all_docs = []

    for sheet_name in excel.sheet_names:
        print(f"📄 Reading sheet: {sheet_name}")

        df = pd.read_excel(input_path, sheet_name=sheet_name, header=[0, 1])

        # Single header
        if not isinstance(df.columns[0], tuple):
            df = pd.read_excel(input_path, sheet_name=sheet_name, header=0)
            df.columns = [prettify_key(c) for c in df.columns]
            df = df.fillna("")
            for col in df.columns:
                if is_date_column(col):
                    df[col] = df[col].apply(convert_to_mongo_date)
            all_docs.extend(df.to_dict(orient="records"))
            continue

        # Multi-header (merged)
        df.columns = [(prettify_key(a), prettify_key(b)) for a, b in df.columns]
        df = df.fillna("")

        for _, row in df.iterrows():
            doc = {}
            for (main, sub), value in row.items():
                if not main and sub:
                    key = prettify_key(sub)
                    val = convert_to_mongo_date(value) if is_date_column(key) else value
                    doc[key] = val
                else:
                    main_key = prettify_key(main)
                    sub_key = prettify_key(sub)
                    val = convert_to_mongo_date(value) if is_date_column(sub_key) else value
                    if not main_key:
                        doc[sub_key] = val
                    else:
                        if main_key not in doc:
                            doc[main_key] = {}
                        doc[main_key][sub_key] = val
            all_docs.append(doc)

    # Write JSON file
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, indent=4, ensure_ascii=False)

    print(f"✅ JSON saved to: {output_path}")
    print(f"📦 Total records: {len(all_docs)}")

# Example usage
input_file = r"C:/Users/ak965/workspace/learning/python/rag/Reports/4.Goal Status Report 2025-26 All.xlsx"
output_json = r"C:/Users/ak965/workspace/learning/python/rag/output_file/goal_setting.json"

excel_to_nested_json(input_file, output_json)

