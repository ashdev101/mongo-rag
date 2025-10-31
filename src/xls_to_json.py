# import pandas as pd
# import json
# from pathlib import Path
# from datetime import datetime
# import re

# # --- Helper functions ---

# def prettify_key(key: str) -> str:
#     """
#     Convert messy keys into lowercase, readable keys.
#     Example:
#         'exit_checklist_-_employee' -> 'exit checklist employee'
#     """
#     if pd.isna(key):
#         return ""
#     key = str(key)
#     # Replace underscores and hyphens with spaces
#     key = key.replace("_", " ").replace("-", " ")
#     # Remove punctuation like (), /, ., :
#     key = re.sub(r"[()/,.:]+", " ", key)
#     # Remove multiple spaces  
#     key = re.sub(r"\s+", " ", key)
#     return key.strip().lower()


# def is_date_column(name: str) -> bool:
#     """Detect date-like columns by name."""
#     date_keywords = [
#         "date", "joining", "resignation", "leaving", "dob",
#         "date_of_birth", "date_of_joining", "date_of_resignation", "date_of_leaving"
#         "start_date", "end_date" ,"doj"
#     ]
#     return any(k in name.lower() for k in date_keywords)


# def convert_to_mongo_date(value):
#     """Convert datetime or string to MongoDB Extended JSON date."""
#     if pd.isna(value) or value == "":
#         return ""
#     if isinstance(value, (datetime, pd.Timestamp)):
#         return {"$date": value.strftime("%Y-%m-%dT%H:%M:%SZ")}
#     for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d-%b-%Y"):
#         try:
#             dt = datetime.strptime(str(value), fmt)
#             return {"$date": dt.strftime("%Y-%m-%dT%H:%M:%SZ")}
#         except ValueError:
#             continue
#     return value


# def excel_to_nested_json(input_path: str, output_path: str):
#     """
#     Converts Excel with merged or normal headers into nested JSON.
#     Converts date-like fields into MongoDB Extended JSON format.
#     Keys are cleaned to lowercase, human-readable format.
#     """
#     input_path = Path(input_path)
#     engine = 'xlrd' if input_path.suffix.lower() == '.xls' else 'openpyxl'
#     excel = pd.ExcelFile(input_path, engine=engine)
#     all_docs = []

#     for sheet_name in excel.sheet_names:
#         print(f"📄 Reading sheet: {sheet_name}")

#         df = pd.read_excel(input_path, sheet_name=sheet_name, header=[0, 1])

#         # Single header
#         if not isinstance(df.columns[0], tuple):
#             df = pd.read_excel(input_path, sheet_name=sheet_name, header=0)
#             df.columns = [prettify_key(c) for c in df.columns]
#             df = df.fillna("")
#             for col in df.columns:
#                 if is_date_column(col):
#                     df[col] = df[col].apply(convert_to_mongo_date)
#             all_docs.extend(df.to_dict(orient="records"))
#             continue

#         # Multi-header (merged)
#         df.columns = [(prettify_key(a), prettify_key(b)) for a, b in df.columns]
#         df = df.fillna("")

#         for _, row in df.iterrows():
#             doc = {}
#             for (main, sub), value in row.items():
#                 if not main and sub:
#                     key = prettify_key(sub)
#                     val = convert_to_mongo_date(value) if is_date_column(key) else value
#                     doc[key] = val
#                 else:
#                     main_key = prettify_key(main)
#                     sub_key = prettify_key(sub)
#                     val = convert_to_mongo_date(value) if is_date_column(sub_key) else value
#                     if not main_key:
#                         doc[sub_key] = val
#                     else:
#                         if main_key not in doc:
#                             doc[main_key] = {}
#                         doc[main_key][sub_key] = val
#             all_docs.append(doc)

#     # Write JSON file
#     output_path = Path(output_path)
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(all_docs, f, indent=4, ensure_ascii=False)

#     print(f"✅ JSON saved to: {output_path}")
#     print(f"📦 Total records: {len(all_docs)}")

# # Example usage
# input_file = r"Dataset/System Reports/7.PIP Transaction Report.xls"
# output_json = r"/home/harshchinchakar/WORK Files/TataPlay/Mongo_Rag/Outputs/xls_to_json/PIP.json"

# excel_to_nested_json(input_file, output_json)

#!/usr/bin/env python3
"""
xls_to_json_final_v2.py

Robust Excel -> JSON converter tuned to the uploaded System Reports and
the exact output contract you've described.

Interactive: prompts for input path ("Input path for file/dir :") and optional
output dir & engine.

Main improvements over prior versions:
- Robust header detection and title-row skipping.
- Footer / placeholder row removal.
- Proper multi-header handling (preserve nested objects where appropriate).
- **Post-processing flattening + coercion**:
  - If a field value is a single-key dict (common mis-parses), flatten to a scalar
    using heuristics and coerce types (int/float/date).
  - Preserve intended nested dicts (multiple subkeys).
- Exact Mongo Extended JSON date formatting: {"$date": "YYYY-MM-DDT00:00:00Z"}.
"""

from __future__ import annotations
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

# -----------------------
# Helpers: prettify, date conversion, numeric cast
# -----------------------

def prettify_key(key: Any) -> str:
    if pd.isna(key) or key is None:
        return ""
    s = str(key)
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[()/,.:]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def is_date_column(name: str) -> bool:
    if not name:
        return False
    date_keywords = [
        "date", "joining", "resignation", "leaving", "dob",
        "date_of_birth", "date_of_joining", "date_of_resignation", "date_of_leaving",
        "start_date", "end_date", "doj", "assigned on", "assigned on date"
    ]
    return any(k in name.lower() for k in date_keywords)

def _format_dt_to_mongo(dt: datetime) -> Dict[str, str]:
    return {"$date": dt.strftime("%Y-%m-%dT%H:%M:%SZ")}

def convert_to_mongo_date(value: Any) -> Any:
    if pd.isna(value) or value == "":
        return ""
    if isinstance(value, (datetime, pd.Timestamp)):
        dt = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
        dt_mid = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
        return _format_dt_to_mongo(dt_mid)
    if isinstance(value, (int, float)) and not math.isnan(value):
        try:
            dt = datetime(1899, 12, 30) + timedelta(days=float(value))
            dt_mid = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            return _format_dt_to_mongo(dt_mid)
        except Exception:
            pass
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%b-%y"):
        try:
            dt = datetime.strptime(s, fmt)
            dt_mid = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            return _format_dt_to_mongo(dt_mid)
        except Exception:
            continue
    try:
        parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if not pd.isna(parsed):
            dt = parsed.to_pydatetime()
            dt_mid = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            return _format_dt_to_mongo(dt_mid)
    except Exception:
        pass
    return value

_NUMBER_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?\d*\.\d+$")

def try_cast_number(val: Any) -> Any:
    """If val (string) is an integer or float, cast accordingly. Otherwise return original."""
    if isinstance(val, (int, float)):
        return val
    if val is None:
        return val
    s = str(val).strip()
    if _NUMBER_RE.match(s):
        try:
            return int(s)
        except Exception:
            pass
    if _FLOAT_RE.match(s):
        try:
            return float(s)
        except Exception:
            pass
    return val

# -----------------------
# Placeholder/footer detection & cleaning
# -----------------------

PLACEHOLDER_PATTERNS = [
    re.compile(r"^<\?.*\?>$", re.IGNORECASE),
    re.compile(r"^XDO_.*", re.IGNORECASE),
    re.compile(r"^<\?\w+_.*\?>$", re.IGNORECASE),
    re.compile(r"^\?{0,1}<?[A-Z0-9_]+>\??$", re.IGNORECASE),
]

def is_placeholder_value(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    if s == "":
        return False
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(s):
            return True
    return False

def drop_footer_and_noise_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.shape[0] == 0:
        return df
    df = df.fillna("")
    # Remove fully empty rows
    df = df[~df.apply(lambda r: all(str(x).strip() == "" for x in r), axis=1)].reset_index(drop=True)

    ncols = max(1, df.shape[1])
    footer_start = None
    for i in range(df.shape[0] - 1, -1, -1):
        row = df.iloc[i]
        placeholder_count = sum(1 for v in row if is_placeholder_value(v))
        empty_count = sum(1 for v in row if str(v).strip() == "")
        if (placeholder_count + empty_count) >= 0.75 * ncols:
            footer_start = i
        else:
            if footer_start is not None:
                break
    if footer_start is not None:
        df = df.iloc[:footer_start].reset_index(drop=True)

    # Remove rows that are duplicates of header row (sometimes exports repeat header)
    if df.shape[0] >= 2:
        try:
            if all(str(x).strip() == str(y).strip() for x, y in zip(df.iloc[0].tolist(), df.iloc[1].tolist())):
                df = df.drop(index=1).reset_index(drop=True)
        except Exception:
            pass

    # Remove trailing rows that are now placeholders
    df = df[~df.apply(lambda r: all(is_placeholder_value(v) or str(v).strip() == "" for v in r), axis=1)].reset_index(drop=True)
    return df

# -----------------------
# Header detection & reading
# -----------------------

def _read_sample_rows(input_path: Path, sheet: str, engine: str, nrows: int = 8) -> pd.DataFrame:
    return pd.read_excel(input_path, sheet_name=sheet, header=None, nrows=nrows, engine=engine)

def detect_header_rows(input_path: Path, sheet_name: str, engine: str, max_rows: int = 8) -> Sequence[int]:
    try:
        sample = _read_sample_rows(input_path, sheet_name, engine, nrows=max_rows)
    except Exception:
        return [0]
    ncols = max(1, sample.shape[1])
    non_empty_counts = [sample.iloc[r].notna().sum() for r in range(sample.shape[0])]
    non_empty_ratios = [cnt / ncols for cnt in non_empty_counts]
    candidates = [i for i, ratio in enumerate(non_empty_ratios) if ratio >= 0.3]
    if not candidates:
        for i, ratio in enumerate(non_empty_ratios):
            if ratio > 0:
                return [i]
        return [0]
    first = candidates[0]
    if non_empty_counts[first] == 1:
        if len(candidates) > 1:
            first = candidates[1]
        else:
            if len(non_empty_ratios) > first + 1 and non_empty_ratios[first + 1] >= 0.25:
                first = first + 1
    if first + 1 < len(non_empty_ratios):
        second_ratio = non_empty_ratios[first + 1]
        if second_ratio >= 0.3:
            second_row = sample.iloc[first + 1].astype(str).fillna("")
            textual_count = sum(1 for v in second_row if re.search(r"[A-Za-z]", v))
            if textual_count >= max(1, ncols // 4):
                return [first, first + 1]
    return [first]

def collapse_multiindex_levels(levels: Tuple[Any, ...]) -> Tuple[str, str]:
    str_levels = ["" if pd.isna(x) else str(x) for x in levels]
    if len(str_levels) <= 2:
        main = str_levels[0] if len(str_levels) > 0 else ""
        sub = str_levels[1] if len(str_levels) > 1 else ""
    else:
        main = " ".join([s for s in str_levels[:-1] if s])
        sub = str_levels[-1]
    return main, sub

def _safe_excel_file(input_path: Path, engine_hint: Optional[str] = None) -> Tuple[pd.ExcelFile, str]:
    suffix = input_path.suffix.lower()
    preferred = engine_hint or ("xlrd" if suffix == ".xls" else "openpyxl")
    tried = []
    for eng in [preferred, "openpyxl", "xlrd", "pyxlsb"]:
        if eng in tried:
            continue
        tried.append(eng)
        try:
            excel = pd.ExcelFile(input_path, engine=eng)
            return excel, eng
        except Exception:
            continue
    raise RuntimeError(f"Unable to open {input_path} with engines: {tried}")

def _read_sheet(input_path: Path, sheet_name: str, engine: str, header_rows: Sequence[int]) -> pd.DataFrame:
    try:
        df = pd.read_excel(input_path, sheet_name=sheet_name, header=header_rows, engine=engine)
    except Exception:
        raw = pd.read_excel(input_path, sheet_name=sheet_name, header=None, engine=engine)
        if len(header_rows) == 1:
            r = header_rows[0]
            if raw.shape[0] > r:
                cols = raw.iloc[r].fillna("").tolist()
                data = raw.iloc[r + 1 :].reset_index(drop=True)
                df = pd.DataFrame(data.values, columns=cols)
            else:
                df = raw
        else:
            r1, r2 = header_rows[0], header_rows[1]
            if raw.shape[0] > max(r1, r2):
                header_arr1 = raw.iloc[r1].fillna("")
                header_arr2 = raw.iloc[r2].fillna("")
                header = pd.MultiIndex.from_arrays([header_arr1.values, header_arr2.values])
                data = raw.iloc[max(r1, r2) + 1 :].reset_index(drop=True)
                df = pd.DataFrame(data.values, columns=header)
            else:
                df = raw
    return df

# -----------------------
# Post-processing flatten & coerce
# -----------------------

def flatten_single_key_dicts(obj: Any) -> Any:
    """
    Recursively traverse obj (which is likely a dict) and flatten any dicts of form:
      key: { inner_key: inner_value }
    into key: chosen_scalar where heuristics choose which side (inner_key or inner_value)
    and perform type coercion (int/float/date) when appropriate.
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            # Recursively process v first
            v_proc = flatten_single_key_dicts(v)
            # handle single-key dict case
            if isinstance(v_proc, dict) and len(v_proc) == 1:
                inner_k, inner_v = next(iter(v_proc.items()))
                chosen = decide_flatten_value(inner_k, inner_v, parent_key=k)
                out[k] = flatten_single_key_dicts(chosen) if isinstance(chosen, dict) else chosen
            else:
                out[k] = v_proc
        return out
    elif isinstance(obj, list):
        return [flatten_single_key_dicts(x) for x in obj]
    else:
        return obj

def decide_flatten_value(inner_k: Any, inner_v: Any, parent_key: Optional[str] = None) -> Any:
    """
    Decide whether to use inner_k or inner_v (or a coerced variant) when flattening.
    Heuristics used:
    1. If inner_v is non-empty and not equal (case-insensitive) to inner_k -> prefer inner_v.
    2. If inner_v is empty (""), but inner_k looks numeric -> cast and use inner_k.
    3. If inner_v equals inner_k (modulo case) -> prefer inner_v (preserves original casing).
    4. If either side is date-like, parse to Mongo date form using convert_to_mongo_date.
    5. Else prefer inner_v if non-empty else inner_k.
    Finally attempt to cast numeric strings to int/float.
    """
    ik = inner_k
    iv = inner_v
    # normalize to strings for comparisons
    iks = "" if ik is None else str(ik).strip()
    ivs = "" if iv is None else str(iv).strip()

    # If inner_v non-empty and different from inner_k (case-insensitive), prefer inner_v
    if ivs and (iks.lower() != ivs.lower()):
        # If date-like prefer parsed date
        parsed = try_date_from_string(ivs)
        if parsed is not None:
            return parsed
        # numeric cast
        num = try_cast_number(ivs)
        return num

    # If inner_v empty but inner_k looks numeric -> use numeric cast of inner_k
    if (not ivs) and iks:
        num = try_cast_number(iks)
        if isinstance(num, (int, float)):
            return num
        # try date parse of inner_k
        parsed = try_date_from_string(iks)
        if parsed is not None:
            return parsed
        # otherwise return original inner_k string
        return iks

    # If both present and equal modulo case -> preserve inner_v (keeps original casing)
    if ivs and iks and iks.lower() == ivs.lower():
        # try parse date first
        parsed = try_date_from_string(ivs)
        if parsed is not None:
            return parsed
        num = try_cast_number(ivs)
        return num

    # fallback: if inner_v present, parse number/date then return
    if ivs:
        parsed = try_date_from_string(ivs)
        if parsed is not None:
            return parsed
        num = try_cast_number(ivs)
        return num

    # fallback use inner_k
    parsed = try_date_from_string(iks)
    if parsed is not None:
        return parsed
    num = try_cast_number(iks)
    return num if not isinstance(num, str) else iks

def try_date_from_string(s: str) -> Optional[Dict[str, str]]:
    """Try to parse string s to Mongo date dict; return None if not parseable."""
    if s is None:
        return None
    candidate = convert_to_mongo_date(s)
    if isinstance(candidate, dict) and "$date" in candidate:
        return candidate
    return None

# -----------------------
# Workbook processing orchestrator (keeps earlier robust logic)
# -----------------------

def process_workbook(input_path: Path, output_path: Path, engine_hint: Optional[str] = None) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    excel, engine = _safe_excel_file(input_path, engine_hint=engine_hint)
    all_docs: List[dict] = []

    for sheet in excel.sheet_names:
        print(f"[R] Reading sheet '{sheet}'")
        try:
            header_rows = detect_header_rows(input_path, sheet, engine=engine, max_rows=8)
            header_rows = header_rows[:2]
        except Exception:
            header_rows = [0]

        df = _read_sheet(input_path, sheet, engine=engine, header_rows=header_rows)
        df = df.dropna(axis=1, how="all")
        if df.shape[1] == 0:
            print(f"[E]  sheet '{sheet}' has no columns. Skipping.")
            continue

        df = drop_footer_and_noise_rows(df)
        if df.shape[0] == 0:
            print(f"[E]  sheet '{sheet}' empty after dropping noise. Skipping.")
            continue

        # Single header path
        if not isinstance(df.columns[0], tuple):
            cols = []
            for idx, c in enumerate(df.columns):
                pk = prettify_key(c)
                if pk == "":
                    # create a stable unnamed fallback
                    pk = f"unnamed {idx+1}"
                cols.append(pk)
            df.columns = cols
            df = df.fillna("")
            for col in df.columns:
                if is_date_column(col):
                    df[col] = df[col].apply(convert_to_mongo_date)

            # Drop rows that are repeated header rows
            df = df[~df.apply(lambda r: all(str(r[c]).strip().lower() == str(c).strip().lower() for c in df.columns), axis=1)].reset_index(drop=True)
            # Remove placeholder-only rows
            df = df[~df.apply(lambda r: all(is_placeholder_value(v) or str(v).strip() == "" for v in r), axis=1)].reset_index(drop=True)
            records = df.to_dict(orient="records")
            all_docs.extend(records)
            continue

        # Multi-index header
        new_cols: List[Tuple[str, str]] = []
        for col in df.columns:
            if isinstance(col, tuple):
                main, sub = collapse_multiindex_levels(col)
            else:
                main, sub = (str(col), "")
            new_cols.append((main, sub))

        mains = [c[0] for c in new_cols]
        subs = [c[1] for c in new_cols]
        non_empty_mains = sum(1 for m in mains if m and str(m).strip())
        total_cols = max(1, len(mains))
        main_ratio = non_empty_mains / total_cols

        # If top-level headings mostly empty -> collapse to single header using subkeys
        if main_ratio < 0.25:
            final_cols = []
            for i, sk in enumerate(subs):
                pk = prettify_key(sk)
                if pk == "":
                    pk = f"unnamed {i+1}"
                final_cols.append(pk)
            df.columns = final_cols
            df = df.fillna("")
            for col in df.columns:
                if is_date_column(col):
                    df[col] = df[col].apply(convert_to_mongo_date)
            df = df[~df.apply(lambda r: all(str(r[c]).strip().lower() == str(c).strip().lower() for c in df.columns), axis=1)].reset_index(drop=True)
            df = df[~df.apply(lambda r: all(is_placeholder_value(v) or str(v).strip() == "" for v in r), axis=1)].reset_index(drop=True)
            records = df.to_dict(orient="records")
            all_docs.extend(records)
            continue

        # Preserve nested mapping
        cols_pp = [(prettify_key(a), prettify_key(b)) for a, b in new_cols]
        df.columns = pd.MultiIndex.from_tuples(cols_pp)
        df = df.fillna("")

        for _, row in df.iterrows():
            doc = {}
            for (main, sub), value in row.items():
                if (not main or str(main).strip() == "") and sub:
                    key = prettify_key(sub)
                    val = convert_to_mongo_date(value) if is_date_column(key) else ("" if pd.isna(value) else value)
                    doc[key] = val
                else:
                    main_key = prettify_key(main)
                    sub_key = prettify_key(sub)
                    val = convert_to_mongo_date(value) if is_date_column(sub_key) else ("" if pd.isna(value) else value)
                    if not main_key:
                        doc[sub_key] = val
                    else:
                        if main_key not in doc:
                            doc[main_key] = {}
                        doc[main_key][sub_key] = val
            # skip empty or placeholder-only docs
            if not doc:
                continue
            if all(is_placeholder_value(v) or (isinstance(v, str) and v.strip() == "") for v in flatten_doc_values(doc)):
                continue
            all_docs.append(doc)

    # Post-process: flatten single-key dicts and coerce types/dates
    cleaned_docs = []
    for d in all_docs:
        # First, flatten any nested single-key dicts recursively
        flat = flatten_single_key_dicts(d)
        # Now ensure top-level numeric/date coercion where appropriate (for flat dicts)
        final = {}
        for k, v in flat.items():
            # if value is string and column name indicates date -> convert
            if isinstance(v, str):
                if is_date_column(k):
                    final[k] = convert_to_mongo_date(v)
                    continue
                # numeric cast attempt
                num = try_cast_number(v)
                final[k] = num
                continue
            # if value is dict (a true nested object) -> recurse flatten inner single-key dicts
            if isinstance(v, dict):
                final[k] = flatten_single_key_dicts(v)
                continue
            final[k] = v
        # Skip docs that are now empty / placeholder-only
        if not final:
            continue
        if all(is_placeholder_value(v) or (isinstance(v, str) and v.strip() == "") for v in flatten_doc_values(final)):
            continue
        cleaned_docs.append(final)

    # Write JSON
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(cleaned_docs, fh, indent=4, ensure_ascii=False)

    print(f"[S] Saved: {output_path}  (records: {len(cleaned_docs)})")

def flatten_doc_values(d: Any) -> List[Any]:
    vals: List[Any] = []
    if isinstance(d, dict):
        for v in d.values():
            vals.extend(flatten_doc_values(v))
    else:
        vals.append(d)
    return vals

# -----------------------
# CLI / interactive entrypoint
# -----------------------

def gather_excel_files(path: Path) -> List[Path]:
    if path.is_file():
        if path.suffix.lower() in (".xls", ".xlsx"):
            return [path]
        raise ValueError(f"Provided file {path} is not an .xls or .xlsx")
    if path.is_dir():
        files = sorted([p for p in path.iterdir() if p.suffix.lower() in (".xls", ".xlsx")])
        return files
    raise ValueError(f"Path {path} does not exist")

def main():
    raw_input_path = input("Input path for file/dir : ").strip()
    if not raw_input_path:
        print("No input provided. Exiting.")
        return
    input_path = Path(raw_input_path).expanduser().resolve()

    output_dir_raw = input("Output directory (press ENTER for default 'Outputs/xls_to_json') : ").strip()
    output_base = Path(output_dir_raw).expanduser().resolve() if output_dir_raw else Path("Outputs/xls_to_json").expanduser().resolve()
    output_base.mkdir(parents=True, exist_ok=True)

    engine_raw = input("Optional pandas engine (openpyxl, xlrd, pyxlsb) - press ENTER to auto-select: ").strip()
    engine_choice = engine_raw if engine_raw else None

    try:
        files = gather_excel_files(input_path)
    except Exception as e:
        print(f"Error: {e}")
        return

    if not files:
        print("No .xls/.xlsx files found.")
        return

    for f in files:
        try:
            out_name = f.stem + ".json"
            out_path = output_base / out_name
            print(f"\n[P] Processing file: {f.name}")
            process_workbook(f, out_path, engine_hint=engine_choice)
        except Exception as exc:
            print(f"[E] Failed {f.name}: {exc}")

    print("\nAll done.")

if __name__ == "__main__":
    main()
