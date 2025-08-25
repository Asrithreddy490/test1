# app.py
from __future__ import annotations
import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

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
from ui_file_checker import render_file_checker_tab  # separate UI module
from counts_generator import compute_counts_from_datamap, export_counts_to_excel
import importlib, counts_generator  # (optional) hot‑reload during dev
importlib.reload(counts_generator)  # safe if Streamlit caches an old copy
from tabplan_parser import parse_tabplan
from typing import Dict




# ----------------------
# Page + session
# ----------------------
set_page()

if 'questions' not in st.session_state:
    st.session_state.questions = load_questions()


# ----------------------
# Helper: show/hide sidebar
# ----------------------
def _toggle_sidebar(show: bool):
    """
    Hide sidebar completely unless show=True.
    (We also gate rendering the sidebar content below.)
    """
    if show:
        st.markdown(
            "<style>section[data-testid='stSidebar']{display:block !important;}</style>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<style>section[data-testid='stSidebar']{display:none !important;}</style>",
            unsafe_allow_html=True,
        )


# ----------------------
# Navigation (replaces tabs)
# ----------------------
SECTIONS = [
    "🧪 File Format Checker",
    #"📥 Import Questions",
    "🗂️ Tabplan Runner", 
    "✏️ Add/Edit Questions",
    "🏷️ Manage Banners",
    "📊 Generate Tables",
    "🔢 Generate Counts",
    
]

section = st.radio("Navigate", SECTIONS, horizontal=True, key="section_switcher")

# Only show sidebar on these sections
SHOW_SIDEBAR_SECTIONS = {"📥 Import Questions", "✏️ Add/Edit Questions"}
_toggle_sidebar(section in SHOW_SIDEBAR_SECTIONS)


# ----------------------
# Sidebar: Stored Questions (rendered only when allowed)
# ----------------------
if section in SHOW_SIDEBAR_SECTIONS:
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
# Section: File Format Checker
# ----------------------
if section == "🧪 File Format Checker":
    render_file_checker_tab()


# ----------------------
# Section: Import Questions
# ----------------------
elif section == "📥 Import Questions":
    st.header("Import from Datamap")

    colA, colB = st.columns(2)
    with colA:
        uploaded_file = st.file_uploader(
            "Upload Datamap Excel File",
            type=["xls", "xlsx", "xlsm"],  # allow xlsm too
            help="Upload your survey datamap Excel file (Sheet1)"
        )
    with colB:
        data_file_for_axis = st.text_input(
            "Data File Path (for axis resolution)*",
            value=DEFAULT_DATA_FILE,
            help="Used to resolve actual column names from Variable ID or Question Label (e.g., S3r1)"
        )

    if uploaded_file is not None and st.button("⚡ Generate Questions from Datamap", type="primary"):
        try:
            with st.spinner("🔍 Processing datamap..."):
                # Load data so parser can resolve column names like S3r1 / hGender
                data_df_axis = None
                if data_file_for_axis and os.path.exists(data_file_for_axis):
                    data_df_axis = load_data(data_file_for_axis)
                else:
                    st.warning("Data file not found. Axis will be created without column resolution.")

                # Pass data_df to enable label-token matching (e.g., 'S3r1:' -> 'S3r1')
                new_questions = parse_datamap_to_json(uploaded_file, data_df=data_df_axis)

                # Re-id sequentially after existing ones
                existing_ids = [q['id'] for q in st.session_state.questions] if st.session_state.questions else [0]
                start_id = max(existing_ids) + 1
                for i, q in enumerate(new_questions):
                    q['id'] = start_id + i

                st.session_state.questions.extend(new_questions)
                if save_questions(st.session_state.questions):
                    st.success(f"✅ Added {len(new_questions)} new questions from datamap!")
                    # Optional: preview
                    st.write("Preview of first 3 questions created:")
                    st.json(new_questions[:3])
                    st.rerun()
        except Exception as e:
            st.error(f"❌ Error processing datamap: {str(e)}")
            st.exception(e)


# ----------------------
# Section: Add/Edit Question
# ----------------------
elif section == "✏️ Add/Edit Questions":
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
# Section: Generate Tables
# ----------------------
elif section == "📊 Generate Tables":
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
# Section: Manage Banners
# ----------------------
elif section == "🏷️ Manage Banners":
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
# Section: Generate Counts
# ----------------------
elif section == "🔢 Generate Counts":
    st.header("Generate Counts (from Datamap + Data)")

    colA, colB = st.columns(2)
    with colA:
        data_file_counts = st.text_input("Data File Path*", value=DEFAULT_DATA_FILE)
    with colB:
        datamap_file_counts = st.file_uploader("Upload Datamap Excel (Sheet1)", type=["xls","xlsx","xlsm"])

    if st.button("⚡ Generate Counts", type="primary"):
        if not os.path.exists(data_file_counts):
            st.error(f"Data file not found: {data_file_counts}")
            st.stop()
        if datamap_file_counts is None:
            st.error("Please upload a Datamap Excel file.")
            st.stop()

        try:
            with st.spinner("Computing counts..."):
                data_df = load_data(data_file_counts)
                dm_df = pd.read_excel(datamap_file_counts, sheet_name="Sheet1")

                unresolved = []
                counts_df = compute_counts_from_datamap(dm_df, data_df, unresolved_report=unresolved)

                st.success("✅ Counts generated")
                st.dataframe(counts_df.head(50), use_container_width=True)

                # Downloads
                today = datetime.today().strftime("%Y%m%d")
                excel_name = f"Counts_{today}.xlsx"
                csv_name = f"Counts_{today}.csv"

                with pd.ExcelWriter(excel_name, engine="openpyxl") as writer:
                    counts_df.to_excel(writer, sheet_name="Counts", index=False)
                with open(excel_name, "rb") as f:
                    st.download_button(
                        "⬇️ Download Excel (.xlsx)",
                        f.read(),
                        file_name=excel_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                st.download_button(
                    "⬇️ Download CSV (.csv)",
                    counts_df.to_csv(index=False).encode("utf-8"),
                    file_name=csv_name,
                    mime="text/csv"
                )

                # Unresolved suggestions
                if unresolved:
                    st.warning(f"{len(unresolved)} items couldn’t be mapped. Suggestions available.")
                    unresolved_df = pd.DataFrame(unresolved)
                    st.dataframe(unresolved_df.head(20), use_container_width=True)
                    st.download_button(
                        "⬇️ Unresolved mapping suggestions",
                        data=unresolved_df.to_csv(index=False).encode("utf-8"),
                        file_name="unresolved_variable_mapping_suggestions.csv",
                        mime="text/csv",
                    )
        except Exception as e:
            st.error(f"Failed to generate counts: {e}")
# ----------------------
# Section: Tabplan Runner (dynamic tabs per tabplan)
# ----------------------
elif section == "🗂️ Tabplan Runner":
    from tabplan_parser import parse_tabplan  # ensure import is at top too

    st.header("Run Tabplan")

    colA, colB, colC = st.columns(3)
    with colA:
        tabplan_file = st.file_uploader(
            "Upload Tabplan Excel",
            type=["xls", "xlsx"],
            help="We will detect the column that lists questions/variables."
        )
    with colB:
        datamap_for_tabplan = st.file_uploader(
            "Datamap (for auto-create)",
            type=["xls", "xlsx", "xlsm"],
            help="Used only if you click 'Auto-create missing from Datamap'."
        )
    with colC:
        data_file_tabplan = st.text_input(
            "Data File Path*",
            value=DEFAULT_DATA_FILE,
            help="Dataset used for generating tables."
        )

    # Parse tabplan
    if tabplan_file is not None and st.button("🔍 Parse Tabplan"):
        try:
            with st.spinner("Reading tabplan..."):
                tab_items = parse_tabplan(tabplan_file)
                if not tab_items:
                    st.warning("No questions detected in the tabplan. Please check the header names.")
                else:
                    st.success(f"Detected {len(tab_items)} question(s) from the tabplan.")
                st.session_state["_tabplan_items"] = tab_items
        except Exception as e:
            st.error(f"Failed to read tabplan: {e}")

    tab_items = st.session_state.get("_tabplan_items", [])

    # Helper: token from label
    def _head_token_from_label(label: str) -> str:
        if not label:
            return ""
        t = str(label).strip()
        t = t.split(":", 1)[0].strip()
        t = t.split(None, 1)[0].strip()
        return t

    # Find a matching saved question config
    def find_question_config(qid: str, label: str):
        token = _head_token_from_label(label).lower()
        qid_low = str(qid).strip().lower()
        qs = st.session_state.questions or []

        # 1) direct string question_var
        for q in qs:
            qv = q.get("question_var")
            if isinstance(qv, str) and qv.lower() == qid_low:
                return q

        # 2) multi list membership
        for q in qs:
            qv = q.get("question_var")
            if isinstance(qv, list) and any(str(v).lower() == qid_low for v in qv):
                return q

        # 3) token vs question_var
        if token:
            for q in qs:
                qv = q.get("question_var")
                if isinstance(qv, str) and qv.lower() == token:
                    return q
                if isinstance(qv, list) and any(str(v).lower() == token for v in qv):
                    return q

        # 4) fallback: substring in question_text
        for q in qs:
            qt = str(q.get("question_text", "")).lower()
            if qid_low in qt or (token and token in qt):
                return q

        return None

    # Auto-create missing questions from Datamap (only those present in tabplan)
    if tab_items and datamap_for_tabplan is not None and st.button("📎 Auto-create missing from Datamap"):
        if not data_file_tabplan or not os.path.exists(data_file_tabplan):
            st.error(f"Data file not found: {data_file_tabplan}")
        else:
            try:
                from datamap_parser import parse_datamap_to_json  # ensure latest
                with st.spinner("Creating missing questions from datamap..."):
                    data_df_for_axis = load_data(data_file_tabplan)
                    # Generate ALL questions from datamap
                    all_from_dm = parse_datamap_to_json(datamap_for_tabplan, data_df=data_df_for_axis)

                    # Build fast lookups
                    def _norm(s): return str(s).strip().lower()
                    dm_by_qvar = {}
                    for q in all_from_dm:
                        qv = q.get("question_var")
                        if isinstance(qv, str):
                            dm_by_qvar[_norm(qv)] = q
                        elif isinstance(qv, list):
                            for v in qv:
                                dm_by_qvar[_norm(v)] = q

                    created = []
                    for item in tab_items:
                        qid = item["qid"]
                        label = item["label"]
                        token = _head_token_from_label(label)
                        # Already present?
                        if find_question_config(qid, label) is not None:
                            continue
                        # Try to fetch from datamap-derived list
                        candidate = (
                            dm_by_qvar.get(_norm(qid)) or
                            (dm_by_qvar.get(_norm(token)) if token else None)
                        )
                        if candidate:
                            # assign new id and append
                            new_id = max([q['id'] for q in st.session_state.questions], default=0) + 1
                            cand_copy = dict(candidate)
                            cand_copy["id"] = new_id
                            st.session_state.questions.append(cand_copy)
                            created.append((qid, cand_copy.get("question_var")))
                    if created:
                        save_questions(st.session_state.questions)
                        st.success(f"Created {len(created)} missing question(s) from datamap.")
                        with st.expander("Details"):
                            st.write(created)
                        st.rerun()
                    else:
                        st.info("No new questions were created. Either all are already present or could not be matched from datamap.")
            except Exception as e:
                st.error(f"Auto-create failed: {e}")

    # Stop if no tabplan yet
    if not tab_items:
        st.info("Upload your tabplan and click 'Parse Tabplan' to continue.")
        st.stop()

    # Load data once for generation
    if not data_file_tabplan or not os.path.exists(data_file_tabplan):
        st.error(f"Data file not found: {data_file_tabplan}")
        st.stop()
    data_df_for_run = load_data(data_file_tabplan)

    # Build dynamic UI tabs per tabplan question
    tab_labels = [f"{i+1}. {item['qid']}" for i, item in enumerate(tab_items)]
    tabs = st.tabs(tab_labels)

    # Collector for “Export All” (Excel with one sheet per question)
    export_sheets: dict[str, pd.DataFrame] = {}

    for (item, t) in zip(tab_items, tabs):
        with t:
            qid = item["qid"]
            qlabel = item["label"]
            st.subheader(f"{qid}")
            st.caption(qlabel if qlabel else "")

            qcfg = find_question_config(qid, qlabel)
            if qcfg is None:
                st.warning("No matching saved question config found. Add/import (or use Auto-create) for this question first.")
                with st.expander("Tabplan row"):
                    st.json(item)
                continue

            with st.expander("Question config", expanded=False):
                st.json(qcfg)

            if st.button(f"📊 Generate table for {qid}", key=f"gen_{qid}"):
                try:
                    with st.spinner("Generating table..."):
                        month, year = get_now_month_year()
                        df_out, out_file = generate_tables(
                            questions=[qcfg],
                            data=data_df_for_run,
                            study_name=DEFAULT_STUDY_NAME,
                            client_name=DEFAULT_CLIENT_NAME,
                            banner_config=load_banner_config(),
                            month=month,
                            year=year
                        )
                        if df_out is None:
                            st.warning("No output produced.")
                        else:
                            st.dataframe(df_out.head(50), use_container_width=True)
                            export_sheets[qid] = df_out.copy()
                            with open(out_file, "rb") as f:
                                st.download_button(
                                    label=f"⬇️ Download CSV for {qid}",
                                    data=f,
                                    file_name=out_file,
                                    mime="text/csv"
                                )
                except Exception as e:
                    st.error(f"Failed to generate: {e}")

    if export_sheets:
        today = datetime.today().strftime("%Y%m%d")
        xlsx_name = f"Tabplan_Output_{today}.xlsx"
        try:
            with pd.ExcelWriter(xlsx_name, engine="openpyxl") as writer:
                for sheet_name, df_sheet in export_sheets.items():
                    safe = str(sheet_name)[:31] or "Sheet"
                    df_sheet.to_excel(writer, sheet_name=safe, index=False)
            with open(xlsx_name, "rb") as f:
                st.download_button(
                    "⬇️ Download ALL (Excel, 1 sheet per question)",
                    f.read(),
                    file_name=xlsx_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Export-all failed: {e}")



# ----------------------
# Current Questions Display (always available)
# ----------------------
with st.expander("📋 View Current Questions (JSON)"):
    st.json(st.session_state.questions)
