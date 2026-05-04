import pandas as pd
import numpy as np
from models import create_dynamic_table, insert_data

def read_file(filepath):
    """Load CSV or Excel with encoding detection, and convert time columns to string."""
    ext = filepath.split(".")[-1].lower()
    if ext == "csv":
        encodings = ["utf-16", "utf-8", "latin1", "cp1252"]
        for enc in encodings:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                break
            except:
                continue
        else:
            raise ValueError("Could not decode CSV")
    elif ext in ["xlsx", "xls", "xlsm"]:
        df = pd.read_excel(filepath, engine="openpyxl")
    else:
        raise ValueError("Unsupported file format")
    # Convert any datetime.time columns to string to avoid SQLite insertion error
    import datetime as dt
    for col in df.columns:
        if df[col].dtype == object:
            # Check if first non-null value is datetime.time
            sample = df[col].dropna().head(1)
            if not sample.empty and isinstance(sample.iloc[0], dt.time):
                df[col] = df[col].apply(lambda x: x.strftime("%H:%M:%S") if isinstance(x, dt.time) else x)
    # Basic cleaning
    df.columns = [str(c).strip() for c in df.columns]
    df = df.drop_duplicates()
    return df
    """Load CSV or Excel with encoding detection."""
    ext = filepath.split('.')[-1].lower()
    if ext == 'csv':
        encodings = ['utf-16', 'utf-8', 'latin1', 'cp1252']
        for enc in encodings:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                break
            except:
                continue
        else:
            raise ValueError("Could not decode CSV")
    elif ext in ['xlsx', 'xls', 'xlsm']:
        df = pd.read_excel(filepath, engine='openpyxl')
    else:
        raise ValueError("Unsupported file format")
    # Basic cleaning
    df.columns = [str(c).strip() for c in df.columns]
    df = df.drop_duplicates()
    return df

def process_upload(filepath):
    """Read file, create table, insert data. Returns DataFrame."""
    df = read_file(filepath)
    create_dynamic_table(df)
    insert_data(df)
    return df
