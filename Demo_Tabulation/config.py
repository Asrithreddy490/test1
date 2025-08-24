# config.py
import streamlit as st

JSON_FILE = "questions_master.json"
DEFAULT_DATA_FILE = "Final_CE_10042023_V3.csv"
DEFAULT_STUDY_NAME = "DTV-010 Feature Prioritization"
DEFAULT_CLIENT_NAME = "PEERLESS INSIGHTS"
PAGE_TITLE = "Survey Table Config Manager"

def set_page():
    st.set_page_config(layout="wide", page_title=PAGE_TITLE)
    st.title(f"📊 {PAGE_TITLE}")
