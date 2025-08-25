# table_service.py
import os
from datetime import datetime
import pandas as pd

from tab_generator import TabGenerator

def _build_metadata_rows(client_name, study_name, month, year, table_number, question_text, base_text, columns_like):
    metadata = pd.DataFrame(
        [
            [""],
            ["#page"],
            [client_name],
            [study_name],
            [f"{month} {year}"],
            [f"Table {table_number}"],
            [question_text],
            [f"Base: {base_text}"]
        ],
        columns=["Label"]
    ).reindex(columns=columns_like, fill_value="")
    return metadata

def generate_tables(questions, data, study_name, client_name, banner_config, month, year):
    """
    Loops questions, builds each table via TabGenerator, and returns
    (final_df, file_name). If nothing generated, returns (None, None).
    """
    results = []

    for i, question in enumerate(questions, start=1):
        tg = TabGenerator(
            client_name=client_name,
            study_name=study_name,
            month=month,
            year=year,
            first_data=data,
            question_var=question["question_var"],
            question_text=question["question_text"],
            base_text=question["base_text"],
            display_structure=question["display_structure"],
            question_type=question["question_type"],
            table_number=i,
            mean_var=question["mean_var"],
            filter_condition=question["base_filter"],
            show_sigma=question["show_sigma"]
        )

        cross_tab_df = tg.generate_crosstab(banner_config, tg.display_structure)

        banner_labels = [""] + [seg["label"] for seg in banner_config]
        banner_ids = [""] + [seg["id"] for seg in banner_config]

        metadata = _build_metadata_rows(
            client_name=client_name,
            study_name=study_name,
            month=month,
            year=year,
            table_number=i,
            question_text=question["question_text"],
            base_text=question["base_text"],
            columns_like=cross_tab_df.columns
        )

        full_table = pd.concat(
            [
                metadata,
                pd.DataFrame([[""] * len(cross_tab_df.columns)], columns=cross_tab_df.columns),
                pd.DataFrame([banner_labels], columns=cross_tab_df.columns),
                pd.DataFrame([banner_ids], columns=cross_tab_df.columns),
                cross_tab_df
            ],
            ignore_index=True
        )
        results.append(full_table)

    if not results:
        return None, None

    final_df = pd.concat(results, ignore_index=True)
    today = datetime.today().strftime('%m%d%Y')
    file_name = f"{study_name.replace(' ', '_')}_Output_Tables_{today}.csv"
    final_df.to_csv(file_name, index=False, header=False)
    # Also write a standard name if you want (optional)
    final_df.to_csv("tab_output.csv", index=False, header=False)

    return final_df, file_name
