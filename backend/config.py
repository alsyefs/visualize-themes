# backend/config.py
import os
import glob

# ==============================================================================
# 'calculate_irr.py' configuration      ========================================
# ==============================================================================
# (Based on QualCoder):
FILE_COLUMN = "File"
CODER_NAME_COLUMN = "Coder"
TEXT_COLUMN = "Coded"
CODE_ID = "Id"
CODE_COLUMN = "Codename"
MEMO_COLUMN = "Coded_Memo"
# ---------
INPUT_DIRECTORY = "backend/irr_input"
OUTPUT_MERGED_FILE = "backend/input/codebook.csv"
OUTPUT_MERGED_IRR_DATA_FILE = "merged_irr_data.csv"
CODETEXTS_INPUT_DIR = "backend/codetexts"
OUTPUT_DIRECTORY = "backend/output"
IRR_AGREEMENT_INPUT_FILE = OUTPUT_DIRECTORY + "/" + OUTPUT_MERGED_IRR_DATA_FILE
OUTPUT_FILENAME = "agreements.txt"
OUTPUT_DETAILED_AGREEMENT_FILE_PATH = OUTPUT_DIRECTORY + "/" + OUTPUT_FILENAME
CODEBOOK_DEFINITIONS_DIRECTORY = "backend/codebook_definitions"
TRANSCRIPTS_DIRECTORY = "backend/transcripts"
NOTES_FILE = OUTPUT_DIRECTORY + "/" + "first_merge_notes.txt"
HTML_OUTPUT_FILENAME = OUTPUT_DIRECTORY + "/" + "codes.html"
CODETEXT_OUTPUT_FILE = OUTPUT_DIRECTORY + "/" + "merged_code_text.csv"
# ==============================================================================
# === Codebook Configuration            ========================================
# ==============================================================================
# CODEBOOKS_BY_CODERS = secret.CODEBOOKS_BY_CODERS
# Dynamic file loading from INPUT_DIRECTORY
CODEBOOKS_BY_CODERS = []
if os.path.exists(INPUT_DIRECTORY):
    # Get all CSV files in the directory
    _files = [f for f in os.listdir(INPUT_DIRECTORY) if f.lower().endswith(".csv")]
    # Sort them to ensure consistent merge order
    _files.sort()
    # Create full paths
    CODEBOOKS_BY_CODERS = [os.path.join(INPUT_DIRECTORY, f) for f in _files]
else:
    print(f"Warning: Directory '{INPUT_DIRECTORY}' not found.")


# Create the directory if it doesn't exist
os.makedirs(CODETEXTS_INPUT_DIR, exist_ok=True)

CODETEXTS_BY_CODERS = []
if os.path.exists(CODETEXTS_INPUT_DIR):
    _ct_files = [
        f for f in os.listdir(CODETEXTS_INPUT_DIR) if f.lower().endswith(".csv")
    ]
    _ct_files.sort()
    CODETEXTS_BY_CODERS = [os.path.join(CODETEXTS_INPUT_DIR, f) for f in _ct_files]

if not os.path.exists(CODEBOOK_DEFINITIONS_DIRECTORY):
    os.makedirs(CODEBOOK_DEFINITIONS_DIRECTORY, exist_ok=True)
# ==============================================================================
# 'mark_agreements.py' configuration      ========================================
# ==============================================================================
# THRESHOLD: WORDS_OVERLAP_PERCENTAGE=0.3 means they share 30% of unique words.
# This catches "segment vs sub-segment" without being too loose.
# WORDS_OVERLAP_PERCENTAGE=1.0 means exact word match only.
WORDS_OVERLAP_PERCENTAGE = 1  # (Default: 0.3)
# Percentage (0.0 to 1.0) of transcript text assumed to be non-codable (headers, footers, metadata, 'Answer:').
# Example: 0.10 removes 10% of the total word count from the True Negative calculation.
TRANSCRIPT_NON_CODABLE_MARGIN = 0.00
# ==============================================================================
# RESEARCHER STRATEGY TOGGLES
# ==============================================================================
# 1. TEXT ALIGNMENT
# If True, checks for overlapping text across DIFFERENT codes and unifies the text string.
# Example: Coder A marks "Hello World" as Code X. Coder B marks "Hello" as Code Y.
# Result: Both become "Hello World" so they can be compared as the same segment.
# If a Coder A codes a paragraph and Coder B codes just one sentence of it,
# this forces them to be treated as the same segment so their codes can be compared.
ALIGN_SEGMENTS_ACROSS_CODES = True  # (Default: False)

# 2. FILTERING (The "Ignore Silence" Rule)
# If True, filters the dataset to only include text segments that were identified (coded)
# by ALL coders (regardless of the specific code used).
# This effectively ignores "Unitization Errors" (Silence vs Code) and focuses purely on "Classification Agreement".
# Set to True to follow the instruction: "If one coder ignores a code, just ignore it."
# This calculates agreement ONLY on segments where BOTH coders marked something.
# It removes cases where one person coded a segment and the other missed it completely.
CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY = False  # (Default: False)
# WARNING: If STRIJBOS_METHOD is set to 'METHOD_C' (Full List), you likely want
# 'CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY' set to FALSE so that 1-0 disagreements are not filtered out.
# If set to True, it might override Strijbos settings by removing "Omissions".
# If STRIJBOS_METHOD is 'METHOD_A' or 'METHOD_B', this setting has no effect.
# ==============================================================================
# STRIJBOS CALCULATION TOGGLES
# ==============================================================================
# Choose which method to use for the "Agreements.txt" statistical report.
# METHOD_A : Mutual Agreement (Intersection). Excludes 0-0 and 1-0/0-1 mismatches (Strict).
# METHOD_B : Union Agreement. Includes 1-0/0-1 disagreements. Excludes 0-0 (Silence).
# METHOD_C : Full Master List. Includes 0-0 (Silence) as Agreement. (Requires Phase 2 to work).
STRIJBOS_METHOD = "METHOD_A"
# STRIJBOS_METHOD = "METHOD_B"
# STRIJBOS_METHOD = "METHOD_C"
# ==============================================================================
# AGREEMENT CALCULATION MODE
# ==============================================================================
# Determines how agreement is defined for statistics and the visual report.
# 1 = STANDARD (Exact Match):
#     Coders must select the exact same Code ID (e.g., "Emotions: Joy" vs "Emotions: Joy").
#     "Emotions: Joy" vs "Emotions: Happy" is a DISAGREEMENT.
#
# 2 = WEIGHTED (Category/Hierarchy Match):
#     Coders must select the same Category (e.g., "Emotions").
#     "Emotions: Joy" vs "Emotions: Happy" is a PARTIAL AGREEMENT (Counted as agreement for Kappa/F1).
#     Visuals will show a "Partial Agreement" icon for these items.
#
# Any other value will default to 1 (Standard).
AGREEMENT_CALCULATION_MODE = 1  # (Default: 1)

# ==============================================================================
# Reference: Methodological issues in developing a multi-dimensional coding procedure for small-group chat communication
# ==============================================================================
# Citation:
# Title: "Methodological issues in developing a multi-dimensional coding procedure for small-group chat communication"
# Author: Jan Willem Strijbos, Gerry Stahl
# Journal: International Journal of Human-Computer Studies, Volume 65, Issue 7, July 2007, Pages 582-591
# DOI: 10.1016/j.ijhcs.2007.03.005
# Link: (https://doi.org/10.1016/j.learninstruc.2007.03.005)
# Page: 399
# Quote:
# """
# (a) Include only units coded by both coders (exclude units with missing values);
# (b) Categorise missing values as ‘no code’ and include this category;
# (c) Categorise missing values and non-coded units as ‘no code’ and include this category.
# """
