# datamap_parser.py
from __future__ import annotations
import re
import pandas as pd


# Exact IDs to always skip
EXCLUDED_EXACT = {
    # your existing skip list
    "responseid", "respid", "hdummydp", "status",
    "interview_start", "interview_end", "lengthofintv",
    # the new ones you shared
    "record", "uuid", "date", "markers", "start_date",
}

# Prefixes to skip (case-insensitive): e.g., "vd...", "vb...", "vos...", "vlist", "qtime", "vmobiledevice", "vmobileos"
EXCLUDED_PREFIXES = [
    "vlist",
    "qtime",
    "vos",
    "vb",
    "vmobiledevice",
    "vmobileos",
    "vd",
]

def _normalize(s) -> str:
    if pd.isna(s):
        return ""
    return re.sub(r"[^a-z0-9_]+", "", str(s).strip().lower())

def _head_token_from_label(label) -> str:
    if pd.isna(label):
        return ""
    text = str(label).strip()
    token = text.split(":", 1)[0].strip()
    token = token.split(None, 1)[0].strip()
    return token

def _is_single_like(qtype: str) -> bool:
    q = (qtype or "").strip().lower()
    return q == "single" or ("grid" in q)

def _resolve_column_name(data_cols, var_id: str, q_label: str) -> str | None:
    cols = list(data_cols)
    def normmap(vals): return {_normalize(c): c for c in vals}
    cols_norm = normmap(cols)

    if var_id and var_id in cols:
        return var_id

    vid_norm = _normalize(var_id)
    if vid_norm and vid_norm in cols_norm:
        return cols_norm[vid_norm]

    token = _head_token_from_label(q_label)
    if token and token in cols:
        return token

    token_norm = _normalize(token)
    if token_norm and token_norm in cols_norm:
        return cols_norm[token_norm]

    if token:
        tlow = token.lower()
        for c in cols:
            if str(c).lower().startswith(tlow):
                return c
    return None

def _is_excluded_system_var(question_id: str, var_id: str, q_label: str) -> bool:
    """
    Return True if this row should be excluded from axis generation based on
    exact names or prefixes; checks Question ID, Variable ID and label token.
    """
    qid = _normalize(question_id)
    vid = _normalize(var_id)
    tok = _normalize(_head_token_from_label(q_label))

    # exact
    if qid in EXCLUDED_EXACT or vid in EXCLUDED_EXACT or tok in EXCLUDED_EXACT:
        return True

    # prefixes
    def has_excluded_prefix(s: str) -> bool:
        for p in EXCLUDED_PREFIXES:
            if s.startswith(_normalize(p)):
                return True
        return False

    return has_excluded_prefix(qid) or has_excluded_prefix(vid) or has_excluded_prefix(tok)

def parse_datamap_to_json(datamap_file, data_df: pd.DataFrame | None = None):
    """
    Parse a survey datamap Excel and generate question configurations.

    Pass data_df to resolve columns via Variable ID or Question Label token.
    """
    df = pd.read_excel(datamap_file, sheet_name="Sheet1")
    df = df.dropna(subset=["Question ID"])

    questions = []
    question_counter = 1

    grouped = df.groupby("Question ID", sort=False)
    data_cols = set(data_df.columns) if data_df is not None else set()

    for question_id, group in grouped:
        first_row = group.iloc[0]
        qtype_raw = str(first_row.get("Type", "")).strip().lower()
        qtext = first_row.get("Question Label")
        qtext = str(qtext) if pd.notna(qtext) else str(question_id)

        # ---- NEW: skip system/metadata variables ----
        if _is_excluded_system_var(
            question_id=str(question_id),
            var_id=str(first_row.get("Variable ID", "")),
            q_label=str(first_row.get("Question Label", "")),
        ):
            # silently skip
            continue

        # ---------------- SINGLE (and GRID as single) ----------------
        if _is_single_like(qtype_raw):
            display_structure = []
            for _, row in group.iterrows():
                if pd.notna(row.get("Answer Code")):
                    code_val = row["Answer Code"]
                    try:
                        code_val = int(code_val) if str(code_val).isdigit() else code_val
                    except Exception:
                        pass
                    display_structure.append(["code", str(row.get("Answer Label")), code_val])

            qvar = str(question_id)
            if data_df is not None:
                resolved = _resolve_column_name(
                    data_cols, str(first_row.get("Variable ID", "")), str(first_row.get("Question Label", ""))
                )
                if resolved:
                    qvar = resolved

            questions.append({
                "id": question_counter,
                "question_var": qvar,
                "question_text": qtext,
                "base_text": "Total Respondents",
                "display_structure": display_structure,
                "base_filter": None,
                "question_type": "single",
                "mean_var": None,
                "show_sigma": True
            })
            question_counter += 1

        # ---------------- MULTI ----------------
        elif qtype_raw == "multi":
            option_vars = []
            display_structure = []

            for _, row in group.iterrows():
                opt_label = row.get("Answer Label")
                opt_q_label = row.get("Question Label")
                var_id = str(row.get("Variable ID", "") or "")
                token = _head_token_from_label(opt_q_label)

                # If any option looks like an excluded system var, skip that option silently
                if _is_excluded_system_var(question_id=str(question_id), var_id=var_id, q_label=str(opt_q_label or "")):
                    continue

                resolved = None
                if data_df is not None:
                    prefer = token or var_id
                    resolved = _resolve_column_name(data_cols, prefer, opt_q_label or "")

                colname = resolved or (token if token else None) or (var_id if var_id else None) or f"{question_id}_{len(option_vars)+1}"

                option_vars.append(colname)
                display_structure.append(["code", str(opt_label) if pd.notna(opt_label) else colname, colname])

            if len(option_vars) == 0:
                # entire multi was system-like; skip the question
                continue

            if len(option_vars) > 1:
                display_structure.insert(0, ["net", f"Any {question_id} (NET)", option_vars])

            questions.append({
                "id": question_counter,
                "question_var": option_vars,
                "question_text": qtext,
                "base_text": "Total Respondents",
                "display_structure": display_structure,
                "base_filter": None,
                "question_type": "multi",
                "mean_var": None,
                "show_sigma": True
            })
            question_counter += 1

        # ---------------- OPEN NUMERIC ----------------
        elif qtype_raw == "numeric":
            qvar = str(question_id)
            if data_df is not None:
                resolved = _resolve_column_name(
                    data_cols, str(first_row.get("Variable ID", "")), str(first_row.get("Question Label", ""))
                )
                if resolved:
                    qvar = resolved

            questions.append({
                "id": question_counter,
                "question_var": qvar,
                "question_text": qtext,
                "base_text": "Total Respondents",
                "display_structure": [],
                "base_filter": None,
                "question_type": "open_numeric",
                "mean_var": qvar,
                "show_sigma": True
            })
            question_counter += 1

        # ---------------- OTHER TYPES (best-effort single-like) ----------------
        else:
            has_codes = ("Answer Code" in group.columns) and pd.notna(group["Answer Code"]).any()
            if has_codes:
                display_structure = []
                for _, row in group.iterrows():
                    if pd.notna(row.get("Answer Code")):
                        code_val = row["Answer Code"]
                        try:
                            code_val = int(code_val) if str(code_val).isdigit() else code_val
                        except Exception:
                            pass
                        display_structure.append(["code", str(row.get("Answer Label")), code_val])

                qvar = str(question_id)
                if data_df is not None:
                    resolved = _resolve_column_name(
                        data_cols, str(first_row.get("Variable ID", "")), str(first_row.get("Question Label", ""))
                    )
                    if resolved:
                        qvar = resolved

                questions.append({
                    "id": question_counter,
                    "question_var": qvar,
                    "question_text": qtext,
                    "base_text": "Total Respondents",
                    "display_structure": display_structure,
                    "base_filter": None,
                    "question_type": "single",
                    "mean_var": None,
                    "show_sigma": True
                })
                question_counter += 1
            # else: skip silently

    return questions
