def plan_analyses(profile):
    plans = []
    cols = {c['name']: c for c in profile['columns']}
    # Group by semantic role
    money_cols = [c for c in profile['columns'] if c.get('semantic_role') == 'money']
    datetime_cols = [c for c in profile['columns'] if c.get('semantic_role') == 'datetime']
    category_cols = [c for c in profile['columns'] if c.get('semantic_role') == 'category']
    numeric_cols = [c for c in profile['columns'] if c.get('semantic_role') == 'numeric']
    target_col = None
    # Target detection (from semantic module)
    from semantic import detect_target_column
    target_name = detect_target_column(profile)
    if target_name:
        target_col = cols[target_name]

    # 1. Time series if date + money/numeric
    if datetime_cols and (money_cols or numeric_cols):
        val_col = money_cols[0] if money_cols else numeric_cols[0]
        plans.append({'type': 'time_series', 'date_col': datetime_cols[0]['name'], 'value_col': val_col['name']})

    # 2. Category breakdown on categories
    for cat in category_cols[:3]:
        # If target exists, do grouped analysis
        if target_col:
            plans.append({'type': 'target_breakdown', 'cat_col': cat['name'], 'target_col': target_col['name']})
        else:
            plans.append({'type': 'category_breakdown', 'col': cat['name']})

    # 3. Distributions for money/numeric
    for col in (money_cols + numeric_cols)[:3]:
        plans.append({'type': 'distribution', 'col': col['name']})

    # 4. Correlation if at least 2 numeric/money
    all_numerics = money_cols + numeric_cols
    if len(all_numerics) >= 2:
        plans.append({'type': 'correlation', 'cols': [c['name'] for c in all_numerics[:5]]})

    # 5. KPI cards for money/numeric
    if (money_cols + numeric_cols):
        plans.append({'type': 'kpi', 'cols': [c['name'] for c in (money_cols + numeric_cols)[:4]]})

    # 6. Pattern: day/hour heatmap if datetime
    if datetime_cols and (money_cols or numeric_cols):
        plans.append({'type': 'heatmap', 'date_col': datetime_cols[0]['name'], 'value_col': (money_cols or numeric_cols)[0]['name']})

    return plans
