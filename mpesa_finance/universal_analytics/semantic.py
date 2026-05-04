"""Heuristic keyword-based detection of column semantic roles."""
import re

def infer_semantic_role(col_name: str, col_type: str, sample_values: list) -> str:
    """
    Return semantic role: money, datetime, category, id, target, text, numeric, boolean.
    Priority: money > datetime > category > id > target > boolean > numeric.
    """
    name_lower = col_name.lower()
    # Money indicators
    if any(word in name_lower for word in ['amount', 'salary', 'income', 'price', 'revenue', 'cost', 'fee', 'balance', 'paid', 'sent', 'received']):
        return 'money'
    # Datetime indicators (already typed as datetime)
    if col_type == 'datetime':
        return 'datetime'
    # Category indicators
    if col_type == 'categorical' and len(sample_values) <= 30:
        return 'category'
    # ID indicators
    if any(word in name_lower for word in ['id', 'code', 'key', 'number']) and col_type in ('text','numeric'):
        return 'id'
    # Binary/boolean indicator
    if col_type == 'boolean':
        return 'boolean'
    # Numeric
    if col_type == 'numeric':
        return 'numeric'
    return 'text'

def detect_target_column(profile: list) -> str | None:
    """
    Try to identify a potential target variable (binary column with meaningful name).
    """
    binary_cols = [c for c in profile['columns'] if c['type'] == 'boolean' or
                   (c['type'] == 'categorical' and c['unique'] == 2)]
    if binary_cols:
        # prefer column with name suggesting target
        for c in binary_cols:
            if any(kw in c['name'].lower() for kw in ['default', 'attrition', 'status', 'target', 'flag']):
                return c['name']
        # fallback: first binary
        return binary_cols[0]['name']
    return None
