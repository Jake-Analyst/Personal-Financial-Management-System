from models import engine
from sqlalchemy import text, func

def get_summary(start=None, end=None, category=None):
    """Return total income, expenses, and net balance using dynamic columns."""
    # Identify likely income and expense columns by semantic roles (money + keyword)
    income_cols = []
    expense_cols = []
    for col in get_money_columns():
        name_lower = col.lower()
        if any(kw in name_lower for kw in ['received', 'income', 'credit', 'deposit']):
            income_cols.append(col)
        elif any(kw in name_lower for kw in ['sent', 'expense', 'debit', 'withdrawn']):
            expense_cols.append(col)
    if not income_cols and not expense_cols:
        # Fallback: all money columns, treat positive as income? Not safe.
        return {'income': 0, 'expenses': 0, 'balance': 0}

    where = build_where_clause(start, end, category)
    # Income: sum of positive values from income columns + negative values from expense columns? No, we assume income columns are always positive amounts.
    income_sql_parts = [f"COALESCE(SUM(`{c}`), 0)" for c in income_cols]
    expense_sql_parts = [f"COALESCE(SUM(`{c}`), 0)" for c in expense_cols]
    income_query = f"SELECT {'+'.join(income_sql_parts) if income_sql_parts else '0'} as income FROM user_data {where}"
    expense_query = f"SELECT {'+'.join(expense_sql_parts) if expense_sql_parts else '0'} as expenses FROM user_data {where}"
    with engine.connect() as conn:
        income = conn.execute(text(income_query)).scalar() or 0
        expenses = conn.execute(text(expense_query)).scalar() or 0
    balance = income - expenses
    return {'income': round(income, 2), 'expenses': round(expenses, 2), 'balance': round(balance, 2)}

def get_category_spending(start=None, end=None):
    """Spending by category using Transaction Category column if exists, else first categorical column."""
    cat_col = find_category_column()
    if not cat_col:
        return []
    where = build_where_clause(start, end, None)
    sql = f"SELECT `{cat_col}` as cat, COUNT(*) as cnt, SUM(CASE WHEN `{expense_col}` IS NOT NULL THEN `{expense_col}` ELSE 0 END) as total FROM user_data {where} GROUP BY cat ORDER BY total DESC"
    # We need an expense column to sum amounts. Use the first expense column from get_money_columns
    expense_col = None
    for col in get_money_columns():
        if any(kw in col.lower() for kw in ['sent', 'expense', 'debit']):
            expense_col = col
            break
    if not expense_col:
        # Fallback: just count transactions
        sql = f"SELECT `{cat_col}` as cat, COUNT(*) as cnt FROM user_data {where} GROUP BY cat ORDER BY cnt DESC"
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
            return [{'category': r[0], 'amount': r[1]} for r in rows]
    sql = sql.replace('{expense_col}', expense_col)
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    return [{'category': r[0], 'amount': round(r[2], 2)} for r in rows]

def get_spending_by_hour(start=None, end=None, category=None):
    expense_col = find_expense_column()
    if not expense_col:
        return []
    where = build_where_clause(start, end, category)
    sql = f"SELECT CAST(strftime('%H', `Transaction Date`) AS INT) as hour, SUM(`{expense_col}`) as total, COUNT(*) as cnt FROM user_data {where} GROUP BY hour ORDER BY hour"
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    return [{'hour': int(r[0]), 'amount': round(r[1], 2), 'count': r[2]} for r in rows]

def get_top_counterparties(transaction_type='Expense', start=None, end=None, limit=10):
    if transaction_type == 'Income':
        money_col = find_income_column()
    else:
        money_col = find_expense_column()
    counterparty_col = find_counterparty_column()
    if not money_col or not counterparty_col:
        return []
    where = build_where_clause(start, end, None)
    sql = f"SELECT `{counterparty_col}` as cp, SUM(`{money_col}`) as total FROM user_data {where} GROUP BY cp ORDER BY total DESC LIMIT {limit}"
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    return [{'name': r[0], 'amount': round(r[1], 2)} for r in rows if r[0] and r[0].strip()]

# Helper functions to detect columns dynamically
def get_money_columns():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(user_data)"))
        cols = [row[1] for row in result if row[2] in ('REAL', 'FLOAT', 'INTEGER', 'NUMERIC')]
    return cols

def find_income_column():
    for col in get_money_columns():
        if any(kw in col.lower() for kw in ['received', 'income', 'credit']):
            return col
    return None

def find_expense_column():
    for col in get_money_columns():
        if any(kw in col.lower() for kw in ['sent', 'expense', 'debit', 'withdrawn']):
            return col
    return None

def find_category_column():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(user_data)"))
        for row in result:
            if row[2] == 'TEXT' and row[1].lower() not in ('counterparty', 'details', 'description', 'time', 'month', 'weekday'):
                # Prefer a column with 'category' in name
                if 'category' in row[1].lower():
                    return row[1]
    return None

def find_counterparty_column():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(user_data)"))
        for row in result:
            if row[1].lower() in ('counterparty', 'details', 'description'):
                return row[1]
    return None

def build_where_clause(start, end, category):
    conditions = []
    if start:
        conditions.append(f"`Transaction Date` >= '{start}'")
    if end:
        conditions.append(f"`Transaction Date` <= '{end}'")
    if category:
        conditions.append(f"`Transaction Category` = '{category}'")
    return "WHERE " + " AND ".join(conditions) if conditions else ""
