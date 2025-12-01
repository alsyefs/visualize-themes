# 📊 Inter-Rater Reliability (IRR) & Codebook Visualizer

This tool automates the process of merging qualitative coding datasets, calculating Inter-Rater Reliability statistics (Cohen's Kappa, F1-Score/Dice, Krippendorff's Alpha), and generating an interactive HTML dashboard for visualization.

## ▶️ How to Run This App

These instructions are compatible with **Windows**, **macOS**, and **Linux**.

### 1. Prerequisites
* **Install Python**: Ensure you have Python installed (version 3.9 or higher is recommended). [Download Python here](https://www.python.org/downloads/).
* **Git (Optional)**: If you are cloning this repository.

### 2. Setup (One-Time Only)

#### Step 1: Prepare Your Data Folders
Before running the script, you must place your files in the correct directories:

| Folder | Required? | Description |
| :--- | :--- | :--- |
| **`irr_input/`** | **YES** | Place your raw codebook CSV files here. <br>• **Minimum:** 1 file (for single-coder visualization).<br>• **Recommended:** 2+ files (to calculate agreement/IRR stats). |
| **`transcripts/`** | *Optional* | Place the original raw text/transcript files (`.txt`) here.<br>• **If Provided:** The app calculates "True Negatives" (silence), making **Cohen's Kappa** mathematically valid.<br>• **If Omitted:** Cohen's Kappa may be reported as "Invalid/Missing" or biased, but **F1-Scores** will still be correct. |
| **`codebook_definitions/`** | *Optional* | Place a CSV or Excel file defining your codes (columns: *Codename*, *Description*, etc.) to include definitions in the report. |

#### Step 2: Open Your Terminal
* **Windows**: Open PowerShell or Command Prompt.
* **macOS**: Open Terminal (Cmd + Space, type "Terminal").
* **Linux**: Open your preferred terminal.

#### Step 3: Create and Activate a Virtual Environment
This keeps your project dependencies isolated.

**Windows:**
```powershell
# Create environment
python -m venv venv

# Activate environment
.\venv\Scripts\activate
```
(Note: If you see a permission error in PowerShell, try `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)

**Linux / macOS:**
```bash
# Create environment
python3 -m venv venv

# Activate environment
source venv/bin/activate
```

#### Step 4: Install Dependencies
```python
pip install -r requirements.txt
```
---
#### 🚀 Running the Analysis
Once your files are in `irr_input` (and optionally `transcripts`), run the main application:
```python
python app.py
```
The script will automatically perform the following 4 steps:
1. **Merge Codebooks**: Combines individual coder files into a master dataset.
2. **Process Agreements**: Identifies overlaps and stitches text segments based on fuzzy matching (configurable in `config.py`).
3. **Calculate Statistics**: Computes F1, Kappa, and Agreement % based on the merged data.
4. **Generate Report**: Specific HTML and Excel outputs are created.
---
#### 📊 Viewing the Results
Navigate to the `output/` folder to find your results:
1. `codes.html` (Main Report):
    - Open this file in any web browser (Chrome, Edge, Safari).
    - **Browser Tab**: View and filter coded segments interactively.
    - **Charts Tab**: Visualize disagreement distributions and coder volume.
    - **Analysis Details Tab**: View the calculated IRR statistics.
        - Note on Kappa: If you did **not** provide transcripts, look for the "Technical Notes" section regarding the "Prevalence Paradox" and why F1-Score might be the preferred metric.
2. `agreements.txt`: A text summary of the statistical scores (useful for copying into academic papers).
3. `merged_irr_data.csv`: The raw dataset used for calculation, showing how segments were merged and aligned.
---
#### ⚙️ Advanced Configuration (`config.py`)
You can modify `config.py` to change how the algorithm handles text:
- `WORDS_OVERLAP_PERCENTAGE` (Default: 0.30): How much text must overlap for two segments to be considered the "same" segment (30%).
- `CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY`:
    - `True` (Default): Ignores "silence" (omissions). Only calculates disagreement if both coders marked the same area but with different codes.
    - `False`: Strict mode. If Coder A marks text and Coder B does not, it counts as a disagreement.
- `ALIGN_SEGMENTS_ACROSS_CODES`:
    - `False` (Default): 'Code A' and 'Code B' are treated as separate rows, even if they cover the same text.
    - `True`: Forces different codes on the same text to be aligned into a single row (creating a direct conflict).