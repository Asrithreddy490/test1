# banner_config.py
import os, json, streamlit as st
from typing import List, Dict, Any

BANNER_FILE = os.getenv("BANNER_JSON", "banner.json")

_DEFAULT_BANNERS: List[Dict[str, Any]] = [
    {"id": "A", "label": "Total", "condition": None}
]

def _validate_banner_schema(items: Any) -> bool:
    if not isinstance(items, list): return False
    ids = set()
    for it in items:
        if not isinstance(it, dict): return False
        if {"id","label","condition"} - set(it): return False
        if not isinstance(it["id"], str) or not isinstance(it["label"], str): return False
        if it["condition"] is not None and not isinstance(it["condition"], str): return False
        if it["id"] in ids: return False
        ids.add(it["id"])
    return True

def load_banner_config() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(BANNER_FILE):
            with open(BANNER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if _validate_banner_schema(data): return data
            st.warning("⚠️ banner.json invalid; using defaults.")
        else:
            st.info("ℹ️ banner.json not found; using defaults.")
    except Exception as e:
        st.error(f"Error loading banner config: {e}")
    return _DEFAULT_BANNERS.copy()

def save_banner_config(banners: List[Dict[str, Any]]) -> bool:
    try:
        if not _validate_banner_schema(banners):
            st.error("❌ Banner config failed validation. Not saved.")
            return False
        with open(BANNER_FILE, "w", encoding="utf-8") as f:
            json.dump(banners, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving banner config: {e}")
        return False

def get_default_banner_config() -> List[Dict[str, Any]]:
    return _DEFAULT_BANNERS.copy()
