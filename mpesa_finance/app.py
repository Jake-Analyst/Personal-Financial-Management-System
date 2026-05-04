import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from data_loader import process_upload
from profiler import profile_dataframe
from analysis_planner import plan_analyses
from chart_config_generator import build_chart_configs
from insight_generator import generate_insights
from models import engine
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'personal-finance-secret'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

current_profile = None

# ---------- FRONTEND ----------
@app.route('/')
@app.route('/personal')
def personal():
    return render_template('personal.html')

@app.route('/upload', methods=['POST'])
def upload():
    global current_profile
    if 'file' not in request.files:
        return 'No file uploaded', 400
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        df = process_upload(filepath)
        current_profile = profile_dataframe(df)
        return redirect(url_for('personal'))
    except Exception as e:
        return f"Error processing file: {str(e)}", 400

# ---------- API (self-contained, no analytics.py needed) ----------
@app.route('/api/summary')
def api_summary():
    income = expense = 0
    with engine.connect() as conn:
        # Income = sum of Amount Received
        try:
            income = conn.execute(text('SELECT COALESCE(SUM("Amount Received"),0) FROM user_data')).scalar() or 0
            expense = conn.execute(text('SELECT COALESCE(SUM("Amount Sent"),0) FROM user_data')).scalar() or 0
        except:
            pass
    return jsonify({'income': round(income,2), 'expenses': round(expense,2), 'balance': round(income-expense,2)})

@app.route('/api/category_spending')
def api_category_spending():
    data = []
    with engine.connect() as conn:
        try:
            rows = conn.execute(text('SELECT "Transaction Category", SUM("Amount Sent") as total FROM user_data GROUP BY "Transaction Category" ORDER BY total DESC')).fetchall()
            data = [{'category': r[0], 'amount': round(r[1],2)} for r in rows]
        except:
            pass
    return jsonify(data)

@app.route('/api/top_expense_recipients')
def api_top_expense_recipients():
    data = []
    with engine.connect() as conn:
        try:
            rows = conn.execute(text('SELECT Counterparty, SUM("Amount Sent") as total FROM user_data GROUP BY Counterparty ORDER BY total DESC LIMIT 8')).fetchall()
            data = [{'name': r[0].strip() if r[0] else '', 'amount': round(r[1],2)} for r in rows if r[0] and r[0].strip()]
        except:
            pass
    return jsonify(data)

@app.route('/api/insights')
def api_insights():
    insights = []
    with engine.connect() as conn:
        try:
            row = conn.execute(text('SELECT "Transaction Category", SUM("Amount Sent") as total FROM user_data GROUP BY "Transaction Category" ORDER BY total DESC LIMIT 1')).fetchone()
            if row and row[0]:
                insights.append(f"Top spending category: {row[0]} (KES {row[1]:,.0f})")
            income = conn.execute(text('SELECT COALESCE(SUM("Amount Received"),0) FROM user_data')).scalar() or 0
            expense = conn.execute(text('SELECT COALESCE(SUM("Amount Sent"),0) FROM user_data')).scalar() or 0
            if income > 0:
                rate = (expense / income) * 100
                insights.append(f"Expenses are {rate:.0f}% of income")
            week_rows = conn.execute(text('SELECT "Weekday", SUM("Amount Sent") as total FROM user_data GROUP BY "Weekday" ORDER BY total DESC LIMIT 1')).fetchone()
            if week_rows and week_rows[0]:
                insights.append(f"Highest spending day: {week_rows[0]} (KES {week_rows[1]:,.0f})")
        except:
            pass
    if not insights:
        insights.append("Upload data to generate insights.")
    return jsonify(insights)

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return None

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

