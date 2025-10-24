import pandas as pd
import os
import sys
from pathlib import Path

expected_date_fields = [
    'date_of_birth', 'date_of_joining', 'date_of_resignation', 'date_of_leaving'
]

# Rename shortcut columns to proper names
column_rename_map = {
    'dob': 'date_of_birth',
    'doj': 'date_of_joining',
    'dor': 'date_of_resignation',
    'dol': 'date_of_leaving'
}

def parse_date_columns(df, date_columns, date_format="%d-%m-%Y"):
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format=date_format, errors='coerce')  # Convert valid, NaT on error
    return df

def xls_to_csv(input_path, output_dir=None, encoding='utf-8-sig'):
    """
    Safely converts all sheets from an Excel file (.xls or .xlsx) to CSV files.
    Handles empty values, encodings, and numeric/text mixups.
    """
    input_path = Path(input_path).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if not input_path.suffix.lower() in ('.xls', '.xlsx'):
        raise ValueError("Input file must have .xls or .xlsx extension")

    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir).resolve()
        os.makedirs(output_dir, exist_ok=True)

    base_name = input_path.stem
    engine = 'xlrd' if input_path.suffix.lower() == '.xls' else 'openpyxl'
    excel_file = pd.ExcelFile(input_path, engine=engine)

    csv_files = []
    for sheet_name in excel_file.sheet_names:
        print(f"📄 Reading sheet: {sheet_name}")
        df = excel_file.parse(sheet_name)

        # Normalize column names
        df.columns = [col.strip().lower() for col in df.columns]

        df.rename(columns=column_rename_map, inplace=True)

        # Convert expected date fields to datetime
        df = parse_date_columns(df, expected_date_fields, date_format="%d-%m-%Y")

        # Replace NaN/NaT with empty string for clean CSV output
        df = df.fillna('')

        # Sanitize sheet name for filename
        safe_sheet_name = "".join(
            c if c.isalnum() or c in (' ', '_', '-') else "_" for c in sheet_name
        ).strip()

        csv_filename = f"{base_name}_{safe_sheet_name}.csv"
        csv_path = output_dir / csv_filename

        df.to_csv(csv_path, index=False, encoding=encoding)
        csv_files.append(str(csv_path))
        print(f"✅ Saved: {csv_path}")

    return csv_files


# if __name__ == "__main__":
# if len(sys.argv) < 2:
#     print("Usage: python xls_to_csv.py <input_excel_file> [output_directory]")
#     sys.exit(1)

input_file = "C:/Users/ak965/workspace/learning/python/rag/Reports/1.DatabaseReport_Rpt_Data base Report.xls"
output_dir = "C:/Users/ak965/workspace/learning/python/rag/output_file"

try:
    output_files = xls_to_csv(input_file, output_dir)
    print("\nAll sheets converted successfully!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
