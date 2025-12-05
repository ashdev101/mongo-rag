from datetime import datetime as dt
from config import REPORT_CONFIG, ReportName
import json
import pandas as pd
from pathlib import Path



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




def route_report(file_path: str | Path) -> ReportName:

    """
    Validate if the input filename belongs to a known ReportName.
    Returns the matched ReportName enum.
    Raises ValueError if no match is found.
    """

    file_path = Path(file_path)
    filename = file_path.name.lower()
    filename = filename.replace(" - ","_")
    filename=filename.replace(" ","_")
    filename=filename.replace("-","_")
    filename=filename.split(".")[0]


    # strict scan: check each enum value inside filename
    matches = []

    for report in ReportName:
        value = report.value.lower()
        name = report.name.lower()

        if value in filename or name in filename:
            matches.append(report)

    # if multiple matches → ambiguous, force the user to fix naming
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous file name '{filename}'. Matches multiple report types: "
            f"{[m.value for m in matches]}"
        )

    # no match found
    if not matches:
        raise ValueError(
            f"File '{filename}' does not match any valid report type in ReportName enum."
        )

    # return the single matched report
    return matches[0]


def main_clean():
    pass

def clean_historical_rating(file_path):

    if not file_path.endswith("Historical Ratings and Other Information.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path)
    hist_config=REPORT_CONFIG["historical_ratings_and_other_information"]
    FIELDS=hist_config["FIELDS"]
    KEY_RENAMES=hist_config["KEY_RENAMES"]
    NUMERIC_FIELDS=hist_config["NUMERIC_FIELDS"]
    DATE_FIELDS=hist_config["DATE_FIELDS"]
    
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path
    

def clean_performance_360(file_path):

    if not file_path.endswith("Performance 360 degree Feedback participants status - All.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def clean_pip_transaction(file_path):

    if not file_path.endswith("PIP Transaction Report.xls"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path)
    df = df.loc[:, ~df.columns.duplicated()]
    pip_tran_config=REPORT_CONFIG["pip_transaction_report"]
    FIELDS=pip_tran_config["FIELDS"]
    KEY_RENAMES=pip_tran_config["KEY_RENAMES"]
    NUMERIC_FIELDS=pip_tran_config["NUMERIC_FIELDS"]
    DATE_FIELDS=pip_tran_config["DATE_FIELDS"]
    
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def clean_pms_q2(file_path):

    if not file_path.endswith("PMS Q2 25-26 Rating report - all.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path,skiprows=2)

    # flattening the df
    row_counts = df.count(axis=1)
    row_counts

    MAIN_MIN = 10 
    CONT_MAX = 4    
    classifications = []  

    for i in range(len(df)):
        cnt = row_counts[i]

        if cnt >= MAIN_MIN:
            classifications.append("main")
        elif cnt <= CONT_MAX:
            classifications.append("cont")
        else:
            classifications.append("unknown")
    merged_blocks = []
    i = 0

    while i < len(df):
        if classifications[i] == "main":
            block = [i]

            # collect all continuation rows after it
            j = i + 1
            while j < len(df) and classifications[j] == "cont":
                block.append(j)
                j += 1

            merged_blocks.append(block)
            i = j

        elif classifications[i] == "cont":
            merged_blocks.append([i])   # stray continuation (bad data)
            i += 1

        else:
            merged_blocks.append([i])   # unknown irregular row
            i += 1

    flattened_rows = []
    cols = df.columns
    for block in merged_blocks:
        # Take the first (main) row of the block
        main_idx = block[0]
        main_row = df.loc[main_idx].copy()

        # If block has more than one row, merge continuation rows
        if len(block) > 1:
            for cont_idx in block[1:]:
                cont_row = df.loc[cont_idx]

                # For each column, if continuation has value, override main
                for col in cols:
                    if pd.notna(cont_row[col]):
                        main_row[col] = cont_row[col]

        # Store the assembled row
        flattened_rows.append(main_row)
    flattened_df = pd.DataFrame(flattened_rows, columns=cols)
    flattened_df.reset_index(drop=True, inplace=True)
    
    pms_q2_config=REPORT_CONFIG["pms_q2_25_26_rating_report_all"]
    FIELDS=pms_q2_config["FIELDS"]
    KEY_RENAMES=pms_q2_config["KEY_RENAMES"]
    NUMERIC_FIELDS=pms_q2_config["NUMERIC_FIELDS"]
    DATE_FIELDS=pms_q2_config["DATE_FIELDS"]
    
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def clean_pms_task(file_path):

    if not file_path.endswith("PMS Task Status Report All.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path



def clean_leave_transaction(file_path):

    if not file_path.endswith("PMS Task Status Report All.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path,skiprows=1)
    leave_trans_config=REPORT_CONFIG["leave_transaction_with_balance_report_leave_transaction_with_balance_report"]
    FIELDS=leave_trans_config["FIELDS"]
    KEY_RENAMES=leave_trans_config["KEY_RENAMES"]
    NUMERIC_FIELDS=leave_trans_config["NUMERIC_FIELDS"]
    DATE_FIELDS=leave_trans_config["DATE_FIELDS"]
    
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path



def clean_goal_detail(file_path):

    if not file_path.endswith("PMS Task Status Report All.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )

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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def normalize_nested_row(row, fields, key_renames, numeric_fields, date_fields):

    """
    row: pandas Series where row[key] is accessed with multi-level keys
         e.g., row["Core HR"]["Grade"]
    fields: dict of section → list of fields
    key_renames: dict of section → dict of old→new names
    numeric_fields: dict of section → set of numeric field names
    date_fields: dict of section → set of date field names
    """

    cleaned_sections = {}

    for section, field_list in fields.items():
        section_cleaned = {}

        for field in field_list:
            raw_value = None

            # Retrieve nested value if section exists
            try:
                raw_value = row[(section, field)]
            except Exception:
                raw_value = None

            # Rename field inside the section
            new_field = key_renames.get(section, {}).get(field, field)

            # Determine numeric/date membership
            section_numeric = numeric_fields.get(section, set())
            section_dates = date_fields.get(section, set())

            # Build a fake 1D raw_doc to reuse normalize_doc_generic
            fake_raw = {field: raw_value}

            cleaned_value = normalize_doc_generic(
                fake_raw,
                fields=[field],
                key_renames={field: new_field},
                numeric_fields=section_numeric,
                date_fields=section_dates
            )[new_field]

            section_cleaned[new_field] = cleaned_value

        cleaned_sections[section] = section_cleaned

    return cleaned_sections


def clean_offboarding_checklist(file_path):

    if not file_path.endswith("Output1.xls"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )

    df = pd.read_excel(file_path, header=[0, 1])
    df = df.where(df.notna(), None)

    OBC_config=REPORT_CONFIG["offboarding_checklist"]
    FIELDS=OBC_config["FIELDS"]
    KEY_RENAMES=OBC_config["KEY_RENAMES"]
    NUMERIC_FIELDS=OBC_config["NUMERIC_FIELDS"]
    DATE_FIELDS=OBC_config["DATE_FIELDS"]
    
    
    normalized_docs = []

    for _, row in df.iterrows():
        nested_cleaned = normalize_nested_row(
            row=row,
            fields=FIELDS,
            key_renames=KEY_RENAMES,
            numeric_fields=NUMERIC_FIELDS,
            date_fields=DATE_FIELDS
        )
        normalized_docs.append(nested_cleaned)

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path

def clean_base_report(file_path):

    if not file_path.endswith("1.DatabaseReport_Rpt_Data base Report_for Kreeda Labs.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    
    df=pd.read_excel(file_path,skiprows=0)

    base_config=REPORT_CONFIG["base_report"]
    FIELDS=base_config["FIELDS"]
    KEY_RENAMES=base_config["KEY_RENAMES"]
    NUMERIC_FIELDS=base_config["NUMERIC_FIELDS"]
    DATE_FIELDS=base_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def clean_perf_goal(file_path):
    
    if not file_path.endswith("Performance Goal Report 25-26.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path,skiprows=1)

    perf_goal_config=REPORT_CONFIG["base_report"]
    FIELDS=perf_goal_config["FIELDS"]
    KEY_RENAMES=perf_goal_config["KEY_RENAMES"]
    NUMERIC_FIELDS=perf_goal_config["NUMERIC_FIELDS"]
    DATE_FIELDS=perf_goal_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
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

    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path


def clean_goal_status_report(file_path):

    if not file_path.endswith("Goal Status Report 2025-26 All.xlsx"):
        raise FileExistsError(
            f"Filename does not match with known file names."
            "check config.py for valid file names"
            )
    df=pd.read_excel(file_path,skiprows=2)

    goal_setting_config=REPORT_CONFIG["goal_setting_status"]
    FIELDS=goal_setting_config["FIELDS"]
    KEY_RENAMES=goal_setting_config["KEY_RENAMES"]
    NUMERIC_FIELDS=goal_setting_config["NUMERIC_FIELDS"]
    DATE_FIELDS=goal_setting_config["DATE_FIELDS"]

    for col in df.columns:
        if col not in FIELDS:
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


    p = Path(file_path)
    output_dir = Path("json_output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{p.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_docs, f, ensure_ascii=False, indent=2)
    return output_path
