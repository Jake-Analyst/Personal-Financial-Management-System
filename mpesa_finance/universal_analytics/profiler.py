import pandas as pd
import numpy as np
from dateutil.parser import parse as dateparse
from semantic import infer_semantic_role

def detect_column_type(series):
    """Return one of: numeric, datetime, categorical, boolean, text."""
    s = series.dropna()
    if len(s) == 0:
        return 'text'
    if s.dtype == 'bool' or set(s.unique()).issubset({True, False, 0, 1, 'True', 'False', 'true', 'false'}):
        return 'boolean'
    if pd.api.types.is_numeric_dtype(s):
        return 'numeric'
    try:
        converted = pd.to_datetime(s, errors='coerce')
        if converted.notna().sum() / len(s) > 0.8:
            return 'datetime'
    except:
        pass
    unique_ratio = s.nunique() / len(s)
    if unique_ratio < 0.05 or s.nunique() <= 30:
        return 'categorical'
    return 'text'

def profile_dataframe(df):
    profile = {'columns': [], 'row_count': len(df)}
    for col in df.columns:
        series = df[col]
        col_type = detect_column_type(series)
        stats = {
            'name': col,
            'type': col_type,
            'missing': int(series.isna().sum()),
            'unique': int(series.nunique()),
            'sample_values': series.dropna().head(5).tolist()
        }
        if col_type == 'numeric':
            stats['min'] = float(series.min()) if not series.isna().all() else 0
            stats['max'] = float(series.max()) if not series.isna().all() else 0
            stats['mean'] = float(series.mean()) if not series.isna().all() else 0
            stats['median'] = float(series.median()) if not series.isna().all() else 0
        elif col_type == 'datetime':
            try:
                dts = pd.to_datetime(series, errors='coerce').dropna()
                stats['min_date'] = dts.min().isoformat()
                stats['max_date'] = dts.max().isoformat()
            except:
                pass
        elif col_type == 'categorical':
            value_counts = series.value_counts().head(10).to_dict()
            stats['top_categories'] = {str(k): int(v) for k, v in value_counts.items()}
        # Add semantic role
        stats['semantic_role'] = infer_semantic_role(col, col_type, stats.get('sample_values', []))
        profile['columns'].append(stats)
    return profile
