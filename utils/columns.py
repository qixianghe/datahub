import re


def sanitize_column(col: str) -> str:
    """Turn a raw CSV header into a safe Postgres column name.

    Examples:
        'Total Distance (m)'   -> 'total_distance_m'
        'Max Acc (m/s²)'       -> 'max_acc_m_per_s2'
        'HI Accelerations'     -> 'hi_accelerations'
    """
    col = col.strip().lower()
    col = col.replace("²", "2").replace("³", "3")
    col = col.replace("/", "_per_")
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col


def sanitize_columns(columns) -> list:
    return [sanitize_column(c) for c in columns]
