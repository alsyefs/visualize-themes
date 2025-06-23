# ==============================================================================
# === Chart Configuration ===
# === EDIT THESE VALUES FOR YOUR PROJECT ===
# ==============================================================================

# --- Category Names for Specific Charts ---
# The script will create up to three special, standalone charts based on the
# category names you provide here.

# Chart 1 Settings
CATEGORY_1_FOR_CHART = 'scammers-origin'
CATEGORY_1_FOR_CHART_TITLE = 'Distribution of Scammer Origins'

# Chart 2 Settings
CATEGORY_2_FOR_CHART = 'sbr-origin'
CATEGORY_2_FOR_CHART_TITLE = 'Distribution of Scam-Baiter Origins'

# Chart 3 Settings
CATEGORY_3_FOR_CHART = 'sbr-target-scam-type'
CATEGORY_3_FOR_CHART_TITLE = 'Distribution of Targeted Scam Types'
CATEGORY_3_FOR_CHART_FALLBACK = 'target' # Supports a broader fallback keyword.
CATEGORY_3_FOR_CHART_FALLBACK_TITLE = 'Distribution of Targeted Categories'

# --- Default Category for Interactive Breakdown Chart ---
DEFAULT_CATEGORY_FOR_DYNAMIC_CHART = 'sb-challenges'