import pandas as pd
import numpy as np
from sqlalchemy import text
from models import engine

def build_chart_configs(plans, filters=None):
    configs = []
    where_clause = build_where_clause(filters)
    for plan in plans:
        try:
            if plan['type'] == 'kpi':
                cols = plan['cols']
                select_parts = []
                for c in cols:
                    select_parts.append(f"AVG(`{c}`) as `avg_{c}`")
                    select_parts.append(f"SUM(`{c}`) as `sum_{c}`")
                sql = f"SELECT {', '.join(select_parts)} FROM user_data {where_clause}"
                with engine.connect() as conn:
                    result = conn.execute(text(sql)).fetchone()
                    kpi_data = {}
                    if result:
                        for c in cols:
                            kpi_data[c] = {
                                'avg': float(result._mapping[f'avg_{c}']) if result._mapping[f'avg_{c}'] is not None else 0,
                                'sum': float(result._mapping[f'sum_{c}']) if result._mapping[f'sum_{c}'] is not None else 0
                            }
                configs.append({'type': 'kpi', 'data': kpi_data})

            elif plan['type'] == 'time_series':
                date_col, val_col = plan['date_col'], plan['value_col']
                sql = f"SELECT `{date_col}` as dt, SUM(`{val_col}`) as val FROM user_data {where_clause} GROUP BY dt ORDER BY dt"
                with engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                    labels = [str(r[0]) for r in rows]
                    values = [float(r[1]) for r in rows]
                configs.append({
                    'type': 'line',
                    'title': f'{val_col} over time',
                    'labels': labels,
                    'datasets': [{'label': val_col, 'data': values}]
                })

            elif plan['type'] == 'distribution':
                col = plan['col']
                sql = f"SELECT `{col}` FROM user_data {where_clause}"
                with engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                    values = [float(r[0]) for r in rows if r[0] is not None]
                if values:
                    counts, bin_edges = np.histogram(values, bins=10)
                    configs.append({
                        'type': 'bar',
                        'title': f'Distribution of {col}',
                        'labels': [f'{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}' for i in range(len(bin_edges)-1)],
                        'datasets': [{'label': 'Count', 'data': counts.tolist()}]
                    })

            elif plan['type'] == 'category_breakdown':
                col = plan['col']
                sql = f"SELECT `{col}` as cat, COUNT(*) as cnt FROM user_data {where_clause} GROUP BY cat ORDER BY cnt DESC LIMIT 10"
                with engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                    labels = [str(r[0]) for r in rows]
                    values = [int(r[1]) for r in rows]
                configs.append({
                    'type': 'pie',
                    'title': f'Breakdown by {col}',
                    'labels': labels,
                    'datasets': [{'data': values}]
                })

            elif plan['type'] == 'target_breakdown':
                cat_col, target_col = plan['cat_col'], plan['target_col']
                sql = f"SELECT `{cat_col}` as cat, `{target_col}` as tgt, COUNT(*) as cnt FROM user_data {where_clause} GROUP BY cat, tgt"
                with engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                # Build a grouped bar structure
                categories = sorted(set(str(r[0]) for r in rows))
                target_vals = sorted(set(str(r[1]) for r in rows))
                datasets = {}
                for cat in categories:
                    datasets[cat] = {t: 0 for t in target_vals}
                for r in rows:
                    datasets[str(r[0])][str(r[1])] = int(r[2])
                # Output multi‑bar dataset
                out_datasets = []
                for t in target_vals:
                    out_datasets.append({
                        'label': f'{target_col}={t}',
                        'data': [datasets[cat][t] for cat in categories]
                    })
                configs.append({
                    'type': 'bar',
                    'title': f'{cat_col} by {target_col}',
                    'labels': categories,
                    'datasets': out_datasets
                })

            elif plan['type'] == 'correlation':
                cols = plan['cols']
                sql = f"SELECT {', '.join([f'`{c}`' for c in cols])} FROM user_data {where_clause} LIMIT 1000"
                with engine.connect() as conn:
                    df = pd.read_sql(sql, conn)
                    corr = df.corr().round(2)
                    matrix = corr.values.tolist()
                configs.append({
                    'type': 'heatmap',
                    'title': 'Correlation Matrix',
                    'labels': cols,
                    'data': matrix
                })

            elif plan['type'] == 'heatmap':
                date_col, val_col = plan['date_col'], plan['value_col']
                sql = f"SELECT `{date_col}` as dt, `{val_col}` as val FROM user_data {where_clause}"
                with engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                if not rows:
                    continue
                df = pd.DataFrame(rows, columns=['dt','val'])
                df['dt'] = pd.to_datetime(df['dt'], errors='coerce')
                df.dropna(inplace=True)
                df['day'] = df['dt'].dt.dayofweek  # Mon=0..Sun=6
                df['hour'] = df['dt'].dt.hour
                pivot = df.groupby(['day','hour'])['val'].sum().unstack(fill_value=0)
                # Build data structure for heatmap rendering
                days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
                heatmap_data = []
                for day_idx in range(7):
                    row = []
                    for hour in range(24):
                        row.append(float(pivot.loc[day_idx, hour]) if day_idx in pivot.index and hour in pivot.columns else 0.0)
                    heatmap_data.append(row)
                configs.append({
                    'type': 'heatmap',
                    'title': f'{val_col} Heatmap',
                    'xlabels': [f'{h}:00' for h in range(24)],
                    'ylabels': days,
                    'data': heatmap_data
                })
        except Exception as e:
            print(f"Chart generation failed for plan {plan}: {e}")
    return configs

def build_where_clause(filters):
    if not filters: return ""
    conditions = [f"`{col}` = '{val}'" for col, val in filters.items()]
    return "WHERE " + " AND ".join(conditions)
