# backend/create_html_report.py
import pandas as pd
import os
import glob
from collections import defaultdict
import json
import traceback
import backend.config as config
import re

# Import both the renderer and the FAQ generator
from backend.report_template import render_dashboard_html, get_dynamic_faq

CSV_FILENAME = config.OUTPUT_MERGED_FILE
HTML_OUTPUT_FILENAME = config.HTML_OUTPUT_FILENAME
AGREEMENT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
NOTE_FILE_1 = config.NOTES_FILE
NOTE_FILE_2 = config.OUTPUT_DETAILED_AGREEMENT_FILE_PATH
TRANSCRIPTS_DIRECTORY = config.TRANSCRIPTS_DIRECTORY


def load_csv_data(filename):
    if not os.path.exists(filename):
        return None
    try:
        return pd.read_csv(filename, encoding="utf-8-sig", on_bad_lines="skip")
    except Exception as e:
        print(f"Error reading '{filename}': {e}")
        return None


def load_text_report(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception:
            return None
    return ""


def load_codebook_definitions():
    # Looks for the first valid file in the definitions directory
    directory = config.CODEBOOK_DEFINITIONS_DIRECTORY
    if not os.path.exists(directory):
        return [], []

    # prioritizing excel then csv
    extensions = ["*.xlsx", "*.xls", "*.csv", "*.txt"]
    found_files = []
    for ext in extensions:
        found_files.extend(glob.glob(os.path.join(directory, ext)))

    if not found_files:
        return [], []

    # Pick the first file found
    file_path = found_files[0]
    print(f"Loading codebook definition from: {file_path}")

    try:
        df = None
        if file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, on_bad_lines="skip", encoding="utf-8-sig")

        if df is not None:
            # Handle merged cells in Excel files by forward filling category columns
            # Convert columns to string to avoid 'int' object has no attribute 'lower' error
            df.columns = df.columns.astype(str)

            fill_candidates = [
                c for c in df.columns if "cat" in c.lower() or "group" in c.lower()
            ]
            if fill_candidates:
                df[fill_candidates] = df[fill_candidates].ffill()

            df = df.fillna("")
            # Convert columns to list
            columns = list(df.columns)
            # Convert data to dict records
            data = df.to_dict(orient="records")
            return columns, data
    except Exception as e:
        print(f"Error reading codebook definition: {e}")
        return [], []

    return [], []


def load_transcript_files():
    directory = TRANSCRIPTS_DIRECTORY
    if not os.path.exists(directory):
        print(f"Transcript directory not found: '{directory}'")
        return [], {}

    # Recursively find all .txt files
    txt_files = glob.glob(os.path.join(directory, "**", "*.txt"), recursive=True)

    # Get the relative names for display/keys
    file_names = [os.path.relpath(f, directory) for f in txt_files]

    # Create a dictionary to hold the content
    transcript_contents = {}
    for full_path, relative_name in zip(txt_files, file_names):
        try:
            # Read the file content
            with open(full_path, "r", encoding="utf-8-sig") as f:
                transcript_contents[relative_name] = f.read()
        except Exception as e:
            print(f"Error reading transcript file '{full_path}': {e}")
            transcript_contents[relative_name] = f"Error loading file content: {e}"

    # Sort names for consistent display
    file_names.sort()

    return file_names, transcript_contents


def process_irr_data(irr_filename):
    df = load_csv_data(irr_filename)

    # Return 6 items even on failure
    if df is None or df.empty:
        return {}, [], {}, {}, [], []

    # Added "TN" to exclusion list
    base_cols = [
        "id",
        "p",
        "text",
        "code",
        "memo",
        "all_agree",
        "TN",
        "is_true_negative",
        "ignored",
    ]
    coders = [
        c
        for c in df.columns
        if c not in base_cols and not c.endswith("_agreement") and not c.startswith("_")
    ]

    agreement_map = {}
    hierarchical_data = defaultdict(lambda: defaultdict(list))
    cat_counts = defaultdict(int)
    code_counts_by_cat = defaultdict(lambda: defaultdict(int))

    # Initialize new trackers for additional charts
    code_counts_overall = defaultdict(int)
    disagreement_counts_by_code = defaultdict(int)
    coder_counts = defaultdict(int)
    cat_agreement_stats = defaultdict(lambda: {"agree": 0, "disagree": 0})

    records = df.fillna("").to_dict(orient="records")

    # PRE-CALCULATION: Map (Participant + Text) to set of active coders
    # This helps us distinguish between "Silence" (Omission) and "Alternative Code" (Conflict)
    segment_coder_map = defaultdict(set)
    for row in records:
        p_val = str(row.get("p", "")).strip()
        t_val = str(row.get("text", "")).strip()
        key = (p_val, t_val)

        # Which coders marked this specific row (code)?
        for c in coders:
            if int(row.get(c, 0)) == 1:
                segment_coder_map[key].add(c)
    # Tracker for the Unified Master List (Consolidated View)
    # Maps (p, text) -> { sort_id, segment_data, priority_score }
    master_list_map = {}
    # Load Method from Config
    method = getattr(config, "STRIJBOS_METHOD", "METHOD_C")

    # Helper to prioritize statuses: AGREE > DISAGREE > IGNORED > TN
    def get_status_priority(status):
        if status == "AGREE":
            return 4
        if status == "DISAGREE":
            return 3
        if status.startswith("IGNORED"):
            return 2
        if status == "TRUE_NEGATIVE":
            return 1
        return 0

    for row in records:
        p = str(row.get("p", "")).strip()
        text = str(row.get("text", "")).strip()
        code_full = str(row.get("code", "Uncategorized")).strip()
        memo = str(row.get("memo", "")).strip()

        # Raw Data Points
        all_agree_raw = int(row.get("all_agree", 0))
        # Support both new TN column and legacy column if present
        is_tn = int(row.get("TN", 0)) == 1 or int(row.get("is_true_negative", 0)) == 1

        # Calculate Active Coders for this row (how many marked this specific code)
        active_coder_count = sum(int(row.get(c, 0)) for c in coders)
        total_coders = len(coders)

        # Update Reporting Status based on Method
        reporting_status = "UNKNOWN"
        include_in_charts = False
        is_chart_agreement = False

        # Case 1: True Negatives (Explicit flag OR all zeros)
        if is_tn or active_coder_count == 0:
            if method == "METHOD_C":
                reporting_status = "TRUE_NEGATIVE"
                include_in_charts = True
                is_chart_agreement = True
            else:
                # Method A & B ignore True Negatives
                reporting_status = "IGNORED_TN"
                include_in_charts = False

        # Case 2: Mutual Coding (Everyone coded this SPECIFIC code)
        elif active_coder_count == total_coders:
            # If everyone coded, check if they agreed on the code name
            if all_agree_raw == 1:
                reporting_status = "AGREE"
                include_in_charts = True
                is_chart_agreement = True
            elif all_agree_raw == 2:
                reporting_status = "PARTIAL_AGREE"
                include_in_charts = True
                is_chart_agreement = True
            else:
                reporting_status = "DISAGREE"
                include_in_charts = True
                is_chart_agreement = False

        # Case 3: Omission / Partial (Some coded, some didn't) - e.g., 1 vs 0
        else:
            # 1. First, check if this is a "Weighted Agreement" (Mode 2).
            # If yes, we MUST count it, regardless of the Method selected below.
            # This effectively overrides Method A's desire to delete "1 vs 0" rows.
            if all_agree_raw == 2:
                reporting_status = "PARTIAL_AGREE"
                include_in_charts = True
                is_chart_agreement = True
            # 2. If it's NOT a Weighted Agreement, apply the standard Method logic.
            elif method == "METHOD_A":
                # Method A (Intersection):
                # Normally filters out omissions. BUT, we must check if it's a CONFLICT.
                # A Conflict is when Coder A coded 'X' and Coder B coded 'Y' on same text.
                # In that case, Coder B is 'silent' on 'X', but active on the TEXT.

                # Check if ALL coders have coded THIS TEXT (regardless of which code they used)
                who_coded_this_text = segment_coder_map.get((p, text), set())

                # If the set of coders who touched this text covers ALL coders,
                # then it's a mutual UNIT, even if they disagreed on the LABEL.
                is_mutual_unit = len(who_coded_this_text) == total_coders

                if is_mutual_unit:
                    # It is a Conflict (Disagreement)
                    reporting_status = "DISAGREE"
                    include_in_charts = True
                    is_chart_agreement = False
                else:
                    # It is a pure Omission (one coder missed the text entirely)
                    reporting_status = "IGNORED_OMISSION"
                    include_in_charts = False

            else:
                # Method B & C (Union/Full): Treat omission as disagreement
                reporting_status = "DISAGREE"
                include_in_charts = True
                is_chart_agreement = False

        # Save status to row for HTML/JS
        row["reporting_status"] = reporting_status
        row["TN"] = 1 if is_tn else 0

        # Parsing Category
        if ":" in code_full:
            parts = code_full.split(":", 1)
            cat = parts[0].strip()
            code_name = parts[1].strip()
        else:
            cat = "General"
            code_name = code_full

        # Update Charts ONLY if included in this Method
        if include_in_charts:
            cat_counts[cat] += 1
            code_counts_by_cat[cat][code_name] += 1
            code_counts_overall[code_full] += 1

            if is_chart_agreement:
                cat_agreement_stats[cat]["agree"] += 1
            else:
                disagreement_counts_by_code[code_full] += 1
                cat_agreement_stats[cat]["disagree"] += 1

        active_coders = [c for c in coders if row.get(c) == 1]
        coder_label = ", ".join(active_coders) if active_coders else "None"

        # Track coder volume (Raw volume always tracks, regardless of method agreement)
        for c in active_coders:
            coder_counts[c] += 1

        segment = {
            "id": row.get("id"),
            "participant": p,
            "text": text,
            "memo": memo,
            "coders": active_coders,
            "all_agree": all_agree_raw,
            "reporting_status": reporting_status,
            "TN": 1 if is_tn else 0,  # Ensure TN is passed
        }

        hierarchical_data[cat][code_name].append(segment)

        # Consolidated Master List Logic
        # We want the Master List to show EVERY segment, with its 'Best' status.
        # If a segment appears as 'AGREE' in Code A, and 'TN' in the injected negatives,
        # we want the Master List to show the 'AGREE' version.

        # Create a unique key for the segment
        seg_key = (p, text)
        priority = get_status_priority(reporting_status)

        # If this segment is new, or if this version has a higher priority (e.g. AGREE vs TN), store it.
        if (
            seg_key not in master_list_map
            or priority > master_list_map[seg_key]["priority"]
        ):
            master_list_map[seg_key] = {
                "sort_id": row.get("id"),
                "segment": segment,
                "priority": priority,
            }

        key = f"{p}|{text}"

        # Tooltip logic
        if reporting_status == "AGREE":
            tooltip = "Full Agreement"
        elif reporting_status == "TRUE_NEGATIVE":
            tooltip = "True Negative (Master List)"
        elif reporting_status.startswith("IGNORED"):
            tooltip = "Ignored by Method (Omission/TN)"
        else:
            tooltip = f"Disagreement. Marked by: {coder_label}"

        agreement_map[key] = {"status": reporting_status, "tooltip": tooltip}

    # Inject Consolidated Master List
    # Convert the map back to a sorted list
    consolidated_segments = sorted(master_list_map.values(), key=lambda x: x["sort_id"])
    final_master_list = [item["segment"] for item in consolidated_segments]

    # Force this list into a specific "Master List" category
    # This ensures the browser shows one list with EVERYTHING (Coded + Uncoded).
    # We use "Master List" as category and "All Segments" as code name.
    hierarchical_data["Master List"] = {}  # Reset/Ensure category exists
    hierarchical_data["Master List"]["All Segments"] = final_master_list

    # Process aggregates for Top N charts
    def get_top_n(source_dict, n=10):
        sorted_items = sorted(source_dict.items(), key=lambda x: x[1], reverse=True)
        return {
            "labels": [k for k, v in sorted_items[:n]],
            "data": [v for k, v in sorted_items[:n]],
        }

    # Calculate Agreement Percentage per Code (Based on filtered charts)
    code_stats = {}
    for code, total in code_counts_overall.items():
        disagreements = disagreement_counts_by_code.get(code, 0)
        agreements = total - disagreements
        pct = (agreements / total) * 100 if total > 0 else 0
        code_stats[code] = f"{pct:.1f}%"

    # Prepare Category Agreement Data (Stacked)
    sorted_cats = sorted(cat_agreement_stats.keys())
    cat_agree_data = [cat_agreement_stats[c]["agree"] for c in sorted_cats]
    cat_disagree_data = [cat_agreement_stats[c]["disagree"] for c in sorted_cats]

    analysis_data = {
        "categoryDistribution": {
            "labels": list(cat_counts.keys()),
            "data": list(cat_counts.values()),
        },
        "codeBreakdown": {
            k: {"labels": list(v.keys()), "data": list(v.values())}
            for k, v in code_counts_by_cat.items()
        },
        "codeStats": code_stats,
        "topCodes": get_top_n(code_counts_overall, 15),
        "topDisagreements": get_top_n(disagreement_counts_by_code, 15),
        "coderVolume": get_top_n(coder_counts, 20),
        "categoryAgreement": {
            "labels": sorted_cats,
            "agree": cat_agree_data,
            "disagree": cat_disagree_data,
        },
    }

    participant_list = sorted(list(set(r.get("p", "") for r in records)))

    return (
        agreement_map,
        records,
        hierarchical_data,
        analysis_data,
        participant_list,
        coders,
    )


def generate_interactive_html(
    agreement_map,
    irr_records,
    hierarchical_data,
    analysis_data,
    output_filename,
    p_list,
    c_list,
    transcript_files,
    transcript_contents,
):
    notes1_txt = load_text_report(NOTE_FILE_1)
    notes2_txt = load_text_report(NOTE_FILE_2)

    # Parse Raw Counts from first_merge_notes.txt
    raw_counts = {}
    if notes1_txt:
        matches = re.findall(r"-\s+([^\s:]+)\s+:\s+(\d+)\s+segments", notes1_txt)
        for name, count in matches:
            raw_counts[name] = int(count)

    # Inject Raw Counts into analysis_data for the chart
    if "coderVolume" in analysis_data and "labels" in analysis_data["coderVolume"]:
        labels = analysis_data["coderVolume"]["labels"]
        # Map the raw counts to the same order as the labels
        raw_data_aligned = [raw_counts.get(label, 0) for label in labels]
        analysis_data["coderVolume"]["rawData"] = raw_data_aligned

    # Get Dynamic FAQ Data by passing the config module
    faq_data = get_dynamic_faq(config)

    cb_cols, cb_rows = load_codebook_definitions()

    # Get method name for display
    method_name = getattr(config, "STRIJBOS_METHOD", "Unknown Method")

    # Prepare the replacement context
    context = {
        "method_name": method_name,
        "faq_json": json.dumps(faq_data, ensure_ascii=False),
        "hierarchical_json": json.dumps(hierarchical_data, ensure_ascii=False),
        "analysis_json": json.dumps(analysis_data, ensure_ascii=False),
        "irr_records_json": json.dumps(irr_records, ensure_ascii=False),
        "coders_json": json.dumps(c_list),
        "participants_json": json.dumps(p_list),
        "reports_json": json.dumps(
            {"notes1": notes1_txt, "notes2": notes2_txt}, ensure_ascii=False
        ),
        "codebook_columns_json": json.dumps(cb_cols, ensure_ascii=False),
        "codebook_rows_json": json.dumps(cb_rows, ensure_ascii=False),
        "transcript_files_json": json.dumps(transcript_files),
        "transcript_contents_json": json.dumps(transcript_contents, ensure_ascii=False),
    }

    # Generate the complete HTML string
    html_content = render_dashboard_html(context)

    try:
        # Ensure output directory exists before writing
        if os.path.dirname(output_filename):
            os.makedirs(os.path.dirname(output_filename), exist_ok=True)

        with open(output_filename, "w", encoding="utf-8-sig") as f:
            f.write(html_content)
        print(f"Report generated: '{output_filename}'")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()


def main():
    print("--- Starting Report Generation ---")
    agreement_map, irr_records, hierarchical_data, analysis_data, p_list, c_list = (
        process_irr_data(AGREEMENT_CSV_FILE)
    )
    if not irr_records:
        print("No records found in merged IRR file. Please check input.")
        return

    # Load file names and contents
    transcript_files, transcript_contents = load_transcript_files()

    generate_interactive_html(
        agreement_map,
        irr_records,
        hierarchical_data,
        analysis_data,
        HTML_OUTPUT_FILENAME,
        p_list,
        c_list,
        transcript_files,
        transcript_contents,
    )
    print("--- Finished ---")


if __name__ == "__main__":
    main()
