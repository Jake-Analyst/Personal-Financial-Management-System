from models import Transaction
from sqlalchemy import func, extract

def get_summary(start=None, end=None, category=None):
    query = Transaction.query
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category:
        query = query.filter(Transaction.category == category)

    income = query.filter(Transaction.transaction_type == 'Income').with_entities(func.sum(Transaction.amount)).scalar() or 0
    expenses = query.filter(Transaction.transaction_type == 'Expense').with_entities(func.sum(Transaction.amount)).scalar() or 0
    expenses_abs = abs(expenses)
    balance = income + expenses
    return {
        'income': round(income, 2),
        'expenses': round(expenses_abs, 2),
        'balance': round(balance, 2)
    }

def get_category_spending(start=None, end=None):
    query = Transaction.query.filter(Transaction.transaction_type == 'Expense')
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)

    result = query.with_entities(
        Transaction.category,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('cnt')
    ).group_by(Transaction.category).all()
    data = []
    for cat, total, cnt in result:
        data.append({'category': cat, 'amount': abs(round(total, 2)), 'count': cnt})
    return data

def get_monthly_spending(start=None, end=None, category=None):
    query = Transaction.query.filter(Transaction.transaction_type == 'Expense')
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category:
        query = query.filter(Transaction.category == category)

    months = query.with_entities(
        extract('year', Transaction.date).label('year'),
        extract('month', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).group_by('year', 'month').order_by('year', 'month').all()

    monthly = []
    for year, month, total in months:
        monthly.append({
            'date': f"{int(year)}-{int(month):02d}",
            'expenses': abs(round(total, 2))
        })
    return monthly

def get_spending_by_hour(start=None, end=None, category=None):
    query = Transaction.query.filter(Transaction.transaction_type == 'Expense')
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category:
        query = query.filter(Transaction.category == category)

    hours = query.with_entities(
        extract('hour', Transaction.date).label('hour'),
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('cnt')
    ).group_by('hour').order_by('hour').all()

    return [{'hour': int(h), 'amount': abs(round(t, 2)), 'count': cnt} for h, t, cnt in hours]

def get_top_counterparties(transaction_type, start=None, end=None, limit=10):
    query = Transaction.query.filter(Transaction.transaction_type == transaction_type)
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)

    rows = query.with_entities(Transaction.description, Transaction.amount).all()
    counterparties = {}
    for desc, amount in rows:
        name = ''
        if desc and ' â€“ ' in desc:
            name = desc.split(' â€“ ', 1)[1].strip()
        elif desc and ' - ' in desc:
            name = desc.split(' - ', 1)[1].strip()
        elif desc:
            name = desc.strip()
        if name:
            counterparties[name] = counterparties.get(name, 0) + abs(amount)
    sorted_cp = sorted(counterparties.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{'name': name, 'amount': round(amt, 2)} for name, amt in sorted_cp]

def get_heatmap_data(start=None, end=None, category=None):
    """Returns spending by day-of-week (0=Mon..6=Sun) x hour (0-23) with amount and count."""
    from datetime import datetime
    query = Transaction.query.filter(Transaction.transaction_type == 'Expense')
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category:
        query = query.filter(Transaction.category == category)

    rows = query.with_entities(Transaction.date, Transaction.amount).all()
    # Initialize grid
    grid = {}
    for day in range(7):
        for hour in range(24):
            grid[(day, hour)] = {'amount': 0.0, 'count': 0}

    for dt, amt in rows:
        if dt is None:
            continue
        # Python weekday(): Monday=0, Sunday=6
        day = dt.weekday()  # 0=Mon, 6=Sun
        hour = dt.hour
        grid[(day, hour)]['amount'] += abs(amt)
        grid[(day, hour)]['count'] += 1

    result = []
    for (day, hour), vals in grid.items():
        if vals['amount'] > 0:
            result.append({
                'day': day,
                'hour': hour,
                'amount': round(vals['amount'], 2),
                'count': vals['count']
            })
    return result

def get_weekday_spending(start=None, end=None, category=None):
    """Returns total spending by day of week with transaction counts."""
    query = Transaction.query.filter(Transaction.transaction_type == 'Expense')
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category:
        query = query.filter(Transaction.category == category)

    rows = query.with_entities(Transaction.date, Transaction.amount).all()
    days = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0}
    counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for dt, amt in rows:
        if dt is None:
            continue
        day = dt.weekday()
        days[day] += abs(amt)
        counts[day] += 1

    return [{'day': day_names[i], 'amount': round(days[i], 2), 'count': counts[i]} for i in range(7)]
