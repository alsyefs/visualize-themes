# ==============================================================================
# 'calculate_irr.py' configuration
# ==============================================================================
INPUT_DIRECTORY = "irr_input"
TEXT_COLUMN = "Coded"
CODE_COLUMN = "Codename"
CODER_NAME_COLUMN = "Coder"

OUTPUT_MERGEED_FILE = 'input/codebook.csv'
OUTPUT_MERGED_IRR_DATA_FILE = 'merged_irr_data.csv'
IRR_AGREEMENT_INPUT_FILE = "output/" + OUTPUT_MERGED_IRR_DATA_FILE
# ==============================================================================
# === Chart Configuration               ========================================
# === EDIT THESE VALUES FOR THE PROJECT ========================================
# ==============================================================================
import secret
CATEGORY_1_FOR_CHART = secret.CATEGORY_1_FOR_CHART
CATEGORY_1_FOR_CHART_TITLE = secret.CATEGORY_1_FOR_CHART_TITLE
CATEGORY_2_FOR_CHART = secret.CATEGORY_2_FOR_CHART
CATEGORY_2_FOR_CHART_TITLE = secret.CATEGORY_2_FOR_CHART_TITLE
CATEGORY_3_FOR_CHART = secret.CATEGORY_3_FOR_CHART
CATEGORY_3_FOR_CHART_TITLE = secret.CATEGORY_3_FOR_CHART_TITLE
CATEGORY_3_FOR_CHART_FALLBACK = secret.CATEGORY_3_FOR_CHART_FALLBACK
CATEGORY_3_FOR_CHART_FALLBACK_TITLE = secret.CATEGORY_3_FOR_CHART_FALLBACK_TITLE
DEFAULT_CATEGORY_FOR_DYNAMIC_CHART = secret.DEFAULT_CATEGORY_FOR_DYNAMIC_CHART

# ==============================================================================
# === Codebook Configuration            ========================================
INPUT_CODE_TEXT_A = "input/"+secret.INPUT_CODE_TEXT_A
INPUT_CODE_TEXT_B = "input/"+secret.INPUT_CODE_TEXT_B

CODEBOOK_A = 'input/'+secret.CODEBOOK_A
CODEBOOK_B = 'input/'+secret.CODEBOOK_B

IRR_AGREEMENT_COLUMNS = secret.IRR_AGREEMENT_COLUMNS
CODERS_COLUMNS = secret.CODERS_COLUMNS
