# ui_file_checker.py
import streamlit as st
import json
import pandas as pd
from io_utils import probe_file_like, load_data  # reuse your pipeline loader

def render_file_checker_tab():
    st.header("🧪 Check Data File Compatibility")

    uploaded = st.file_uploader(
        "Upload a data file (.csv, .xls, .xlsx, .sav)",
        type=["csv", "xls", "xlsx", "sav"]
    )
    schema_check = st.checkbox("Also check for required columns: record & uuid", value=True)

    st.caption(
        "Excel requires **openpyxl** (.xlsx) / **xlrd** (.xls). "
        "SPSS requires **pyreadstat**. If missing, you'll see a helpful error."
    )

    if uploaded is None:
        return

    # First: raw read (fast). Offer optional full pipeline in UI below.
    res = probe_file_like(uploaded, run_full_pipeline=False)

    if res["ok"]:
        st.success(f"✅ {res['msg']}")
        st.write(f"**File:** `{res['name']}`  |  **Format:** `{res['ext']}`")
        st.write(f"**Shape:** {res['df'].shape[0]} rows × {res['df'].shape[1]} columns")

        st.subheader("Preview (first 10 rows)")
        st.dataframe(res["df"].head(10), use_container_width=True)

        with st.expander("📚 Columns"):
            st.write(list(res["df"].columns))

        if schema_check:
            missing = [c for c in ["record", "uuid"] if c not in res["df"].columns]
            if missing:
                st.warning(
                    f"⚠️ Missing required columns: {missing}. "
                    "Your tabulation pipeline expects these for indexing."
                )
            else:
                st.info("✅ Required columns present: record, uuid")

        with st.expander("Advanced: Try full pipeline load (index + cleaning)"):
            if st.button("Run full pipeline check"):
                # We need to re-run using the actual pipeline loader on the current upload.
                # Save again to a temp path and call load_data.
                try:
                    import os
                    temp_path = f"__pipeline__{res['name']}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded.getbuffer())
                    full_df = load_data(temp_path)
                    st.success("✅ Full pipeline load succeeded.")
                    st.write(f"Indexed & cleaned shape: {full_df.shape}")
                except Exception as e:
                    st.error(f"❌ Full pipeline load failed: {e}")
                finally:
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass

    else:
        st.error(f"❌ {res['msg']}")
