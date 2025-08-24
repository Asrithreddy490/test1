# datamap_parser.py
import pandas as pd

def parse_datamap_to_json(datamap_file):
    """
    Parse a survey datamap Excel file and generate question configurations in JSON format.
    
    Args:
        datamap_file: Path to Excel file or file-like object
        
    Returns:
        List of question configurations in JSON-compatible format
    """
    # Read the Excel file
    df = pd.read_excel(datamap_file, sheet_name="Sheet1")

    # Drop empty rows
    df = df.dropna(subset=["Question ID"])

    questions = []
    question_counter = 1

    # Group by Question ID to handle multi-part questions
    grouped = df.groupby("Question ID")

    for question_id, group in grouped:
        # Skip system variables
        if question_id in [
            "responseid", "respid", "hDummyDP", "status",
            "interview_start", "interview_end", "lengthOfIntv"
        ]:
            continue

        first_row = group.iloc[0]
        question_type = str(first_row["Type"]).strip().lower()

        # ---------------- SINGLE ----------------
        if question_type == "single":
            display_structure = []
            for _, row in group.iterrows():
                if pd.notna(row["Answer Code"]):
                    display_structure.append([
                        "code",
                        str(row["Answer Label"]),
                        int(row["Answer Code"]) if str(row["Answer Code"]).isdigit() else row["Answer Code"]
                    ])

            questions.append({
                "id": question_counter,
                "question_var": question_id,
                "question_text": first_row["Question Label"] if pd.notna(first_row["Question Label"]) else question_id,
                "base_text": "Total Respondents",
                "display_structure": display_structure,
                "base_filter": None,
                "question_type": "single",
                "mean_var": None,
                "show_sigma": True
            })
            question_counter += 1

        # ---------------- MULTI ----------------
        # elif question_type == "multi":
        #     multi_vars = [f"{question_id}_{i+1}" for i in range(len(group))]

        #     display_structure = []
        #     for i, (_, row) in enumerate(group.iterrows()):
        #         display_structure.append([
        #             "code",
        #             row["Question Label"] if pd.notna(row["Question Label"]) else f"Option {i+1}",
        #             f"{question_id}_{i+1}"
        #         ])

        #     if len(multi_vars) > 1:
        #         display_structure.insert(0, [
        #             "net",
        #             f"Any {question_id} (NET)",
        #             multi_vars
        #         ])

        #     questions.append({
        #         "id": question_counter,
        #         "question_var": multi_vars,
        #         "question_text": first_row["Question Label"] if pd.notna(first_row["Question Label"]) else question_id,
        #         "base_text": "Total Respondents",
        #         "display_structure": display_structure,
        #         "base_filter": None,
        #         "question_type": "multi",
        #         "mean_var": None,
        #         "show_sigma": True
        #     })
        #     question_counter += 1

        # # ---------------- NUMERIC ----------------
        # elif question_type == "numeric":
        #     # open numeric questions don’t usually have codes
        #     questions.append({
        #         "id": question_counter,
        #         "question_var": question_id,
        #         "question_text": first_row["Question Label"] if pd.notna(first_row["Question Label"]) else question_id,
        #         "base_text": "Total Respondents",
        #         "display_structure": [],   # no coded structure
        #         "base_filter": None,
        #         "question_type": "open_numeric",
        #         "mean_var": question_id,   # important: for mean/median calc
        #         "show_sigma": True
        #     })
        #     question_counter += 1

        # # ---------------- GRID ----------------
        # elif question_type == "grid":
        #     # Treat grid as single-response
        #     display_structure = []
        #     for _, row in group.iterrows():
        #         if pd.notna(row["Answer Code"]):
        #             display_structure.append([
        #                 "code",
        #                 str(row["Answer Label"]),
        #                 int(row["Answer Code"]) if str(row["Answer Code"]).isdigit() else row["Answer Code"]
        #             ])

        #     questions.append({
        #         "id": question_counter,
        #         "question_var": question_id,
        #         "question_text": first_row["Question Label"] if pd.notna(first_row["Question Label"]) else question_id,
        #         "base_text": "Total Respondents",
        #         "display_structure": display_structure,
        #         "base_filter": None,
        #         "question_type": "single",  # treat as single
        #         "mean_var": None,
        #         "show_sigma": True
        #     })
        #     question_counter += 1

    return questions
