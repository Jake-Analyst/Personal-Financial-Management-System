import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import pandas as pd
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mpesa-personal-finance'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mpesa.db')
engine = create_engine(f'sqlite:///{DB_PATH}')

# ---------- FRONTEND ROUTES ----------
@app.route('/')
def index():
    """Upload page"""
    return render_template('index.html')

@app.route('/personal')
def personal():
    """Dashboard (requires data)"""
    return render_template('personal.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file uploaded', 400
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        df = read_mpesa_file(filepath)
        store_in_db(df)
        return redirect(url_for('personal'))
    except Exception as e:
        return f"Error: {e}", 400

# ---------- API ENDPOINTS ----------
@app.route('/api/summary')
def api_summary():
    with engine.connect() as conn:
        income = conn.execute(text('SELECT COALESCE(SUM("Amount Received"),0) FROM transactions')).scalar() or 0
        expenses = conn.execute(text('SELECT COALESCE(SUM("Amount Sent"),0) FROM transactions')).scalar() or 0
    return jsonify({'income': round(income,2), 'expenses': round(expenses,2), 'balance': round(income - expenses,2)})

@app.route('/api/category_spending')
def api_category_spending():
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT "Transaction Category", SUM("Amount Sent") as total FROM transactions WHERE "Amount Sent" > 0 GROUP BY "Transaction Category" ORDER BY total DESC')).fetchall()
    return jsonify([{'category': r[0], 'amount': round(r[1],2)} for r in rows])

@app.route('/api/top_expense_recipients')
def api_top_expense_recipients():
    limit = request.args.get('limit', 8)
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT Counterparty, SUM("Amount Sent") as total FROM transactions WHERE Counterparty IS NOT NULL AND "Amount Sent" > 0 GROUP BY Counterparty ORDER BY total DESC LIMIT {int(limit)}')).fetchall()
    return jsonify([{'name': r[0].strip(), 'amount': round(r[1],2)} for r in rows if r[0] and r[0].strip()])

@app.route('/api/insights')
def api_insights():
    insights = []
    with engine.connect() as conn:
        row = conn.execute(text('SELECT "Transaction Category", SUM("Amount Sent") as total FROM transactions WHERE "Amount Sent" > 0 GROUP BY "Transaction Category" ORDER BY total DESC LIMIT 1')).fetchone()
        if row:
            insights.append(f"Top spending category: {row[0]} (KES {row[1]:,.0f})")
        income = conn.execute(text('SELECT COALESCE(SUM("Amount Received"),0) FROM transactions')).scalar() or 0
        expenses = conn.execute(text('SELECT COALESCE(SUM("Amount Sent"),0) FROM transactions')).scalar() or 0
        if income > 0:
            insights.append(f"Expenses are {expenses/income*100:.0f}% of income")
        day = conn.execute(text('SELECT Weekday, SUM("Amount Sent") as total FROM transactions GROUP BY Weekday ORDER BY total DESC LIMIT 1')).fetchone()
        if day:
            insights.append(f"Highest spending day: {day[0]} (KES {day[1]:,.0f})")
    if not insights:
        insights.append("Upload M‑Pesa data to generate insights.")
    return jsonify(insights)

# ---------- HELPERS ----------
def read_mpesa_file(filepath):
    ext = filepath.split('.')[-1].lower()
    if ext in ['xlsx', 'xls', 'xlsm']:
        df = pd.read_excel(filepath, engine='openpyxl', sheet_name=0)  # force first sheet
    else:
        for enc in ['utf-16', 'utf-8', 'latin1', 'cp1252']:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                break
            except:
                continue
        else:
            raise ValueError("Could not read CSV file")
    # Clean column names
    df.columns = [str(c).strip() for c in df.columns]
    # If the file has no columns or is empty, raise an error
    if df.empty or len(df.columns) == 0:
        raise ValueError("File appears to be empty or has no headers")
    # Combine date and time if both exist
    if 'Transaction Date' in df.columns and 'Time' in df.columns:
        df['Transaction Date'] = pd.to_datetime(
            df['Transaction Date'].astype(str) + ' ' + df['Time'].astype(str),
            errors='coerce'
        )
    return df
def store_in_db(df):
    with engine.connect() as conn:
        conn.execute(text('DROP TABLE IF EXISTS transactions'))
        conn.commit()
    # Make sure column names are safe for SQL (replace spaces with underscores, remove special chars)
    safe_columns = {col: col.replace(' ', '_').replace('(', '').replace(')', '') for col in df.columns}
    df_renamed = df.rename(columns=safe_columns)
    # Store using the renamed columns
    df_renamed.to_sql('transactions', con=engine, index=False, if_exists='replace')
    
    # Afterwards, we need to rename the table columns back to the original names for our API queries.
    # We'll just use the original column names by quoting them with backticks.
    # Since to_sql created columns with underscores, we can either alter table or rebuild.
    # Simpler: drop, and create table manually with original column names quoted.
    # We'll do a more explicit approach: drop and re-create with proper quoting.
    with engine.connect() as conn:
        # Drop the table created by to_sql
        conn.execute(text('DROP TABLE IF EXISTS transactions'))
        conn.commit()
        # Build CREATE TABLE statement with original column names
        col_defs = []
        for col in df.columns:
            # Use double quotes around column name to allow spaces
            col_defs.append(f'"{col}" TEXT')
        create_sql = f'CREATE TABLE transactions ({", ".join(col_defs)})'
        conn.execute(text(create_sql))
        # Insert data row by row (simple)
        for _, row in df.iterrows():
            placeholders = ', '.join(['?' for _ in df.columns])
            cols = ', '.join([f'"{c}"' for c in df.columns])
            conn.execute(text(f'INSERT INTO transactions ({cols}) VALUES ({placeholders})'), 
                         tuple(row[col] for col in df.columns))
        conn.commit()

