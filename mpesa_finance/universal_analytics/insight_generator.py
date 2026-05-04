import numpy as np
from models import engine
from sqlalchemy import text
from ollamafreeapi import OllamaFreeAPI
import json

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OllamaFreeAPI()
    return _client

def generate_insights(profile, filters=None):
    insights = []
    where = build_where_clause(filters)

    money_cols = [c for c in profile['columns'] if c.get('semantic_role') == 'money']
    cat_cols   = [c for c in profile['columns'] if c.get('semantic_role') == 'category']
    date_cols  = [c for c in profile['columns'] if c.get('semantic_role') == 'datetime']

    # Rule-based: top categories
    for col in cat_cols[:2]:
        sql = f"SELECT `{col['name']}`, COUNT(*) as cnt FROM user_data {where} GROUP BY `{col['name']}` ORDER BY cnt DESC LIMIT 1"
        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
                if row: insights.append(f"Top {col['name']}: '{row[0]}' ({row[1]} occurrences).")
        except: pass

    # Rule-based: money averages
    for col in money_cols[:2]:
        sql = f"SELECT AVG(`{col['name']}`) as avg_val FROM user_data {where}"
        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
                if row and row[0]: insights.append(f"Average {col['name']}: {row[0]:.2f}")
        except: pass

    # Date range
    if date_cols:
        sql = f"SELECT MIN(`{date_cols[0]['name']}`), MAX(`{date_cols[0]['name']}`) FROM user_data {where}"
        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
                if row and row[0]: insights.append(f"Date range: {row[0]} → {row[1]}")
        except: pass

    # Outliers
    for col in money_cols[:1]:
        sql = f"SELECT AVG(`{col['name']}`), AVG(`{col['name']}`*`{col['name']}`) FROM user_data {where}"
        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
                if row and row[0] and row[1]:
                    avg, avg_sq = row[0], row[1]
                    var = avg_sq - avg**2
                    if var > 0:
                        std = np.sqrt(var)
                        sql2 = f"SELECT COUNT(*) FROM user_data {where} WHERE `{col['name']}` > {avg + 2*std} OR `{col['name']}` < {avg - 2*std}"
                        count = conn.execute(text(sql2)).scalar()
                        if count: insights.append(f"{count} outlier(s) in {col['name']} (beyond 2σ).")
        except: pass

    # Growth insights (monthly comparison)
    if date_cols and money_cols:
        date_col = date_cols[0]['name']
        money_col = money_cols[0]['name']
        try:
            sql = f"""
                SELECT strftime('%Y-%m', `{date_col}`) as month, SUM(`{money_col}`) as total
                FROM user_data {where}
                GROUP BY month ORDER BY month DESC LIMIT 2
            """
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()
                if len(rows) == 2:
                    current, previous = rows[0][1], rows[1][1]
                    change = ((current - previous) / previous) * 100 if previous else 0
                    direction = "increased" if change > 0 else "decreased"
                    insights.append(f"{money_col} {direction} by {abs(change):.1f}% compared to previous month.")
        except: pass

    # LLM enhancement
    try:
        summary = build_profile_summary(profile)
        prompt = f"""You are a data analyst. Based on this dataset profile, provide 3-5 specific insights (max 120 chars each). Focus on patterns, trends, anomalies. Profile:\n{summary}\n\nInsights:"""
        client = get_client()
        llm_response = client.chat(model="deepseek-r1:latest", prompt=prompt, temperature=0.7)
        if llm_response:
            llm_lines = [line.strip("-• ").strip() for line in llm_response.split('\n') if line.strip()]
            insights = llm_lines + insights
    except Exception as e:
        print(f"LLM unavailable, using rule-based only: {e}")

    if not insights:
        insights.append("No significant insights found.")
    return insights

def build_where_clause(filters):
    if not filters: return ""
    conditions = [f"`{col}` = '{val}'" for col, val in filters.items()]
    return "WHERE " + " AND ".join(conditions)

def build_profile_summary(profile):
    summary = f"Dataset with {profile['row_count']} rows. Columns:\n"
    for c in profile['columns']:
        summary += f"- {c['name']} ({c.get('semantic_role', 'unknown')})"
        if c['type'] == 'numeric' or c.get('semantic_role') == 'money':
            summary += f"  min={c.get('min')}, max={c.get('max')}, mean={c.get('mean',0):.1f}"
        if c['type'] == 'categorical':
            summary += f"  top={c.get('top_categories',{})}"
        summary += "\n"
    return summary
