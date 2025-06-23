import pandas as pd
import html
import re
import os
from collections import defaultdict
import json
import traceback
import config
# # ==============================================================================
# # === Configuration and Constants ===
# # === EDIT THESE VALUES AS NEEDED ===
# # ==============================================================================
# # --- Category Names for Specific Charts (Used to display charts and must be changed according to your category names) ---
# CATEGORY_1_FOR_CHART = 'scammers-origin' # Add the category name here.
# CATEGORY_1_FOR_CHART_TITLE = 'Distribution of Scammer Origins' # Add the title for the chart.
# CATEGORY_2_FOR_CHART = 'sbr-origin' # Add the category name here.
# CATEGORY_2_FOR_CHART_TITLE = 'Distribution of Scam-Baiter Origins' # Add the title for the chart.
# CATEGORY_3_FOR_CHART = 'sbr-target-scam-type' # Add the category name here.
# CATEGORY_3_FOR_CHART_TITLE = 'Distribution of Targeted Scam Types' # Add the title for the chart.
# CATEGORY_3_FOR_CHART_FALLBACK = 'target' # Add the category name here. This supports a broader fallback keyword.
# CATEGORY_3_FOR_CHART_FALLBACK_TITLE = 'Distribution of Targeted Categories' # Add the title for the chart.
# # Search category chart:
# DEFAULT_CATEGORY_FOR_DYNAMIC_CHART = 'sb-challenges' # Default category for dynamic code breakdown chart, change as needed.



# ==============================================================================
# === Inputs & Outputs ===
# ==============================================================================

# --- Configuration ---
CSV_FILENAME = 'input/codebook.csv'
# Output filename as requested
HTML_OUTPUT_FILENAME = 'output/tss_codes.html' 

# --- Original CSV Column Names (Update if your CSV headers are different) ---
ORIG_FILE_COL = 'File'
ORIG_CODER_COL = 'Coder' 
ORIG_CODED_TEXT_COL = 'Coded'
ORIG_CODENAME_COL = 'Codename' # May contain "Category:Code" or just "Code"
ORIG_MEMO_COL = 'Coded_Memo'
# If your CSV might sometimes contain an explicit 'Category' column:
ORIG_CATEGORY_COL_OPTIONAL = 'Category' 

# --- Internal Column Names Used After Processing ---
CAT_COL = 'CategoryInternal'
CODE_COL = 'CodeInternal'
TEXT_COL = 'CodedTextInternal'
MEMO_COL = 'MemoInternal'
PARTICIPANT_COL = 'ParticipantInternal'
CODER_COL = 'CoderNameInternal' # Retained for hierarchical data, not charted

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
    if df is None: return False # Added check for None df
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
    # Ensure the source column exists before applying functions
    if ORIG_CODENAME_COL not in df_ref.columns:
        print(f"Error: Cannot derive categories/codes, missing source column '{ORIG_CODENAME_COL}'.")
        # Create empty columns to prevent later errors, though data might be unusable
        df_ref[CAT_COL] = 'Error' 
        df_ref[CODE_COL] = 'Error'
        return 

    def derive_category_from_codename(codename_val):
        codename_str = str(codename_val).strip()
        parts = codename_str.split(':', 1)
        # Return 'General' if no colon or if part before colon is empty
        return parts[0].strip() if len(parts) > 1 and parts[0].strip() else 'General'

    def derive_code_from_codename(codename_val):
        codename_str = str(codename_val).strip()
        parts = codename_str.split(':', 1)
        # Return part after colon, or full string if no colon. Handle empty part after colon.
        code_part = parts[1].strip() if len(parts) > 1 else codename_str
        return code_part if code_part else 'Unknown Code' # Assign placeholder if derived code is empty
        
    df_ref[CAT_COL] = df_ref[ORIG_CODENAME_COL].apply(derive_category_from_codename)
    df_ref[CODE_COL] = df_ref[ORIG_CODENAME_COL].apply(derive_code_from_codename)

def preprocess_dataframe(df):
    """Applies preprocessing and returns the processed DataFrame or None."""
    if df is None or df.empty: return None
    essential_cols = [ORIG_FILE_COL, ORIG_CODER_COL, ORIG_CODED_TEXT_COL, ORIG_CODENAME_COL, ORIG_MEMO_COL]
    if not validate_required_columns(df, essential_cols): return None
        
    try:
        # Create a copy to avoid modifying the original DataFrame passed to the function
        df_processed = df.copy()

        # 1. Basic Cleaning & Type Handling
        df_processed[ORIG_MEMO_COL] = df_processed[ORIG_MEMO_COL].fillna('')
        df_processed[ORIG_CODED_TEXT_COL] = df_processed[ORIG_CODED_TEXT_COL].astype(str).fillna('')
        df_processed[ORIG_CODER_COL] = df_processed[ORIG_CODER_COL].astype(str).fillna('Unknown Coder')
        df_processed[ORIG_CODENAME_COL] = df_processed[ORIG_CODENAME_COL].astype(str).str.strip()

        # 2. Extract Participant ID
        def extract_participant(filepath):
            if pd.isna(filepath) or not str(filepath).strip():
                return 'unknown_participant'
            filepath_str = str(filepath)
            basename = os.path.basename(filepath_str)
            participant_id = os.path.splitext(basename)[0]
            return participant_id if participant_id else 'unknown_participant'
        df_processed[PARTICIPANT_COL] = df_processed[ORIG_FILE_COL].apply(extract_participant)

        # 3. Derive Category and Code (Handles both cases)
        use_existing_category = False
        if ORIG_CATEGORY_COL_OPTIONAL in df_processed.columns and not df_processed[ORIG_CATEGORY_COL_OPTIONAL].isnull().all():
            df_cat_check = df_processed[ORIG_CATEGORY_COL_OPTIONAL].dropna().astype(str).str.strip()
            if not df_cat_check.empty and df_cat_check.nunique() > 0: use_existing_category = True

        if use_existing_category:
            print(f"Using existing '{ORIG_CATEGORY_COL_OPTIONAL}' column from CSV.")
            df_processed[CAT_COL] = df_processed[ORIG_CATEGORY_COL_OPTIONAL].astype(str).str.strip()
            df_processed[CODE_COL] = df_processed[ORIG_CODENAME_COL].astype(str).str.strip()
        else:
            if ORIG_CATEGORY_COL_OPTIONAL in df_processed.columns: print(f"Found '{ORIG_CATEGORY_COL_OPTIONAL}' column but it's empty/invalid. Deriving from '{ORIG_CODENAME_COL}'.")
            else: print(f"Deriving Category and Code from '{ORIG_CODENAME_COL}' column.")
            define_derived_categories_codes(df_processed) # Modifies df_processed in place

        # Handle potential empty strings after stripping/derivation
        df_processed[CAT_COL] = df_processed[CAT_COL].replace('', 'Unknown Category')
        df_processed[CODE_COL] = df_processed[CODE_COL].replace('', 'Unknown Code')

        # 4. Rename columns to internal standard names
        df_renamed = df_processed.rename(columns={
            ORIG_CODED_TEXT_COL: TEXT_COL,
            ORIG_MEMO_COL: MEMO_COL,
            ORIG_CODER_COL: CODER_COL 
        })

        # 5. Select and Reorder final columns
        final_columns_to_use = [CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, PARTICIPANT_COL, CODER_COL]
        missing_final_cols = [col for col in final_columns_to_use if col not in df_renamed.columns]
        if missing_final_cols:
            print(f"\nError: Internal processing error. Missing columns after processing: {', '.join(missing_final_cols)}")
            return None
            
        df_final = df_renamed[final_columns_to_use].copy()

        # 6. Final Filter: Remove rows with placeholder/empty category or code using correct .str accessor
        # Ensure columns exist before filtering
        if CAT_COL in df_final.columns and CODE_COL in df_final.columns:
            # Create boolean masks for valid rows
            valid_category = (df_final[CAT_COL].notna() & 
                              (df_final[CAT_COL].astype(str).str.strip() != '') & 
                              (df_final[CAT_COL].astype(str).str.strip().str.lower() != 'unknown category'))
            valid_code = (df_final[CODE_COL].notna() &
                          (df_final[CODE_COL].astype(str).str.strip() != '') &
                          (df_final[CODE_COL].astype(str).str.strip().str.lower() != 'unknown code'))
            
            df_final = df_final[valid_category & valid_code]
        else:
             print(f"Error: Cannot perform final filtering, required columns '{CAT_COL}' or '{CODE_COL}' not found.")
             return None # Or handle differently if partial processing is okay

        
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
    if df is None or df.empty: return {}
    data_structure = defaultdict(lambda: defaultdict(list))
    expected_cols = [CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, PARTICIPANT_COL, CODER_COL] 
    if not all(col in df.columns for col in expected_cols): return {} # Error should be caught earlier
        
    for _, row in df.iterrows():
        # Ensure data is JSON serializable 
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
    if df is None or df.empty: return {}
    participant_data = defaultdict(list)
    expected_cols = [PARTICIPANT_COL, CAT_COL, CODE_COL, TEXT_COL, MEMO_COL, CODER_COL] 
    if not all(col in df.columns for col in expected_cols): return {}

    for _, row in df.iterrows():
         participant_id = str(row[PARTICIPANT_COL]) if pd.notna(row[PARTICIPANT_COL]) else 'N/A'
         # Only add segment if participant is known
         if participant_id != 'N/A':
             participant_data[participant_id].append({
                 'category': str(row[CAT_COL]), 'code': str(row[CODE_COL]),
                 'text': str(row[TEXT_COL]), 'memo': str(row[MEMO_COL]),
                 'coder': str(row[CODER_COL]) 
             })
    return dict(participant_data) 

def prepare_analysis_data(df):
    """Prepares aggregated data for analysis charts."""
    if df is None or df.empty: return {}
    analysis_data = {}
    try: # Wrap analysis preparation in try-except
        all_categories = sorted(df[CAT_COL].unique().tolist())
        analysis_data['allCategories'] = all_categories

        # 1. Category distribution
        cat_counts = df[CAT_COL].value_counts()
        analysis_data['categoryDistribution'] = {'labels': cat_counts.index.astype(str).tolist(), 'data': cat_counts.values.tolist(), 'title': 'Overall Category Distribution (Click bar to see codes)'} if not cat_counts.empty else None

        # 2. Data for dynamic code breakdown chart
        analysis_data['allCategoryCodeCounts'] = {}
        if all_categories:
            for cat_name in all_categories:
                code_counts = df[df[CAT_COL] == cat_name][CODE_COL].value_counts()
                if not code_counts.empty: analysis_data['allCategoryCodeCounts'][cat_name] = {'labels': code_counts.index.astype(str).tolist(), 'data': code_counts.values.tolist()}
            default_cat = config.DEFAULT_CATEGORY_FOR_DYNAMIC_CHART if config.DEFAULT_CATEGORY_FOR_DYNAMIC_CHART in all_categories else (all_categories[0] if all_categories else None)
            analysis_data['defaultCategoryForBreakdown'] = next((c for c in [default_cat] + all_categories if c and c in analysis_data['allCategoryCodeCounts']), None)
        else: analysis_data['defaultCategoryForBreakdown'] = None
            
        # Helper to get chart data
        def get_chart_data_for_category(pattern, title_prefix):
            match = next((c for c in all_categories if c.lower() == pattern.lower()), None) or \
                    next((c for c in all_categories if pattern.lower() in c.lower()), None)
            if match and match in analysis_data['allCategoryCodeCounts']:
                chart_data = analysis_data['allCategoryCodeCounts'][match]
                return {'categoryName': match, 'labels': chart_data['labels'], 'data': chart_data['data'], 'title': f'{title_prefix} ("{match}")'}
            print(f"Info: Category for '{title_prefix}' (pattern '{pattern}') not found or has no codes.")
            return None
                
        # 3. Category 1 Distribution
        analysis_data['category1distribution'] = get_chart_data_for_category(config.CATEGORY_1_FOR_CHART, config.CATEGORY_1_FOR_CHART_TITLE)
        # 4. Category 2 Distribution
        analysis_data['category2distribution'] = get_chart_data_for_category(config.CATEGORY_2_FOR_CHART, config.CATEGORY_2_FOR_CHART_TITLE)
        # 5. Category 3 Distribution
        cat_3_data = get_chart_data_for_category(config.CATEGORY_3_FOR_CHART, config.CATEGORY_3_FOR_CHART_TITLE)
        if not cat_3_data: cat_3_data = get_chart_data_for_category(config.CATEGORY_3_FOR_CHART_FALLBACK, config.CATEGORY_3_FOR_CHART_FALLBACK_TITLE) 
        analysis_data['category3distribution'] = cat_3_data
        # 6. Participant activity (Will be clickable)
        participant_counts = df[PARTICIPANT_COL].value_counts()
        analysis_data['participantActivity'] = {'labels': participant_counts.index.astype(str).tolist(), 'data': participant_counts.values.tolist(), 'title': 'Segments per Participant (Click bar)'} if not participant_counts.empty else None
    except Exception as e:
        print(f"Error preparing analysis data: {e}")
        traceback.print_exc()
        return {} # Return empty on error
            
    return analysis_data

# ==============================================================================
# === HTML Generation Function ===
# ==============================================================================
def generate_interactive_html(hierarchical_data, analysis_data, participant_segment_data, output_filename):
    """Generates the final HTML file including browser, analysis charts, and modals."""

    def safe_json_dumps(data, name):
        # Simplified JSON dumping for JS embedding
        try:
            # Directly dump, assume JS can handle it if passed correctly
            return json.dumps(data if data else {}, ensure_ascii=False)
        except Exception as e:
            print(f"Error serializing {name} data to JSON: {e}")
            traceback.print_exc()
            return "{}"

    analysis_data_json = safe_json_dumps(analysis_data, "analysis")
    hierarchical_data_json = safe_json_dumps(hierarchical_data, "hierarchical")
    participant_data_json = safe_json_dumps(participant_segment_data, "participant")

    html_template = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Analysis Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        /* --- Base & Light Theme Styles --- */
        :root {{
            --bg-color: #f8f9fa; --text-color: #212529; --header-color: #0056b3; --border-color: #dee2e6;
            --control-bg: #e9ecef; --control-border: #ced4da; --control-hover-bg: #dee2e6;
            --primary-accent: #007bff; --primary-accent-hover: #0056b3;
            --segment-bg: #ffffff; --segment-border: #e9ecef; --segment-shadow: rgba(0,0,0,0.05);
            --segment-meta-text: #6c757d; --segment-coder-text: #28a745; --segment-participant-text: #dc3545;
            --segment-memo-bg: #f0f8ff; --segment-memo-border: #bde0fe;
            --modal-bg: #fefefe; --modal-shadow: rgba(0,0,0,0.2); --modal-header-border: #ccc;
            --chart-bg: #fdfdfd; --chart-border: #ddd; --chart-title-color: #0056b3;
            --select-bg: #fff; --select-border: #ccc; --select-text: #333;
        }}
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 0; padding:0; line-height: 1.6;
            background-color: var(--bg-color); color: var(--text-color);
            transition: background-color 0.3s, color 0.3s;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; color: var(--header-color); border-bottom: 2px solid var(--border-color); padding-bottom: 10px; margin-bottom: 20px; }}
        .controls {{ margin-bottom: 20px; text-align: center; padding: 10px; background-color: var(--control-bg); border-radius: 5px; }}
        .controls button, .controls select {{ padding: 10px 15px; margin: 5px 8px; cursor: pointer; border-radius: 5px; border: 1px solid var(--primary-accent-hover); background-color: var(--primary-accent); color: white; font-size: 0.95em; vertical-align: middle; transition: background-color 0.2s; }}
        .controls button:hover, .controls select:hover {{ background-color: var(--primary-accent-hover); }}
        .controls select {{ color: var(--select-text); background-color: var(--select-bg); border-color: var(--select-border); min-width: 200px; }}

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

        /* --- Dark Theme Styles --- */
        .dark-mode {{
            --bg-color: #1a1a1a; --text-color: #e2e2e2; --header-color: #58a6ff; --border-color: #3a3a3a;
            --control-bg: #2c2c2c; --control-border: #444; --control-hover-bg: #383838;
            --primary-accent: #0d6efd; --primary-accent-hover: #3b82f6;
            --segment-bg: #252525; --segment-border: #404040; --segment-shadow: rgba(0,0,0,0.2);
            --segment-meta-text: #9e9e9e; --segment-coder-text: #4ade80; --segment-participant-text: #f87171;
            --segment-memo-bg: #1e293b; --segment-memo-border: #3b82f6;
            --modal-bg: #282828; --modal-shadow: rgba(0,0,0,0.4); --modal-header-border: #444;
            --chart-bg: #252525; --chart-border: #404040; --chart-title-color: #58a6ff;
            --select-bg: #333; --select-border: #555; --select-text: #f1f1f1;
        }}
        .dark-mode .close-button {{ color: #888; }}
        .dark-mode .close-button:hover {{ color: #ddd; }}
        .dark-mode .count {{ color: #aaa; }}
    </style>
</head>
<body class="dark-mode">
<div class="container">
    <h1>TSS Code Analysis Report</h1>
    <div class="controls">
        <button id="themeToggleBtn">Switch to Light Theme</button>
        <button id="toggleBrowserBtn">Show Code Browser</button>
        <button id="toggleAnalysisBtn">Show Analysis</button>
        <button onclick="expandAll()" class="browser-control">Expand All Codes</button>
        <button onclick="collapseAll()" class="browser-control">Collapse All Codes</button>
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
        {browser_html}
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
</div> <script>
    // --- Embedded Data ---
    const analysisData = {analysis_data_json_placeholder};
    const hierarchicalData = {hierarchical_data_json_placeholder};
    const participantSegmentData = {participant_data_json_placeholder};

    let charts = {{}}; // Chart instances registry

    // --- Theme Management ---
    const themeToggleBtn = document.getElementById('themeToggleBtn');

    // Function to apply theme based on saved preference or default
    function applyTheme(theme) {{
        if (theme === 'light') {{
            document.body.classList.remove('dark-mode');
            themeToggleBtn.textContent = 'Switch to Dark Theme';
        }} else {{
            document.body.classList.add('dark-mode');
            themeToggleBtn.textContent = 'Switch to Light Theme';
        }}
        // Update Chart.js defaults for the new theme
        const isDarkMode = document.body.classList.contains('dark-mode');
        const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)';
        const ticksColor = isDarkMode ? '#e2e2e2' : '#212529';
        Chart.defaults.color = ticksColor;
        Chart.defaults.scale.grid.color = gridColor;
        Chart.defaults.scale.ticks.color = ticksColor;
    }}

    // Theme toggle event listener
    themeToggleBtn.addEventListener('click', () => {{
        const isDarkMode = document.body.classList.contains('dark-mode');
        const newTheme = isDarkMode ? 'light' : 'dark';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        // Re-render charts to apply new theme colors
        if (chartsInitialised) {{
             Object.values(charts).forEach(chart => chart.destroy());
             charts = {{}};
             renderAllCharts();
        }}
    }});

    // --- Tooltip Callback ---
    const tooltipPercentageCallback = {{
        label: function(context) {{
            let label = context.dataset.label || context.label || '';
            if (label) {{ label += ': '; }}
            let value = 0;
            if (context.parsed && typeof context.parsed.y === 'number') {{ value = context.parsed.y; }}
            else if (typeof context.parsed === 'number') {{ value = context.parsed; }}
            else if (typeof context.raw === 'number') {{ value = context.raw; }}
            label += value;
            const total = context.dataset.data.reduce((sum, val) => sum + val, 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
            if (percentage > 0 || value > 0) {{ label += ` (${{percentage}}%)`; }}
            return label;
        }}
    }};

    // --- Common Chart Options ---
    const commonChartOptions = (titleText, isBarChart = true, onClickCallback = null) => ({{
        responsive: true, maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }},
            title: {{ display: true, text: titleText, font: {{ size: 14, weight: 'normal' }}, padding: {{ top: 5, bottom: 10 }} }},
            tooltip: {{ callbacks: tooltipPercentageCallback }}
        }},
        scales: isBarChart ? {{
            y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }},
            x: {{ ticks: {{ autoSkip: false, maxRotation: 45, minRotation: 30 }} }}
        }} : {{}},
        onClick: onClickCallback
    }});

    // --- getRandomColorArray ---
    function getRandomColorArray(count) {{
        const colors = ['rgba(88, 166, 255, 0.8)','rgba(255, 99, 132, 0.8)','rgba(75, 192, 192, 0.8)','rgba(255, 206, 86, 0.8)','rgba(153, 102, 255, 0.8)','rgba(255, 159, 64, 0.8)','rgba(74, 222, 128, 0.8)','rgba(248, 113, 113, 0.8)', 'rgba(59, 130, 246, 0.8)', 'rgba(234, 179, 8, 0.8)'];
        const result_colors = [];
        for (let i = 0; i < count; i++) {{ result_colors.push(colors[i % colors.length]); }}
        return result_colors;
    }}

    // --- destroyChart ---
    function destroyChart(chartId) {{
        if (charts[chartId]) {{ charts[chartId].destroy(); delete charts[chartId]; }}
    }}

    // --- Modal Functions (No changes here) ---
    function escapeHTML(str) {{
         if (typeof str !== 'string') return '';
         return str.replace(/[&<>"']/g, function (match) {{ return {{'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}}[match]; }});
    }}
    function showCodeSegmentDetailsModal(category, code) {{
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBodyContent');
        if (!modal || !modalTitle || !modalBody) {{ console.error("Modal elements not found"); return; }}

        modalTitle.textContent = `Segments for Code: "${{escapeHTML(code)}}" (Category: "${{escapeHTML(category)}}")`;
        modalBody.innerHTML = ''; // Clear previous content

        if (hierarchicalData && hierarchicalData[category] && hierarchicalData[category][code]) {{
            const segments = hierarchicalData[category][code];
            if (segments.length > 0) {{
                segments.forEach(seg => {{
                    const itemDiv = document.createElement('div'); itemDiv.className = 'segment-item';
                    const metaP = document.createElement('p'); metaP.className = 'seg-meta';
                    const coderSpan = document.createElement('span'); coderSpan.className = 'seg-coder';
                    coderSpan.textContent = `${{seg.coder || 'N/A'}}`;
                    const separatorSpan = document.createTextNode(' | ');
                    const participantSpan = document.createElement('span'); participantSpan.className = 'seg-participant';
                    participantSpan.textContent = `${{seg.participant || 'N/A'}}`;
                    metaP.appendChild(coderSpan); metaP.appendChild(separatorSpan); metaP.appendChild(participantSpan);
                    itemDiv.appendChild(metaP);
                    const textP = document.createElement('p'); textP.className = 'seg-text'; textP.textContent = seg.text || ''; itemDiv.appendChild(textP);
                    const memoText = seg.memo || ''; const memoDiv = document.createElement('div'); memoDiv.className = 'seg-memo';
                    if (memoText.trim() !== '') {{ memoDiv.textContent = memoText; }} else {{ memoDiv.classList.add('empty-memo'); }}
                    itemDiv.appendChild(memoDiv);
                    modalBody.appendChild(itemDiv);
                }});
            }} else {{ modalBody.innerHTML = "<p class='no-data-message'>No segments found for this specific code.</p>"; }}
        }} else {{
            console.error("Could not find data in hierarchicalData for:", category, code);
            modalBody.innerHTML = "<p class='no-data-message'>Could not retrieve segment data (Category or Code not found).</p>";
        }}
        modal.style.display = 'block';
    }}
    function showParticipantSegmentDetailsModal(participantId) {{
        const modal = document.getElementById('detailsModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBodyContent');
        if (!modal || !modalTitle || !modalBody) {{ console.error("Modal elements not found"); return; }}

        modalTitle.textContent = `All Segments for Participant: "${{escapeHTML(participantId)}}"`;
        modalBody.innerHTML = '';

        if (participantSegmentData && participantSegmentData[participantId]) {{
            const segments = participantSegmentData[participantId];
            const groupedSegments = segments.reduce((acc, seg) => {{
                 const key = `${{seg.category || 'Unknown'}} > ${{seg.code || 'Unknown'}}`;
                 if (!acc[key]) {{ acc[key] = []; }} acc[key].push(seg); return acc;
            }}, {{}});

            if (Object.keys(groupedSegments).length > 0) {{
                 Object.keys(groupedSegments).sort().forEach(groupKey => {{
                     const segList = groupedSegments[groupKey];
                     const groupHeader = document.createElement('h5'); groupHeader.textContent = groupKey; groupHeader.style.marginTop = '15px'; groupHeader.style.borderBottom = '1px solid #eee'; groupHeader.style.paddingBottom = '5px';
                     modalBody.appendChild(groupHeader);
                     segList.forEach(seg => {{
                         const itemDiv = document.createElement('div'); itemDiv.className = 'segment-item';
                         const metaP = document.createElement('p'); metaP.className='seg-meta';
                         const coderSpan = document.createElement('span'); coderSpan.className='seg-coder'; coderSpan.textContent = `Coder: ${{seg.coder || 'N/A'}}`;
                         metaP.appendChild(coderSpan); itemDiv.appendChild(metaP);
                         const textP = document.createElement('p'); textP.className = 'seg-text'; textP.textContent = seg.text || ''; itemDiv.appendChild(textP);
                         const memoText = seg.memo || ''; const memoDiv = document.createElement('div'); memoDiv.className = 'seg-memo';
                         if (memoText.trim() !== '') {{ memoDiv.textContent = memoText; }} else {{ memoDiv.classList.add('empty-memo'); }}
                         itemDiv.appendChild(memoDiv); modalBody.appendChild(itemDiv);
                     }});
                 }});
            }} else {{ modalBody.innerHTML = "<p class='no-data-message'>No segments found for this participant.</p>"; }}
        }} else {{
            console.error("Could not find data in participantSegmentData for:", participantId);
            modalBody.innerHTML = "<p class='no-data-message'>Could not retrieve participant segment data.</p>";
        }}
        modal.style.display = 'block';
    }}
    function closeModal(modalId) {{ document.getElementById(modalId).style.display = 'none'; }}
    window.onclick = function(event) {{ const modal = document.getElementById('detailsModal'); if (event.target == modal) {{ closeModal('detailsModal'); }} }}

    // --- Chart Rendering Logic (No structural changes here) ---
    function handleChartCodeClick(event, elements, chartInstance, categoryName) {{
        if (!elements || elements.length === 0 || !categoryName) return;
        try {{
            const clickedIndex = elements[0].index;
            const codeLabel = chartInstance.data.labels ? chartInstance.data.labels[clickedIndex] : null;
            if (codeLabel) {{ showCodeSegmentDetailsModal(categoryName, codeLabel); }}
            else {{ console.error("Could not get code label from clicked chart element."); }}
        }} catch (e) {{ console.error("Error in handleChartCodeClick:", e); }}
    }}
    function handleParticipantChartClick(event, elements, chartInstance) {{
         if (!elements || elements.length === 0) return;
         try {{
             const clickedIndex = elements[0].index;
             const participantId = chartInstance.data.labels ? chartInstance.data.labels[clickedIndex] : null;
             if (participantId) {{ showParticipantSegmentDetailsModal(participantId); }}
             else {{ console.error("Could not get participant ID from clicked chart element."); }}
         }} catch (e) {{ console.error("Error in handleParticipantChartClick:", e); }}
    }}
    function renderBarChart(canvasId, chartInfo, onClickCallback = null) {{
         destroyChart(canvasId);
         const container = document.getElementById(canvasId + 'Container');
         const canvas = document.getElementById(canvasId);
         if (!container || !canvas) {{ console.error('Canvas or container not found for', canvasId); return; }}
         const titleForChart = chartInfo ? chartInfo.title : "Chart";
         container.querySelectorAll('h3.chart-title-custom, p.no-data-message').forEach(el => el.remove());
         if (!container.contains(canvas)) container.appendChild(canvas);
         if (!chartInfo || !chartInfo.labels || chartInfo.labels.length === 0 || !chartInfo.data || chartInfo.data.length === 0) {{
             const titleH3 = document.createElement('h3'); titleH3.className = 'chart-title-custom'; titleH3.style.textAlign = 'center'; titleH3.textContent = titleForChart; container.insertBefore(titleH3, canvas);
             const noDataP = document.createElement('p'); noDataP.className = 'no-data-message'; noDataP.textContent = 'No data available.'; container.appendChild(noDataP);
             canvas.style.display = 'none'; return;
         }}
         canvas.style.display = 'block';
         const chartConfig = {{ type: 'bar', data: {{ labels: chartInfo.labels, datasets: [{{ label: titleForChart, data: chartInfo.data, backgroundColor: getRandomColorArray(chartInfo.labels.length), borderColor: getRandomColorArray(chartInfo.labels.length).map(c => c.replace('0.8', '1')), borderWidth: 1 }}] }}, options: commonChartOptions(titleForChart, true, onClickCallback) }};
         try {{ charts[canvasId] = new Chart(canvas.getContext('2d'), chartConfig); }} catch (e) {{ console.error("Error creating chart:", canvasId, e); container.innerHTML = `<p class='no-data-message'>Error rendering chart: ${{escapeHTML(titleForChart)}}.</p>`; }}
    }}
    let dynamicCategoryBreakdownChartId = 'dynamicCategoryBreakdownChart';
    let currentDynamicCategory = '';
    function updateDynamicCategoryBreakdown(categoryName) {{
         currentDynamicCategory = categoryName; destroyChart(dynamicCategoryBreakdownChartId);
         const container = document.getElementById(dynamicCategoryBreakdownChartId + 'Container'); const canvas = document.getElementById(dynamicCategoryBreakdownChartId); const controlsDiv = container.querySelector('.dynamic-chart-controls');
         const chartTitle = `Code Breakdown for: ${{escapeHTML(categoryName)}}`;
         if (!container || !canvas) {{ return; }}
         container.querySelectorAll('p.no-data-message, h3.chart-title-custom-dynamic').forEach(el => el.remove());
         if (!container.contains(canvas)) container.appendChild(canvas);
         canvas.style.display = 'none';
         const chartDataForDynamic = analysisData.allCategoryCodeCounts ? analysisData.allCategoryCodeCounts[categoryName] : null;
         if (chartDataForDynamic && chartDataForDynamic.labels && chartDataForDynamic.labels.length > 0) {{
             canvas.style.display = 'block';
             charts[dynamicCategoryBreakdownChartId] = new Chart(canvas.getContext('2d'), {{ type: 'bar', data: {{ labels: chartDataForDynamic.labels, datasets: [{{ label: `Codes in ${{escapeHTML(categoryName)}}`, data: chartDataForDynamic.data, backgroundColor: getRandomColorArray(chartDataForDynamic.labels.length), borderWidth: 1 }}] }}, options: commonChartOptions(chartTitle, true, (e, els) => handleChartCodeClick(e, els, charts[dynamicCategoryBreakdownChartId], categoryName)) }});
         }} else {{
             const titleH3 = document.createElement('h3'); titleH3.className = 'chart-title-custom-dynamic'; titleH3.textContent = chartTitle; titleH3.style.textAlign = 'center';
             const noDataMsgP = document.createElement('p'); noDataMsgP.className = 'no-data-message'; noDataMsgP.textContent = `No code breakdown data available for category: "${{escapeHTML(categoryName)}}".`;
             if(controlsDiv) {{ controlsDiv.insertAdjacentElement('afterend', noDataMsgP); controlsDiv.insertAdjacentElement('afterend', titleH3); }} else {{ container.insertBefore(noDataMsgP, canvas); container.insertBefore(titleH3, noDataMsgP); }}
         }}
         const selector = document.getElementById('categorySelector');
         if(selector && selector.value !== categoryName) {{ selector.value = categoryName; }}
    }}
    function renderAllCharts() {{
        if (!analysisData || Object.keys(analysisData).length === 0 || typeof Chart === 'undefined') {{
            document.querySelector('#analysis-section .charts-grid').innerHTML = "<p class='no-data-message'>No analysis data processed or Chart.js not loaded.</p>"; return;
        }}
        if (analysisData.categoryDistribution) {{ renderBarChart('categoryDistributionChart', analysisData.categoryDistribution, (e, els) => {{ if (els.length > 0) updateDynamicCategoryBreakdown(analysisData.categoryDistribution.labels[els[0].index]); }}); }}
        else {{ document.getElementById('categoryDistributionChartContainer').innerHTML = "<p class='no-data-message'>No data for Category Distribution.</p>"; }}
        const categorySelector = document.getElementById('categorySelector'); const dynamicChartContainer = document.getElementById(dynamicCategoryBreakdownChartId + 'Container'); const dynamicControls = dynamicChartContainer.querySelector('.dynamic-chart-controls');
        if (analysisData.allCategories && analysisData.allCategories.length > 0) {{
            categorySelector.innerHTML = ''; let hasValidOptions = false;
            analysisData.allCategories.forEach(cat => {{ if(analysisData.allCategoryCodeCounts && analysisData.allCategoryCodeCounts[cat]) {{ const option = document.createElement('option'); option.value = cat; option.textContent = cat; categorySelector.appendChild(option); hasValidOptions = true; }} }});
            if (hasValidOptions) {{
                if(dynamicControls) dynamicControls.style.display = 'block'; categorySelector.addEventListener('change', (e) => updateDynamicCategoryBreakdown(e.target.value));
                let defaultCat = analysisData.defaultCategoryForBreakdown; if (!defaultCat || !Array.from(categorySelector.options).find(opt => opt.value === defaultCat)) {{ defaultCat = categorySelector.options[0] ? categorySelector.options[0].value : null; }}
                if (defaultCat) {{ categorySelector.value = defaultCat; updateDynamicCategoryBreakdown(defaultCat); }} else {{ updateDynamicCategoryBreakdown(''); }}
            }} else {{ if(dynamicControls) dynamicControls.style.display = 'none'; updateDynamicCategoryBreakdown(''); }}
        }} else {{ if(dynamicControls) dynamicControls.style.display = 'none'; updateDynamicCategoryBreakdown(''); }}
        if (analysisData.category1distribution) {{ const catName = analysisData.category1distribution.categoryName; renderBarChart('category1distributionChart', analysisData.category1distribution, (e, els) => handleChartCodeClick(e, els, charts['category1distributionChart'], catName)); }}
        else {{ document.getElementById('category1distributionChartContainer').innerHTML = "<p class='no-data-message'>No data for Category 1.</p>"; }}
        if (analysisData.category2distribution) {{ const catName = analysisData.category2distribution.categoryName; renderBarChart('category2distributionChart', analysisData.category2distribution, (e, els) => handleChartCodeClick(e, els, charts['category2distributionChart'], catName)); }}
        else {{ document.getElementById('category2distributionChartContainer').innerHTML = "<p class='no-data-message'>No data for Category 2.</p>"; }}
        if (analysisData.category3distribution) {{ const catName = analysisData.category3distribution.categoryName; renderBarChart('category3distributionChart', analysisData.category3distribution, (e, els) => handleChartCodeClick(e, els, charts['category3distributionChart'], catName)); }}
        else {{ document.getElementById('category3distributionChartContainer').innerHTML = "<p class='no-data-message'>No data for Category 3.</p>"; }}
        if (analysisData.participantActivity) {{ renderBarChart('participantActivityChart', analysisData.participantActivity, (e, els) => handleParticipantChartClick(e, els, charts['participantActivityChart'])); }}
        else {{ document.getElementById('participantActivityChartContainer').innerHTML = "<p class='no-data-message'>No data for Participant Activity.</p>"; }}
    }}

    // --- View Toggling and Initialisation ---
    const browserContent = document.getElementById('browser-content'); const analysisSection = document.getElementById('analysis-section'); const browserControls = document.querySelectorAll('.browser-control'); let chartsInitialised = false;
    document.getElementById('toggleBrowserBtn').addEventListener('click', () => {{ browserContent.style.display = 'block'; analysisSection.style.display = 'none'; browserControls.forEach(btn => btn.style.display = 'inline-block'); }});
    document.getElementById('toggleAnalysisBtn').addEventListener('click', () => {{
        browserContent.style.display = 'none'; analysisSection.style.display = 'block'; browserControls.forEach(btn => btn.style.display = 'none');
        if (!chartsInitialised && typeof Chart !== 'undefined') {{ renderAllCharts(); chartsInitialised = true; }}
        else if (typeof Chart === 'undefined') {{ console.error("Chart.js not loaded!"); analysisSection.innerHTML = "<p class='no-data-message'>Error: Chart.js library not loaded.</p>";}}
    }});

    // Set initial state on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {{
        // Apply saved theme or default to dark
        const savedTheme = localStorage.getItem('theme') || 'dark';
        applyTheme(savedTheme);

        browserContent.style.display = 'block';
        analysisSection.style.display = 'none';
        browserControls.forEach(btn => btn.style.display = 'inline-block');
    }});

    function toggleCodeList(element) {{ const list = element.nextElementSibling; if (list && (list.classList.contains('code-list') || list.classList.contains('segment-list'))) {{ const isOpen = list.style.display === 'block'; list.style.display = isOpen ? 'none' : 'block'; element.classList.toggle('open', !isOpen); }} }}
    function setAllCodeVisibility(visible) {{ const displayStyle = visible ? 'block' : 'none'; document.querySelectorAll('#browser-content .code-list, #browser-content .segment-list').forEach(list => list.style.display = displayStyle); document.querySelectorAll('#browser-content .category, #browser-content .code').forEach(element => element.classList.toggle('open', visible)); }}
    function expandAll() {{ setAllCodeVisibility(true); }}
    function collapseAll() {{ setAllCodeVisibility(false); }}
</script>
</body>
</html>
"""
    # Generate Browser HTML part separately for clarity
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
                sorted_segments = sorted(segments, key=lambda x: (str(x.get('coder','')), str(x.get('participant','')), str(x.get('text',''))))
                for segment_data in sorted_segments:
                    safe_coder = html.escape(str(segment_data.get('coder','N/A')))
                    safe_participant = html.escape(str(segment_data.get('participant','N/A')))
                    safe_text = html.escape(str(segment_data.get('text','')))
                    safe_memo = html.escape(str(segment_data.get('memo','')))
                    browser_html_content += f'    <div class="segment">\n'
                    browser_html_content += f'      <div class="segment-meta"><span class="segment-coder">{safe_coder}</span> | <span class="segment-participant">{safe_participant}</span></div>\n'
                    browser_html_content += f'      <span class="segment-text">"{safe_text}"</span>\n'
                    browser_html_content += f'      <div class="segment-memo">{safe_memo}</div>\n'
                    browser_html_content += f'    </div>\n'
                browser_html_content += '  </div>\n'
            browser_html_content += '</div>\n'
    else:
        browser_html_content = "<p class='no-data-message'>No code browser data to display.</p>"

    # Inject dynamic parts into the template
    final_html = html_template.format(
        browser_html=browser_html_content,
        analysis_data_json_placeholder=analysis_data_json,
        hierarchical_data_json_placeholder=hierarchical_data_json,
        participant_data_json_placeholder=participant_data_json
    )

    # Write the final HTML
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
if __name__ == "__main__":
    print("--- Starting Report Generation ---")
    
    # 1. Load Data
    df_loaded = load_csv_data(CSV_FILENAME)
    
    # 2. Preprocess Data
    df_processed = preprocess_dataframe(df_loaded) 
    
    # Initialize data structures
    analysis_data = {} 
    hierarchical_data = {} 
    participant_segment_data = {} 

    # 3. Prepare Data Structures (only if preprocessing succeeded)
    if df_processed is not None and not df_processed.empty:
        print("Building data structures for HTML...")
        hierarchical_data = build_hierarchical_data(df_processed) 
        participant_segment_data = build_participant_segment_data(df_processed)
        analysis_data = prepare_analysis_data(df_processed) 
        print("Data preparation complete.")
    else:
        print("Skipping data structure preparation due to preprocessing issues or empty data.")

    # 4. Check if there's anything to display
    has_hierarchical_data = bool(hierarchical_data)
    has_analysis_data = analysis_data and any(
        chart_data and chart_data.get('labels') 
        for chart_key, chart_data in analysis_data.items() 
        if isinstance(chart_data, dict) and chart_key not in ['allCategoryCodeCounts', 'allCategories'] 
    )

    # 5. Generate HTML
    if has_hierarchical_data or has_analysis_data:
        print("Generating HTML file...")
        generate_interactive_html(hierarchical_data, analysis_data, participant_segment_data, HTML_OUTPUT_FILENAME)
    else:
        print("No hierarchical or sufficient analysis data available to generate a meaningful report.")
        # Generate a basic HTML shell indicating no data
        generate_interactive_html({}, {}, {}, HTML_OUTPUT_FILENAME) 

    print("--- Script finished. ---")