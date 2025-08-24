# app.py
import streamlit as st
import json
import os
import pandas as pd

from config import (
    JSON_FILE, DEFAULT_DATA_FILE, DEFAULT_STUDY_NAME, DEFAULT_CLIENT_NAME,
    set_page
)
from io_utils import (
    load_questions, save_questions, validate_display_structure,
    load_data, get_now_month_year
)
from banner_config import load_banner_config, save_banner_config, get_default_banner_config
from datamap_parser import parse_datamap_to_json
from table_service import generate_tables
from ui_file_checker import render_file_checker_tab  # ⬅️ new: separate UI module

# ----------------------
# Initialize page & session
# ----------------------
set_page()

if 'questions' not in st.session_state:
    st.session_state.questions = load_questions()

# ----------------------
# Sidebar: Stored Questions
# ----------------------
st.sidebar.header("🔍 Stored Questions")

if st.session_state.questions:
    question_options = {
        f"ID {q['id']} - {q['question_text'][:30]}...": q['id']
        for q in st.session_state.questions
    }
    selected_label = st.sidebar.selectbox(
        "Select Question",
        list(question_options.keys()),
        key="question_select"
    )
    selected_id = question_options[selected_label]

    col1, col2 = st.sidebar.columns(2)
    if col1.button("✏️ Edit", key="edit_btn"):
        st.session_state.edit_id = selected_id
        st.rerun()
    if col2.button("🗑️ Delete", key="delete_btn"):
        st.session_state.questions = [q for q in st.session_state.questions if q['id'] != selected_id]
        if save_questions(st.session_state.questions):
            st.sidebar.success(f"Deleted question ID {selected_id}")
            st.rerun()
else:
    st.sidebar.info("ℹ️ No questions stored yet. Import or add new questions below.")

# ----------------------
# Main content tabs
# ----------------------
tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "🧪 File Format Checker", "📥 Import Questions", "✏️ Add/Edit Questions",
    "📊 Generate Tables", "🏷️ Manage Banners"
])

# ----------------------
# Tab 0: File Format Checker (separate UI module)
# ----------------------
with tab0:
    render_file_checker_tab()

# ----------------------
# Tab 1: Import Questions
# ----------------------
with tab1:
    st.header("Import from Datamap")
    uploaded_file = st.file_uploader(
        "Upload Datamap Excel File",
        type=["xlsx"],
        help="Upload your survey datamap Excel file to automatically generate question configurations"
    )

    if uploaded_file is not None and st.button("⚡ Generate Questions from Datamap", type="primary"):
        try:
            with st.spinner("🔍 Processing datamap..."):
                new_questions = parse_datamap_to_json(uploaded_file)

                existing_ids = [q['id'] for q in st.session_state.questions] if st.session_state.questions else [0]
                start_id = max(existing_ids) + 1

                for i, q in enumerate(new_questions):
                    q['id'] = start_id + i

                st.session_state.questions.extend(new_questions)
                if save_questions(st.session_state.questions):
                    st.success(f"✅ Added {len(new_questions)} new questions from datamap!")
                    st.rerun()
        except Exception as e:
            st.error(f"❌ Error processing datamap: {str(e)}")
            st.exception(e)

# ----------------------
# Tab 2: Add/Edit Question
# ----------------------
with tab2:
    st.header("Add / Edit Question")

    form_defaults = {
        "question_var": "",
        "question_text": "",
        "base_text": "Total Respondents",
        "display_structure": [
            ["code", "Male", 1],
            ["code", "Female", 2],
            ["net", "All Genders", [1, 2]]
        ],
        "base_filter": "",
        "question_type": "single",
        "mean_var": "",
        "show_sigma": True
    }

    if "edit_id" in st.session_state:
        q_to_edit = next((q for q in st.session_state.questions if q['id'] == st.session_state.edit_id), None)
        if q_to_edit:
            form_defaults.update({
                "question_var": ",".join(q_to_edit['question_var']) if isinstance(q_to_edit['question_var'], list) else q_to_edit['question_var'],
                "question_text": q_to_edit['question_text'],
                "base_text": q_to_edit['base_text'],
                "display_structure": q_to_edit['display_structure'],
                "base_filter": q_to_edit['base_filter'] or "",
                "question_type": q_to_edit['question_type'],
                "mean_var": q_to_edit['mean_var'] or "",
                "show_sigma": q_to_edit.get("show_sigma", True)
            })
        else:
            st.warning("Question not found for editing.")
            st.session_state.pop("edit_id", None)

    with st.form("question_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            question_var = st.text_input(
                "Question Variable*",
                value=form_defaults["question_var"],
                help="Variable name(s) from dataset. Separate multiple with commas for multi-select questions"
            )
            question_text = st.text_input(
                "Question Text*",
                value=form_defaults["question_text"],
                help="The text that will appear as the question title in tables"
            )
            base_text = st.text_input(
                "Base Text*",
                value=form_defaults["base_text"],
                help="Base description (e.g., 'Total Respondents')"
            )
            question_type = st.selectbox(
                "Question Type*",
                ["single", "multi", "open_numeric"],
                index=["single", "multi", "open_numeric"].index(form_defaults["question_type"]),
                help="Single-select, Multi-select, or Open Numeric question"
            )

        with col2:
            display_structure = st.text_area(
                "Display Structure (JSON)*",
                value=json.dumps(form_defaults["display_structure"], indent=2),
                height=500,
                help="""Format: [["type", "label", code(s)]]
Example:
[
  ["code", "Very Good", 1],
  ["code", "Good", 2],
  ["net", "Top 2 Box (NET)", [1, 2]]
]"""
            )
            base_filter = st.text_input(
                "Base Filter",
                value=form_defaults["base_filter"],
                help="Optional filter condition (e.g., 'Q1 == 1')"
            )
            mean_var = st.text_input(
                "Mean Variable",
                value=form_defaults["mean_var"],
                help="Optional variable for calculating means"
            )
            show_sigma = st.checkbox(
                "Show Sigma",
                value=form_defaults["show_sigma"],
                help="Show statistical significance testing"
            )

        submitted = st.form_submit_button("💾 Save Question", type="primary")

        if submitted:
            if not all([question_var, question_text, base_text, display_structure]):
                st.error("Please fill in all required fields (*)")
                st.stop()

            try:
                display_structure_parsed = json.loads(display_structure)
                if not validate_display_structure(display_structure_parsed):
                    st.error("Invalid display structure format")
                    st.stop()
            except json.JSONDecodeError:
                st.error("Display Structure must be valid JSON")
                st.stop()

            question_data = {
                "question_var": [v.strip() for v in question_var.split(",")] if "," in question_var else question_var,
                "question_text": question_text,
                "base_text": base_text,
                "display_structure": display_structure_parsed,
                "base_filter": base_filter if base_filter else None,
                "question_type": question_type,
                "mean_var": mean_var if mean_var else None,
                "show_sigma": show_sigma
            }

            if "edit_id" in st.session_state:
                for q in st.session_state.questions:
                    if q['id'] == st.session_state.edit_id:
                        q.update(question_data)
                        break
                success_msg = f"Question ID {st.session_state.edit_id} updated!"
                st.session_state.pop("edit_id", None)
            else:
                new_id = max([q['id'] for q in st.session_state.questions], default=0) + 1
                question_data["id"] = new_id
                st.session_state.questions.append(question_data)
                success_msg = f"Question saved with ID {new_id}!"

            if save_questions(st.session_state.questions):
                st.success(success_msg)
                st.rerun()

# ----------------------
# Tab 3: Generate Tables
# ----------------------
with tab3:
    st.header("Generate Output Tables")

    with st.expander("⚙️ Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_file = st.text_input(
                "Data File Path*",
                value=DEFAULT_DATA_FILE,
                help="Path to your data file (CSV, Excel, or SPSS)"
            )
        with col2:
            study_name = st.text_input("Study Name*", value=DEFAULT_STUDY_NAME)
        with col3:
            client_name = st.text_input("Client Name*", value=DEFAULT_CLIENT_NAME)

    st.subheader("Banner Configuration")
    banner_config = load_banner_config()

    if st.button("✨ Generate Tables", type="primary", disabled=not st.session_state.questions):
        if not all([data_file, study_name, client_name]):
            st.error("Please fill in all required configuration fields (*)")
            st.stop()

        if not os.path.exists(data_file):
            st.error(f"Data file not found at: {data_file}")
            st.stop()

        try:
            with st.spinner("⏳ Generating tables..."):
                data = load_data(data_file)
                month, year = get_now_month_year()
                final_df, file_name = generate_tables(
                    questions=st.session_state.questions,
                    data=data,
                    study_name=study_name,
                    client_name=client_name,
                    banner_config=banner_config,
                    month=month,
                    year=year
                )

                if final_df is not None:
                    st.success(f"✅ Tables generated successfully! Saved to: {file_name}")
                    with open(file_name, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Tables",
                            data=f,
                            file_name=file_name,
                            mime="text/csv"
                        )
                else:
                    st.warning("No tables were generated")
        except Exception as e:
            st.error(f"❌ Error generating tables: {str(e)}")
            st.exception(e)

# ----------------------
# Tab 4: Manage Banners (banner.json)
# ----------------------
with tab4:
    st.header("Manage Banners (banner.json)")

    # Helpers
    def _validate_rows(rows):
        ids = set()
        for r in rows:
            if not r.get("id") or not r.get("label"):
                return False, "Each row must have non-empty 'id' and 'label'."
            if r["id"] in ids:
                return False, f"Duplicate id '{r['id']}' found."
            ids.add(r["id"])
        return True, ""

    def _normalize_rows(rows):
        # Convert "" to None for condition, strip spaces
        out = []
        for r in rows:
            rid = str(r.get("id", "")).strip()
            lbl = str(r.get("label", "")).strip()
            cond = r.get("condition", None)
            if isinstance(cond, str):
                cond = cond.strip()
                if cond == "":
                    cond = None
            out.append({"id": rid, "label": lbl, "condition": cond})
        return out

    mode = st.radio("Edit mode", ["Table editor", "Raw JSON"], horizontal=True)

    current_banners = load_banner_config()

    if mode == "Table editor":
        st.write("Add/remove rows directly. Ensure unique `id` values.")

        df = pd.DataFrame(current_banners, columns=["id", "label", "condition"])

        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "id": st.column_config.TextColumn("id", help="Short code (A, B, C...) or custom key"),
                "label": st.column_config.TextColumn("label", help="Display label on banner"),
                "condition": st.column_config.TextColumn(
                    "condition",
                    help="pandas.query condition; leave blank for Total"
                )
            }
        )

        colA, colB, colC, colD = st.columns(4)
        with colA:
            if st.button("💾 Save banners"):
                rows = edited.to_dict(orient="records")
                rows = _normalize_rows(rows)
                ok, msg = _validate_rows(rows)
                if not ok:
                    st.error(f"❌ {msg}")
                else:
                    if save_banner_config(rows):
                        st.success("✅ banner.json saved.")
                        st.rerun()

        with colB:
            if st.button("↩️ Reload from file"):
                st.experimental_rerun()

        with colC:
            if st.button("🧹 Reset to defaults"):
                defaults = get_default_banner_config()
                if save_banner_config(defaults):
                    st.success("✅ Reset to default banners.")
                    st.rerun()

        with colD:
            st.download_button(
                "⬇️ Download banner.json",
                data=json.dumps(_normalize_rows(edited.to_dict(orient="records")), indent=4, ensure_ascii=False),
                file_name="banner.json",
                mime="application/json"
            )

        st.divider()
        st.caption("Tip: Conditions are evaluated via pandas.query on your dataset.")

    else:  # Raw JSON mode
        json_text = st.text_area(
            "banner.json",
            value=json.dumps(current_banners, indent=4, ensure_ascii=False),
            height=400
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save JSON"):
                try:
                    parsed = json.loads(json_text)
                    if save_banner_config(parsed):
                        st.success("✅ banner.json saved.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Invalid JSON: {e}")

        with c2:
            if st.button("🧹 Reset to defaults"):
                defaults = get_default_banner_config()
                if save_banner_config(defaults):
                    st.success("✅ Reset to default banners.")
                    st.rerun()

        with c3:
            uploaded = st.file_uploader("Upload banner.json", type=["json"], label_visibility="collapsed")
            if uploaded is not None:
                try:
                    upl = json.load(uploaded)
                    if save_banner_config(upl):
                        st.success("✅ Uploaded and saved banner.json.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to load uploaded JSON: {e}")

# ----------------------
# Current Questions Display
# ----------------------
with st.expander("📋 View Current Questions (JSON)"):
    st.json(st.session_state.questions)
