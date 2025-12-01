import pandas as pd
import html
import os
import glob
from collections import defaultdict
import json
import traceback
import config
import re

CSV_FILENAME = "input/codebook.csv"
HTML_OUTPUT_FILENAME = "output/codes.html"
AGREEMENT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
NOTE_FILE_1 = "output/first_merge_notes.txt"
NOTE_FILE_2 = "output/agreements.txt"
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
            # This targets columns like 'category-id', 'category-name', etc.
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

    # Added "memo" to exclusion list
    base_cols = ["id", "p", "text", "code", "memo", "all_agree"]
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

    for row in records:
        p = str(row.get("p", "")).strip()
        text = str(row.get("text", "")).strip()
        code_full = str(row.get("code", "Uncategorized")).strip()
        # Capture the memo
        memo = str(row.get("memo", "")).strip()
        all_agree = int(row.get("all_agree", 0))

        if ":" in code_full:
            parts = code_full.split(":", 1)
            cat = parts[0].strip()
            code_name = parts[1].strip()
        else:
            cat = "General"
            code_name = code_full

        cat_counts[cat] += 1
        code_counts_by_cat[cat][code_name] += 1

        # Update new trackers
        code_counts_overall[code_full] += 1
        if all_agree == 0:
            disagreement_counts_by_code[code_full] += 1
            cat_agreement_stats[cat]["disagree"] += 1
        else:
            cat_agreement_stats[cat]["agree"] += 1

        active_coders = [c for c in coders if row.get(c) == 1]
        coder_label = ", ".join(active_coders) if active_coders else "Unknown"

        # Track coder volume
        for c in active_coders:
            coder_counts[c] += 1

        segment = {
            "id": row.get("id"),
            "participant": p,
            "text": text,
            "memo": memo,
            "coders": active_coders,
            "all_agree": all_agree,
        }

        hierarchical_data[cat][code_name].append(segment)

        key = f"{p}|{text}"
        status = "AGREE" if all_agree == 1 else "DISAGREE"
        tooltip = (
            "Full Agreements"
            if all_agree == 1
            else f"Disagreement. Marked by: {coder_label}"
        )
        agreement_map[key] = {"status": status, "tooltip": tooltip}

    # Process aggregates for Top N charts
    def get_top_n(source_dict, n=10):
        sorted_items = sorted(source_dict.items(), key=lambda x: x[1], reverse=True)
        return {
            "labels": [k for k, v in sorted_items[:n]],
            "data": [v for k, v in sorted_items[:n]],
        }

    # Calculate Agreement Percentage per Code
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
        # Pass the calculated code statistics here
        "codeStats": code_stats,
        # New Chart Data
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


def get_html_template():
    return r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IRR Analysis Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/choices.js/public/assets/styles/choices.min.css"/>
    <script src="https://cdn.jsdelivr.net/npm/choices.js/public/assets/scripts/choices.min.js"></script>
    <script src="https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js"></script>
    <style>
        /* Default to Dark Theme */
        :root { 
            --bg-color: #121212; 
            --text-color: #e0e0e0; 
            --nav-bg: #1f1f1f; 
            --border: #333333; 
            --primary: #0d6efd; 
            --success: #198754; 
            --danger: #dc3545; 
            --card-bg: #1e1e1e; 
            --hover-bg: #2c2c2c;
        }
        
        /* Light Theme Override */
        [data-theme="light"] {
            --bg-color: #f8f9fa; 
            --text-color: #212529; 
            --nav-bg: #ffffff; 
            --border: #dee2e6; 
            --card-bg: #ffffff;
            --hover-bg: #e9ecef;
        }

        body { font-family: 'Segoe UI', sans-serif; background: var(--bg-color); color: var(--text-color); margin: 0; padding-bottom: 50px; transition: background 0.3s, color 0.3s; }
        
        .navbar { display: flex; justify-content: space-between; background: var(--nav-bg); padding: 10px 20px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 1000; align-items: center; }
        .nav-tabs { display: flex; gap: 10px; }
        .nav-btn { padding: 8px 16px; border: none; background: transparent; cursor: pointer; font-weight: 600; opacity: 0.7; color: var(--text-color); }
        .nav-btn.active { background: var(--primary); color: white; opacity: 1; border-radius: 4px; }
        .nav-btn:hover:not(.active) { background: var(--hover-bg); }

        .theme-toggle { background: transparent; border: 1px solid var(--border); color: var(--text-color); padding: 5px 10px; border-radius: 4px; cursor: pointer; }
        
        .nav-select { background: var(--nav-bg); color: var(--text-color); border: 1px solid var(--border); padding: 6px; border-radius: 4px; margin-left: 10px; cursor: pointer; }

        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .view-section { display: none; }
        .view-section.active { display: block; }

        .category-block { margin-top: 10px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 5px; overflow: hidden; }
        .category-header { padding: 10px; background: var(--hover-bg); cursor: pointer; font-weight: bold; display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); }
        
        .code-list { display: none; padding-top: 5px; }
        .code-block { margin: 5px 15px; border-left: 2px solid var(--border); padding-left: 10px; }
        .code-header { 
            cursor: pointer; 
            padding: 10px 15px; 
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-left: 4px solid var(--primary); /* Accent color on the left */
            border-radius: 4px; 
            font-weight: 600; 
            color: var(--text-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .code-header:hover { 
            background: var(--hover-bg); 
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            border-color: var(--primary);
        }

        .segment-list { display: none; margin-left: 15px; border-left: 2px solid var(--border); }
        
        .segment { background: var(--card-bg); padding: 10px; margin-bottom: 8px; border-bottom: 1px solid var(--border); font-size: 0.95em; }
        .status-icon { float: right; font-size: 1.2em; }
        .status-agree { color: var(--success); }
        .status-disagree { color: var(--danger); }
        
        .coder-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; color: #fff; font-weight: bold; }
        .meta-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; background: #444; color: #ddd; }

        .irr-table { width: 100%; border-collapse: collapse; font-size: 0.9em; background: var(--card-bg); color: var(--text-color); }
        .irr-table th, .irr-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
        .clickable-text { cursor: pointer; transition: color 0.2s; }
        .clickable-text:hover { color: var(--primary); text-decoration: underline; }
        .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        /* Update .chart-card and add .chart-container */
        .chart-card { 
            background: var(--card-bg); 
            padding: 15px; 
            border-radius: 8px; 
            border: 1px solid var(--border); 
            height: 400px; 
            display: flex; 
            flex-direction: column; 
        }
        .chart-container {
            flex: 1;
            position: relative;
            min-height: 0;
            width: 100%;
        }

        .controls { margin-bottom: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .sticky-toolbar {
            position: -webkit-sticky; /* Safari */
            position: sticky;
            top: 57px; /* Matches approximate height of the navbar */
            z-index: 990; /* Below navbar (1000) but above content */
            background-color: var(--bg-color); /* Opaque background so text doesn't show through */
            padding: 10px 0; /* Vertical padding for aesthetics */
            border-bottom: 1px solid var(--border);
            margin-top: -10px; /* Adjust for parent padding */
        }
        .report-pre { white-space: pre-wrap; font-family: monospace; background: var(--card-bg); color: var(--text-color); padding: 15px; border: 1px solid var(--border); border-radius: 5px; max-height: 600px; overflow-y: auto; }
        .sub-nav-btn { padding: 6px 12px; background: var(--card-bg); border: 1px solid var(--border); color: var(--text-color); cursor: pointer; margin-right: 5px; border-radius: 4px; }
        .sub-nav-btn.active { background: var(--primary); color: white; border-color: var(--primary); }

        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(2px); }
        .modal-content { 
            background-color: var(--card-bg); 
            margin: 2vh auto; 
            padding: 0; 
            border: 1px solid var(--border); 
            width: 96%; 
            height: 94vh; 
            border-radius: 8px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.5); 
            display: flex; 
            flex-direction: column; 
        }
        .modal-header { padding: 15px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: var(--nav-bg); border-radius: 8px 8px 0 0; }
        .modal-body-container {
            display: flex;
            flex: 1;
            overflow: hidden; /* Contain scrolls inside children */
        }
        .modal-sidebar {
            width: 280px;
            background: var(--nav-bg);
            border-right: 1px solid var(--border);
            overflow-y: auto;
            padding: 15px;
            flex-shrink: 0;
        }
        .modal-text-area {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.8;
            font-size: 1.1em;
            color: var(--text-color);
            position: relative;
        }
        .modal-footer { padding: 15px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 10px; background: var(--nav-bg); border-radius: 0 0 8px 8px; }
        .close-modal { color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close-modal:hover { color: var(--text-color); }
        .highlight-span {
            background-color: rgba(255, 255, 0, 0.15);
            border-bottom: 2px solid; 
            cursor: pointer;
            transition: background 0.2s;
            border-radius: 2px;
        }
        .highlight-span:hover {
            background-color: rgba(255, 255, 0, 0.4);
        }
        .highlight-active {
            background-color: rgba(255, 255, 0, 0.6) !important;
            box-shadow: 0 0 10px rgba(255,255,0,0.5);
        }

        .sidebar-code-item {
            padding: 8px;
            border-bottom: 1px solid var(--border);
            font-size: 0.9em;
            cursor: pointer;
            border-left: 4px solid transparent;
        }
        .sidebar-code-item:hover {
            background: var(--hover-bg);
        }
        .sidebar-code-item.active {
            background: var(--hover-bg);
            border-left-color: var(--primary);
        }
        
        .coder-dot {
            height: 10px; width: 10px; 
            border-radius: 50%; 
            display: inline-block; 
            margin-right: 5px;
        }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; transition: background 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { opacity: 0.9; }
        .btn-secondary { background: var(--border); color: var(--text-color); }
        .btn-secondary:hover { background: #555; }
        .memo-block {
            margin-top: 4px;
            font-size: 0.85em;
            color: var(--text-color);
            opacity: 0.8;
            background: rgba(255, 255, 255, 0.05);
            padding: 4px 8px;
            border-left: 2px solid var(--primary);
            border-radius: 0 4px 4px 0;
            display: inline-block;
        }
        
        /* Codebook Definition Table Styles */
        .def-table-container { overflow-x: auto; margin-top: 15px; }
        .def-table { width: 100%; border-collapse: collapse; font-size: 0.9em; background: var(--card-bg); color: var(--text-color); }
        
        /* Updated table cell styles for better width and text wrapping */
        .def-table th, .def-table td { padding: 8px; border: 1px solid var(--border); vertical-align: top; }
        .def-table th { background: var(--nav-bg); cursor: pointer; white-space: nowrap; position: sticky; top: 0; z-index: 10; }
        .def-table th:hover { background: var(--hover-bg); }
        
        /* Specific column sizing classes */
        .col-narrow { width: 80px; min-width: 80px; white-space: nowrap; }
        .col-wide { min-width: 300px; white-space: normal; }
        .col-normal { min-width: 150px; }

        /* Switch from input to textarea styles for wrapping */
        .def-table textarea { 
            background: transparent; 
            border: none; 
            color: inherit; 
            width: 100%; 
            font-family: inherit; 
            font-size: inherit; 
            resize: vertical; 
            min-height: 60px;
            line-height: 1.4;
        }
        .def-table textarea:focus { outline: 1px solid var(--primary); background: rgba(255,255,255,0.05); }
        
        .action-cell { width: 50px; min-width: 50px !important; text-align: center; }
        .btn-sm { padding: 2px 8px; font-size: 0.8em; margin: 0 2px; }
        .btn-add { background: var(--success); color: white; margin-bottom: 10px; }
        .btn-danger { background: var(--danger); color: white; border: none; cursor: pointer; border-radius: 3px; }
        
        /* Separate Save Buttons */
        .btn-save-mem { background: var(--primary); color: white; margin-right: 10px; }
        .btn-download { background: #444; color: white; border: 1px solid var(--border); margin-left: 5px; }
        .btn-download:hover { background: #555; }

        /* Disagreement Report Styles */
        .report-textarea {
            width: 100%;
            height: 600px;
            background: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border);
            font-family: 'Segoe UI', monospace; /* Mixed font for readability */
            padding: 15px;
            font-size: 1em;
            resize: vertical;
            white-space: pre-wrap;
            overflow-y: auto;
        }
        
        /* Enhanced Simple Modal Styles */
        .modal-metadata {
            background: rgba(255, 255, 255, 0.05);
            padding: 10px 15px;
            border-bottom: 1px solid var(--border);
            font-size: 0.85em;
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .meta-item { display: flex; flex-direction: column; }
        .meta-label { font-weight: bold; color: var(--primary); opacity: 0.8; font-size: 0.9em; }
        .meta-value { font-family: monospace; }
        
        .modal-nav-btn {
            min-width: 100px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        .modal-nav-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
            background: var(--card-bg);
            border-color: var(--border);
        }

        /* Transcript Grid Styles */
        .transcript-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-top: 15px; }
        .transcript-card { 
            background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; 
            cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; display: flex; align-items: center; gap: 15px;
        }
        .transcript-card:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); border-color: var(--primary); }
        .t-icon { font-size: 1.8em; color: var(--primary); opacity: 0.8; }
        .t-info { flex: 1; overflow: hidden; }
        .t-name { font-weight: 600; font-size: 1em; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .t-meta { font-size: 0.8em; opacity: 0.6; }
        /* FAQ Styles */
        .faq-container { max-width: 900px; margin: 0 auto; }
        .faq-item { 
            background: var(--card-bg); 
            border: 1px solid var(--border); 
            margin-bottom: 10px; 
            border-radius: 6px; 
            overflow: hidden; 
            transition: border-color 0.2s;
        }
        .faq-item:hover { border-color: var(--primary); }
        .faq-question {
            padding: 15px 20px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.02);
        }
        .faq-question:after {
            content: '+';
            font-size: 1.2em;
            font-weight: bold;
            color: var(--primary);
        }
        .faq-item.open .faq-question:after { content: '-'; }
        .faq-item.open .faq-question { border-bottom: 1px solid var(--border); background: var(--hover-bg); }
        
        .faq-answer {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            padding: 0 20px;
            color: var(--text-color);
            opacity: 0.9;
            line-height: 1.6;
        }
        .faq-item.open .faq-answer {
            padding: 20px;
            max-height: 1000px; /* Arbitrary large height for transition */
            transition: max-height 0.5s ease-in;
        }
        .faq-search-container {
            margin-bottom: 30px;
            text-align: center;
        }
        #faq-search {
            width: 100%;
            max-width: 600px;
            padding: 12px 20px;
            border-radius: 25px;
            border: 1px solid var(--border);
            background: var(--card-bg);
            color: var(--text-color);
            font-size: 1.1em;
            transition: box-shadow 0.3s;
        }
        #faq-search:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(13, 110, 253, 0.2);
        }
    </style>
</head>
<body>

<nav class="navbar">
    <div style="font-weight: bold; display:flex; align-items:center; gap:15px;">
        <span>IRR Dashboard</span>
        <button class="theme-toggle" onclick="toggleTheme()" id="theme-btn">☀ Light Mode</button>
    </div>
    <div>
        <select id="participant-filter" class="nav-select" onchange="onParticipantSelect(this.value)">
            <option value="">Show All Participants</option>
        </select>
        <select id="coder-filter" class="nav-select" onchange="onCoderSelect(this.value)">
            <option value="">Show All Coders</option>
        </select>
    </div>
    <div class="nav-tabs">
        <button class="nav-btn active" onclick="switchTab('browser')" id="btn-browser">Browser</button>
        <button class="nav-btn" onclick="switchTab('analysis')" id="btn-analysis">Charts</button>
        <button class="nav-btn" onclick="switchTab('data')" id="btn-data">Analysis Details</button>
        <button class="nav-btn" onclick="switchTab('codebook')" id="btn-codebook" style="display:none;">Codebook definition</button>
        <button class="nav-btn" onclick="switchTab('transcripts')" id="btn-transcripts">Transcripts</button>
        <button class="nav-btn" onclick="switchTab('faq')" id="btn-faq">FAQ</button>
    </div>
</nav>

<div class="container">
    <div id="view-browser" class="view-section active">
        <div class="controls sticky-toolbar">
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
            <textarea id="search-box" placeholder="Filter text or search category:code... Use ';' to search multiple terms (e.g. 'code-a; code-b')" onkeyup="filterBrowser()" style="padding:5px; width:900px; height:36px; vertical-align:middle; resize:vertical; font-family:inherit;"></textarea>
            <button onclick="resetBrowserFilter()" style="font-size:0.8em; cursor:pointer;">Reset Filters</button>
        </div>
        <div id="browser-root"></div>
    </div>

    <div id="view-faq" class="view-section">
        <div class="faq-container">
            <h2 style="text-align: center; margin-bottom: 10px;">Research Protocol & Methodology FAQ</h2>
            <p style="text-align: center; opacity: 0.7; margin-bottom: 25px;">
                Common questions regarding code processing, merging logic, and statistical interpretation.
            </p>
            
            <div class="faq-search-container">
                <input type="text" id="faq-search" placeholder="Search questions (e.g., 'omissions', 'merged', 'colors')..." onkeyup="filterFAQ()">
            </div>

            <div id="faq-list">
                </div>
        </div>
    </div>

    <div id="view-analysis" class="view-section">
         <div class="charts-grid">
            <div class="chart-card">
                <h4>Category Distribution (Click to filter)</h4>
                <div class="chart-container">
                    <canvas id="chart-cat"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div style="display:flex; justify-content:space-between">
                    <h4>Code Breakdown</h4>
                    <select id="cat-select" onchange="updateCodeChart()"></select>
                </div>
                <div class="chart-container">
                    <canvas id="chart-code"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <h4>Top 15 Codes by Frequency</h4>
                <div class="chart-container">
                    <canvas id="chart-top-codes"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h4>Top 15 Codes by Disagreement Count</h4>
                <div class="chart-container">
                    <canvas id="chart-top-disagreements"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h4>Coder Activity Volume (Segments Coded)</h4>
                <div class="chart-container">
                    <canvas id="chart-coder-vol"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h4>Agreement vs. Disagreement by Category</h4>
                <div class="chart-container">
                    <canvas id="chart-cat-agree"></canvas>
                </div>
            </div>
        </div>
    </div>

    <div id="view-data" class="view-section">
        <div class="controls" style="border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 20px;">
            <strong>View: </strong>
            <button class="sub-nav-btn active" onclick="switchSubTab('table', this)">Data Table</button>
            <button class="sub-nav-btn" onclick="switchSubTab('notes1', this)">Merge Notes</button>
            <button class="sub-nav-btn" onclick="switchSubTab('notes2', this)">Agreement Stats</button>
            <button class="sub-nav-btn" onclick="switchSubTab('disagreements', this)">Disagreement Report</button>
        </div>

        <div id="sub-view-disagreements" class="sub-view" style="display:none;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div>
                    <h3 style="margin:0 0 5px 0">Disagreement Report <span id="disagreement-count" style="font-size:0.8em; opacity:0.8; font-weight:normal"></span></h3>
                    <p style="margin:0; font-size: 0.9em; opacity: 0.7;">
                        Note: Text segments displayed here are the result of merging overlapped coding. They may appear longer than original individual selections to preserve context.
                    </p>
                </div>
                <button class="btn btn-primary" onclick="copyDisagreementReport()">Copy Report</button>
            </div>
            <textarea id="content-disagreements" class="report-textarea" readonly></textarea>
        </div>

        <div id="sub-view-table" class="sub-view">
             <div class="controls" style="display:flex; align-items:center;">
                <button onclick="renderTable('all')">All Rows</button>
                <button onclick="renderTable('disagree')">Disagreements Only</button>
                <button onclick="renderTable('agree')">Agreements Only</button>
                <span id="table-row-count" style="margin-left: 15px; font-weight: bold; color: var(--primary);"></span>
                <button onclick="downloadTableCSV()" style="margin-left:auto;" class="btn btn-primary">Download CSV</button>
            </div>
            <div style="overflow-x:auto;">
                <table class="irr-table">
                    <thead><tr><th>#</th><th>ID</th><th>P</th><th>Text</th><th>Code</th><th>Coders</th><th>Status</th></tr></thead>
                    <tbody id="table-body"></tbody>
                </table>
            </div>
        </div>

        <div id="sub-view-notes1" class="sub-view" style="display:none;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h3 style="margin:0">First Merge Notes (Log)</h3>
                <button class="btn btn-secondary" onclick="copyElementText('content-notes1', this)">Copy Report</button>
            </div>
            <div id="content-notes1" class="report-pre"></div>
        </div>

        <div id="sub-view-notes2" class="sub-view" style="display:none;">
             <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h3 style="margin:0">Agreement Statistics Report</h3>
                <button class="btn btn-secondary" onclick="copyElementText('content-notes2', this)">Copy Report</button>
            </div>
            <div id="content-notes2" class="report-pre"></div>
        </div>
    </div>

    <div id="view-codebook" class="view-section">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
            <div>
                <button class="btn btn-add" onclick="addCodebookRow()">+ Add New Row</button>
                <input type="text" id="codebook-search" placeholder="Search definition..." onkeyup="renderCodebookTable()" 
                       style="padding:6px; border-radius:4px; border:1px solid var(--border); background: var(--card-bg); color:var(--text-color); margin-left:10px; width: 300px;">
            </div>
            <div>
                <button class="btn btn-save-mem" onclick="saveCurrentEdit()" id="btn-save-edit">Save current edit</button>
                <span style="border-left: 1px solid var(--border); margin: 0 10px; height: 20px; display: inline-block; vertical-align: middle;"></span>
                <button class="btn btn-download" onclick="exportCodebookCSV()">Download CSV</button>
                <button class="btn btn-download" onclick="exportCodebookXLSX()">Download Excel</button>
            </div>
        </div>
        <p style="font-size:0.9em; opacity:0.7;">Note: Click 'Save current edit' to confirm changes in memory before switching tabs. Use Download buttons to export files.</p>
        <div id="codebook-table-root" class="def-table-container"></div>
    </div>
    <div id="view-transcripts" class="view-section">
        <h3 style="margin-top: 0;">Available Transcripts</h3>
        <p>Click on a file card to load its content. Files are loaded dynamically from the <code>transcripts/</code> folder.</p>
        
        <div style="margin-bottom: 15px;">
             <input type="text" id="transcript-search" placeholder="Search transcripts..." onkeyup="renderTranscriptList()" 
               style="padding: 8px; width: 100%; max-width: 400px; border: 1px solid var(--border); border-radius: 4px; background: var(--card-bg); color: var(--text-color);">
        </div>

        <div id="transcript-grid" class="transcript-grid">
            </div>
        
        <ul id="transcript-list" style="display:none;"></ul>

        <button class="btn btn-primary" style="margin-top: 25px;" onclick="loadAllTranscripts()">Load All in New Window (Warning: May be slow)</button>
    </div>
    <div id="text-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 style="margin:0" id="modal-title">Full Text View</h3>
                <span class="close-modal" onclick="closeTextModal()">&times;</span>
            </div>
            
            <div class="modal-body-container">
                <div class="modal-sidebar" id="modal-sidebar-content">
                    <div style="opacity:0.6; font-style:italic;">No codes found.</div>
                </div>
                <div class="modal-text-area" id="modal-text-content">
                    </div>
            </div>

            <div class="modal-footer">
                <span style="margin-right: auto; font-size: 0.9em; opacity: 0.7;">* Highlighting is based on text matching. Repeated phrases may all be highlighted.</span>
                <button class="btn btn-secondary" onclick="closeTextModal()">Close</button>
                <button class="btn btn-primary" onclick="copyModalText()" id="copy-btn">Copy Raw Text</button>
            </div>
        </div>
    </div>
    
    <div id="simple-text-modal" class="modal">
        <div class="modal-content" style="height: 70vh; margin: 5vh auto; width: 70%;">
            <div class="modal-header">
                <h3 style="margin:0">Segment Detail</h3>
                <span class="close-modal" onclick="closeSimpleTextModal()">&times;</span>
            </div>
            
            <div id="simple-modal-meta" class="modal-metadata"></div>
            
            <div style="padding: 20px; overflow-y: auto; flex: 1; white-space: pre-wrap; font-size: 1.1em; line-height: 1.6;" id="simple-modal-content">
            </div>
            
            <div class="modal-footer" style="justify-content: space-between;">
                <div style="display:flex; gap: 10px;">
                    <button class="btn btn-secondary modal-nav-btn" id="btn-prev-seg" onclick="navigateSimpleModal(-1)">
                        &larr; Previous <span id="prev-id-display" style="font-size: 0.8em; opacity: 0.7; margin-left: 4px;"></span>
                    </button>
                    <button class="btn btn-secondary modal-nav-btn" id="btn-next-seg" onclick="navigateSimpleModal(1)">
                        Next &rarr; <span id="next-id-display" style="font-size: 0.8em; opacity: 0.7; margin-left: 4px;"></span>
                    </button>
                </div>
                <div style="display:flex; gap: 10px;">
                    <button class="btn btn-secondary" onclick="copySimpleModalText(this)">Copy Text</button>
                    <button class="btn btn-secondary" onclick="closeSimpleTextModal()">Close</button>
                </div>
            </div>
        </div>
    </div>
</div>


<script>
    const DATA = {
        hierarchical: {hierarchical_json},
        analysis: {analysis_json},
        irrRecords: {irr_records_json},
        coders: {coders_json},
        participants: {participants_json},
        textReports: {reports_json},
        codebook: {
            columns: {codebook_columns_json},
            rows: {codebook_rows_json}
        },
        transcriptFiles: {transcript_files_json},
        // Embedded content for file:// compatibility
        transcriptContents: {transcript_contents_json},
        faqData: {faq_json}
    };
    
    let chartInstances = {};
    // Global to track the currently active dataset for the detailed code chart
    let activeCodeBreakdown = DATA.analysis.codeBreakdown;

    document.addEventListener('DOMContentLoaded', () => {
        renderBrowser();
        renderReports(); 
        renderTable('all'); 
        renderFAQ(); // Initial render of FAQ
        populateCoderDropdown();
        populateParticipantDropdown();
        
        // Check if codebook exists and initialize
        if (DATA.codebook.columns && DATA.codebook.columns.length > 0) {
            document.getElementById('btn-codebook').style.display = 'block';
            renderCodebookTable();
        }

        // Restore active tab from localStorage
        const savedTab = localStorage.getItem('activeTab') || 'browser';
        switchTab(savedTab);
    });

    function toggleTheme() {
        const html = document.documentElement;
        const btn = document.getElementById('theme-btn');
        if (html.getAttribute('data-theme') === 'light') {
            html.removeAttribute('data-theme');
            btn.innerText = '☀ Light Mode';
        } else {
            html.setAttribute('data-theme', 'light');
            btn.innerText = '☾ Dark Mode';
        }
    }

    function switchTab(tabId) {
        // Save state
        localStorage.setItem('activeTab', tabId);

        document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
        
        const targetView = document.getElementById('view-' + tabId);
        if(targetView) targetView.classList.add('active');
        
        const targetBtn = document.getElementById('btn-' + tabId);
        if(targetBtn) targetBtn.classList.add('active');

        if(tabId === 'analysis') {
            // Slight delay to ensure DOM is visible before Chart.js renders
            setTimeout(initCharts, 50);
        }
    }

    function switchSubTab(viewId, btnElement) {
        document.querySelectorAll('.sub-view').forEach(el => el.style.display = 'none');
        document.getElementById('sub-view-' + viewId).style.display = 'block';
        document.querySelectorAll('.sub-nav-btn').forEach(el => el.classList.remove('active'));
        btnElement.classList.add('active');
        
        // Render report on demand
        if (viewId === 'disagreements') {
            renderDisagreementReport();
        }
    }

    function getCoderColor(name) {
        // Use the index of the coder in the global list to ensure distinct separation
        // If name is not in list (e.g. unknown), use a backup hash
        let index = DATA.coders.indexOf(name);
        
        if (index === -1) {
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = name.charCodeAt(i) + ((hash << 5) - hash);
            }
            index = Math.abs(hash);
        }
        
        // Use Golden Angle (approx 137.5 degrees) to distribute colors evenly around the wheel
        // This prevents adjacent items from having similar colors
        const hue = (index * 137.508) % 360;
        
        // Use consistent saturation and lightness for readability
        const saturation = '75%'; 
        const lightness = '45%'; 
        
        return `hsl(${hue}, ${saturation}, ${lightness})`;
    }

    function populateCoderDropdown() {
        const select = document.getElementById('coder-filter');
        DATA.coders.sort().forEach(coder => {
            const opt = document.createElement('option');
            opt.value = coder;
            opt.innerText = coder;
            select.appendChild(opt);
        });
    }

    function populateParticipantDropdown() {
        const select = document.getElementById('participant-filter');
        DATA.participants.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.innerText = p;
            select.appendChild(opt);
        });
    }

    function onCoderSelect(val) {
        // Pass false to prevent switching tabs
        filterBrowser(null, 'text', false);
        updateCharts();
    }

    function onParticipantSelect(val) {
        filterBrowser(null, 'text', false);
        updateCharts();
    }

    function updateCharts() {
        const coderName = document.getElementById('coder-filter').value;
        const participantName = document.getElementById('participant-filter').value;

        // 1. Filter Records based on both Dropdowns
        const records = DATA.irrRecords.filter(r => {
            const matchCoder = !coderName || r[coderName] === 1;
            const matchParticipant = !participantName || r.p === participantName;
            return matchCoder && matchParticipant;
        });

        // 2. Aggregate Data
        const catCounts = {};
        const codeCountsByCat = {};
        const codeCountsOverall = {};
        const disagreeCounts = {};
        const coderVol = {};
        const catAgreeStats = {};

        records.forEach(r => {
            // Parse Category and Code
            let cat = "General";
            let codeName = r.code;
            if (r.code.includes(':')) {
                const parts = r.code.split(':', 2);
                cat = parts[0].trim();
                codeName = parts[1].trim();
            }

            // Category Distribution
            catCounts[cat] = (catCounts[cat] || 0) + 1;

            // Code Breakdown (Structure: { Category: { Code: Count } })
            if (!codeCountsByCat[cat]) codeCountsByCat[cat] = {};
            codeCountsByCat[cat][codeName] = (codeCountsByCat[cat][codeName] || 0) + 1;

            // Top Codes
            codeCountsOverall[r.code] = (codeCountsOverall[r.code] || 0) + 1;

            // Disagreements
            if (r.all_agree === 0) {
                disagreeCounts[r.code] = (disagreeCounts[r.code] || 0) + 1;
            }

            // Coder Volume (Who else coded these segments?)
            DATA.coders.forEach(c => {
                if (r[c] === 1) coderVol[c] = (coderVol[c] || 0) + 1;
            });

            // Category Agreement
            if (!catAgreeStats[cat]) catAgreeStats[cat] = { agree: 0, disagree: 0 };
            if (r.all_agree === 1) catAgreeStats[cat].agree++;
            else catAgreeStats[cat].disagree++;
        });

        // 3. Update Global Code Breakdown Data
        activeCodeBreakdown = {};
        Object.keys(codeCountsByCat).forEach(cat => {
            activeCodeBreakdown[cat] = {
                labels: Object.keys(codeCountsByCat[cat]),
                data: Object.values(codeCountsByCat[cat])
            };
        });

        // 4. Update Chart Instances
        updateChartData('chart-cat', Object.keys(catCounts), Object.values(catCounts));

        const topCodes = getTopN(codeCountsOverall, 15);
        updateChartData('chart-top-codes', topCodes.labels, topCodes.data);

        const topDis = getTopN(disagreeCounts, 15);
        updateChartData('chart-top-disagreements', topDis.labels, topDis.data);

        //const topVol = getTopN(coderVol, 20);
        //updateChartData('chart-coder-vol', topVol.labels, topVol.data);

        const sortedCats = Object.keys(catAgreeStats).sort();
        const agreeData = sortedCats.map(c => catAgreeStats[c].agree);
        const disagreeData = sortedCats.map(c => catAgreeStats[c].disagree);
        
        const chartAgree = chartInstances['chart-cat-agree']; 
        if (chartAgree) {
            chartAgree.data.labels = sortedCats;
            chartAgree.data.datasets[0].data = agreeData;
            chartAgree.data.datasets[1].data = disagreeData;
            chartAgree.update();
        }

        const catSelect = document.getElementById('cat-select');
        const currentVal = catSelect.value;
        catSelect.innerHTML = '';
        Object.keys(activeCodeBreakdown).sort().forEach(c => {
            const opt = document.createElement('option');
            opt.value = c; opt.innerText = c; catSelect.appendChild(opt);
        });
        if (currentVal && activeCodeBreakdown[currentVal]) {
            catSelect.value = currentVal;
        }
        updateCodeChart();
    }

    function getTopN(sourceObj, n) {
        const sorted = Object.entries(sourceObj).sort((a, b) => b[1] - a[1]).slice(0, n);
        return {
            labels: sorted.map(x => x[0]),
            data: sorted.map(x => x[1])
        };
    }

    function updateChartData(chartKey, labels, data) {
        let chart = chartInstances[chartKey];
        if (!chart) {
            chart = Chart.getChart(chartKey);
            if(chart) chartInstances[chartKey] = chart;
        }
        if (chart) {
            chart.data.labels = labels;
            chart.data.datasets[0].data = data;
            chart.update();
        }
    }

    function renderBrowser() {
        const root = document.getElementById('browser-root');
        root.innerHTML = '';
        
        Object.keys(DATA.hierarchical).sort().forEach(cat => {
            const catBlock = document.createElement('div');
            catBlock.className = 'category-block';
            catBlock.setAttribute('data-cat', cat);

            const header = document.createElement('div');
            header.className = 'category-header';
            
            let totalSegs = 0;
            let totalAgree = 0;
            const codesInCat = Object.keys(DATA.hierarchical[cat]);
            const codeCount = codesInCat.length;

            Object.values(DATA.hierarchical[cat]).forEach(arr => {
                totalSegs += arr.length;
                arr.forEach(seg => {
                    if(seg.all_agree === 1) totalAgree++;
                });
            });
            
            const totalDisagree = totalSegs - totalAgree;
            const catPct = totalSegs > 0 ? ((totalAgree / totalSegs) * 100).toFixed(1) : "0.0";
            let catPctColor = 'var(--text-color)';
            if (parseFloat(catPct) >= 80) catPctColor = 'var(--success)';
            else if (parseFloat(catPct) < 60) catPctColor = 'var(--primary)';
            else catPctColor = '#fd7e14';

            header.innerHTML = `
                <span style="flex: 1;">${cat}</span> 
                <span style="opacity: 0.8; font-weight: normal;">(${codeCount} codes)</span>
                <span style="flex: 1; display: flex; justify-content: flex-end; align-items: center; gap: 10px; font-family: monospace; font-size: 0.9em; font-weight: normal;">
                    <span style="color: ${catPctColor}; font-weight: bold;" title="Category Agreement Percentage">${catPct}%</span>
                    <span style="opacity: 0.3">|</span>
                    <span style="color: var(--success)" title="Total Agreements">Agr: ${totalAgree}</span>
                    <span style="color: var(--danger)" title="Total Disagreements">Dis: ${totalDisagree}</span>
                </span>
            `;
            header.onclick = () => toggleDisplay(header.nextElementSibling);
            catBlock.appendChild(header);

            const codeList = document.createElement('div');
            codeList.className = 'code-list';

            Object.keys(DATA.hierarchical[cat]).sort().forEach(code => {
                const codeBlock = document.createElement('div');
                codeBlock.className = 'code-block';
                codeBlock.setAttribute('data-code', code);
                
                const segments = DATA.hierarchical[cat][code];
                const total = segments.length;
                const agreeCount = segments.filter(s => s.all_agree === 1).length;
                const disagreeCount = total - agreeCount;
                const pct = total > 0 ? ((agreeCount / total) * 100).toFixed(1) : "0.0";
                let pctColor = 'var(--text-color)';
                if (parseFloat(pct) >= 80) pctColor = 'var(--success)';
                else if (parseFloat(pct) < 60) pctColor = 'var(--primary)';
                else pctColor = '#fd7e14'; 

                const cHeader = document.createElement('div');
                cHeader.className = 'code-header';
                
                cHeader.innerHTML = `
                    <span style="flex: 1; text-align: left; overflow: hidden; text-overflow: ellipsis; margin-right: 10px;">
                        ${code}
                    </span>
                    <span style="opacity: 0.8; font-weight: normal;" title="Total Segments">
                        (${total} segments)
                    </span>
                    <span style="flex: 1; display: flex; justify-content: flex-end; align-items: center; gap: 10px; font-family: monospace; font-size: 0.9em;">
                        <span style="color: ${pctColor}; font-weight: bold;" title="Agreement Percentage">${pct}%</span>
                        <span style="opacity: 0.3">|</span>
                        <span style="color: var(--success)" title="Agreements (Consensus)">Agr: ${agreeCount}</span>
                        <span style="color: var(--danger)" title="Disagreements">Dis: ${disagreeCount}</span>
                    </span>
                `;
                
                cHeader.onclick = () => toggleDisplay(cHeader.nextElementSibling);
                codeBlock.appendChild(cHeader);

                const segList = document.createElement('div');
                segList.className = 'segment-list';

                DATA.hierarchical[cat][code].forEach(seg => {
                    const div = document.createElement('div');
                    div.className = 'segment';
                    div.setAttribute('data-coders', seg.coders.join(','));
                    div.setAttribute('data-participant', seg.participant);

                    const statusHtml = seg.all_agree 
                        ? '<span class="status-icon status-agree" title="Consensus">&#10003;</span>' 
                        : '<span class="status-icon status-disagree" title="Disagreement">&#10007;</span>';
                    
                    let badges = '';
                    seg.coders.forEach(c => {
                        badges += `<span class="coder-tag" style="background-color:${getCoderColor(c)}">${c}</span>`;
                    });

                    const memoHtml = seg.memo ? `<div class="memo-block">📝 <strong>Memo:</strong> ${escapeHtml(seg.memo)}</div>` : '';

                    div.innerHTML = `
                        <div style="margin-bottom:4px; color:#666;">
                            <span class="meta-tag">${seg.participant}</span>
                            ${badges}
                            ${statusHtml}
                        </div>
                        <div style="font-style:italic;">"${escapeHtml(seg.text)}"</div>
                        ${memoHtml}
                    `;
                    segList.appendChild(div);
                });
                codeBlock.appendChild(segList);
                codeList.appendChild(codeBlock);
            });
            catBlock.appendChild(codeList);
            root.appendChild(catBlock);
        });
    }

    function toggleDisplay(el) { el.style.display = (el.style.display === 'block') ? 'none' : 'block'; }
    
    function expandAll() { 
        const visibleCats = document.querySelectorAll('.category-block[style*="display: block"], .category-block:not([style*="display"])');
        visibleCats.forEach(block => {
             block.querySelector('.code-list').style.display = 'block';
             block.querySelectorAll('.segment-list').forEach(s => s.style.display = 'block');
        });
    }

    function collapseAll() { 
        document.querySelectorAll('.code-list, .segment-list').forEach(e => e.style.display = 'none'); 
    }

    function resetBrowserFilter() {
        document.getElementById('search-box').value = "";
        document.getElementById('coder-filter').value = ""; 
        document.getElementById('participant-filter').value = ""; 
        filterBrowser(null, "text", false);
    }

    function filterBrowser(filterVal = null, type = 'text', switchView = true) {
        if (type === 'text' && filterVal === null) {
             filterVal = document.getElementById('search-box').value;
        }
        
        if (type !== 'text') {
            document.getElementById('search-box').value = "";
            document.getElementById('coder-filter').value = "";
            document.getElementById('participant-filter').value = "";
            if (switchView) switchTab('browser');
        }

        const rawTerms = (filterVal || "").toLowerCase().split(';');
        const searchTerms = rawTerms.map(t => t.trim()).filter(t => t.length > 0);
        const isSearchEmpty = searchTerms.length === 0;

        const selectedCoder = document.getElementById('coder-filter').value;
        const selectedParticipant = document.getElementById('participant-filter').value;
        const catBlocks = document.querySelectorAll('.category-block');
        
        catBlocks.forEach(block => {
            const catName = block.getAttribute('data-cat');
            // 1. Category Filter (From Charts)
            if (type === 'category') {
                if (catName === filterVal) {
                    block.style.display = 'block';
                    block.querySelector('.code-list').style.display = 'block';
                    block.querySelectorAll('.code-block').forEach(cb => {
                        cb.style.display = 'block';
                        cb.querySelector('.segment-list').style.display = 'block';
                        cb.querySelectorAll('.segment').forEach(s => s.style.display = 'block');
                    });
                    block.scrollIntoView({behavior: "smooth"});
                } else {
                    block.style.display = 'none';
                }
                return;
            }

            // 2. Code Filter (From Charts)
            if (type === 'code') {
                let targetCode = filterVal;
                let targetCat = null;
                if (filterVal.includes(':')) {
                    const parts = filterVal.split(':', 2);
                    targetCat = parts[0].trim();
                    targetCode = parts[1].trim();
                }
                if (targetCat && catName !== targetCat) {
                    block.style.display = 'none';
                    return;
                }

                const codeBlocks = block.querySelectorAll('.code-block');
                let hasMatch = false;
                codeBlocks.forEach(cb => {
                    if (cb.getAttribute('data-code') === targetCode) {
                        cb.style.display = 'block';
                        cb.querySelector('.segment-list').style.display = 'block';
                        cb.querySelectorAll('.segment').forEach(s => s.style.display = 'block');
                        hasMatch = true;
                    } else {
                        cb.style.display = 'none';
                    }
                });

                if (hasMatch) {
                    block.style.display = 'block';
                    block.querySelector('.code-list').style.display = 'block';
                    if(targetCat) block.scrollIntoView({behavior: "smooth"});
                } else {
                    block.style.display = 'none';
                }
                return;
            }

            // 3. Combined Search with Multi-term support
            const catMatchesAnyTerm = isSearchEmpty || searchTerms.some(term => catName.toLowerCase().includes(term));
            const kebabCat = catName.toLowerCase().trim().replace(/\s+/g, '-');
            let categoryHasVisibleContent = false;
            const codeBlocks = block.querySelectorAll('.code-block');
            
            codeBlocks.forEach(cb => {
                const codeName = cb.getAttribute('data-code');
                const kebabCode = codeName.toLowerCase().trim().replace(/\s+/g, '-');
                const kebabFull = `${kebabCat}:${kebabCode}`;

                const codeMatchesAnyTerm = searchTerms.some(term => 
                    codeName.toLowerCase().includes(term) || term === kebabFull
                );
                
                let codeHasVisibleContent = false;
                const segments = cb.querySelectorAll('.segment');

                segments.forEach(seg => {
                    const segCoders = (seg.getAttribute('data-coders') || "").split(',');
                    const segParticipant = seg.getAttribute('data-participant');
                    const coderMatches = !selectedCoder || segCoders.includes(selectedCoder);
                    const participantMatches = !selectedParticipant || segParticipant === selectedParticipant;
                    const segTextRaw = seg.innerText.toLowerCase();
                    const textMatchesAnyTerm = isSearchEmpty || searchTerms.some(term => segTextRaw.includes(term));
                    const contentMatch = textMatchesAnyTerm || codeMatchesAnyTerm || catMatchesAnyTerm;

                    if (coderMatches && participantMatches && contentMatch) {
                        seg.style.display = 'block';
                        codeHasVisibleContent = true;
                    } else {
                        seg.style.display = 'none';
                    }
                });

                if (codeHasVisibleContent) {
                    cb.style.display = 'block';
                    cb.querySelector('.segment-list').style.display = 'block';
                    categoryHasVisibleContent = true;
                } else {
                    cb.style.display = 'none';
                }
            });

            if (categoryHasVisibleContent) {
                block.style.display = 'block';
                block.querySelector('.code-list').style.display = 'block';
            } else {
                block.style.display = 'none';
            }
        });
    }

    function initCharts() {
        if (chartInstances['chart-cat']) return; 
        
        const ctxCat = document.getElementById('chart-cat');
        if(ctxCat) {
            chartInstances['chart-cat'] = new Chart(ctxCat, {
                type: 'bar',
                data: {
                    labels: DATA.analysis.categoryDistribution.labels,
                    datasets: [{ label: 'Segments', data: DATA.analysis.categoryDistribution.data, backgroundColor: '#0d6efd' }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const idx = elements[0].index;
                            filterBrowser(DATA.analysis.categoryDistribution.labels[idx], 'category');
                        }
                    }
                }
            });
        }
        
        const catSelect = document.getElementById('cat-select');
        if (catSelect) {
            catSelect.innerHTML = '';
            Object.keys(DATA.analysis.codeBreakdown).sort().forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c; catSelect.appendChild(opt);
            });
            updateCodeChart();
        }

        const ctxTopCodes = document.getElementById('chart-top-codes');
        if(ctxTopCodes) {
             chartInstances['chart-top-codes'] = new Chart(ctxTopCodes, { 
                type: 'bar',
                data: {
                    labels: DATA.analysis.topCodes.labels,
                    datasets: [{ label: 'Frequency', data: DATA.analysis.topCodes.data, backgroundColor: '#6610f2' }]
                },
                options: { 
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const idx = elements[0].index;
                            filterBrowser(DATA.analysis.topCodes.labels[idx], 'code');
                        }
                    }
                }
            });
        }

        const ctxTopDis = document.getElementById('chart-top-disagreements');
        if(ctxTopDis) {
            chartInstances['chart-top-disagreements'] = new Chart(ctxTopDis, { 
                type: 'bar',
                data: {
                    labels: DATA.analysis.topDisagreements.labels,
                    datasets: [{ label: 'Disagreements', data: DATA.analysis.topDisagreements.data, backgroundColor: '#dc3545' }]
                },
                options: { 
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const idx = elements[0].index;
                            filterBrowser(DATA.analysis.topDisagreements.labels[idx], 'code');
                        }
                    }
                }
            });
        }

        const ctxCoder = document.getElementById('chart-coder-vol');
        if(ctxCoder) {
            // Prepare datasets dynamically
            const datasets = [];
            const rawData = DATA.analysis.coderVolume.rawData;
            
            // Only add Raw bar if we successfully parsed data
            if (rawData && rawData.some(x => x > 0)) {
                datasets.push({ 
                    label: 'Raw Input Events', 
                    data: rawData, 
                    backgroundColor: '#6c757d', // Grey
                    order: 2 
                });
            }
            
            // Always add Merged bar
            datasets.push({ 
                label: 'Merged Segments (Final)', 
                data: DATA.analysis.coderVolume.data, 
                backgroundColor: '#fd7e14', // Orange
                order: 1 
            });

            chartInstances['chart-coder-vol'] = new Chart(ctxCoder, { 
                type: 'bar',
                data: {
                    labels: DATA.analysis.coderVolume.labels,
                    datasets: datasets
                },
                options: { 
                    responsive: true, maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',  // Group bars by coder
                        intersect: false,
                    },
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const idx = elements[0].index;
                            const selectedCoder = DATA.analysis.coderVolume.labels[idx];
                            const drop = document.getElementById('coder-filter');
                            if(drop) drop.value = selectedCoder;
                            onCoderSelect(selectedCoder);
                        }
                    }
                }
            });
        }

        const ctxCatAgree = document.getElementById('chart-cat-agree');
        if(ctxCatAgree) {
            chartInstances['chart-cat-agree'] = new Chart(ctxCatAgree, { 
                type: 'bar',
                data: {
                    labels: DATA.analysis.categoryAgreement.labels,
                    datasets: [
                        { label: 'Agree', data: DATA.analysis.categoryAgreement.agree, backgroundColor: '#198754' },
                        { label: 'Disagree', data: DATA.analysis.categoryAgreement.disagree, backgroundColor: '#dc3545' }
                    ]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    scales: { x: { stacked: true }, y: { stacked: true } },
                    onClick: (e, elements) => {
                        if (elements.length > 0) {
                            const idx = elements[0].index;
                            filterBrowser(DATA.analysis.categoryAgreement.labels[idx], 'category');
                        }
                    }
                }
            });
        }
    }

    function updateCodeChart() {
        const cat = document.getElementById('cat-select').value;
        if(!cat) return;
        
        const data = activeCodeBreakdown[cat];
        if (!data) return; 

        const ctxCode = document.getElementById('chart-code');
        
        if(!ctxCode) return;
        if (chartInstances['code']) chartInstances['code'].destroy();
        
        chartInstances['code'] = new Chart(ctxCode, {
            type: 'bar',
            data: { labels: data.labels, datasets: [{ label: `Codes in ${cat}`, data: data.data, backgroundColor: '#198754' }] },
            options: { 
                responsive: true, maintainAspectRatio: false,
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        filterBrowser(data.labels[idx], 'code');
                    }
                }
            }
        });
    }

    function renderTable(filterType) {
        currentTableFilter = filterType;
        const body = document.getElementById('table-body');
        const countLabel = document.getElementById('table-row-count');
        body.innerHTML = '';
        
        let data = [...DATA.irrRecords];

        data.sort((a, b) => {
            const codeA = (a.code || "").toLowerCase();
            const codeB = (b.code || "").toLowerCase();
            if (codeA < codeB) return -1;
            if (codeA > codeB) return 1;
            return 0;
        });

        if (filterType === 'agree') data = data.filter(r => r.all_agree === 1);
        if (filterType === 'disagree') data = data.filter(r => r.all_agree === 0);
        
        // Update global filtered data for modal navigation
        currentTableData = data;

        // Calculate total coding events
        let totalEvents = 0;
        data.forEach(r => {
            DATA.coders.forEach(c => {
                if (r[c] === 1) totalEvents++;
            });
        });

        if(countLabel) countLabel.innerText = `Showing: ${data.length} rows (${totalEvents} coding events)`;
        
        const thead = document.querySelector('.irr-table thead tr');
        if(thead) thead.innerHTML = '<th>#</th><th>ID</th><th>P</th><th style="width: 50%">Text</th><th>Code (Agr %)</th><th>Coders</th><th>Status</th>';

        data.forEach((r, index) => {
            const tr = document.createElement('tr');
            const active = DATA.coders.filter(c => r[c] === 1).join(", ");
            const statusIcon = r.all_agree ? '<span class="status-agree">&#10003;</span>' : '<span class="status-disagree">&#10007;</span>';
            
            const codePct = DATA.analysis.codeStats[r.code] || "N/A";
            let pctColor = '#666';
            const pctVal = parseFloat(codePct);
            if (!isNaN(pctVal)) {
                if (pctVal >= 80) pctColor = 'var(--success)';
                else if (pctVal < 60) pctColor = 'var(--danger)';
                else pctColor = 'var(--primary)';
            }

            // Update onclick to pass the index (index relative to current filtered view)
            tr.innerHTML = `
                <td>${index + 1}</td>
                <td>${r.id}</td>
                <td>${r.p}</td>
                <td class="clickable-text" style="max-width: 40vw; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" 
                    title="Click to view full text" 
                    onclick="openSimpleTextModal(${index})">
                    ${escapeHtml(r.text)}
                </td>
                <td>
                    ${r.code}<br>
                    <span style="font-size:0.85em; color:${pctColor}; font-weight:bold;">${codePct}</span>
                </td>
                <td>${active}</td>
                <td style="text-align:center">${statusIcon}</td>
            `;
            body.appendChild(tr);
        });
    }

    // --- Disagreement Report Logic ---
    function renderDisagreementReport() {
        const reportArea = document.getElementById('content-disagreements');
        if (!reportArea) return;

        // 1. Group records by Text segment
        const grouped = {};
        let totalDisagreementCodes = 0;
        
        // Use original DATA.irrRecords to capture all potential disagreements, 
        // but we can filter if necessary. Usually report is for all.
        DATA.irrRecords.forEach(r => {
            // Count total disagreement codes (rows where all_agree is 0)
            if (r.all_agree === 0) {
                totalDisagreementCodes++;
            }

            // Only process if there's a disagreement associated with this text
            // We group by text because that's the visual unit for the user
            const key = r.text;
            if (!grouped[key]) {
                grouped[key] = { 
                    text: r.text, 
                    coderData: {},
                    hasDisagreement: false
                };
                DATA.coders.forEach(c => grouped[key].coderData[c] = []);
            }
            
            // Check provided agreement status from Python backend
            // This ensures the report matches the data table and chart logic
            if (r.all_agree === 0) {
                grouped[key].hasDisagreement = true;
            }
            
            DATA.coders.forEach(coder => {
                if (r[coder] === 1) {
                    // Only add the code to the report list if it is part of a disagreement.
                    // If r.all_agree is 1, both coders have this code, so we exclude it from the diff report.
                    if (r.all_agree === 0) {
                        grouped[key].coderData[coder].push(r.code);
                    }
                }
            });
        });

        // 2. Filter for segments where coders actually differ based on backend logic
        const disagreementList = [];
        
        Object.values(grouped).forEach(item => {
            // Only include if the backend flagged a disagreement
            if (item.hasDisagreement) {
                disagreementList.push(item);
            }
        });

        const countSpan = document.getElementById('disagreement-count');
        if (countSpan) {
            countSpan.innerText = `(${totalDisagreementCodes} codes)`;
        }

        // 3. Format Text
        let reportText = `#### Note: Only conflicting codes are listed (agreements are omitted). Segments may appear longer than the original selections due to fuzzy matching and merging to preserve context.\n\n`;

        disagreementList.forEach((item, idx) => {
            reportText += `${idx + 1}. "${item.text}"\n`;
            DATA.coders.forEach(coder => {
                const codes = item.coderData[coder];
                if (codes.length > 0) {
                    const codeStr = codes.map(c => `\`${c}\``).join(', ');
                    reportText += `${coder}: ${codeStr}\n`;
                } else {
                    // Optional: Show if they missed it entirely? 
                    // Per example format, if they have no codes, we might skip or show empty.
                    // The example implies showing assignments.
                    // Uncomment next line to show explicit misses:
                    // reportText += `${coder}: [No Code]\n`;
                }
            });
            reportText += `\n`;
        });

        if (disagreementList.length === 0) {
            reportText += "No disagreements found in current dataset.";
        }

        reportArea.value = reportText;
    }

    function copyDisagreementReport() {
        const copyText = document.getElementById("content-disagreements");
        copyText.select();
        copyText.setSelectionRange(0, 99999); /* For mobile devices */
        
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(copyText.value).then(() => {
                alert("Report copied to clipboard!");
            });
        } else {
            document.execCommand("copy");
            alert("Report copied to clipboard!");
        }
    }

    // Logic for the Simple Text Modal
    function openSimpleTextModal(index) {
        currentModalIndex = index;
        updateSimpleModalContent();
        document.getElementById('simple-text-modal').style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    function updateSimpleModalContent() {
        // Bounds checking
        if (currentModalIndex < 0 || currentModalIndex >= currentTableData.length) return;

        const r = currentTableData[currentModalIndex];
        const metaDiv = document.getElementById('simple-modal-meta');
        const contentDiv = document.getElementById('simple-modal-content');
        const prevBtn = document.getElementById('btn-prev-seg');
        const nextBtn = document.getElementById('btn-next-seg');
        const prevDisplay = document.getElementById('prev-id-display');
        const nextDisplay = document.getElementById('next-id-display');

        // Update Metadata
        const activeCoders = DATA.coders.filter(c => r[c] === 1).join(", ");
        metaDiv.innerHTML = `
            <div class="meta-item"><span class="meta-label">Row #</span><span class="meta-value">${currentModalIndex + 1}</span></div>
            <div class="meta-item"><span class="meta-label">ID</span><span class="meta-value">${r.id}</span></div>
            <div class="meta-item"><span class="meta-label">Participant</span><span class="meta-value">${r.p}</span></div>
            <div class="meta-item"><span class="meta-label">Code</span><span class="meta-value">${r.code}</span></div>
            <div class="meta-item"><span class="meta-label">Coders</span><span class="meta-value">${activeCoders || "None"}</span></div>
            <div class="meta-item"><span class="meta-label">Agreement</span><span class="meta-value">${r.all_agree ? "Yes" : "No"}</span></div>
        `;

        // Update Text
        const textarea = document.createElement('textarea');
        textarea.innerHTML = r.text;
        contentDiv.innerText = textarea.value;

        // Update Navigation Buttons
        if (currentModalIndex <= 0) {
            prevBtn.disabled = true;
            prevDisplay.innerText = "";
        } else {
            prevBtn.disabled = false;
            prevDisplay.innerText = `(#${currentModalIndex})`; // Display 1-based index of previous? Or 0-based? usually user wants current row num.
            // Let's show row number
            prevDisplay.innerText = `(Row ${currentModalIndex})`;
        }

        if (currentModalIndex >= currentTableData.length - 1) {
            nextBtn.disabled = true;
            nextDisplay.innerText = "";
        } else {
            nextBtn.disabled = false;
            nextDisplay.innerText = `(Row ${currentModalIndex + 2})`;
        }
    }

    function navigateSimpleModal(direction) {
        const newIndex = currentModalIndex + direction;
        if (newIndex >= 0 && newIndex < currentTableData.length) {
            currentModalIndex = newIndex;
            updateSimpleModalContent();
        }
    }

    function copySimpleModalText(btn) {
        const content = document.getElementById('simple-modal-content').innerText;
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(() => {
                const original = btn.innerText;
                btn.innerText = "Copied!";
                setTimeout(() => btn.innerText = original, 1500);
            });
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = content;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand("copy");
            document.body.removeChild(textArea);
            const original = btn.innerText;
            btn.innerText = "Copied!";
            setTimeout(() => btn.innerText = original, 1500);
        }
    }

    function closeSimpleTextModal() {
        document.getElementById('simple-text-modal').style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    // Helper to open the existing text modal with dynamic content
    function openTextModal() {
        const modal = document.getElementById('text-modal');
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    function loadAllTranscripts() {
        if (!confirm(`Are you sure you want to load ${DATA.transcriptFiles.length} transcripts? This will open a new window and could freeze your browser if files are large.`)) {
            return;
        }

        const newWindow = window.open('', '_blank');
        newWindow.document.write(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>All Transcripts</title>
                <style>body { font-family: monospace; white-space: pre-wrap; margin: 20px; }</style>
            </head>
            <body>
                <h1>Loading All Transcripts...</h1>
            </body>
            </html>
        `);

        // We can't fetch all content synchronously or it will block the UI thread.
        // For simplicity (and since this is a user-initiated action), we'll do sequential fetch/write.
        
        let allContent = '';
        let loadedCount = 0;
        const totalFiles = DATA.transcriptFiles.length;

        function fetchAndAppend(index) {
            if (index >= totalFiles) {
                // Final render
                newWindow.document.body.innerHTML = allContent;
                return;
            }

            const fileName = DATA.transcriptFiles[index];
            const filePath = `transcripts/${fileName}`;
            
            fetch(filePath)
                .then(response => {
                    if (!response.ok) throw new Error(`Status ${response.status}`);
                    return response.text();
                })
                .then(text => {
                    loadedCount++;
                    newWindow.document.body.innerHTML = `<h1>Loaded ${loadedCount}/${totalFiles} Transcripts...</h1>`;
                    allContent += `\n\n--- FILE: ${fileName} ---\n\n${text}`;
                    fetchAndAppend(index + 1);
                })
                .catch(error => {
                    loadedCount++;
                    newWindow.document.body.innerHTML = `<h1>Loaded ${loadedCount}/${totalFiles} Transcripts (Error on ${fileName})...</h1>`;
                    allContent += `\n\n--- ERROR Loading FILE: ${fileName} ---\n\n${error.message}\n`;
                    fetchAndAppend(index + 1);
                });
        }

        fetchAndAppend(0);
    }

    function closeTextModal() {
        document.getElementById('text-modal').style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    function copyModalText() {
        const content = document.getElementById('modal-text-content').innerText;
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(onCopySuccess);
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = content;
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                onCopySuccess();
            } catch (err) {
                console.error('Copy failed', err);
            }
            document.body.removeChild(textArea);
        }
    }

    function onCopySuccess() {
        const btn = document.getElementById('copy-btn');
        const original = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = original, 2000);
    }

    function downloadTableCSV() {
        let data = DATA.irrRecords;
        if (currentTableFilter === 'agree') data = data.filter(r => r.all_agree === 1);
        if (currentTableFilter === 'disagree') data = data.filter(r => r.all_agree === 0);

        const headers = ['ID', 'Participant', 'Text', 'Code', 'Coders', 'Agreement Status'];
        const csvRows = [headers.join(',')];

        data.forEach(r => {
            const active = DATA.coders.filter(c => r[c] === 1).join(", ");
            const status = r.all_agree ? "1" : "0";
            
            const row = [
                r.id,
                r.p,
                escapeCsv(r.text),
                escapeCsv(r.code),
                escapeCsv(active),
                status
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `irr_data_${currentTableFilter}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function escapeCsv(text) {
        if (text === null || text === undefined) return "";
        let str = String(text);
        if (str.includes('"') || str.includes(',') || str.includes('\n')) {
            str = '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }

    function copyElementText(elementId, btn) {
        const content = document.getElementById(elementId).innerText;
        const originalText = btn.innerText;
        
        const showSuccess = () => {
            btn.innerText = 'Copied!';
            setTimeout(() => btn.innerText = originalText, 2000);
        };

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(showSuccess);
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = content;
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                showSuccess();
            } catch (err) {
                console.error('Copy failed', err);
                alert("Copy failed. Please select text manually.");
            }
            document.body.removeChild(textArea);
        }
    }

    window.onclick = function(event) {
        const modal = document.getElementById('text-modal');
        const simpleModal = document.getElementById('simple-text-modal');
        if (event.target == modal) {
            closeTextModal();
        }
        if (event.target == simpleModal) {
            closeSimpleTextModal();
        }
    }

    function renderReports() {
        const notes1 = DATA.textReports.notes1 || "No merge notes available.";
        const notes2 = DATA.textReports.notes2 || "No agreement stats available.";
        
        const el1 = document.getElementById('content-notes1');
        if(el1) el1.innerText = notes1;

        const el2 = document.getElementById('content-notes2');
        if(el2) el2.innerText = notes2;
        // Also render the transcript file list
        renderTranscriptList();
    }
    
    function renderTranscriptList() {
        const grid = document.getElementById('transcript-grid');
        const input = document.getElementById('transcript-search');
        if (!grid) return;
        
        const searchTerm = (input ? input.value : '').toLowerCase();
        
        grid.innerHTML = '';
        if (DATA.transcriptFiles.length === 0) {
            grid.innerHTML = '<div style="opacity:0.7; padding:15px;">No transcript files found in <code>transcripts/</code> directory.</div>';
            return;
        }
        
        const filtered = DATA.transcriptFiles.filter(f => f.toLowerCase().includes(searchTerm));
        
        if (filtered.length === 0) {
             grid.innerHTML = '<div style="opacity:0.7; padding:15px;">No matching transcripts found.</div>';
             return;
        }

        filtered.forEach(fileName => {
            const card = document.createElement('div');
            card.className = 'transcript-card';
            card.onclick = () => loadTranscriptContent(fileName);
            
            // Derive some "fake" metadata or just file info for the card
            const ext = fileName.split('.').pop().toUpperCase();
            
            card.innerHTML = `
                <div class="t-icon">📄</div>
                <div class="t-info">
                    <div class="t-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                    <div class="t-meta">${ext} File</div>
                </div>
            `;
            grid.appendChild(card);
        });
    }

    function loadTranscriptContent(fileName) { // Updated parameter handling if called directly
        // Handle case where called from onclick element
        if (typeof fileName === 'object' && fileName.getAttribute) {
             fileName = fileName.getAttribute('data-filename');
        }
        
        const modal = document.getElementById('text-modal');
        const textArea = document.getElementById('modal-text-content');
        const sidebarArea = document.getElementById('modal-sidebar-content');
        const titleArea = document.getElementById('modal-title');

        titleArea.innerText = `Transcript: ${fileName}`;

        // Get Raw Text
        let rawText = DATA.transcriptContents[fileName];
        if (!rawText) {
            textArea.innerText = `ERROR: Could not find embedded content for file: ${fileName}`;
            openTextModal();
            return;
        }

        // Escape HTML in raw text manually first
        let processedHtml = rawText.replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;")
                              .replace(/"/g, "&quot;")
                              .replace(/'/g, "&#039;");

        // Identify Participant ID ... (existing code) ...
        const pId = fileName.replace(/\.[^/.]+$/, "").toLowerCase();
        
        const relevantRecords = DATA.irrRecords.filter(r => {
            const recP = (r.p || "").toLowerCase().trim();
            if (!recP) return false;
            const safeRecP = recP.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(^|_|-|\\b)${safeRecP}($|_|-|\\b)`);
            return regex.test(pId);
        });

        // 1. Build Sidebar Data
        const uniqueCodes = {};
        relevantRecords.forEach(r => {
            if (!uniqueCodes[r.code]) {
                uniqueCodes[r.code] = { count: 0, coders: new Set() };
            }
            uniqueCodes[r.code].count++;
            // Find which coders were active
            DATA.coders.forEach(c => {
                if (r[c] === 1) uniqueCodes[r.code].coders.add(c);
            });
        });

        // Render Sidebar
        sidebarArea.innerHTML = '<h4 style="margin-top:0; border-bottom:1px solid var(--border); padding-bottom:10px;">Codes Found</h4>';
        if (Object.keys(uniqueCodes).length === 0) {
            sidebarArea.innerHTML += '<div style="padding:10px; opacity:0.7">No codes linked to this participant ID.</div>';
        } else {
            Object.keys(uniqueCodes).sort().forEach(code => {
                const info = uniqueCodes[code];
                const div = document.createElement('div');
                div.className = 'sidebar-code-item';
                
                // Create dots for coders
                let coderDots = '';
                info.coders.forEach(c => {
                    coderDots += `<span class="coder-dot" style="background-color:${getCoderColor(c)}" title="${c}"></span>`;
                });

                div.innerHTML = `
                    <div style="font-weight:600; margin-bottom:4px;">${code}</div>
                    <div style="font-size:0.8em; opacity:0.8;">
                        ${coderDots}
                        <span style="float:right;">${info.count} refs</span>
                    </div>
                `;
                div.onclick = () => highlightSpecificCode(code);
                sidebarArea.appendChild(div);
            });
        }

        // 2. Highlight Text
        const sortedRecords = [...relevantRecords].sort((a, b) => b.text.length - a.text.length);
        const uniqueSegments = [...new Set(sortedRecords.map(r => r.text))];

        uniqueSegments.forEach(segmentText => {
            if (!segmentText || segmentText.length < 2) return;

            const matchRecs = relevantRecords.filter(r => r.text === segmentText);
            let activeCoders = new Set();
            matchRecs.forEach(r => {
                DATA.coders.forEach(c => { if(r[c] === 1) activeCoders.add(c); });
            });
            
            const coderArray = Array.from(activeCoders);
            const mainColor = coderArray.length > 0 ? getCoderColor(coderArray[0]) : 'var(--primary)';
            const tooltip = `Codes: ${[...new Set(matchRecs.map(r=>r.code))].join(', ')}\nCoders: ${coderArray.join(', ')}`;
            const dataCodes = [...new Set(matchRecs.map(r=>r.code))].join('|');

            const replacement = `<span class="highlight-span" style="border-color:${mainColor}" title="${tooltip}" data-codes="${dataCodes}">$&</span>`;
            
            try {
               const trimmed = segmentText.trim();

               // Split into words to handle whitespace robustly (matching tabs, newlines, nbsp)
               const tokens = trimmed.split(/[\s\u00A0]+/);

               const escapedTokens = tokens.map(t => {
                   // Use '\\$&' (2 backslashes) in Python raw string.
                   // Python writes \\$& to file. JS sees literal backslash + $&.
                   // JS Replace produces: Literal Backslash + Matched Char (e.g. "\[").
                   // This correctly escapes the character for the Regex engine.
                   let safe = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                   
                   // Handle HTML Entities
                   safe = safe.replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;");

                   // Handle Quotes (Smart vs Straight)
                   safe = safe.replace(/['’‘]/g, "(?:&#039;|'|’|‘)");
                   safe = safe.replace(/["“”]/g, "(?:&quot;|\"|“|”)");

                   // Handle Punctuation
                   safe = safe.replace(/\\\.\\\.\\\./g, "(?:\\.\\.\\.|…)");
                   safe = safe.replace(/-/g, "(?:-|–|—)");
                   
                   return safe;
               });

               // Join with robust whitespace regex that tolerates HTML tags in between words
               const spaceRegex = '(?:<[^>]+>)*[\\s\\u00A0]+(?:<[^>]+>)*';
               let pattern = escapedTokens.join(spaceRegex);

               const re = new RegExp(pattern, 'gi');
               processedHtml = processedHtml.replace(re, replacement);
            } catch(e) { console.log("Regex error", e); }
        });

        textArea.innerHTML = processedHtml;
        openTextModal();
    }

    function highlightSpecificCode(code) {
        // Remove active class from sidebar items
        document.querySelectorAll('.sidebar-code-item').forEach(el => el.classList.remove('active'));
        // Add to clicked
        event.currentTarget.classList.add('active');

        const spans = document.querySelectorAll('.highlight-span');
        let firstFound = null;

        spans.forEach(span => {
            const spanCodes = (span.getAttribute('data-codes') || "").split('|');
            if (spanCodes.includes(code)) {
                span.classList.add('highlight-active');
                if(!firstFound) firstFound = span;
            } else {
                span.classList.remove('highlight-active');
            }
        });

        if (firstFound) {
            firstFound.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }let codebookState = [];
    let codebookSort = { col: null, asc: true };

    function renderCodebookTable() {
        const root = document.getElementById('codebook-table-root');
        const columns = DATA.codebook.columns;
        
        // Initialize state on first run
        if (codebookState.length === 0 && DATA.codebook.rows.length > 0) {
            codebookState = JSON.parse(JSON.stringify(DATA.codebook.rows));
            codebookState.forEach((r, i) => r._ui_id = i);
        }
        
        if (columns.length === 0) {
            root.innerHTML = '<p>No codebook definition found or file is empty.</p>';
            return;
        }

        const searchTerm = document.getElementById('codebook-search').value.toLowerCase();

        let displayRows = codebookState.filter(row => {
            if (!searchTerm) return true;
            return Object.values(row).some(val => 
                String(val).toLowerCase().includes(searchTerm)
            );
        });

        // Sorting logic (preserved)
        if (codebookSort.col) {
            displayRows.sort((a, b) => {
                let valA = a[codebookSort.col] || "";
                let valB = b[codebookSort.col] || "";
                const numA = parseFloat(valA);
                const numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) { valA = numA; valB = numB; } 
                else { valA = String(valA).toLowerCase(); valB = String(valB).toLowerCase(); }

                if (valA < valB) return codebookSort.asc ? -1 : 1;
                if (valA > valB) return codebookSort.asc ? 1 : -1;
                return 0;
            });
        }

        // Attempt to identify a category column for coloring
        const catCol = columns.find(c => c.toLowerCase().includes('cat') || c.toLowerCase().includes('group'));

        // Define column width logic
        const getColClass = (colName) => {
            const lower = colName.toLowerCase();
            if (lower.includes('id') && !lower.includes('description')) return 'col-narrow';
            if (lower.includes('description') || lower === 'includes' || lower === 'excludes') return 'col-wide';
            return 'col-normal';
        };

        let html = '<table class="def-table"><thead><tr>';
        html += '<th class="action-cell">Actions</th>'; 
        columns.forEach(col => {
            const arrow = codebookSort.col === col ? (codebookSort.asc ? ' ▲' : ' ▼') : '';
            const colClass = getColClass(col);
            html += `<th class="${colClass}" onclick="sortCodebook('${col}')">${col}${arrow}</th>`;
        });
        html += '</tr></thead><tbody>';

        displayRows.forEach(row => {
            // Determine row color based on category column
            let rowStyle = '';
            let cellStyle = '';
            if (catCol && row[catCol]) {
                const baseColor = getCoderColor(String(row[catCol])); // baseColor is now HSL
                
                // NEW LOGIC: Extract HUE from the base color string (e.g., '120')
                const hueMatch = baseColor.match(/hsl\((\d+)/);
                const hue = hueMatch ? hueMatch[1] : 0;
                
                // Create a very faint background using HSLA (lightness reduced to 20%
                // and opacity set to 0.5) for a readable background color.
                const bg = `hsla(${hue}, 70%, 20%, 0.5)`; 
                
                rowStyle = `background-color: ${bg};`;
                // Stronger border uses the vivid HSL color
                rowStyle += `border-left: 5px solid ${baseColor};`;
            }

            html += `<tr style="${rowStyle}">`;
            html += `<td class="action-cell"><button class="btn-danger btn-sm" onclick="deleteCodebookRow(${row._ui_id})">✕</button></td>`;
            columns.forEach(col => {
                const val = row[col] !== undefined ? row[col] : "";
                html += `<td><textarea onchange="updateCodebookCell(${row._ui_id}, '${col}', this.value)">${escapeHtml(String(val))}</textarea></td>`;
            });
            html += `</tr>`;
        });

        html += '</tbody></table>';
        root.innerHTML = html;
    }

    function sortCodebook(col) {
        if (codebookSort.col === col) {
            codebookSort.asc = !codebookSort.asc;
        } else {
            codebookSort.col = col;
            codebookSort.asc = true;
        }
        renderCodebookTable();
    }

    function updateCodebookCell(id, col, value) {
        const row = codebookState.find(r => r._ui_id === id);
        if (row) {
            row[col] = value;
        }
    }

    // Visual confirmation of save
    function saveCurrentEdit() {
        const btn = document.getElementById('btn-save-edit');
        
        // In reality, data is already in 'codebookState', so this is just UX
        // Display a more informative message about in-memory-only save
        btn.innerText = "✓ Saved (In-Memory Only)!";
        btn.style.backgroundColor = "var(--success)";
        
        setTimeout(() => {
            btn.innerText = "Save current edit";
            btn.style.backgroundColor = ""; // revert to CSS class
        }, 3000); // Keep the message visible for longer

        // Provide a temporary alert/tooltip message near the button or use the existing informational paragraph.
        const infoParagraph = document.querySelector('#view-codebook p');
        if (infoParagraph) {
            infoParagraph.innerHTML = `
                <strong style="color:var(--success);">Changes saved to browser memory!</strong> To keep these edits, you must click 
                <strong>'Download CSV'</strong> or <strong>'Download Excel'</strong> before leaving or refreshing the page.
            `;
             setTimeout(() => {
                infoParagraph.innerHTML = `Note: Click 'Save current edit' to confirm changes in memory before switching tabs. Use Download buttons to export files.`;
            }, 5000);
        }
    }

    function deleteCodebookRow(id) {
        if (confirm("Are you sure you want to delete this row?")) {
            codebookState = codebookState.filter(r => r._ui_id !== id);
            renderCodebookTable();
        }
    }

    function addCodebookRow() {
        const newRow = { _ui_id: Date.now() }; // simple unique id
        DATA.codebook.columns.forEach(col => newRow[col] = "");
        // Insert at top
        codebookState.unshift(newRow);
        renderCodebookTable();
    }

    function getCleanData() {
        return codebookState.map(row => {
            const { _ui_id, ...rest } = row;
            return rest;
        });
    }

    async function exportCodebookXLSX() {
        const cleanData = getCleanData();
        if (cleanData.length === 0) return;
        
        const columns = DATA.codebook.columns;
        const catCol = columns.find(c => c.toLowerCase().includes('cat') || c.toLowerCase().includes('group'));
        
        // Create workbook and worksheet
        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet('Codebook');

        // Add headers
        const headerRow = worksheet.addRow(columns);
        headerRow.font = { bold: true };
        
        // Add Data with styling
        cleanData.forEach(dataRow => {
            const rowValues = columns.map(col => dataRow[col] || "");
            const addedRow = worksheet.addRow(rowValues);
            
            // Apply color if category exists
            if (catCol && dataRow[catCol]) {
                // Recalculate color as Hex for Excel because getCoderColor returns HSL
                const name = String(dataRow[catCol]);
                let index = DATA.coders.indexOf(name);
                if (index === -1) {
                    let hash = 0;
                    for (let i = 0; i < name.length; i++) {
                        hash = name.charCodeAt(i) + ((hash << 5) - hash);
                    }
                    index = Math.abs(hash);
                }
                const hue = (index * 137.508) % 360;
                
                // HSL to Hex conversion (using S=0.75, L=0.45 to match getCoderColor)
                const s = 0.75, l = 0.45;
                const k = n => (n + hue / 30) % 12;
                const a = s * Math.min(l, 1 - l);
                const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
                const toHex = x => Math.round(x * 255).toString(16).padStart(2, '0');
                const hexColor = `${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;

                // Use a very light shade of the color for the fill by appending 70% opacity in AARRGGBB
                const lightFillColor = '33' + hexColor; 
                
                // Apply to each cell in row
                addedRow.eachCell({ includeEmpty: true }, (cell, colIndex) => {
                    cell.fill = {
                        type: 'pattern',
                        pattern: 'solid',
                        fgColor: { argb: lightFillColor }, 
                    };
                    
                    // Add border for clarity (optional but looks better)
                    const baseBorder = {style:'thin', color: {argb:'FF888888'}};
                    const leftBorder = colIndex === 1 
                        ? {style:'thick', color: {argb: 'FF' + hexColor}} 
                        : baseBorder;
                        
                    cell.border = {
                        top: baseBorder,
                        left: leftBorder,
                        bottom: baseBorder,
                        right: baseBorder
                    };
                });
            }
            
            // Set text wrapping for description columns
            addedRow.eachCell((cell, colNumber) => {
                const colName = columns[colNumber - 1].toLowerCase();
                 if (colName.includes('description') || colName === 'includes' || colName === 'excludes') {
                     cell.alignment = { wrapText: true, vertical: 'top' };
                 } else {
                     cell.alignment = { vertical: 'top' };
                 }
            });
        });

        // Adjust column widths based on content type
        worksheet.columns = columns.map(col => {
            const lower = col.toLowerCase();
            let width = 20;
            if (lower.includes('id') && !lower.includes('description')) width = 12;
            if (lower.includes('description') || lower === 'includes' || lower === 'excludes') width = 50;
            return { width: width };
        });

        // Write file
        const buffer = await workbook.xlsx.writeBuffer();
        const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'updated_codebook.xlsx';
        a.click();
        window.URL.revokeObjectURL(url);
    }
    
    function exportCodebookCSV() {
        const cleanData = getCleanData();
        if (cleanData.length === 0) return;
        
        const headers = Object.keys(cleanData[0]);
        const csvRows = [headers.join(',')];

        cleanData.forEach(row => {
            const values = headers.map(header => {
                const escaped = ('' + (row[header] || '')).replace(/"/g, '""');
                return `"${escaped}"`;
            });
            csvRows.push(values.join(','));
        });

        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', 'updated_codebook.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function renderFAQ() {
        const root = document.getElementById('faq-list');
        const searchTerm = document.getElementById('faq-search').value.toLowerCase();
        root.innerHTML = '';

        DATA.faqData.forEach(item => {
            const q = item.q;
            const a = item.a;
            
            // Simple search logic
            if (searchTerm && !q.toLowerCase().includes(searchTerm) && !a.toLowerCase().includes(searchTerm)) {
                return;
            }

            const el = document.createElement('div');
            el.className = 'faq-item';
            
            el.innerHTML = `
                <div class="faq-question" onclick="toggleFAQ(this)">${q}</div>
                <div class="faq-answer">${a}</div>
            `;
            root.appendChild(el);
        });

        if (root.children.length === 0) {
            root.innerHTML = '<div style="text-align:center; padding:20px; opacity:0.6;">No questions found matching your search.</div>';
        }
    }

    function toggleFAQ(headerElement) {
        const item = headerElement.parentElement;
        item.classList.toggle('open');
    }

    function filterFAQ() {
        renderFAQ();
    }

</script>
</body>
</html>
"""


def get_dynamic_faq():
    faq_items = []

    # Get configuration values
    overlap_pct = getattr(config, "WORDS_OVERLAP_PERCENTAGE", 0.0) * 100
    align_segments = getattr(config, "ALIGN_SEGMENTS_ACROSS_CODES", False)
    mutual_only = getattr(config, "CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY", False)
    margin_pct = getattr(config, "TRANSCRIPT_NON_CODABLE_MARGIN", 0.10) * 100

    # ==============================================================================
    # SECTION 1: DATA PROCESSING & MERGING (Most Common Questions)
    # ==============================================================================

    faq_items.append(
        {
            "q": "Why do some of my text selections look different or longer than what I originally coded?",
            "a": (
                f"This is due to the <strong>Fuzzy Matching & Merging</strong> process.<br><br>"
                f"<strong>The Logic:</strong> The system compares text segments from different coders. If two segments share "
                f"at least <strong>{overlap_pct:.0f}%</strong> of their unique words (tokens), they are considered to be the 'same' segment.<br>"
                f"<strong>The Result:</strong> To preserve the full context of what both coders saw, the system merges them by keeping "
                f"the <strong>longest version</strong> of the text. If you coded 'The quick brown fox' and your partner coded "
                f"'The quick brown fox jumps', the final report will display 'The quick brown fox jumps' for both of you to avoid grammatical fragmentation."
            ),
        }
    )

    faq_items.append(
        {
            "q": "What happened to codes that seem to have disappeared?",
            "a": (
                "Codes are rarely deleted, but they are often grouped or filtered for clarity:<br>"
                "1. <strong>Merged:</strong> If you and another coder marked similar text with the same code, those two rows are now displayed as a single 'Agreement' row.<br>"
                "2. <strong>Renamed:</strong> If the Codebook definitions file contained mapping rules, some codes might have been normalized to a standard name.<br>"
                "3. <strong>Cleaned:</strong> Rows with missing critical metadata (like Participant ID) or empty text bodies are dropped during data sanitation."
            ),
        }
    )

    faq_items.append(
        {
            "q": "What do the colors in the 'Browser' tab indicate?",
            "a": (
                "<ul>"
                "<li><strong style='color: var(--success)'>Green Text (80%+ Agreement):</strong> High consensus. Both coders selected this consistently.</li>"
                "<li><strong style='color: #fd7e14'>Orange Text (60-80%):</strong> Moderate agreement. Usually implies slight variations in text selection boundaries.</li>"
                "<li><strong style='color: var(--primary)'>Blue Text (<60%):</strong> Low agreement. Indicates that while the code category matches, the specific text segments or frequency differed significantly.</li>"
                "<li><strong>Coder Badges:</strong> Small colored tags showing exactly which coder marked the segment. If a coder is missing from the badge list on a row, they did not code that specific segment.</li>"
                "</ul>"
            ),
        }
    )

    # ==============================================================================
    # SECTION 2: ALIGNMENT & SCORING LOGIC (Dynamic based on Config)
    # ==============================================================================

    # Alignment Strategy
    if align_segments:
        faq_items.append(
            {
                "q": "I coded 'Segment A' as Code X, and my partner coded it as Code Y. Why are they grouped together?",
                "a": (
                    "<strong>Segment Alignment is ENABLED.</strong><br>"
                    "The system is currently configured to align text boundaries across <em>different</em> codes. "
                    "Because you both coded the same (or overlapping) text, the system treats this as a single unit of analysis where you "
                    "disagreed on the category (Code X vs. Code Y). It appears as a direct conflict in the statistics."
                ),
            }
        )
    else:
        faq_items.append(
            {
                "q": "I coded 'Segment A' as Code X, and my partner coded it as Code Y. Why are they two separate rows?",
                "a": (
                    "<strong>Segment Alignment is DISABLED.</strong><br>"
                    "The system treats Code X and Code Y as completely independent entities. "
                    "Because the code labels differ, the system does not force them into a single row, even if the text overlaps. "
                    "You will see one row for Code X (where you = 1, partner = 0) and another row for Code Y (where you = 0, partner = 1)."
                ),
            }
        )

    # Omission Handling - UPDATED to include the word "Omissions" for searchability
    if mutual_only:
        faq_items.append(
            {
                "q": "How are Omissions (missing codes/silence) handled? Do they count against my score?",
                "a": (
                    "<strong>No. Mutual Segments Mode is ENABLED.</strong><br>"
                    "The analysis focuses on <em>Classification Agreement</em> (did we agree on the code?) rather than "
                    "<em>Unitization Agreement</em> (did we find the same text?).<br>"
                    "If Coder A marks a segment and Coder B does not (Omission/Silence), the system assumes Coder B simply missed it "
                    "rather than actively disagreeing. These rows are filtered out of the strict disagreement calculation."
                ),
            }
        )
    else:
        faq_items.append(
            {
                "q": "How are Omissions (missing codes/silence) handled? Do they count against my score?",
                "a": (
                    "<strong>Yes. Strict Coding Mode is ENABLED.</strong><br>"
                    "The system treats an omission (silence) as a disagreement. If Coder A marks a segment and Coder B does not, "
                    "it is calculated as a 0 vs 1 disagreement. To achieve high reliability in this mode, coders must agree on both "
                    "<em>what</em> to code and <em>where</em> to code it."
                ),
            }
        )

    # ==============================================================================
    # SECTION 3: STATISTICAL INTERPRETATION
    # ==============================================================================

    faq_items.append(
        {
            "q": "What is the difference between F1-Score and Cohen's Kappa?",
            "a": (
                "<strong>F1-Score (Dice Coefficient):</strong> Measures the overlap between two coders on the codes they actually applied. "
                "It is generally robust for qualitative data and rare codes.<br><br>"
                "<strong>Cohen's Kappa:</strong> Measures agreement while attempting to account for 'chance'. It requires knowing "
                "how much text was <em>not</em> coded (True Negatives) to calculate properly."
            ),
        }
    )

    faq_items.append(
        {
            "q": "Why is my Cohen's Kappa low (or negative) even though we have high percentage agreement?",
            "a": (
                "This is known as the <strong>Prevalence Paradox</strong>.<br>"
                "Kappa penalizes agreement on 'silence'. If a specific code is very rare (e.g., appears in only 1% of the text), "
                "coders could theoretically agree 99% of the time simply by <em>not</em> coding it. "
                "If you have even one disagreement on a rare code, Kappa interprets this as 'worse than random chance', "
                "potentially driving the score into negative numbers. In these cases, trust the <strong>F1-Score</strong>."
            ),
        }
    )

    faq_items.append(
        {
            "q": "How are 'True Negatives' (uncoded text) calculated?",
            "a": (
                "To calculate Kappa, we must estimate the volume of text that <em>nobody</em> coded.<br>"
                "The system does this by taking the total word count of the transcripts and subtracting the word count of all coded segments. "
                f"A safety margin of <strong>{margin_pct:.0f}%</strong> is subtracted from the total to account for headers, footers, timestamps, "
                "and interviewer questions that are not valid for coding."
            ),
        }
    )

    return faq_items


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

    # Get Dynamic FAQ Data
    faq_data = get_dynamic_faq()

    cb_cols, cb_rows = load_codebook_definitions()

    reports_json = json.dumps(
        {"notes1": notes1_txt, "notes2": notes2_txt}, ensure_ascii=False
    )
    html_content = get_html_template()
    html_content = html_content.replace(
        "{faq_json}", json.dumps(faq_data, ensure_ascii=False)
    )
    html_content = html_content.replace(
        "{hierarchical_json}", json.dumps(hierarchical_data, ensure_ascii=False)
    )
    html_content = html_content.replace(
        "{analysis_json}", json.dumps(analysis_data, ensure_ascii=False)
    )
    html_content = html_content.replace(
        "{irr_records_json}", json.dumps(irr_records, ensure_ascii=False)
    )
    html_content = html_content.replace("{coders_json}", json.dumps(c_list))
    html_content = html_content.replace("{participants_json}", json.dumps(p_list))
    html_content = html_content.replace("{reports_json}", reports_json)

    # Inject Codebook Data
    html_content = html_content.replace(
        "{codebook_columns_json}", json.dumps(cb_cols, ensure_ascii=False)
    )
    html_content = html_content.replace(
        "{codebook_rows_json}", json.dumps(cb_rows, ensure_ascii=False)
    )

    # Inject Transcript File List
    html_content = html_content.replace(
        "{transcript_files_json}", json.dumps(transcript_files)
    )
    # Inject Transcript File List
    html_content = html_content.replace(
        "{transcript_files_json}", json.dumps(transcript_files)
    )
    # Inject Transcript Contents for direct access
    html_content = html_content.replace(
        "{transcript_contents_json}",
        json.dumps(transcript_contents, ensure_ascii=False),
    )

    try:
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
