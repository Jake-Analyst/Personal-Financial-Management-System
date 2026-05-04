import os, json, http.client, re
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import pandas as pd
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine
from sqlalchemy import text as sqlalchemy_text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mpesa-personal-finance'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mpesa.db')
engine = create_engine(f'sqlite:///{DB_PATH}')

GEMINI_API_KEY = "AIzaSyAWjXLr_inNsL5P9fzUZqfWYi3_MmniI7Q"

@app.route('/')
def index(): return render_template('index.html')

@app.route('/personal')
def personal(): return render_template('personal.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files: return 'No file uploaded', 400
    file = request.files['file']
    if file.filename == '': return 'No file selected', 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        df = read_mpesa_file(filepath)
        store_in_db(df)
        return redirect(url_for('personal'))
    except Exception as e:
        return f"Error: {e}", 400

def fetch_data():
    with engine.connect() as conn:
        income = conn.execute(sqlalchemy_text('SELECT COALESCE(SUM(Amount_Received),0) FROM transactions')).scalar() or 0
        expenses = conn.execute(sqlalchemy_text("SELECT COALESCE(SUM(Amount_Sent),0) FROM transactions WHERE Counterparty != 'Transaction Cost'")).scalar() or 0
        fees = conn.execute(sqlalchemy_text("SELECT COALESCE(SUM(Amount_Sent),0) FROM transactions WHERE Counterparty = 'Transaction Cost'")).scalar() or 0
        balance = conn.execute(sqlalchemy_text('SELECT Balance FROM transactions ORDER BY Transaction_Date DESC, rowid DESC LIMIT 1')).scalar() or 0
        min_date = conn.execute(sqlalchemy_text('SELECT MIN(Transaction_Date) FROM transactions')).scalar()
        max_date = conn.execute(sqlalchemy_text('SELECT MAX(Transaction_Date) FROM transactions')).scalar()
        cat_rows = conn.execute(sqlalchemy_text("SELECT Transaction_Category, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Transaction_Category ORDER BY total DESC")).fetchall()
        inc_src = conn.execute(sqlalchemy_text("SELECT Counterparty, SUM(Amount_Received) as total FROM transactions WHERE Amount_Received > 0 GROUP BY Counterparty ORDER BY total DESC")).fetchall()
        top_rec = conn.execute(sqlalchemy_text("SELECT Counterparty, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Counterparty ORDER BY total DESC LIMIT 7")).fetchall()
        week_rows = conn.execute(sqlalchemy_text("SELECT Weekday, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Weekday")).fetchall()
        rec_recip = conn.execute(sqlalchemy_text("SELECT Counterparty, COUNT(*) as cnt, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Counterparty HAVING cnt >= 5")).fetchall()
    return income, expenses, fees, balance, min_date, max_date, cat_rows, inc_src, top_rec, week_rows, rec_recip

@app.route('/api/summary')
def api_summary():
    try:
        inc, exp, fees, bal, _, _, _, _, _, _, _ = fetch_data()
        return jsonify({'income': round(inc,2), 'expenses': round(exp,2), 'balance': round(bal,2), 'fees': round(fees,2)})
    except: return jsonify({'income':0,'expenses':0,'balance':0,'fees':0})

@app.route('/api/category_spending')
def api_category_spending():
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy_text("SELECT Transaction_Category, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Transaction_Category")).fetchall()
            data = [{'category': r[0], 'amount': round(r[1],2)} for r in rows]
            online_rows = conn.execute(sqlalchemy_text("SELECT Counterparty, SUM(Amount_Sent) as total FROM transactions WHERE Amount_Sent > 0 AND Transaction_Category = 'Pay Bill Online' GROUP BY Counterparty")).fetchall()
            for r in online_rows:
                data.append({'category': r[0].strip(), 'amount': round(r[1],2)})
        return jsonify(data)
    except: return jsonify([])

@app.route('/api/monthly_overview')
def api_monthly_overview():
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy_text("SELECT Month, SUM(CASE WHEN Amount_Received > 0 THEN Amount_Received ELSE 0 END) as Income, SUM(CASE WHEN Amount_Sent > 0 AND Counterparty != 'Transaction Cost' THEN Amount_Sent ELSE 0 END) as Expenses FROM transactions GROUP BY Month ORDER BY CASE Month WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3 WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6 WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9 WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12 END")).fetchall()
        return jsonify([{'month': r[0], 'income': round(r[1],2), 'expenses': round(r[2],2), 'net': round(r[1]-r[2],2)} for r in rows])
    except: return jsonify([])

@app.route('/api/income_sources')
def api_income_sources():
    try:
        _, _, _, _, _, _, _, inc_src, _, _, _ = fetch_data()
        total = sum(r[1] for r in inc_src) if inc_src else 0
        sources = [{'name': r[0].strip(), 'amount': round(r[1],2)} for r in inc_src if r[0] and r[0].strip()]
        top5 = sources[:5]
        others = sum(s['amount'] for s in sources[5:])
        if others > 0: top5.append({'name': 'Others', 'amount': round(others,2)})
        warning = total > 0 and len(top5) > 0 and top5[0]['amount']/total > 0.7
        return jsonify({'sources': top5, 'warning': warning, 'total_income': round(total,2)})
    except: return jsonify({'sources':[], 'warning':False, 'total_income':0})

@app.route('/api/weekday_spending')
def api_weekday_spending():
    try:
        _, _, _, _, _, _, _, _, _, week_rows, _ = fetch_data()
        data = [{'day': r[0], 'amount': round(r[1],2)} for r in week_rows]
        highest = max(data, key=lambda x: x['amount'])['day'] if data else ''
        return jsonify({'data': data, 'highest_day': highest})
    except: return jsonify({'data':[], 'highest_day':''})

@app.route('/api/balance_trend')
def api_balance_trend():
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy_text("SELECT Transaction_Date, Balance FROM transactions ORDER BY Transaction_Date ASC")).fetchall()
            points = [{'date': str(r[0]), 'balance': round(r[1],2)} for r in rows]
            min_val = min(r[1] for r in rows) if rows else 0
            min_date = next((str(r[0]) for r in rows if r[1]==min_val), None)
        return jsonify({'points': points, 'min_balance': round(min_val,2), 'min_date': min_date})
    except: return jsonify({'points':[], 'min_balance':0, 'min_date':None})

@app.route('/api/top_expense_recipients')
def api_top_expense_recipients():
    limit = request.args.get('limit', 8)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy_text(f"SELECT Counterparty, SUM(Amount_Sent) as total FROM transactions WHERE Counterparty IS NOT NULL AND Amount_Sent > 0 AND Counterparty != 'Transaction Cost' GROUP BY Counterparty ORDER BY total DESC LIMIT {int(limit)}")).fetchall()
        return jsonify([{'name': r[0].strip(), 'amount': round(r[1],2)} for r in rows if r[0] and r[0].strip()])
    except: return jsonify([])

@app.route('/api/ai-insights')
def api_ai_insights():
    try:
        inc, exp, fees, bal, min_date, max_date, cat_rows, inc_src, top_rec, week_rows, rec_recip = fetch_data()
    except:
        return jsonify(["Upload M‑Pesa data to generate insights."])

    data_context = f"""
**Financial Summary**
- Period: {min_date} to {max_date}
- Total Income: KES {inc:,.0f}
- Total Expenses: KES {exp:,.0f}
- Net Savings: KES {inc-exp:,.0f}
- Savings Rate: {((inc-exp)/inc*100) if inc else 0:.1f}%
- M‑Pesa Fees: KES {fees:,.0f}
- Current Balance: KES {bal:,.0f}

**Spending Categories**
{chr(10).join(f"- {r[0]}: KES {r[1]:,.0f}" for r in cat_rows) if cat_rows else 'N/A'}

**Income Sources**
{chr(10).join(f"- {r[0].strip()}: KES {r[1]:,.0f} ({(r[1]/inc*100):.1f}%)" for r in inc_src) if inc_src else 'N/A'}

**Weekday Spending**
{chr(10).join(f"- {r[0]}: KES {r[1]:,.0f}" for r in week_rows) if week_rows else 'N/A'}

**Top Recipients**
{chr(10).join(f"- {r[0].strip()}: KES {r[1]:,.0f}" for r in top_rec) if top_rec else 'N/A'}

**Recurring Recipients (5+ transactions)**
{chr(10).join(f"- {r[0].strip()}: {r[1]} times, total KES {r[2]:,.0f}" for r in rec_recip) if rec_recip else 'None'}
"""

    prompt = (
        "You are a world-class personal finance advisor. Generate 6–8 high-quality, specific, actionable insights from the financial data below. "
        "Every insight must interpret, project, or prescribe — never just restate a number. "
        "Rank by financial impact, and label each insight with [CRITICAL], [ADVISORY], or [POSITIVE]. "
        "Each insight must contain a specific KES figure or percentage. "
        "End each insight with a forward-looking projection or a concrete, numbered recommendation. "
        "Cover: trend, projection, anomaly, concentration risk, behaviour pattern, cost optimisation, opportunity, and recipient intelligence (if data permits). "
        "Vary sentence openings; never start with 'Your' or 'You have'. Minimum 6, maximum 10 insights.\n\n"
        "Data:" + data_context
    )

    insights = []
    if GEMINI_API_KEY:
        try:
            conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
            })
            headers = {"Content-Type": "application/json"}
            conn.request("POST", f"/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}", payload, headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            if "candidates" in data and data["candidates"]:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                insights = [line.strip() for line in text.split("\n") if re.match(r'^\[(CRITICAL|ADVISORY|POSITIVE)\]', line.strip())]
        except Exception as e:
            print(f"AI call failed: {e}")

    if not insights:
        savings_rate = ((inc - exp) / inc * 100) if inc > 0 else 0
        with engine.connect() as conn2:
            monthly_rows = conn2.execute(sqlalchemy_text("SELECT Month, SUM(CASE WHEN Amount_Received > 0 THEN Amount_Received ELSE 0 END) as Inc, SUM(CASE WHEN Amount_Sent > 0 AND Counterparty != 'Transaction Cost' THEN Amount_Sent ELSE 0 END) as Exp FROM transactions GROUP BY Month ORDER BY MIN(Transaction_Date)")).fetchall()
        month_count = len(monthly_rows) if monthly_rows else 1
        avg_monthly_savings = (inc - exp) / month_count if month_count else 0
        annual_proj = avg_monthly_savings * 12
        if avg_monthly_savings > 0:
            insights.append(f"[POSITIVE] At your current pace, you are saving approximately KES {avg_monthly_savings:,.0f} per month. Over 12 months, that's KES {annual_proj:,.0f} — enough to build a solid emergency fund.")
        if len(monthly_rows) >= 2:
            first_month_exp = monthly_rows[0][2]
            last_month_exp = monthly_rows[-1][2]
            if first_month_exp > 0:
                change = ((last_month_exp - first_month_exp) / first_month_exp) * 100
                trend = "increased" if change > 0 else "decreased"
                insights.append(f"[ADVISORY] Expenses {trend} by {abs(change):.0f}% from {monthly_rows[0][0]} to {monthly_rows[-1][0]}. If this continues, your annual spending could reach KES {last_month_exp * 12:,.0f}.")
        try:
            with engine.connect() as conn2:
                max_tx = conn2.execute(sqlalchemy_text("SELECT Transaction_Date, Amount_Sent, Counterparty FROM transactions WHERE Amount_Sent = (SELECT MAX(Amount_Sent) FROM transactions WHERE Counterparty != 'Transaction Cost') AND Counterparty != 'Transaction Cost' LIMIT 1")).fetchone()
                if max_tx and max_tx[1] > 0:
                    avg_daily = exp / (month_count * 30 or 1)
                    multiple = max_tx[1] / avg_daily if avg_daily > 0 else 1
                    insights.append(f"[CRITICAL] A single transfer of KES {max_tx[1]:,.0f} to {max_tx[2].strip()} stands out — it's {multiple:.1f}x your average daily spend. Verify this was planned.")
        except: pass
        if inc_src and inc > 0 and inc_src[0][1] / inc > 0.7:
            share = inc_src[0][1]/inc*100
            insights.append(f"[CRITICAL] {share:.0f}% of your income came from {inc_src[0][0].strip()} — extremely high concentration. If that source stops for a month, your expenses exceed your income by KES {exp - (inc - inc_src[0][1]):,.0f}.")
        for r in rec_recip[:2]:
            annual = (r[2] / month_count) * 12
            insights.append(f"[ADVISORY] {r[0].strip()} was paid {r[1]} times, totalling KES {r[2]:,.0f}. At this rate, you'll send roughly KES {annual:,.0f} annually. A standing order could simplify payments and reduce fees.")
        if fees > 0:
            insights.append(f"[ADVISORY] M‑Pesa fees of KES {fees:,.0f} were incurred this period. Reducing transaction frequency could save over KES {fees * 12:,.0f} per year.")
        if len(insights) < 6:
            insights.append("[POSITIVE] Your consistent tracking is commendable. Keep monitoring spending to maintain this financial awareness.")

    return jsonify(insights[:8])

# ---------- FULL AI ASSISTANT CHAT (Gemini) ----------
@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    question = data.get('question', '').strip() if data else ''
    if not question:
        return jsonify({'answer': 'Please ask a question.'})

    try:
        inc, exp, fees, bal, min_date, max_date, cat_rows, inc_src, top_rec, week_rows, rec_recip = fetch_data()
    except:
        return jsonify({'answer': 'No transaction data found. Please upload a statement first.'})

    savings_rate = ((inc - exp) / inc * 100) if inc > 0 else 0
    net = inc - exp

    context = f"""
You are JAKE, a friendly, expert personal financial assistant embedded in the JAKE Financial Management System.
You have access to the user's real M‑Pesa transaction data for the period {min_date} to {max_date}.
Answer the user's question concisely, using specific numbers from the data when relevant.
Be encouraging, practical, and never talk down to the user.
If the question is unclear, ask for clarification.
If asked for advice, give personalised, actionable suggestions based on the data.

CURRENT FINANCIAL SNAPSHOT:
- Total income: KES {inc:,.0f}
- Total expenses: KES {exp:,.0f}
- Net savings: KES {net:,.0f} (savings rate {savings_rate:.1f}%)
- Current balance: KES {bal:,.0f}
- M‑Pesa fees: KES {fees:,.0f}
- Top spending category: {cat_rows[0][0] if cat_rows else 'N/A'} (KES {cat_rows[0][1]:,.0f})
- Top income source: {inc_src[0][0].strip() if inc_src else 'N/A'} (KES {inc_src[0][1]:,.0f})
- Peak spending weekday: {max(week_rows, key=lambda x:x[1])[0] if week_rows else 'N/A'} (KES {max(week_rows, key=lambda x:x[1])[1] if week_rows else 0:,.0f})
- Recurring recipients (5+ times): {', '.join(f"{r[0].strip()} ({r[1]} times, total KES {r[2]:,.0f})" for r in rec_recip[:3]) if rec_recip else 'None'}

SPENDING CATEGORIES:
{chr(10).join(f"- {r[0]}: KES {r[1]:,.0f}" for r in cat_rows) if cat_rows else 'N/A'}

INCOME SOURCES:
{chr(10).join(f"- {r[0].strip()}: KES {r[1]:,.0f} ({(r[1]/inc*100):.1f}%)" for r in inc_src) if inc_src else 'N/A'}

User question: {question}

Your answer:
"""

    answer = "I'm not sure how to answer that, but I'm here to help with your finances!"
    if GEMINI_API_KEY:
        try:
            conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
            payload = json.dumps({
                "contents": [{"parts": [{"text": context}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300}
            })
            headers = {"Content-Type": "application/json"}
            conn.request("POST", f"/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}", payload, headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            if "candidates" in data and data["candidates"]:
                answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Chat AI error: {e}")

    return jsonify({'answer': answer})

# ---------- PDF REPORT ----------
@app.route('/api/report')
def api_report():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
    from reportlab.lib.enums import TA_CENTER
    from io import BytesIO
    import datetime as dt

    try:
        inc, exp, fees, bal, min_date, max_date, cat_rows, inc_src, top_rec, week_rows, rec_recip = fetch_data()
    except:
        return jsonify({'error': 'No transaction data'}), 400

    ai_recs = []
    if GEMINI_API_KEY:
        try:
            summary = f"""
            Income: KES {inc:,.0f}, Expenses: KES {exp:,.0f}, Net: KES {inc-exp:,.0f}
            Savings rate: {((inc-exp)/inc*100) if inc else 0:.1f}%
            Top spending category: {cat_rows[0][0] if cat_rows else 'N/A'}
            Top income source: {inc_src[0][0].strip() if inc_src else 'N/A'}
            Peak spending weekday: {max(week_rows, key=lambda x:x[1])[0] if week_rows else 'N/A'}
            M‑Pesa fees: KES {fees:,.0f}
            """
            prompt = (
                "Based on the following personal finance data, provide 3-5 powerful, actionable recommendations. "
                "Each recommendation must be specific, data-driven, and include a KES amount or percentage. "
                "Focus on concrete steps to improve savings, reduce fees, diversify income, and optimise spending. "
                "Do not restate obvious numbers; instead prescribe a clear action with its financial impact. "
                "Format each recommendation as a single line without numbering.\n\n" + summary
            )
            conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300}
            })
            headers = {"Content-Type": "application/json"}
            conn.request("POST", f"/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}", payload, headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            if "candidates" in data and data["candidates"]:
                ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
                ai_recs = [line.strip("-• ").strip() for line in ai_text.split("\n") if line.strip() and len(line) > 10]
        except: pass

    if not ai_recs:
        if inc > 0 and exp > inc * 0.7: ai_recs.append("Reduce spending by at least 10% to build a buffer.")
        if inc > 0 and (inc - exp) / inc < 0.2: ai_recs.append("Aim to save at least 20% of your income.")
        if inc_src and inc_src[0][1] / inc > 0.7: ai_recs.append("Diversify your income sources.")
        if rec_recip: ai_recs.append("Set up standing orders for recurring payments.")
        if fees > 300: ai_recs.append("Consolidate transactions to reduce M‑Pesa costs.")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    normal = styles['Normal']; normal.fontSize = 10
    center = ParagraphStyle(name='Center', parent=normal, alignment=TA_CENTER)
    heading = ParagraphStyle(name='Heading2', parent=styles['Heading2'], fontSize=14, spaceBefore=1*cm, spaceAfter=0.4*cm)
    fmk = lambda v: f"KES {v:,.0f}"
    story = []
    story.append(Spacer(1,2*cm))
    story.append(Paragraph("JAKE Financial Management System", center))
    story.append(Spacer(1,0.8*cm))
    story.append(Paragraph("Personal Finance Report", styles['Title']))
    story.append(HRFlowable(width="80%", thickness=1, color=colors.grey, spaceAfter=0.6*cm))
    period = f"{min_date} – {max_date}" if min_date else ""
    story.append(Paragraph(f"Period: {period}", center))
    story.append(Paragraph(f"Generated: {dt.date.today().strftime('%d %B %Y')}", center))
    story.append(Spacer(1,1*cm))
    story.append(Paragraph("Confidential – for account holder only.", center))
    story.append(PageBreak())
    savings = inc - exp
    savings_rate = (savings/inc*100) if inc else 0
    story.append(Paragraph("1. EXECUTIVE SUMMARY", heading))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=0.3*cm))
    story.append(Paragraph(f"Income: {fmk(inc)}", normal))
    story.append(Paragraph(f"Expenses: {fmk(exp)}", normal))
    story.append(Paragraph(f"Balance: {fmk(bal)}", normal))
    story.append(Paragraph(f"Savings rate: {savings_rate:.1f}%", normal))
    story.append(Paragraph("Excellent shape." if savings_rate>=40 else "Healthy." if savings_rate>=20 else "Spending high.", normal))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph("2. SPENDING PATTERNS", heading))
    if week_rows:
        wm = {r[0]:r[1] for r in week_rows}
        story.append(Paragraph(f"Peak day: {max(wm, key=wm.get)} ({fmk(wm[max(wm, key=wm.get)])})", normal))
        story.append(Paragraph(f"Quietest day: {min(wm, key=wm.get)} ({fmk(wm[min(wm, key=wm.get)])})", normal))
    story.append(Paragraph("3. M‑PESA FEES", heading))
    story.append(Paragraph(f"Total fees: {fmk(fees)}", normal))
    if fees > 300: story.append(Paragraph("Consider consolidating transactions.", normal))
    story.append(Paragraph("4. RECOMMENDATIONS", heading))
    for i, rec in enumerate(ai_recs, 1):
        story.append(Paragraph(f"{i}. {rec}", normal))
    def footer(canvas, doc):
        canvas.setFont("Helvetica",8)
        canvas.drawCentredString(A4[0]/2, 1.5*cm, f"JAKE Financial System · Page {canvas.getPageNumber()}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pdf = buffer.getvalue(); buffer.close()
    resp = make_response(pdf)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename=JAKE_FinancialReport.pdf'
    return resp

def read_mpesa_file(filepath):
    ext = filepath.split('.')[-1].lower()
    if ext in ['xlsx', 'xls', 'xlsm']:
        df = pd.read_excel(filepath, engine='openpyxl', sheet_name=0)
    else:
        for enc in ['utf-16', 'utf-8', 'latin1', 'cp1252']:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                break
            except: continue
        else: raise ValueError("Could not read CSV")
    df.columns = [str(c).strip() for c in df.columns]
    if 'Time' in df.columns:
        df['Time'] = df['Time'].apply(lambda x: str(x) if pd.notna(x) else '')
    for col in df.columns:
        if df[col].dtype == object:
            try: df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            except: pass
    if 'Transaction Date' in df.columns and 'Time' in df.columns:
        df['Transaction Date'] = pd.to_datetime(df['Transaction Date'].astype(str) + ' ' + df['Time'], errors='coerce', dayfirst=True)
        df = df.drop(columns=['Time'])
    elif 'Transaction Date' in df.columns:
        df['Transaction Date'] = pd.to_datetime(df['Transaction Date'], errors='coerce', dayfirst=True)
    df['Amount Received'] = pd.to_numeric(df['Amount Received'], errors='coerce').fillna(0)
    df['Amount Sent'] = pd.to_numeric(df['Amount Sent'], errors='coerce').fillna(0)
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
    df = df.drop_duplicates().sort_values('Transaction Date')
    return df

def store_in_db(df):
    rename = {
        'Transaction Date':'Transaction_Date','Transaction Category':'Transaction_Category',
        'Amount Received':'Amount_Received','Amount Sent':'Amount_Sent',
        'Counterparty':'Counterparty','Balance':'Balance','Month':'Month','Weekday':'Weekday'
    }
    df = df.rename(columns=rename)
    with engine.connect() as conn:
        conn.execute(sqlalchemy_text('DROP TABLE IF EXISTS transactions'))
        conn.commit()
    df.to_sql('transactions', con=engine, index=False, if_exists='replace')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
