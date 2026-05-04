import numpy as np
from analytics import get_monthly_spending, get_category_spending
from datetime import datetime
from dateutil.relativedelta import relativedelta

def forecast_next_month():
    monthly = get_monthly_spending()
    if len(monthly) < 2:
        return {
            'forecast': sum(m['expenses'] for m in monthly) if monthly else 0,
            'message': 'Not enough historical data for reliable forecast.'
        }

    x = np.arange(len(monthly))
    y = np.array([m['expenses'] for m in monthly], dtype=float)
    a, b = np.polyfit(x, y, 1)
    next_index = len(monthly)
    forecast = a * next_index + b
    forecast = max(0, round(forecast, 2))

    last_month_str = monthly[-1]['date']
    last_date = datetime.strptime(last_month_str, "%Y-%m")
    next_date = last_date + relativedelta(months=1)

    return {
        'forecast': forecast,
        'month': next_date.strftime('%Y-%m'),
        'message': 'Forecast based on linear trend.'
    }

def budget_recommendations():
    category_data = {item['category']: item['amount'] for item in get_category_spending()}
    total_expense = sum(category_data.values())
    if total_expense == 0:
        return []

    essential_cats = ['Food', 'Bills', 'Transport', 'Health', 'Education']
    entertainment_cats = ['Entertainment', 'Shopping', 'Other']
    savings_target = 0.20

    current = {}
    for cat, amt in category_data.items():
        current[cat] = amt / total_expense

    recommendations = []
    essential_pct = sum(current.get(c, 0) for c in essential_cats)
    if essential_pct > 0.60:
        excess = essential_pct - 0.60
        rec_amount = excess * total_expense
        recommendations.append({
            'type': 'warning',
            'message': f"Your essential spending is {essential_pct*100:.0f}% of total. Try to reduce it by {excess*100:.0f}% to save approx KES {rec_amount:,.0f}."
        })

    ent_pct = sum(current.get(c, 0) for c in entertainment_cats)
    if ent_pct > 0.30:
        excess_ent = ent_pct - 0.30
        rec_amount_ent = excess_ent * total_expense
        recommendations.append({
            'type': 'warning',
            'message': f"Non-essential spending (Shopping, Entertainment) is {ent_pct*100:.0f}%. Reduce it by {excess_ent*100:.0f}% to save KES {rec_amount_ent:,.0f}."
        })

    if 'Savings' in current and current['Savings'] < savings_target:
        gap = savings_target - current['Savings']
        gap_amount = gap * total_expense
        recommendations.append({
            'type': 'tip',
            'message': f"Your savings are only {current['Savings']*100:.0f}% of expenses. Aim for at least 20% – allocate KES {gap_amount:,.0f} more per period."
        })

    return recommendations
