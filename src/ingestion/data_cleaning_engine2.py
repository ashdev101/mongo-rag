
from datetime import datetime as dt
from ingestion.config import REPORT_CONFIG, ReportName
from collections import defaultdict
import json
import pandas as pd
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError


import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not found in .env")
client = MongoClient(MONGO_URI)
db = client["hr"]

def parse_date(value):

    # returns good date compaitible with mongodb
    if pd.isna(value) or value == "":
        return None

    if isinstance(value, (dt, pd.Timestamp)):
        return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value

    val = str(value).strip()

    date_formats = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d-%b-%Y",                 
    "%d-%b-%Y".upper(),         
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f%z"    
    ]

    for fmt in date_formats:
        try:
            return dt.strptime(val, fmt)
        except:
            pass

    return None



def normalize_doc_generic(raw_doc, fields, key_renames, numeric_fields, date_fields):
    
    cleaned = {}

    for field in fields:
        old_key = field
        new_key = key_renames.get(field, field)

        value = raw_doc.get(old_key)

        # Missing value
        if value is None:
            if new_key in numeric_fields:
                cleaned[new_key] = None
            elif new_key in date_fields:
                cleaned[new_key] = None  
            else:
                cleaned[new_key] = "NA"
            continue

        # Date fields
        if new_key in date_fields:
            # If already MongoDB extended JSON date, keep as is
            if isinstance(value, dict) and "$date" in value:
                cleaned[new_key] = value
            else:
                cleaned[new_key] = parse_date(value)
            continue

        # Numeric fields
        if new_key in numeric_fields:
            try:
                cleaned[new_key] = int(value)
            except Exception:
                cleaned[new_key] = None
            continue

        # Default: treat as string field
        value_str = str(value).strip()
        cleaned[new_key] = value_str if value_str else "NA"


    return cleaned

def normalize_columns(df):
    df.columns = (
        df.columns
        .astype(str)
        .str.replace(r"[\n\t]+", " ", regex=True)   # remove \n, \t
        .str.strip()                               # trim ends
        .str.replace(r"\s+", " ", regex=True)      # collapse spaces
    )
    return df


def process_and_upload_base_report(file_path: str):


    # ----------- Read Excel ----------- #
    df = pd.read_excel(file_path, skiprows=0)

    base_config = REPORT_CONFIG["base_report"]
    FIELDS = base_config["FIELDS"]
    KEY_RENAMES = base_config["KEY_RENAMES"]
    NUMERIC_FIELDS = base_config["NUMERIC_FIELDS"]
    DATE_FIELDS = base_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            raise IndexError(
                f"Unexpected column found: {col}. "
                f"Check config.py for expected columns."
            )

    df = df.where(df.notna(), None)
    df = df.where("", None)

    # ----------- Normalize rows ----------- #
    raw_docs = [row.to_dict() for _, row in df.iterrows()]

    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]

    # ---------- Build employee lookup ---------- #
    employee_lookup = {}

    for doc in normalized_docs:
        emp_code = doc.get("employee code")
        if emp_code:
            employee_lookup[emp_code] = doc

    # ---------- Enrich manager details ---------- #
    for doc in normalized_docs:
        manager_code = doc["manager employee code"]

        manager_details = None

        if manager_code in employee_lookup.keys():
            manager_doc = employee_lookup[manager_code]

            manager_details = {
                "manager name": manager_doc.get("first name")+" "+manager_doc.get("last name"),
                "manager email": manager_doc.get("email"),
                "manager designation": manager_doc.get("designation")
            }

        doc["manager details"] = manager_details

    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["base_report"]

    session = client.start_session()

    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


def process_and_upload_goal_detail_report(file_path):

    df=pd.read_excel(file_path,skiprows=1)

    goal_detail_config=REPORT_CONFIG["goal_detail_report"]
    FIELDS=goal_detail_config["FIELDS"]
    KEY_RENAMES=goal_detail_config["KEY_RENAMES"]
    NUMERIC_FIELDS=goal_detail_config["NUMERIC_FIELDS"]
    DATE_FIELDS=goal_detail_config["DATE_FIELDS"]
    
    for col in df.columns:
        if col not in FIELDS:
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []

    df = df.where(df.notna(), None)
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]

    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["goal_detail_report"]

    session = client.start_session()

    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_historical_ratings_and_other_information(file_path):

    df=pd.read_excel(file_path)
    hist_config=REPORT_CONFIG["historical_ratings_and_other_information"]
    FIELDS=hist_config["FIELDS"]
    KEY_RENAMES=hist_config["KEY_RENAMES"]
    NUMERIC_FIELDS=hist_config["NUMERIC_FIELDS"]
    DATE_FIELDS=hist_config["DATE_FIELDS"]
    
    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []


    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["historical_ratings_and_other_information"]

    session = client.start_session()

    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_performance_360_degree_feedback_participants_status_all(file_path):
    df=pd.read_excel(file_path)
    p360_config=REPORT_CONFIG["performance_360_feedback_participants_status_all"]
    FIELDS=p360_config["FIELDS"]
    KEY_RENAMES=p360_config["KEY_RENAMES"]
    NUMERIC_FIELDS=p360_config["NUMERIC_FIELDS"]
    DATE_FIELDS=p360_config["DATE_FIELDS"]
    
    for col in df.columns:
        if col not in FIELDS:
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []


    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["performance_360_degree_feedback_participants_status_all"]
    

    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_pip_transaction_report(file_path):
    df=pd.read_excel(file_path)
    df = normalize_columns(df)
    df.columns = df.columns.str.replace(r"\.\d+$", "", regex=True)
    df = df.drop(columns=["PIP Completion date",''], errors="ignore")
    df = df.loc[:, ~df.columns.duplicated()]
    pip_tran_config=REPORT_CONFIG["pip_transaction_report"]
    FIELDS=pip_tran_config["FIELDS"]
    KEY_RENAMES=pip_tran_config["KEY_RENAMES"]
    NUMERIC_FIELDS=pip_tran_config["NUMERIC_FIELDS"]
    DATE_FIELDS=pip_tran_config["DATE_FIELDS"]
    
    for col in df.columns:
        if col.strip() not in FIELDS:
            print(FIELDS)
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []


    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["pip_transaction_report"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


def process_and_upload_pms_task(file_path):
    df=pd.read_excel(file_path)
    pms_task_config=REPORT_CONFIG["pms_task_status_report_all"]
    FIELDS=pms_task_config["FIELDS"]
    KEY_RENAMES=pms_task_config["KEY_RENAMES"]
    NUMERIC_FIELDS=pms_task_config["NUMERIC_FIELDS"]
    DATE_FIELDS=pms_task_config["DATE_FIELDS"]
    
    for col in df.columns:
        if col not in FIELDS:
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []


    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["pms_task_status_report_all"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


def process_and_upload_leave_transaction(file_path):

    df=pd.read_excel(file_path,skiprows=1)


    #Convert to string and strip whitespace
    df["ABSENCE_NAME"] = df["ABSENCE_NAME"].astype(str).str.strip()

    #  Remove trailing dots
    df["ABSENCE_NAME"] = df["ABSENCE_NAME"].str.replace(r"\.+$", "", regex=True)

    #  Normalize hyphen usage and extra spaces
    df["ABSENCE_NAME"] = (
        df["ABSENCE_NAME"]
        .str.replace("-", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # 4. Standardize final values
    df["ABSENCE_NAME"] = df["ABSENCE_NAME"].replace({
        "Casual Leave": "Casual Leave",
        "Sick Leave": "Sick Leave",
        "Annual Leave": "Annual Leave"
    })

    leave_trans_config=REPORT_CONFIG["leave_transaction_with_balance_report_leave_transaction_with_balance_report"]
    FIELDS=leave_trans_config["FIELDS"]
    KEY_RENAMES=leave_trans_config["KEY_RENAMES"]
    NUMERIC_FIELDS=leave_trans_config["NUMERIC_FIELDS"]
    DATE_FIELDS=leave_trans_config["DATE_FIELDS"]
    
    for col in df.columns:
        print(col)
        if col not in FIELDS:
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []


    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)
    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["leave_transaction_with_balance_report"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_performance_goal_report(file_path):
    df=pd.read_excel(file_path,skiprows=2)

    perf_goal_config=REPORT_CONFIG["performance_goal_report_2025_2026"]
    FIELDS=perf_goal_config["FIELDS"]
    KEY_RENAMES=perf_goal_config["KEY_RENAMES"]
    NUMERIC_FIELDS=perf_goal_config["NUMERIC_FIELDS"]
    DATE_FIELDS=perf_goal_config["DATE_FIELDS"]

    print(FIELDS)
    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )

    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["performance_goal_report_2025_2026"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_goal_status_report(file_path):

    df=pd.read_excel(file_path,skiprows=1)

    goal_setting_config=REPORT_CONFIG["goal_setting_status"]
    FIELDS=goal_setting_config["FIELDS"]
    KEY_RENAMES=goal_setting_config["KEY_RENAMES"]
    NUMERIC_FIELDS=goal_setting_config["NUMERIC_FIELDS"]
    DATE_FIELDS=goal_setting_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["goal_setting_status"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


# --- Offboarding Checklist Automation ---
def process_and_upload_offboarding_checklist(file_path):
    """
    Automated cleaning and upload for Offboarding Checklist, using flattened Core HR fields.
    Reads the config from ingestion.config.REPORT_CONFIG["offboarding_checklist"].
    Expects Core HR fields at the top level, not nested.
    """

    config = REPORT_CONFIG["offboarding_checklist"]
    FIELDS = config["FIELDS"]
    KEY_RENAMES = config["KEY_RENAMES"]
    NUMERIC_FIELDS = config["NUMERIC_FIELDS"]
    DATE_FIELDS = config["DATE_FIELDS"]
    #TARGET_COLLECTION = config["TARGET_COLLECTION"]
    TARGET_COLLECTION = "oc_test"
    # Read Excel with multi-index columns (for nested sections)
    df = pd.read_excel(file_path, header=[0, 1])
    df = df.where(df.notna(), None)

    # Only flatten Core HR fields, keep others nested
    processed_rows = []
    core_hr_fields = [k for k in FIELDS if not isinstance(FIELDS[k], list)]
    nested_sections = [k for k in FIELDS if isinstance(FIELDS[k], list)]
    for _, row in df.iterrows():
        doc = {}
        # Flatten Core HR fields
        for field in core_hr_fields:
            try:
                doc[field] = row[("Core HR", field)]
            except Exception:
                doc[field] = None
        # Keep other sections nested
        for section in nested_sections:
            section_dict = {}
            for field in FIELDS[section]:
                try:
                    section_dict[field] = row[(section, field)]
                except Exception:
                    section_dict[field] = None
            doc[section] = section_dict
        processed_rows.append(doc)

    # Normalize: flatten only Core HR fields, keep others nested
    normalized_docs = []
    for doc in processed_rows:
        # Normalize Core HR fields
        norm_core_hr = normalize_doc_generic(
            {k: doc[k] for k in core_hr_fields},
            core_hr_fields,
            KEY_RENAMES.get("Core HR", {}),
            set(NUMERIC_FIELDS.get("Core HR", [])),
            set(DATE_FIELDS.get("Core HR", [])),
        )
        # Normalize nested sections
        for section in nested_sections:
            norm_section = normalize_doc_generic(
                doc[section],
                FIELDS[section],
                KEY_RENAMES.get(section, {}),
                set(NUMERIC_FIELDS.get(section, [])),
                set(DATE_FIELDS.get(section, [])),
            )
            norm_core_hr[section] = norm_section
        normalized_docs.append(norm_core_hr)

    # MongoDB Transaction
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db[TARGET_COLLECTION]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)
            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)
    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")
    finally:
        session.end_session()
        client.close()
    return


def process_and_upload_rr_thank_you(file_path):
    df=pd.read_excel(file_path,sheet_name="Thank You")

    rr_thank_you_config=REPORT_CONFIG["r&r_thank_you"]
    FIELDS=rr_thank_you_config["FIELDS"]
    KEY_RENAMES=rr_thank_you_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_thank_you_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_thank_you_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_thank_you_report"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_rr_debutant_of_the_qtr(file_path):
    df=pd.read_excel(file_path,sheet_name="Debutant of the Qtr")

    rr_debutant_config=REPORT_CONFIG["r&r_debutant_of_the_qtr"]
    FIELDS=rr_debutant_config["FIELDS"]
    KEY_RENAMES=rr_debutant_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_debutant_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_debutant_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_debutant_of_the_qtr"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_rr_ceo_of_the_quarter(file_path):
    df=pd.read_excel(file_path,sheet_name="CEO of the Quarter")

    rr_ceo_config=REPORT_CONFIG["r&r_ceo_of_the_quarter"]
    FIELDS=rr_ceo_config["FIELDS"]
    KEY_RENAMES=rr_ceo_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_ceo_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_ceo_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_ceo_of_the_quarter"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_rr_cross_functional(file_path):
    df=pd.read_excel(file_path,sheet_name="Cross Functional")

    rr_cfc_config=REPORT_CONFIG["r&r_cross_functional"]
    FIELDS=rr_cfc_config["FIELDS"]
    KEY_RENAMES=rr_cfc_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_cfc_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_cfc_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_cross_functional"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


def process_and_upload_rr_intrafunctional(file_path):
    df=pd.read_excel(file_path,sheet_name="Intrafunctional ")

    rr_func_config=REPORT_CONFIG["r&r_intrafunctional"]
    FIELDS=rr_func_config["FIELDS"]
    KEY_RENAMES=rr_func_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_func_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_func_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_intrafunctional"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return

def process_and_upload_rr_job_well_done(file_path):
    df=pd.read_excel(file_path,sheet_name="Job Well Done")

    rr_jwd_config=REPORT_CONFIG["r&r_job_well_done"]
    FIELDS=rr_jwd_config["FIELDS"]
    KEY_RENAMES=rr_jwd_config["KEY_RENAMES"]
    NUMERIC_FIELDS=rr_jwd_config["NUMERIC_FIELDS"]
    DATE_FIELDS=rr_jwd_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
            print(col)
            raise IndexError(
                f"File doesn't contain Expected Columns."
                f"check config.py for expected columns"
            )
    raw_docs = []
    df = df.where(df.notna(), None)
    # Convert each DF row → raw dict
    for idx, row in df.iterrows():
        raw_doc = row.to_dict()


        raw_docs.append(raw_doc)

    # Normalize
    normalized_docs = [
        normalize_doc_generic(
            doc,
            FIELDS,
            KEY_RENAMES,
            NUMERIC_FIELDS,
            DATE_FIELDS
        )
        for doc in raw_docs
    ]
    # ---------- MongoDB Transaction ---------- #
    client = MongoClient(MONGO_URI)
    db = client["hr-cleaned"]
    collection = db["r&r_job_well_done"]
    session = client.start_session()
    try:
        with session.start_transaction():
            collection.delete_many({}, session=session)

            if normalized_docs:
                collection.insert_many(normalized_docs, session=session)

    except PyMongoError as e:
        session.abort_transaction()
        raise RuntimeError(f"MongoDB transaction failed: {e}")

    finally:
        session.end_session()
        client.close()
    return


def verify_impoortant_fields(
    db_name: str="hr-cleaned",
    base_collection_name: str = "base_report"
):
    client = MongoClient(MONGO_URI)
    db = client[db_name]

    base_collection = db[base_collection_name]

    # -------- Build lookup from base_report -------- #
    base_lookup = {}
    for doc in base_collection.find({}, {
        "employee code": 1,
        "region": 1,
        "department": 1,
        "grade": 1
    }):
        emp_code = doc.get("employee code")
        if emp_code:
            base_lookup[str(emp_code)] = {
                "region": doc.get("region"),
                "department": doc.get("department"),
                "grade": doc.get("grade"),
            }

    exceptions = set()

    # -------- Iterate all collections -------- #
    for collection_name in db.list_collection_names():
        if collection_name == base_collection_name:
            continue

        collection = db[collection_name]

        for doc in collection.find():
            doc_id = doc["_id"]

            emp_code = doc.get("employee code")

            # Fallback: receiver employee code
            if not emp_code:
                emp_code = doc.get("receiver employee code")
                if emp_code:
                    collection.update_one(
                        {"_id": doc_id},
                        {"$set": {"employee code": emp_code}}
                    )

            # If still missing → exception
            if not emp_code:
                exceptions.add(collection_name)
                continue

            emp_code = str(emp_code)

            base_data = base_lookup.get(emp_code)
            if not base_data:
                continue  # employee not found in base_report, skip silently

            update_fields = {}
            for field in ["region", "department", "grade"]:
                if field not in doc and base_data.get(field) is not None:
                    update_fields[field] = base_data[field]

            if update_fields:
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": update_fields}
                )

    return sorted(list(exceptions))