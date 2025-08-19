import streamlit as st
import pandas as pd
import os
from datetime import datetime

#python -m streamlit run tab_viewer.py run this in terminal to run the app ("http://localhost:8501") 

st.set_page_config(layout="wide")
st.title("Tabulation Peerless")
file_path = "tabs_output.csv"
if os.path.exists(file_path):
    df = pd.read_csv(file_path)
    st.dataframe(df,use_container_width=True, hide_index=True)
    st.success(f"last Updated: {datetime.fromtimestamp(os.path.getatime(file_path)).strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.warning("No Output file found")
