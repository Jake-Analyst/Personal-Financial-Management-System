import pandas as pd
import numpy as np
from datetime import datetime
from models import db, Transaction
import os

# ---------- CATEGORISATION ----------
CATEGORY_KEYWORDS = {
    'Food': ['restaurant', 'food', 'hotel', 'lunch', 'dinner', 'supermarket', 'naivas', 'carrefour', 'kfc', 'java'],
    'Transport': ['matatu', 'bus', 'taxi', 'uber', 'bolt', 'fuel', 'parking', 'fare'],
    'Bills': ['kplc', 'electricity', 'water', 'rent', 'zuku', 'safaricom', 'airtel', 'internet', 'dstv', 'netflix'],
    'Shopping': ['clothes', 'shopping', 'amazon', 'jumia', 'electronics', 'gadget', 'lipa na m-pesa', 'pay bill'],
    'Savings': ['savings', 'investment', 'money market', 'fund', 'equity', 'sacco'],
    'Entertainment': ['movie', 'cinema', 'concert', 'club', 'game', 'netflix', 'spotify'],
    'Health': ['hospital', 'clinic', 'pharmacy', 'doctor', 'med', 'insurance'],
    'Education': ['school', 'fee', 'course', 'book', 'tuition'],
    'Airtime': ['data bundles', 'airtime', 'safaricom data'],
    'Personal Transfer': ['transfer of funds', 'customer transfer'],
    'Business Payment': ['payment to small business', 'merchant payment', 'customer payment to small business'],
    'Transaction Cost': ['transaction cost', 'pay bill charge', 'transfer of funds charge']
}

def categorise_transaction(row):
    if row['transaction_type'] == 'Income':
        return 'Income'
    desc = str(row.get('description', '')).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in desc for word in keywords):
            return category
    return 'Other'

def find_column(cols, keywords):
    """Return the first column name that contains any of the keywords (case-insensitive)."""
    for col in cols:
        col_lower = col.lower()
        if any(kw in col_lower for kw in keywords):
            return col
    return None

def read_file(filepath):
    """Read CSV or Excel file and return a DataFrame."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.csv':
        encodings_to_try = ['utf-16', 'utf-8', 'latin1', 'cp1252']
        for enc in encodings_to_try:
            try:
                return pd.read_csv(
                    filepath,
                    encoding=enc,
                    on_bad_lines='skip',
                    skip_blank_lines=True,
                    engine='python',
                    quoting=1
                )
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV file with any encoding.")
    elif ext in ['.xlsx', '.xls', '.xlsm']:
        try:
            return pd.read_excel(filepath, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"Could not read Excel file: {e}")
    else:
        raise ValueError(f"Unsupported file format: {ext}. Please upload a CSV or Excel file.")

def parse_mpesa_csv(filepath):
    df = read_file(filepath)
    # Clean column names
    df.columns = df.columns.str.strip().str.lower()

    # CASE 1: Exact format with 'transaction date' and 'amount received' / 'amount sent'
    if ('transaction date' in df.columns and
        ('amount received' in df.columns or 'amount sent' in df.columns)):

        date_col = 'transaction date'
        time_col = 'time' if 'time' in df.columns else None
        if time_col:
            df['combined_datetime'] = pd.to_datetime(
                df[date_col].astype(str) + ' ' + df[time_col].astype(str),
                errors='coerce'
            )
            df.dropna(subset=['combined_datetime'], inplace=True)
            df['date'] = df['combined_datetime']
        else:
            df['date'] = pd.to_datetime(df[date_col], errors='coerce')
            df.dropna(subset=['date'], inplace=True)

        credit_col = 'amount received' if 'amount received' in df.columns else None
        debit_col = 'amount sent' if 'amount sent' in df.columns else None
        df['credit'] = pd.to_numeric(df.get(credit_col, 0), errors='coerce').fillna(0)
        df['debit'] = pd.to_numeric(df.get(debit_col, 0), errors='coerce').fillna(0)

        desc_parts = []
        if 'transaction category' in df.columns:
            desc_parts.append(df['transaction category'].astype(str))
        if 'counterparty' in df.columns:
            desc_parts.append(df['counterparty'].astype(str))
        df['description'] = desc_parts[0] if desc_parts else ''
        if len(desc_parts) > 1:
            df['description'] = df['description'].str.cat(desc_parts[1:], sep=' – ')

        std = pd.DataFrame()
        std['date'] = df['date']
        std['amount'] = np.where(df['credit'] > 0, df['credit'], -df['debit'])
        std['transaction_type'] = std['amount'].apply(lambda x: 'Income' if x >= 0 else 'Expense')
        std['description'] = df['description']
        std['receipt_no'] = 'GEN_' + df['date'].astype(str) + '_' + df.index.astype(str)

    else:
        # CASE 2: Fallback keyword-based detection
        date_col = find_column(df.columns, ['date', 'time', 'completion'])
        if not date_col:
            raise ValueError("No date column found. Detected columns: " + ", ".join(df.columns.tolist()))

        credit_col = find_column(df.columns, [
            'paid in', 'credit', 'money in', 'deposit', 'received', 'amount received'
        ])
        debit_col = find_column(df.columns, [
            'withdrawn', 'debit', 'money out', 'sent', 'payment', 'paid', 'amount sent'
        ])
        if not credit_col and not debit_col:
            raise ValueError("No income/expense columns found. Detected columns: " + ", ".join(df.columns.tolist()))

        desc_col = find_column(df.columns, [
            'details', 'description', 'narration', 'particulars', 'reference', 'notes',
            'transaction category', 'counterparty'
        ])

        std = pd.DataFrame()
        std['date'] = pd.to_datetime(df[date_col], errors='coerce')
        std.dropna(subset=['date'], inplace=True)
        std['credit'] = pd.to_numeric(df.get(credit_col, 0), errors='coerce').fillna(0)
        std['debit'] = pd.to_numeric(df.get(debit_col, 0), errors='coerce').fillna(0)
        std['amount'] = np.where(std['credit'] > 0, std['credit'], -std['debit'])
        std['transaction_type'] = std['amount'].apply(lambda x: 'Income' if x >= 0 else 'Expense')
        std['description'] = df[desc_col].astype(str) if desc_col else ''
        receipt_col = find_column(df.columns, ['receipt', 'receipt no', 'transaction id', 'ref'])
        std['receipt_no'] = df[receipt_col].astype(str) if receipt_col else 'GEN_' + std['date'].astype(str) + '_' + std.index.astype(str)

    std = std[std['amount'] != 0]
    std.drop_duplicates(subset='receipt_no', inplace=True)
    return std

def import_transactions_from_csv(filepath):
    df = parse_mpesa_csv(filepath)
    df['category'] = df.apply(categorise_transaction, axis=1)

    db.session.query(Transaction).delete()
    db.session.commit()

    for _, row in df.iterrows():
        tx = Transaction(
            receipt_no=row['receipt_no'],
            date=row['date'],
            amount=row['amount'],
            transaction_type=row['transaction_type'],
            description=row.get('description', ''),
            category=row['category']
        )
        db.session.add(tx)
    db.session.commit()
    return len(df)
