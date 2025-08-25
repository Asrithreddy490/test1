# tabplan_parser.py
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
import pandas as pd

# Heuristics for likely columns in tabplan
QID_COL_CANDIDATES = [
    "question id", "question_id", "qid", "q id", "questionid",
    "variable", "variable id", "variable_id", "var", "var id", "var_id",
    "question", "qno", "q no", "qname", "q_name", "qcode", "q_code",
]
LABEL_COL_CANDIDATES = [
    "question label", "question_label", "label", "title", "question text", "question_text", "text"
]
TYPE_COL_CANDIDATES = ["type", "qtype", "question type", "question_type"]

def _norm(s: Any) -> str:
    if pd.isna(s):
        return ""
    return re.sub(r"\s+", " ", str(s).strip())

def _choose_column(cols: List[str], candidates: List[str]) -> Optional[str]:
    low = {c.lower(): c for c in cols}
    for want in candidates:
        if want in low:
            return low[want]
    # fuzzy: startswith match
    for c in cols:
        for want in candidates:
            if c.lower().startswith(want):
                return c
    return None

def parse_tabplan(excel_file, sheet: str | int | None = None) -> List[Dict[str, Any]]:
    """
    Parse a tabplan Excel and return a normalized list of questions to tab.
    Returns list of dicts: { 'qid': str, 'label': str, 'type': str, 'raw': dict }
    """
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet if sheet is not None else 0)
    except Exception:
        # Some files have named sheet like "Tabplan" or "Plan"
        for name in ["Tabplan", "TABPLAN", "Plan", "PLAN", "Sheet1"]:
            try:
                df = pd.read_excel(excel_file, sheet_name=name)
                break
            except Exception:
                df = None
        if df is None:
            raise

    # Drop blank rows
    df = df.dropna(how="all")
    if df.empty:
        return []

    # Find columns
    cols = list(df.columns)
    qid_col = _choose_column(cols, QID_COL_CANDIDATES)
    label_col = _choose_column(cols, LABEL_COL_CANDIDATES)
    type_col = _choose_column(cols, TYPE_COL_CANDIDATES)

    if qid_col is None:
        # Try to infer a QID-like column: first string column with many Q*/S*/h* patterns
        for c in cols:
            vals = df[c].dropna().astype(str).str.strip()
            if (vals.str.match(r"^[A-Za-z]\w+").mean() > 0.5) and (vals.nunique() > 3):
                qid_col = c
                break

    results: List[Dict[str, Any]] = []
    if qid_col is None:
        # No usable column; return empty with raw hint
        return results

    for _, row in df.iterrows():
        qid = _norm(row.get(qid_col, ""))
        if not qid:
            continue
        label = _norm(row.get(label_col, "")) if label_col else ""
        qtype = _norm(row.get(type_col, "")) if type_col else ""

        results.append({
            "qid": qid,
            "label": label or qid,
            "type": qtype.lower() if qtype else "",
            "raw": {k: row.get(k) for k in cols},
        })

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for r in results:
        key = (r["qid"], r["label"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return deduped
