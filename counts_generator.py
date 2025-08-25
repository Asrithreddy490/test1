"""
counts_generator.py
-------------------
Counts from datamap + data.

Enhancements:
- Treat 'grid' types as single-choice.
- Resolve data column by Variable ID OR by Question Label head token (e.g., 'S3r1:' -> 'S3r1').
- Optional unresolved_report collects rows we couldn't map, with suggestions.

Expected datamap columns:
  ["Question ID","Variable ID","Type","Start","Finish","Answer Code","Question Label","Answer Label"]
"""

from __future__ import annotations
import re
from typing import Sequence, Union, Optional, Any, List, Dict

import numpy as np
import pandas as pd

# Values considered as "checked" for multi-response
DEFAULT_CHECKED_VALUES: Sequence[Union[int, str, bool]] = (1, "1", True, "Y", "Yes", "TRUE")


# ---------- helpers ----------

def _normalize(s: Any) -> str:
    """Lowercase + keep only [a-z0-9_] to compare safely."""
    if pd.isna(s):
        return ""
    return re.sub(r"[^a-z0-9_]+", "", str(s).strip().lower())


def _head_token_from_label(label: Any) -> str:
    """
    Extract the head token from Question Label.
    Examples:
      'S3r1: In advertising...' -> 'S3r1'
      'hGender: Hidden: Gender' -> 'hGender'
      'Q2b_101 brand awareness' -> 'Q2b_101'
    """
    if pd.isna(label):
        return ""
    text = str(label).strip()
    # split by ':' first; else by whitespace
    token = text.split(":", 1)[0].strip()
    token = token.split(None, 1)[0].strip()
    return token


def _is_checked(series: pd.Series,
                checked_values: Sequence[Union[int, str, bool]] = DEFAULT_CHECKED_VALUES) -> pd.Series:
    """Return boolean mask where entries are considered 'checked'."""
    s_num = pd.to_numeric(series, errors="coerce")
    mask_num = s_num == 1
    s_str = series.astype(str).str.strip()
    checked_tokens = {str(v).strip() for v in checked_values}
    mask_tokens = s_str.isin(checked_tokens)
    return (mask_num | mask_tokens).fillna(False)


def _is_single_like(qtype: str) -> bool:
    """Treat 'single' and any type containing 'grid' as single-choice."""
    q = (qtype or "").strip().lower()
    return q == "single" or ("grid" in q)


def _resolve_column_name(
    data_df: pd.DataFrame,
    var_id: str,
    q_label: str,
) -> tuple[Optional[str], List[str]]:
    """
    Try to find the matching column in data_df using:
      1) exact var_id
      2) case-insensitive / normalized var_id
      3) head token from label (exact, then normalized)
      4) startswith/contains heuristics on the token
    Returns (column_name_or_None, suggestions_list)
    """
    cols = list(data_df.columns)
    cols_norm = {_normalize(c): c for c in cols}

    # 1) exact match
    if var_id and var_id in data_df.columns:
        return var_id, []

    # 2) normalized/case-insensitive match
    vid_norm = _normalize(var_id)
    if vid_norm and vid_norm in cols_norm:
        return cols_norm[vid_norm], []

    # 3) try token from label
    token = _head_token_from_label(q_label)
    if token and token in data_df.columns:
        return token, []

    token_norm = _normalize(token)
    if token_norm and token_norm in cols_norm:
        return cols_norm[token_norm], []

    # 4) heuristic: startswith / contains by token (case-insensitive)
    sugg: List[str] = []
    if token:
        tlow = token.lower()
        starts = [c for c in cols if str(c).lower().startswith(tlow)]
        contains = [c for c in cols if tlow in str(c).lower()]
        # keep unique order: starts first, then contains
        seen = set()
        for c in starts + contains:
            if c not in seen:
                sugg.append(c)
                seen.add(c)

    return None, sugg[:10]  # limit suggestions


# ---------- main API ----------

def compute_counts_from_datamap(
    datamap_df: pd.DataFrame,
    data_df: pd.DataFrame,
    *,
    type_column: str = "Type",
    var_column: str = "Variable ID",
    answer_code_column: str = "Answer Code",
    label_column: str = "Question Label",
    checked_values: Sequence[Union[int, str, bool]] = DEFAULT_CHECKED_VALUES,
    var_map: Optional[Dict[str, str]] = None,
    unresolved_report: Optional[List[Dict[str, Any]]] = None,
) -> pd.DataFrame:
    """
    Compute counts for each row of datamap.

    - 'single' and any 'grid*' types -> equality to Answer Code
    - 'multi' -> count of checked values (1/'1'/True/'Y'/'Yes'/'TRUE')
    - Others -> NaN

    If var_map provided, it overrides resolution for that Variable ID.
    If unresolved_report provided, append a dict for rows we couldn't map.
    """
    dm = datamap_df.copy()
    counts: List[Optional[int]] = []

    for _, row in dm.iterrows():
        var_id = str(row.get(var_column, "") or "").strip()
        qtype = str(row.get(type_column, "") or "").strip().lower()
        code = row.get(answer_code_column, np.nan)
        q_label = str(row.get(label_column, "") or "").strip()

        # Resolve data column
        resolved_col: Optional[str] = None
        suggestions: List[str] = []

        # Manual override first
        if var_map and var_id in var_map:
            if var_map[var_id] in data_df.columns:
                resolved_col = var_map[var_id]
            else:
                # overridden name doesn't exist, fall back to resolver
                resolved_col, suggestions = _resolve_column_name(data_df, var_id, q_label)
        else:
            resolved_col, suggestions = _resolve_column_name(data_df, var_id, q_label)

        if resolved_col is None and unresolved_report is not None:
            unresolved_report.append({
                "Variable ID": var_id,
                "Question Label": q_label,
                "Type": qtype,
                "hint_top_matches": suggestions
            })

        value: Optional[int] = np.nan

        if resolved_col is not None:
            col = data_df[resolved_col]

            if _is_single_like(qtype) and pd.notna(code):
                # Compare as-is, then fallback to string equality
                try:
                    value = int((col == code).sum())
                except Exception:
                    value = int((col.astype(str) == str(code)).sum())

            elif qtype == "multi":
                mask = _is_checked(col, checked_values=checked_values)
                value = int(mask.sum())

        counts.append(value)

    dm["Counts"] = counts

    ordered_cols = [
        "Question ID", "Variable ID", "Type", "Start", "Finish",
        "Answer Code", "Question Label", "Answer Label", "Counts"
    ]
    cols = [c for c in ordered_cols if c in dm.columns] + [c for c in dm.columns if c not in ordered_cols]
    return dm[cols]


def export_counts_to_excel(counts_df: pd.DataFrame, path: str, sheet_name: str = "Counts") -> str:
    """Save counts to Excel and return the path."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        counts_df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


# Optional CLI usage
if __name__ == "__main__":
    import argparse
    from datetime import datetime
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Compute counts from datamap + data.")
    parser.add_argument("--datamap", required=True, help="Path to datamap Excel")
    parser.add_argument("--sheet", default="Sheet1", help="Datamap sheet name (default: Sheet1)")
    parser.add_argument("--data", required=True, help="Path to data file (csv/xlsx/xls)")
    parser.add_argument("--out", default=None, help="Output Excel path; default: Counts_YYYYMMDD.xlsx")
    args = parser.parse_args()

    dm = pd.read_excel(args.datamap, sheet_name=args.sheet)
    if args.data.lower().endswith(".csv"):
        df = pd.read_csv(args.data)
    else:
        df = pd.read_excel(args.data)

    unresolved: List[Dict[str, Any]] = []
    res = compute_counts_from_datamap(dm, df, unresolved_report=unresolved)

    out = args.out or f"Counts_{datetime.today().strftime('%Y%m%d')}.xlsx"
    export_counts_to_excel(res, out)
    print(f"Saved: {Path(out).resolve()}")

    if unresolved:
        ur_path = "unresolved_variable_mapping_suggestions.csv"
        pd.DataFrame(unresolved).to_csv(ur_path, index=False)
        print(f"Wrote unresolved mapping suggestions: {Path(ur_path).resolve()}")
