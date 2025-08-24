# io_utils.py
import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime
import pyreadstat

from tab_generator import clean_blank_and_convert_to_numeric
from config import JSON_FILE

# ---------- Question storage ----------
def load_questions():
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Error loading questions: {str(e)}")
        return []

def save_questions(questions):
    try:
        with open(JSON_FILE, "w", encoding='utf-8') as f:
            json.dump(questions, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving questions: {str(e)}")
        return False

def validate_display_structure(structure):
    if not isinstance(structure, list):
        return False
    for item in structure:
        if not (isinstance(item, (list, tuple)) and len(item) >= 3):
            return False
        if item[0] not in ["code", "net"]:
            return False
    return True

# ---------- Data loading ----------
def load_data(path: str) -> pd.DataFrame:
    """Load data with supported formats and apply cleaning/indexing."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext == ".xls":
        df = pd.read_excel(path, engine='xlrd')
    elif ext == ".xlsx":
        df = pd.read_excel(path, engine='openpyxl')
    elif ext == ".sav":
        df, _ = pyreadstat.read_sav(path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    # Index + cleaning
    if "record" in df.columns and "uuid" in df.columns:
        df = df.set_index(keys=["record", "uuid"]).sort_index()
    df = clean_blank_and_convert_to_numeric(df)
    return df

# ---------- Time helpers ----------
def get_now_month_year():
    now = datetime.now()
    return now.strftime("%B"), now.year

# ---------- Raw readers for probe ----------
def try_read_raw(path: str, ext: str):
    """Read a file by extension without pipeline cleaning."""
    try:
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext == ".xls":
            df = pd.read_excel(path, engine="xlrd")
        elif ext == ".xlsx":
            df = pd.read_excel(path, engine="openpyxl")
        elif ext == ".sav":
            df, _ = pyreadstat.read_sav(path)
        else:
            return (False, None, f"Unsupported file format: {ext}")
        return (True, df, "File read successfully.")
    except ImportError as e:
        return (False, None, f"Missing package: {e}")
    except Exception as e:
        return (False, None, f"Error while reading: {e}")

def probe_file_like(uploaded_file, run_full_pipeline: bool = False):
    """
    Save uploaded file to temp path, test raw read, optionally test full load_data().
    Returns dict with results.
    """
    name = uploaded_file.name
    ext = os.path.splitext(name)[1].lower()
    temp_path = f"__probe__{name}"

    result = {
        "name": name, "ext": ext, "ok": False, "msg": "",
        "df": None, "pipeline_ok": None, "pipeline_msg": None
    }
    try:
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        ok, df, msg = try_read_raw(temp_path, ext)
        result.update({"ok": ok, "df": df, "msg": msg})

        if ok and run_full_pipeline:
            try:
                full_df = load_data(temp_path)   # ✅ now defined above
                result["pipeline_ok"] = True
                result["pipeline_msg"] = f"Full pipeline succeeded. Shape: {full_df.shape}"
            except Exception as e:
                result["pipeline_ok"] = False
                result["pipeline_msg"] = f"Full pipeline failed: {e}"

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

    return result
