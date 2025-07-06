import pandas as pd
import html
import os
from collections import defaultdict
import json
import traceback
import config
import sys


# ==============================================================================
# === Inputs & Outputs ===
# ==============================================================================
CSV_FILENAME = 'input/codebook.csv'
HTML_OUTPUT_FILENAME = 'output/codes.html'
# --- Original Column Names from CSV ---
ORIG_FILE_COL = 'File'
ORIG_CODER_COL = 'Coder'
ORIG_CODED_TEXT_COL = 'Coded'
ORIG_CODENAME_COL = 'Codename'
ORIG_MEMO_COL = 'Coded_Memo'
ORIG_CATEGORY_COL_OPTIONAL = 'Category'

# --- Internal Column Names Used After Processing ---
CAT_COL = 'CategoryInternal'
CODE_COL = 'CodeInternal'
TEXT_COL = 'CodedTextInternal'
MEMO_COL = 'MemoInternal'
PARTICIPANT_COL = 'ParticipantInternal'
CODER_COL = 'CoderNameInternal'  # Retained for hierarchical data, not charted


# ==============================================================================
# === Data Loading and Preprocessing Functions ===
# ==============================================================================

def load_csv_data(filename):
    """Loads data from the specified CSV file."""
    if not os.path.exists(filename):
        print(f"Error: File not found at '{filename}'")
        return None
    try:
        df = pd.read_csv(filename)
        print(f"Successfully loaded '{filename}'.")
        if df.empty:
            print("Warning: CSV file is empty.")
        return df
    except pd.errors.EmptyDataError:
        print(f"Error: CSV file '{filename}' is empty or invalid.")
        return None
    except Exception as e:
        print(f"Error reading CSV file '{filename}': {e}")
        traceback.print_exc()
        return None

def validate_required_columns(df, required_cols):
    """Checks if DataFrame contains all required original columns."""
    if df is None:
        return False
    actual_cols = df.columns
    missing_cols = [col for col in required_cols if col not in actual_cols]
    if missing_cols:
        print(f"\nError: Missing essential columns from CSV: {', '.join(missing_cols)}")
        print(f"Expected columns: {', '.join(required_cols)}")
        print(f"Found columns: {', '.join(actual_cols)}")
        return False
    return True

def define_derived_categories_codes(df_ref):
    """Helper function to define CAT_COL and CODE_COL from ORIG_CODENAME_COL."""
    if ORIG_CODENAME_COL not in df_ref.columns:
        print(f"Error: Cannot derive categories/codes, missing source column '{ORIG_CODENAME_COL}'.")
        df_ref[CAT_COL] = 'Error'
        df_ref[CODE_COL] = 'Error'
        return

    def derive_category_from_codename(codename_val):
        codename_str = str(codename_val).strip()
        parts = codename_str.split(':', 1)
        return parts[0].strip() if len(parts) > 1 and parts[0].strip() else 'General'

    def derive_code_from_codename(codename_val):
        codename_str = str(codename_val).strip()
        parts = codename_str.split(':', 1)
        code_part = parts[1].strip() if len(parts) > 1 else codename_str
        return code_part if code_part else 'Unknown Code'

    df_ref[CAT_COL] = df_ref[ORIG_CODENAME_COL].apply(derive_category_from_codename)
    df_ref[CODE_COL] = df_ref[ORIG_CODENAME_COL].apply(derive_code_from_codename)

def preprocess_dataframe(df):
    """Applies preprocessing and returns the processed DataFrame or None."""
    if df is None or df.empty:
        return None
    essential_cols = [ORIG_FILE_COL, ORIG_CODER_COL, ORIG_CODED_TEXT_COL, ORIG_CODENAME_COL, ORIG_MEMO_COL]
    if not validate_required_columns(df, essential_cols):
        return None

    try:
        df_processed = df.copy()

        df_processed[ORIG_MEMO_COL] = df_processed[ORIG_MEMO_COL].fillna('')
        df_processed[ORIG_CODED_TEXT_COL] = df_processed[ORIG_CODED_TEXT_COL].astype(str).fillna('')
        df_processed[ORIG_CODER_COL] = df_processed[ORIG_CODER_COL].astype(str).fillna('Unknown Coder')
        df_processed[ORIG_CODENAME_COL] = df_processed[ORIG_CODENAME_COL].astype(str).str.strip()

        def extract_participant(filepath):
            if pd.isna(filepath) or not str(filepath).strip():
                return 'unknown_participant'
            filepath_str = str(filepath)
            basename = os.path.basename(filepath_str)
            participant_id = os.path.splitext(basename)[0]
            return participant_id if participant_id else 'unknown_participant'
        df_processed[PARTICIPANT_COL] = df_processed[ORIG_FILE_COL].apply(extract_participant)

        use_existing_category = False
        if ORIG_CATEGORY_COL_OPTIONAL in df_processed.columns and not df_processed[ORIG_CATEGORY_COL_OPTIONAL].isnull().all():
            df_cat_check = df_processed[ORIG_CATEGORY_COL_OPTIONAL].dropna().astype(str).str.strip()
            if not df_cat_check.empty and df_cat_check.nunique() > 0:
                use_existing_category = True

        if use_existing_category:
            print(f"Using existing '{ORIG_CATEGORY_COL_OPTIONAL}' column from CSV.")
            df_processed[CAT_COL] = df_processed[ORIG_CATEGORY_COL_OPTIONAL].astype(str).str.strip()
            df_processed[CODE_COL] = df_processed[ORIG_CODENAME_COL].astype(str).str.strip()
        else:
            if ORIG_CATEGORY_COL_OPTIONAL in df_processed.columns:
                print(f"Found '{ORIG_CATEGORY_COL_OPTIONAL}' column but it's empty/invalid. Deriving from '{ORIG_CODENAME_COL}'.")
            else:
                print(f"Deriving Category and Code from '{ORIG_CODENAME_COL}' column.")
            define_derived_categories_codes(df_processed)

        df_processed[CAT_COL] = df_processed[CAT_COL].replace('', 'Unknown Category')
        df_processed[CODE_COL] = df_processed[CODE_COL].replace('', 'Unknown Code')

        df_renamed = df_processed.rename(columns={
            ORIG_CODED_TEXT_COL: TEXT_COL,
            ORIG_MEMO_COL: MEMO_COL,
            ORIG_CODER_COL: CODER_COL
        })

        final_columns_to_use = [CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, PARTICIPANT_COL, CODER_COL]
        missing_final_cols = [col for col in final_columns_to_use if col not in df_renamed.columns]
        if missing_final_cols:
            print(f"\nError: Internal processing error. Missing columns after processing: {', '.join(missing_final_cols)}")
            return None

        df_final = df_renamed[final_columns_to_use].copy()

        if CAT_COL in df_final.columns and CODE_COL in df_final.columns:
            valid_category = (df_final[CAT_COL].notna() &
                              (df_final[CAT_COL].astype(str).str.strip() != '') &
                              (df_final[CAT_COL].astype(str).str.strip().str.lower() != 'unknown category'))
            valid_code = (df_final[CODE_COL].notna() &
                          (df_final[CODE_COL].astype(str).str.strip() != '') &
                          (df_final[CODE_COL].astype(str).str.strip().str.lower() != 'unknown code'))

            df_final = df_final[valid_category & valid_code]
        else:
            print(f"Error: Cannot perform final filtering, required columns '{CAT_COL}' or '{CODE_COL}' not found.")
            return None

        print(f"Data preprocessing complete. Processed {len(df_final)} valid rows.")
        if df_final.empty:
            print("Warning: No valid rows remaining after preprocessing and filtering.")

        return df_final

    except Exception as e:
        print(f"Error during dataframe preprocessing: {e}")
        traceback.print_exc()
        return None

# ==============================================================================
# === Data Structuring Functions ===
# ==============================================================================

def build_hierarchical_data(df):
    """Builds nested dict for code browser: Category -> Code -> [Segments]"""
    if df is None or df.empty:
        return {}
    data_structure = defaultdict(lambda: defaultdict(list))
    expected_cols = [CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, PARTICIPANT_COL, CODER_COL]
    if not all(col in df.columns for col in expected_cols):
        return {}

    for _, row in df.iterrows():
        data_structure[str(row[CAT_COL])][str(row[CODE_COL])].append({
            'participant': str(row[PARTICIPANT_COL]) if pd.notna(row[PARTICIPANT_COL]) else 'N/A',
            'coder': str(row[CODER_COL]) if pd.notna(row[CODER_COL]) else 'N/A',
            'text': str(row[TEXT_COL]) if pd.notna(row[TEXT_COL]) else '',
            'memo': str(row[MEMO_COL]) if pd.notna(row[MEMO_COL]) else ''
        })

    final_structure = {str(category): {str(code): segments for code, segments in codes.items()}
                       for category, codes in data_structure.items()}
    return final_structure

def build_participant_segment_data(df):
    """Builds dict mapping participant ID to list of their segments."""
    if df is None or df.empty:
        return {}
    participant_data = defaultdict(list)
    expected_cols = [PARTICIPANT_COL, CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, CODER_COL]
    if not all(col in df.columns for col in expected_cols):
        return {}

    for _, row in df.iterrows():
        participant_id = str(row[PARTICIPANT_COL]) if pd.notna(row[PARTICIPANT_COL]) else 'N/A'
        coder_name = str(row[CODER_COL]) if pd.notna(row[CODER_COL]) else 'N/A'
        if participant_id != 'N/A':
            participant_data[participant_id].append({
                'category': str(row[CAT_COL]), 'code': str(row[CODE_COL]),
                'text': str(row[TEXT_COL]), 'memo': str(row[MEMO_COL]),
                'coder': coder_name, 'participant': participant_id
            })
    return dict(participant_data)


def prepare_analysis_data(df):
    """
    Prepares aggregated data for analysis charts.
    Counts are based on *unique participants* per category or code, not on the total number of segments.
    All chart data is sorted by count in descending order.
    """
    if df is None or df.empty:
        return {}
    analysis_data = {}
    try:
        all_categories = sorted(df[CAT_COL].unique().tolist())
        analysis_data['allCategories'] = all_categories

        cat_counts = df.groupby(CAT_COL)[PARTICIPANT_COL].nunique().sort_values(ascending=False)
        analysis_data['categoryDistribution'] = {
            'labels': cat_counts.index.astype(str).tolist(),
            'data': cat_counts.values.tolist(),
            'title': 'Category Distribution (by Unique Participant)'
        } if not cat_counts.empty else None

        analysis_data['allCategoryCodeCounts'] = {}
        if all_categories:
            for cat_name in all_categories:
                df_cat_filtered = df[df[CAT_COL] == cat_name]
                code_counts = df_cat_filtered.groupby(CODE_COL)[PARTICIPANT_COL].nunique().sort_values(ascending=False)

                if not code_counts.empty:
                    analysis_data['allCategoryCodeCounts'][cat_name] = {
                        'labels': code_counts.index.astype(str).tolist(),
                        'data': code_counts.values.tolist()
                    }

            default_cat = config.DEFAULT_CATEGORY_FOR_DYNAMIC_CHART if config.DEFAULT_CATEGORY_FOR_DYNAMIC_CHART in all_categories else (
                all_categories[0] if all_categories else None)
            analysis_data['defaultCategoryForBreakdown'] = next((c for c in [default_cat] + all_categories if c and c in analysis_data['allCategoryCodeCounts']), None)
        else:
            analysis_data['defaultCategoryForBreakdown'] = None

        def get_chart_data_for_category(pattern, title_prefix):
            match = next((c for c in all_categories if c.lower() == pattern.lower()), None) or \
                next((c for c in all_categories if pattern.lower() in c.lower()), None)

            if match and match in analysis_data['allCategoryCodeCounts']:
                chart_data = analysis_data['allCategoryCodeCounts'][match]
                return {
                    'categoryName': match,
                    'labels': chart_data['labels'],
                    'data': chart_data['data'],
                    'title': f'{title_prefix} (by Unique Participant)'
                }

            print(f"Info: Category for '{title_prefix}' (pattern '{pattern}') not found or has no codes.")
            return None

        analysis_data['category1distribution'] = get_chart_data_for_category(config.CATEGORY_1_FOR_CHART, config.CATEGORY_1_FOR_CHART_TITLE)
        analysis_data['category2distribution'] = get_chart_data_for_category(config.CATEGORY_2_FOR_CHART, config.CATEGORY_2_FOR_CHART_TITLE)
        cat_3_data = get_chart_data_for_category(config.CATEGORY_3_FOR_CHART, config.CATEGORY_3_FOR_CHART_TITLE)
        if not cat_3_data:
            cat_3_data = get_chart_data_for_category(config.CATEGORY_3_FOR_CHART_FALLBACK, config.CATEGORY_3_FOR_CHART_FALLBACK_TITLE)
        analysis_data['category3distribution'] = cat_3_data

        participant_counts = df[PARTICIPANT_COL].value_counts()
        analysis_data['participantActivity'] = {
            'labels': participant_counts.index.astype(str).tolist(),
            'data': participant_counts.values.tolist(),
            'title': 'Segments per Participant (Click bar)'
        } if not participant_counts.empty else None

    except Exception as e:
        print(f"Error preparing analysis data: {e}")
        traceback.print_exc()
        return {}

    return analysis_data

# ==============================================================================
# === HTML Generation Function ===
# ==============================================================================

def generate_interactive_html(hierarchical_data, analysis_data, participant_segment_data, output_filename, participant_list=None, coder_list=None):
    """Generates the final HTML file including browser, analysis charts, and modals."""

    def safe_json_dumps(data, name):
        try:
            return json.dumps(data if data else {}, ensure_ascii=False)
        except Exception as e:
            print(f"Error serializing {name} data to JSON: {e}")
            traceback.print_exc()
            return "{}"

    config_data = {
        'CATEGORY_1_FOR_CHART': config.CATEGORY_1_FOR_CHART,
        'CATEGORY_1_FOR_CHART_TITLE': config.CATEGORY_1_FOR_CHART_TITLE,
        'CATEGORY_2_FOR_CHART': config.CATEGORY_2_FOR_CHART,
        'CATEGORY_2_FOR_CHART_TITLE': config.CATEGORY_2_FOR_CHART_TITLE,
        'CATEGORY_3_FOR_CHART': config.CATEGORY_3_FOR_CHART,
        'CATEGORY_3_FOR_CHART_TITLE': config.CATEGORY_3_FOR_CHART_TITLE,
        'CATEGORY_3_FOR_CHART_FALLBACK': config.CATEGORY_3_FOR_CHART_FALLBACK,
        'CATEGORY_3_FOR_CHART_FALLBACK_TITLE': config.CATEGORY_3_FOR_CHART_FALLBACK_TITLE,
    }
    config_json = json.dumps(config_data)
    analysis_data_json = safe_json_dumps(analysis_data, "analysis")
    hierarchical_data_json = safe_json_dumps(hierarchical_data, "hierarchical")
    participant_data_json = safe_json_dumps(participant_segment_data, "participant")
    participant_list_json = json.dumps(participant_list if participant_list else [])
    coder_list_json = json.dumps(coder_list if coder_list else [])

    html_template = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Analysis Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/choices.js/public/assets/styles/choices.min.css"/>
    <script src="https://cdn.jsdelivr.net/npm/choices.js/public/assets/scripts/choices.min.js"></script>
    <style>
        :root {{
            --bg-color: #f8f9fa; --text-color: #212529; --header-color: #0056b3; --border-color: #dee2e6;
            --control-bg: #e9ecef; --control-border: #ced4da; --control-hover-bg: #dee2e6;
            --primary-accent: #007bff; --primary-accent-hover: #0056b3;
            --segment-bg: #ffffff; --segment-border: #e9ecef; --segment-shadow: rgba(0,0,0,0.05);
            --segment-meta-text: #6c757d; --segment-coder-text: #28a745; --segment-participant-text: #dc3545;
            --segment-memo-bg: #f0f8ff; --segment-memo-border: #bde0fe;
            --modal-bg: #fefefe; --modal-shadow: rgba(0,0,0,0.2); --modal-header-border: #ccc;
            --chart-bg: #fdfdfd; --chart-border: #ddd; --chart-title-color: #0056b3;
            --choices-bg: #fff; --choices-border: #ccc; --choices-text: #333; --choices-item-bg: #007bff;
        }}
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 0; padding:0; line-height: 1.6;
            background-color: var(--bg-color); color: var(--text-color);
            transition: background-color 0.3s, color 0.3s;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; color: var(--header-color); border-bottom: 2px solid var(--border-color); padding-bottom: 10px; margin-bottom: 20px; }}
        .controls {{ display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 15px; margin-bottom: 20px; padding: 10px; background-color: var(--control-bg); border-radius: 8px; }}
        .controls button {{ padding: 10px 15px; cursor: pointer; border-radius: 5px; border: 1px solid var(--primary-accent-hover); background-color: var(--primary-accent); color: white; font-size: 0.95em; transition: background-color 0.2s; }}
        .controls button:hover {{ background-color: var(--primary-accent-hover); }}
        # .filter-group {{ display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 5px; }}
        #browser-content {{ margin-top: 20px; }}
        .category, .code {{ cursor: pointer; font-weight: bold; margin-top: 15px; padding: 10px 10px 10px 30px; border-radius: 5px; background-color: var(--control-bg); border: 1px solid var(--control-border); position: relative; }}
        .category:hover, .code:hover {{ background-color: var(--control-hover-bg); }}
        .category::before, .code::before {{ content: '\25B6'; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 0.9em; transition: transform 0.2s ease; color: var(--header-color); }}
        .category.open::before, .code.open::before {{ transform: translateY(-50%) rotate(90deg); }}
        .code-list, .segment-list {{ display: none; margin-left: 25px; padding-left: 20px; border-left: 2px solid #adb5bd; }}
        .segment {{ background-color: var(--segment-bg); border: 1px solid var(--segment-border); padding: 12px; margin-top: 10px; border-radius: 4px; box-shadow: 0 1px 3px var(--segment-shadow); }}
        .segment-meta {{ font-size: 0.9em; color: var(--segment-meta-text); margin-bottom: 5px; }}
        .segment-coder {{ font-weight: bold; color: var(--segment-coder-text); }}
        .segment-participant {{ font-weight: bold; color: var(--segment-participant-text); }}
        .segment-text {{ display: block; margin-top: 5px; font-style: italic; color: var(--text-color); white-space: pre-wrap; word-wrap: break-word;}}
        .segment-memo {{ font-size: 0.95em; color: var(--primary-accent); margin-top: 8px; white-space: pre-wrap; word-wrap: break-word; padding: 8px; border-left: 3px solid var(--segment-memo-border); background-color: var(--segment-memo-bg); }}
        .segment-memo:empty, .segment-memo.empty-memo {{ display: none; }}
        .count {{ font-size: 0.85em; color: #495057; margin-left: 10px; font-weight: normal; }}
        #analysis-section {{ margin-top: 20px; padding-top:1px; background-color: var(--segment-bg); border: 1px solid var(--border-color); border-radius: 5px; }}
        #analysis-section h2 {{ text-align:center; margin-top: 20px; color: var(--header-color);}}
        .charts-grid {{ display: flex; flex-wrap: wrap; justify-content: space-around; align-items: flex-start; }}
        .chart-container {{ width: 100%; height: 400px; margin: 15px; padding: 15px; border: 1px solid var(--chart-border); border-radius: 4px; background-color: var(--chart-bg); box-shadow: 0 2px 4px var(--segment-shadow); box-sizing: border-box; position: relative; display: flex; flex-direction: column; }}
        @media (min-width: 992px) {{ .chart-container {{ width: calc(50% - 30px); }} }}
        .dynamic-chart-controls {{ text-align: center; margin-bottom:10px; flex-shrink:0;}}
        .no-data-message {{ text-align: center; color: #777; font-style: italic; padding: 20px; width:100%; margin: auto; }}
        .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); }}
        .modal-content {{ background-color: var(--modal-bg); margin: 5% auto; padding: 20px 25px; border: 1px solid #888; border-radius: 5px; width: 85%; max-width: 800px; max-height: 85vh; overflow-y: auto; position: relative; box-shadow: 0 5px 15px var(--modal-shadow); }}
        .modal-header {{ padding-bottom: 10px; border-bottom: 1px solid var(--modal-header-border); margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        .modal-header h4 {{ margin:0; font-size: 1.4em; color: var(--header-color);}}
        .modal-body .segment-item {{ margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px dotted var(--modal-header-border); }}
        .modal-body .segment-item:last-child {{ border-bottom: none; }}
        .modal-body .seg-meta {{ margin-bottom: 8px; font-size: 0.95em; }}
        .modal-body .seg-coder {{ font-weight: bold; color: var(--segment-coder-text); }}
        .modal-body .seg-participant {{ font-weight: bold; color: var(--segment-participant-text); }}
        .modal-body .seg-category-code {{ display: block; font-size: 0.9em; color: #555; margin-top: 3px;}}
        .modal-body .seg-text {{font-style: italic; display:block; margin: 5px 0; white-space: pre-wrap; word-wrap: break-word; color: var(--text-color); background-color: var(--bg-color); padding: 8px; border-radius: 3px; border: 1px solid var(--border-color); }}
        .modal-body .seg-memo {{font-size: 0.9em; color: var(--primary-accent); background-color:var(--segment-memo-bg); padding: 8px; border-left: 3px solid var(--primary-accent); margin-top:8px; white-space: pre-wrap; word-wrap: break-word;}}
        .modal-body .seg-memo.empty-memo {{display:none;}}
        .close-button {{ color: #aaa; font-size: 30px; font-weight: bold; line-height: 1; cursor: pointer; background: none; border: none; padding: 0 5px; }}
        .close-button:hover, .close-button:focus {{ color: #333; text-decoration: none; }}
        
        .dark-mode {{
            --bg-color: #1a1a1a; --text-color: #e2e2e2; --header-color: #58a6ff; --border-color: #3a3a3a;
            --control-bg: #2c2c2c; --control-border: #444; --control-hover-bg: #383838;
            --primary-accent: #0d6efd; --primary-accent-hover: #3b82f6;
            --segment-bg: #252525; --segment-border: #404040; --segment-shadow: rgba(0,0,0,0.2);
            --segment-meta-text: #9e9e9e; --segment-coder-text: #4ade80; --segment-participant-text: #f87171;
            --segment-memo-bg: #1e293b; --segment-memo-border: #3b82f6;
            --modal-bg: #282828; --modal-shadow: rgba(0,0,0,0.4); --chart-bg: #252525; --chart-border: #404040; --chart-title-color: #58a6ff;
            --choices-bg: #333; --choices-border: #555; --choices-text: #f1f1f1; --choices-item-bg: #0d6efd;
        }}
        .dark-mode .close-button {{ color: #888; }}
        .dark-mode .close-button:hover {{ color: #ddd; }}
        .dark-mode .count {{ color: #aaa; }}
        
        .choices {{ min-width: 200px; }}
        .choices__inner {{ background-color: var(--choices-bg); border-color: var(--choices-border); color: var(--choices-text); border-radius: 5px; padding: 4px 8px; font-size: 0.70em; }}
        .choices__list--dropdown, .choices__list[aria-expanded] {{ background-color: var(--choices-bg); border-color: var(--choices-border); color: var(--choices-text); }}
        .choices__list--dropdown .choices__item--selectable.is-highlighted, .choices__list[aria-expanded] .choices__item--selectable.is-highlighted {{ background-color: var(--primary-accent-hover); }}
        .choices__item {{ color: var(--choices-text); }}
        .choices__placeholder {{ color: var(--choices-text); opacity: 0.7;}}
        .choices[data-type*="select-one"]::after {{ border-color: var(--choices-text) transparent transparent; }}
        .choices.is-open[data-type*="select-one"]::after {{ border-color: transparent transparent var(--choices-text); }}
        .choices__item--choice {{ color: var(--choices-text);}}

    </style>
</head>
<body class="dark-mode">
<div class="container">
    <h1>Code Analysis Report</h1>
    <div class="controls">
        <div>
            <button id="themeToggleBtn">Switch to Light Theme</button>
            <button id="toggleBrowserBtn">Show Code Browser</button>
            <button id="toggleAnalysisBtn">Show Analysis</button>
        </div>
        <div>
            <button onclick="expandAll()" class="browser-control">Expand All Codes</button>
            <button onclick="collapseAll()" class="browser-control">Collapse All Codes</button>
        </div>
        <select id="participantFilter"></select>
        <select id="coderFilter"></select>
        <div class="filter-group">
            
        </div>
    </div>
    <div id="analysis-section" style="display:none;">
        <h2>Data Analysis</h2>
        <div class="charts-grid">
            <div class="chart-container" id="categoryDistributionChartContainer"><canvas id="categoryDistributionChart"></canvas></div>
            <div class="chart-container" id="dynamicCategoryBreakdownChartContainer">
                <div class="dynamic-chart-controls">
                    <label for="categorySelector">Select Category for Breakdown: </label>
                    <select id="categorySelector"></select>
                </div>
                <canvas id="dynamicCategoryBreakdownChart"></canvas>
            </div>
            <div class="chart-container" id="category1distributionChartContainer"><canvas id="category1distributionChart"></canvas></div>
            <div class="chart-container" id="category2distributionChartContainer"><canvas id="category2distributionChart"></canvas></div>
            <div class="chart-container" id="category3distributionChartContainer"><canvas id="category3distributionChart"></canvas></div>
            <div class="chart-container" id="participantActivityChartContainer"><canvas id="participantActivityChart"></canvas></div>
        </div>
    </div>
    <div id="browser-content" style="display:block;">
        <div id="browser-html-wrapper">{browser_html}</div>
    </div>
    <div id="detailsModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h4 id="modalTitle">Details</h4>
                <span class="close-button" onclick="closeModal('detailsModal')">&times;</span>
            </div>
            <div class="modal-body" id="modalBodyContent"></div>
        </div>
    </div>
</div>
<script>
    const initialAnalysisData = {analysis_data_json_placeholder};
    const initialHierarchicalData = {hierarchical_data_json_placeholder};
    const participantSegmentData = {participant_data_json_placeholder};
    const participantList = {participant_list_json_placeholder};
    const coderList = {coder_list_json_placeholder};
    const config = {config_json_placeholder};
    const allSegmentsRaw = Object.values(participantSegmentData).flat();
    
    let charts = {{}};
    let currentParticipant = '__ALL__';
    let currentCoder = '__ALL__';
    let chartsInitialised = false;
    let choicesParticipant, choicesCoder;

    function escapeHTML(str) {{
        if (typeof str !== 'string') return '';
        return str.replace(/[&<>"']/g, match => ({{
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }}[match]));
    }}

    const themeToggleBtn = document.getElementById('themeToggleBtn');
    function applyTheme(theme) {{
        if (theme === 'light') {{
            document.body.classList.remove('dark-mode');
            themeToggleBtn.textContent = 'Switch to Dark Theme';
        }} else {{
            document.body.classList.add('dark-mode');
            themeToggleBtn.textContent = 'Switch to Light Theme';
        }}
        const isDarkMode = document.body.classList.contains('dark-mode');
        const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)';
        const ticksColor = isDarkMode ? '#e2e2e2' : '#212529';
        Chart.defaults.color = ticksColor;
        Chart.defaults.scale.grid.color = gridColor;
        Chart.defaults.scale.ticks.color = ticksColor;
    }}

    themeToggleBtn.addEventListener('click', () => {{
        const newTheme = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        if (chartsInitialised) {{
             applyFiltersAndUpdateViews();
        }}
    }});

    function renderCodeBrowser(data) {{
        const wrapper = document.getElementById('browser-html-wrapper');
        if (!wrapper) return;
        let html = "";
        const sortedCategories = Object.keys(data).sort();
        if (sortedCategories.length === 0) {{
            wrapper.innerHTML = `<p class='no-data-message'>No codes or segments found for the current filter.</p>`;
            return;
        }}
        sortedCategories.forEach(categoryName => {{
            const codesInCategory = data[categoryName];
            const sortedCodeNames = Object.keys(codesInCategory).sort();
            const categorySegmentCount = Object.values(codesInCategory).reduce((sum, segments) => sum + segments.length, 0);
            html += `<div class="category" onclick="toggleCodeList(this)">${{escapeHTML(categoryName)}}<span class="count">(${{categorySegmentCount}} segments)</span></div><div class="code-list">`;
            sortedCodeNames.forEach(codeName => {{
                const segments = codesInCategory[codeName];
                html += `<div class="code" onclick="toggleCodeList(this)">${{escapeHTML(codeName)}}<span class="count">(${{segments.length}} segments)</span></div><div class="segment-list">`;
                const sortedSegments = [...segments].sort((a, b) => (a.coder + a.participant + a.text).localeCompare(b.coder + b.participant + b.text));
                sortedSegments.forEach(seg => {{
                    html += `<div class="segment">
                        <div class="segment-meta"><span class="segment-coder">${{escapeHTML(seg.coder)}}</span> | <span class="segment-participant">${{escapeHTML(seg.participant)}}</span></div>
                        <span class="segment-text">"${{escapeHTML(seg.text)}}"</span>
                        <div class="segment-memo ${{seg.memo ? '' : 'empty-memo'}}">${{escapeHTML(seg.memo)}}</div>
                    </div>`;
                }});
                html += `</div>`;
            }});
            html += `</div>`;
        }});
        wrapper.innerHTML = html;
    }}

    function buildHierarchicalDataFromSegments(segments) {{
        const data = {{}};
        segments.forEach(seg => {{
            if (!data[seg.category]) data[seg.category] = {{}};
            if (!data[seg.category][seg.code]) data[seg.category][seg.code] = [];
            data[seg.category][seg.code].push(seg);
        }});
        return data;
    }}

    function recalculateAnalysisData(segments, {{participant, coder}}) {{
        if (segments.length === 0) {{
            return {{ allCategories: [], allCategoryCodeCounts: {{}} }};
        }}
        const newAnalysisData = {{}};
        const allCategories = [...new Set(segments.map(s => s.category))].sort();
        newAnalysisData.allCategories = allCategories;

        let titleSuffix = '';
        if (participant !== '__ALL__' && coder !== '__ALL__') titleSuffix = `(for ${{escapeHTML(participant)}} & ${{escapeHTML(coder)}})`;
        else if (participant !== '__ALL__') titleSuffix = `(for ${{escapeHTML(participant)}})`;
        else if (coder !== '__ALL__') titleSuffix = `(for ${{escapeHTML(coder)}})`;
        else titleSuffix = '(by Unique Participant)';

        const isFiltered = participant !== '__ALL__' || coder !== '__ALL__';
        
        const catCounts = segments.reduce((acc, seg) => {{
            const key = seg.category;
            if (!acc[key]) acc[key] = new Set();
            acc[key].add(isFiltered ? JSON.stringify(seg) : seg.participant);
            return acc;
        }}, {{}});
        const sortedCatCounts = Object.entries(catCounts).map(([k, v]) => ([k, v.size])).sort((a, b) => b[1] - a[1]);
        newAnalysisData.categoryDistribution = {{
            labels: sortedCatCounts.map(e => e[0]),
            data: sortedCatCounts.map(e => e[1]),
            title: `Category Distribution ${{titleSuffix}}`
        }};

        newAnalysisData.allCategoryCodeCounts = {{}};
        allCategories.forEach(cat => {{
            const catSegments = segments.filter(s => s.category === cat);
            const codeCounts = catSegments.reduce((acc, seg) => {{
                const key = seg.code;
                if (!acc[key]) acc[key] = new Set();
                acc[key].add(isFiltered ? JSON.stringify(seg) : seg.participant);
                return acc;
            }}, {{}});
            const sortedCodeCounts = Object.entries(codeCounts).map(([k, v]) => ([k, v.size])).sort((a, b) => b[1] - a[1]);
            if (sortedCodeCounts.length > 0) {{
                newAnalysisData.allCategoryCodeCounts[cat] = {{
                    labels: sortedCodeCounts.map(e => e[0]),
                    data: sortedCodeCounts.map(e => e[1]),
                }};
            }}
        }});
        
        newAnalysisData.defaultCategoryForBreakdown = initialAnalysisData.defaultCategoryForBreakdown;
        const getChartData = (pattern, title) => {{
            const match = allCategories.find(c => c.toLowerCase() === pattern.toLowerCase()) || allCategories.find(c => c.toLowerCase().includes(pattern.toLowerCase()));
            if (match && newAnalysisData.allCategoryCodeCounts[match]) {{
                return {{ categoryName: match, ...newAnalysisData.allCategoryCodeCounts[match], title: `${{title}} ${{titleSuffix}}` }};
            }}
            return null;
        }};

        newAnalysisData.category1distribution = getChartData(config.CATEGORY_1_FOR_CHART, config.CATEGORY_1_FOR_CHART_TITLE);
        newAnalysisData.category2distribution = getChartData(config.CATEGORY_2_FOR_CHART, config.CATEGORY_2_FOR_CHART_TITLE);
        newAnalysisData.category3distribution = getChartData(config.CATEGORY_3_FOR_CHART, config.CATEGORY_3_FOR_CHART_TITLE) || getChartData(config.CATEGORY_3_FOR_CHART_FALLBACK, config.CATEGORY_3_FOR_CHART_FALLBACK_TITLE);
        
        newAnalysisData.participantActivity = isFiltered ? null : initialAnalysisData.participantActivity;

        return newAnalysisData;
    }}

    function applyFiltersAndUpdateViews() {{
        currentParticipant = choicesParticipant.getValue(true) || '__ALL__';
        currentCoder = choicesCoder.getValue(true) || '__ALL__';

        let relevantSegments = allSegmentsRaw;
        if (currentParticipant !== '__ALL__') {{
            relevantSegments = relevantSegments.filter(s => s.participant === currentParticipant);
        }}
        if (currentCoder !== '__ALL__') {{
            relevantSegments = relevantSegments.filter(s => s.coder === currentCoder);
        }}

        const newHierarchicalData = buildHierarchicalDataFromSegments(relevantSegments);
        renderCodeBrowser(newHierarchicalData);

        const newAnalysisData = recalculateAnalysisData(relevantSegments, {{ participant: currentParticipant, coder: currentCoder }});
        
        Object.values(charts).forEach(chart => chart.destroy());
        charts = {{}};

        if (document.getElementById('analysis-section').style.display === 'block') {{
             renderAllCharts(newAnalysisData);
        }} else {{
            chartsInitialised = false;
        }}
    }}

    document.addEventListener('DOMContentLoaded', () => {{
        const savedTheme = localStorage.getItem('theme') || 'dark';
        applyTheme(savedTheme);

        const participantSelect = document.getElementById('participantFilter');
        const coderSelect = document.getElementById('coderFilter');

        const choicesOptions = {{
            shouldSort: true,
            removeItemButton: true,
            searchResultLimit: 10,
        }};

        choicesParticipant = new Choices(participantSelect, {{ ...choicesOptions, placeholder: true, placeholderValue: 'Filter by Participant' }});
        choicesParticipant.setChoices([
            {{ value: '__ALL__', label: 'All', selected: true }},
            ...participantList.map(p => ({{ value: p, label: p }}))
        ]);

        choicesCoder = new Choices(coderSelect, {{ ...choicesOptions, placeholder: true, placeholderValue: 'Filter by Coder' }});
        choicesCoder.setChoices([
            {{ value: '__ALL__', label: 'All', selected: true }},
            ...coderList.map(c => ({{ value: c, label: c }}))
        ]);
        
        participantSelect.addEventListener('change', applyFiltersAndUpdateViews);
        coderSelect.addEventListener('change', applyFiltersAndUpdateViews);

        document.getElementById('toggleBrowserBtn').addEventListener('click', () => {{
            document.getElementById('browser-content').style.display = 'block';
            document.getElementById('analysis-section').style.display = 'none';
            document.querySelectorAll('.browser-control').forEach(btn => btn.style.display = 'inline-block');
        }});

        document.getElementById('toggleAnalysisBtn').addEventListener('click', () => {{
            document.getElementById('browser-content').style.display = 'none';
            document.getElementById('analysis-section').style.display = 'block';
            document.querySelectorAll('.browser-control').forEach(btn => btn.style.display = 'none');
            if (!chartsInitialised) {{
                applyFiltersAndUpdateViews();
                chartsInitialised = true;
            }}
        }});
        renderCodeBrowser(initialHierarchicalData);
    }});

    function renderAllCharts(data) {{
        if (!data || typeof Chart === 'undefined') {{
            document.querySelector('#analysis-section .charts-grid').innerHTML = "<p class='no-data-message'>No analysis data or Chart.js not loaded.</p>";
            return;
        }}

        renderBarChart('categoryDistributionChart', data.categoryDistribution, (e, els, chart) => {{
            if (els.length > 0) updateDynamicCategoryBreakdown(data.categoryDistribution.labels[els[0].index], data);
        }});

        const dynamicContainer = document.getElementById('dynamicCategoryBreakdownChartContainer');
        const selector = document.getElementById('categorySelector');
        if (data.allCategories && data.allCategories.length > 0) {{
            dynamicContainer.style.display = 'flex';
            selector.innerHTML = '';
            let hasOptions = false;
            data.allCategories.forEach(cat => {{
                if (data.allCategoryCodeCounts[cat]) {{
                    const option = document.createElement('option');
                    option.value = cat;
                    option.textContent = cat;
                    selector.appendChild(option);
                    hasOptions = true;
                }}
            }});
            selector.onchange = (e) => updateDynamicCategoryBreakdown(e.target.value, data);
            if (hasOptions) {{
                 let defaultCat = data.defaultCategoryForBreakdown;
                 if (!defaultCat || !data.allCategoryCodeCounts[defaultCat]) {{
                    defaultCat = selector.options[0]?.value;
                 }}
                 if (defaultCat) {{
                    selector.value = defaultCat;
                    updateDynamicCategoryBreakdown(defaultCat, data);
                 }}
            }} else {{ updateDynamicCategoryBreakdown(null, data); }}
        }} else {{
            dynamicContainer.style.display = 'none';
        }}

        const setupChart = (chartId, chartData) => {{
            const container = document.getElementById(chartId + 'Container');
            if (chartData) {{
                container.style.display = 'flex';
                const catName = chartData.categoryName;
                renderBarChart(chartId, chartData, (e, els, chart) => handleChartCodeClick(e, els, chart, catName));
            }} else {{
                container.style.display = 'none';
            }}
        }};

        setupChart('category1distributionChart', data.category1distribution);
        setupChart('category2distributionChart', data.category2distribution);
        setupChart('category3distributionChart', data.category3distribution);

        const participantContainer = document.getElementById('participantActivityChartContainer');
        if (data.participantActivity) {{
            participantContainer.style.display = 'flex';
            renderBarChart('participantActivityChart', data.participantActivity, (e, els, chart) => handleParticipantChartClick(e, els, chart));
        }} else {{
            participantContainer.style.display = 'none';
        }}
    }}

    function renderBarChart(canvasId, chartInfo, onClickCallback) {{
         destroyChart(canvasId);
         const container = document.getElementById(canvasId + 'Container');
         const canvas = document.getElementById(canvasId);
         if (!container || !canvas) return;
         const titleForChart = chartInfo ? chartInfo.title : "Chart";
         container.style.display = 'flex';
         canvas.style.display = 'block';
         container.querySelectorAll('.no-data-message').forEach(el => el.remove());

         if (!chartInfo || !chartInfo.labels || chartInfo.labels.length === 0) {{
             canvas.style.display = 'none';
             if (!container.querySelector('.no-data-message')) {{
                const noDataP = document.createElement('p');
                noDataP.className = 'no-data-message';
                noDataP.textContent = `No data available for: ${{titleForChart}}`;
                container.appendChild(noDataP);
             }}
             return;
         }}
         const chartConfig = {{ type: 'bar', data: {{ labels: chartInfo.labels, datasets: [{{ label: titleForChart, data: chartInfo.data, backgroundColor: getRandomColorArray(chartInfo.labels.length), borderWidth: 1 }}] }}, options: commonChartOptions(titleForChart, true, onClickCallback) }};
         charts[canvasId] = new Chart(canvas.getContext('2d'), chartConfig);
    }}
    
    function updateDynamicCategoryBreakdown(categoryName, currentAnalysisData) {{
         const chartId = 'dynamicCategoryBreakdownChart';
         destroyChart(chartId);
         const container = document.getElementById(chartId + 'Container');
         const canvas = document.getElementById(chartId);
         const controlsDiv = container.querySelector('.dynamic-chart-controls');
         container.querySelectorAll('.no-data-message').forEach(el => el.remove());

         if (!categoryName || !currentAnalysisData.allCategoryCodeCounts[categoryName]) {{
             canvas.style.display = 'none';
             controlsDiv.style.visibility = 'hidden';
             const noDataP = document.createElement('p');
             noDataP.className = 'no-data-message';
             noDataP.textContent = `Select a category to see its breakdown.`;
             container.appendChild(noDataP);
             return;
         }}
         
         canvas.style.display = 'block';
         controlsDiv.style.visibility = 'visible';
         const chartData = currentAnalysisData.allCategoryCodeCounts[categoryName];
         const title = `Code Breakdown for: ${{escapeHTML(categoryName)}}`;
         charts[chartId] = new Chart(canvas.getContext('2d'), {{ type: 'bar', data: {{ labels: chartData.labels, datasets: [{{ label: title, data: chartData.data, backgroundColor: getRandomColorArray(chartData.labels.length), borderWidth: 1 }}] }}, options: commonChartOptions(title, true, (e, els, chart) => handleChartCodeClick(e, els, chart, categoryName)) }});
         const selector = document.getElementById('categorySelector');
         if(selector && selector.value !== categoryName) {{ selector.value = categoryName; }}
    }}

    function destroyChart(chartId) {{ if (charts[chartId]) {{ charts[chartId].destroy(); delete charts[chartId]; }} }}
    
    function getRandomColorArray(count) {{
        const colors = ['rgba(88, 166, 255, 0.8)','rgba(255, 99, 132, 0.8)','rgba(75, 192, 192, 0.8)','rgba(255, 206, 86, 0.8)','rgba(153, 102, 255, 0.8)','rgba(255, 159, 64, 0.8)','rgba(74, 222, 128, 0.8)','rgba(248, 113, 113, 0.8)'];
        const result = [];
        for (let i = 0; i < count; i++) {{ result.push(colors[i % colors.length]); }}
        return result;
    }}
    
    const tooltipPercentageCallback = {{
        label: function(context) {{
            let label = context.dataset.label || context.label || '';
            if (label) {{ label += ': '; }}
            const value = context.raw || 0;
            label += value;
            const total = context.dataset.data.reduce((sum, val) => sum + val, 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
            if (percentage > 0 || value > 0) {{ label += ` (${{percentage}}%)`; }}
            return label;
        }}
    }};

    const commonChartOptions = (titleText, isBarChart = true, onClickCallback = null) => {{
        const isDarkMode = document.body.classList.contains('dark-mode');
        return {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }},
                title: {{ display: true, text: titleText, font: {{ size: 14 }}, padding: {{ top: 5, bottom: 10 }}, color: isDarkMode ? '#58a6ff' : '#0056b3' }},
                tooltip: {{ callbacks: isBarChart ? undefined : tooltipPercentageCallback }}
            }},
            scales: isBarChart ? {{
                y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }},
                x: {{ ticks: {{ autoSkip: false, maxRotation: 45, minRotation: 30 }} }}
            }} : undefined,
            onClick: onClickCallback ? (e, els) => onClickCallback(e, els, e.chart) : null
        }}
    }};
    
    function handleChartCodeClick(event, elements, chartInstance, categoryName) {{
        if (!elements || elements.length === 0 || !categoryName) return;
        const codeLabel = chartInstance.data.labels[elements[0].index];
        if (codeLabel) showCodeSegmentDetailsModal(categoryName, codeLabel);
    }}

    function handleParticipantChartClick(event, elements, chartInstance) {{
         if (!elements || elements.length === 0) return;
         const participantId = chartInstance.data.labels[elements[0].index];
         if (participantId) showParticipantSegmentDetailsModal(participantId);
    }}

    function showCodeSegmentDetailsModal(category, code) {{
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBodyContent');
        modalTitle.textContent = `Segments for Code: "${{escapeHTML(code)}}" (Category: "${{escapeHTML(category)}}")`;
        modalBody.innerHTML = '';
        let segments = allSegmentsRaw.filter(s => s.category === category && s.code === code);
        if (currentParticipant !== '__ALL__') segments = segments.filter(s => s.participant === currentParticipant);
        if (currentCoder !== '__ALL__') segments = segments.filter(s => s.coder === currentCoder);
        
        if (segments.length > 0) {{
            segments.forEach(seg => modalBody.insertAdjacentHTML('beforeend', createSegmentItemHtml(seg)));
        }} else {{
            modalBody.innerHTML = "<p class='no-data-message'>No segments found for this code with the current filter.</p>";
        }}
        modal.style.display = 'block';
    }}

    function showParticipantSegmentDetailsModal(participantId) {{
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBodyContent');
        modalTitle.textContent = `All Segments for Participant: "${{escapeHTML(participantId)}}"`;
        modalBody.innerHTML = '';
        const segments = participantSegmentData[participantId] || [];
        if (segments.length > 0) {{
             segments.forEach(seg => modalBody.insertAdjacentHTML('beforeend', createSegmentItemHtml(seg, true)));
        }} else {{
             modalBody.innerHTML = "<p class='no-data-message'>No segments found for this participant.</p>";
        }}
        modal.style.display = 'block';
    }}

    function createSegmentItemHtml(seg, showCategory = false) {{
        return `<div class="segment-item">
            <div class="seg-meta">
                <span class="seg-coder">Coder: ${{escapeHTML(seg.coder)}}</span>
                ${{showCategory ? `<span class="seg-category-code"><b>${{escapeHTML(seg.category)}} &gt; ${{escapeHTML(seg.code)}}</b></span>` : ''}}
            </div>
            <p class="seg-text">"${{escapeHTML(seg.text)}}"</p>
            <div class="seg-memo ${{seg.memo ? '' : 'empty-memo'}}">${{escapeHTML(seg.memo)}}</div>
        </div>`;
    }}

    function closeModal(modalId) {{ document.getElementById(modalId).style.display = 'none'; }}
    window.onclick = function(event) {{ if (event.target.id === 'detailsModal') closeModal('detailsModal'); }};
    function toggleCodeList(element) {{ const list = element.nextElementSibling; if (!list) return; const isOpen = list.style.display === 'block'; list.style.display = isOpen ? 'none' : 'block'; element.classList.toggle('open', !isOpen); }}
    function setAllCodeVisibility(visible) {{ const display = visible ? 'block' : 'none'; document.querySelectorAll('#browser-html-wrapper .code-list, #browser-html-wrapper .segment-list').forEach(el => el.style.display = display); document.querySelectorAll('#browser-html-wrapper .category, #browser-html-wrapper .code').forEach(el => el.classList.toggle('open', visible)); }}
    function expandAll() {{ setAllCodeVisibility(true); }}
    function collapseAll() {{ setAllCodeVisibility(false); }}
</script>
</body>
</html>
"""
    browser_html_content = ""
    if hierarchical_data:
        sorted_categories = sorted(hierarchical_data.keys())
        for category_name in sorted_categories:
            codes_in_category = hierarchical_data[category_name]
            sorted_code_names = sorted(codes_in_category.keys())
            category_segment_count = sum(len(segments) for segments in codes_in_category.values())
            safe_category_name = html.escape(str(category_name))
            browser_html_content += f'<div class="category" onclick="toggleCodeList(this)">{safe_category_name}<span class="count">({category_segment_count} segments)</span></div>\n'
            browser_html_content += '<div class="code-list">\n'
            for code_name in sorted_code_names:
                segments = codes_in_category[code_name]
                segment_count = len(segments)
                safe_code_name = html.escape(str(code_name))
                browser_html_content += f'  <div class="code" onclick="toggleCodeList(this)">{safe_code_name}<span class="count">({segment_count} segments)</span></div>\n'
                browser_html_content += '  <div class="segment-list">\n'
                sorted_segments = sorted(
                    segments, key=lambda x: (str(x.get('coder', '')), str(x.get('participant', '')), str(x.get('text', ''))))
                for segment_data in sorted_segments:
                    safe_coder = html.escape(str(segment_data.get('coder', 'N/A')))
                    safe_participant = html.escape(str(segment_data.get('participant', 'N/A')))
                    safe_text = html.escape(str(segment_data.get('text', '')))
                    safe_memo = html.escape(str(segment_data.get('memo', '')))
                    browser_html_content += f'    <div class="segment">\n'
                    browser_html_content += f'      <div class="segment-meta"><span class="segment-coder">{safe_coder}</span> | <span class="segment-participant">{safe_participant}</span></div>\n'
                    browser_html_content += f'      <span class="segment-text">"{safe_text}"</span>\n'
                    browser_html_content += f'      <div class="segment-memo">{safe_memo}</div>\n'
                    browser_html_content += f'    </div>\n'
                browser_html_content += '  </div>\n'
            browser_html_content += '</div>\n'
    else:
        browser_html_content = "<p class='no-data-message'>No code browser data to display.</p>"

    final_html = html_template.format(
        browser_html=browser_html_content,
        analysis_data_json_placeholder=analysis_data_json,
        hierarchical_data_json_placeholder=hierarchical_data_json,
        participant_data_json_placeholder=participant_data_json,
        participant_list_json_placeholder=participant_list_json,
        coder_list_json_placeholder=coder_list_json,
        config_json_placeholder=config_json
    )

    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"\nSuccessfully generated interactive HTML: '{output_filename}'")
    except Exception as e:
        print(f"\nError writing HTML file: {e}")
        traceback.print_exc()


# ==============================================================================
# === Main Execution Block ===
# ==============================================================================
def main():
    print("--- Starting Report Generation ---")

    df_loaded = load_csv_data(CSV_FILENAME)

    df_processed = preprocess_dataframe(df_loaded)

    analysis_data = {}
    hierarchical_data = {}
    participant_segment_data = {}
    participant_list = []
    coder_list = []

    if df_processed is not None and not df_processed.empty:
        print("Building data structures for HTML...")
        hierarchical_data = build_hierarchical_data(df_processed)
        participant_segment_data = build_participant_segment_data(df_processed)
        analysis_data = prepare_analysis_data(df_processed)
        participant_list = sorted(df_processed[PARTICIPANT_COL].dropna().unique().tolist())
        coder_list = sorted(df_processed[CODER_COL].dropna().unique().tolist())
        print("Data preparation complete.")
    else:
        print("Skipping data structure preparation due to preprocessing issues or empty data.")

    has_hierarchical_data = bool(hierarchical_data)
    has_analysis_data = analysis_data and any(
        chart_data and chart_data.get('labels')
        for chart_key, chart_data in analysis_data.items()
        if isinstance(chart_data, dict) and chart_key not in ['allCategoryCodeCounts', 'allCategories']
    )

    if has_hierarchical_data or has_analysis_data:
        print("Generating HTML file...")
        generate_interactive_html(hierarchical_data, analysis_data,
                                  participant_segment_data, HTML_OUTPUT_FILENAME, participant_list, coder_list)
    else:
        print("No hierarchical or sufficient analysis data available to generate a meaningful report.")
        generate_interactive_html({}, {}, {}, HTML_OUTPUT_FILENAME, [], [])

    print("--- Generating HTML finished. ---")

if __name__ == "__main__":
    main()
    sys.exit(0)
# ==============================================================================
# === End of Script ===