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
INPUT_DIRECTORY = "irr_input"
OUTPUT_MERGED_FILE = "input/codebook.csv"
OUTPUT_MERGED_IRR_DATA_FILE = "merged_irr_data.csv"
IRR_AGREEMENT_INPUT_FILE = "output/" + OUTPUT_MERGED_IRR_DATA_FILE
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

# Dynamic Configuration for Codetexts
CODETEXTS_INPUT_DIR = "codetexts"

# Create the directory if it doesn't exist
os.makedirs(CODETEXTS_INPUT_DIR, exist_ok=True)

CODETEXTS_BY_CODERS = []
if os.path.exists(CODETEXTS_INPUT_DIR):
    _ct_files = [
        f for f in os.listdir(CODETEXTS_INPUT_DIR) if f.lower().endswith(".csv")
    ]
    _ct_files.sort()
    CODETEXTS_BY_CODERS = [os.path.join(CODETEXTS_INPUT_DIR, f) for f in _ct_files]

# Directory for Codebook Definitions (Excel/CSV files)
CODEBOOK_DEFINITIONS_DIRECTORY = "codebook_definitions"
if not os.path.exists(CODEBOOK_DEFINITIONS_DIRECTORY):
    os.makedirs(CODEBOOK_DEFINITIONS_DIRECTORY, exist_ok=True)
# ==============================================================================
# 'mark_agreements.py' configuration      ========================================
# ==============================================================================
# THRESHOLD: WORDS_OVERLAP_PERCENTAGE=0.3 means they share 30% of unique words.
# This catches "segment vs sub-segment" without being too loose.
WORDS_OVERLAP_PERCENTAGE = 0.30
TRANSCRIPTS_DIRECTORY = "transcripts"
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
ALIGN_SEGMENTS_ACROSS_CODES = False  # (Default: False)

# 2. FILTERING (The "Ignore Silence" Rule)
# If True, filters the dataset to only include text segments that were identified (coded)
# by ALL coders (regardless of the specific code used).
# This effectively ignores "Unitization Errors" (Silence vs Code) and focuses purely on "Classification Agreement".
# Set to True to follow the instruction: "If one coder ignores a code, just ignore it."
# This calculates agreement ONLY on segments where BOTH coders marked something.
# It removes cases where one person coded a segment and the other missed it completely.
CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY = True  # (Defualt: False)
