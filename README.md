# Codebook Visualization App

This application provides a suite of tools for qualitative data analysis, designed to work with CSV files exported from **QualCoder**.

---

## 🚀 Main Features

1.  **Interactive HTML Report**: Creates a dynamic HTML report to explore and visualize your qualitative data from a `codebook.csv` file. The report automatically groups codes under their parent categories, includes participant filtering, and generates interactive charts.
2.  **LaTeX Appendix Generation**: Generates a LaTeX table from your codebook data, suitable for an academic paper's appendix. You can choose from multiple formats (Condensed, Very Short, Short, Long).
3.  **Inter-Rater Reliability (IRR) Calculation**: Calculates IRR scores (Fleiss' Kappa or Krippendorff's Alpha) from multiple codebook files. It merges codebooks, marks agreements based on text and subtext matching, and generates a detailed report.
4.  **Codebook Merging**: Merges multiple `codebook.csv` files into a single file.
5.  **Code-Text Merging**: Merges `code_text.csv` files exported from QualCoder.

---

## 📂 Project Structure

```
visualize-themes/
├── app.py                          # Main application entry point
├── create_html_report.py           # HTML report generator
├── create_latex_appendix_of_codebook.py  # LaTeX table generator
├── calculate_irr.py                # Merges codebooks for IRR
├── mark_agreements.py              # Marks agreements in merged IRR data
├── compare_agreement_columns.py    # Calculates and compares agreement scores
├── merge_codebooks.py              # Utility to merge codebooks
├── merge_code_text.py              # Utility to merge code_text files
├── config.py                       # Configuration settings
├── secret.py                       # Chart configuration (project-specific)
├── requirements.txt                # Python dependencies
├── input/                          # Input directory for codebook.csv
├── irr_input/                      # Input directory for IRR calculation files
├── output/                         # Generated reports and files
└── ...
```

---

## ⚙️ Input File Requirements

For the application to work correctly, your `codebook.csv` file **must** adhere to the following structure and formatting rules.

#### 1. File Origin

This application is designed to parse CSV files exported from **QualCoder**. While you can create the CSV manually, using a QualCoder export is highly recommended.

The CSV file must have these headers: `Codename`, `Coded_Memo`, `Coded`, `File`, and `Coder`.

| Codename                   | Coded_Memo                 | Coded                                    | File               | Coder |
| :------------------------- | :------------------------- | :--------------------------------------- | :----------------- | :---- |
| `my-category:some-code`    | A description for this code| "This is a direct quote from the source."| interviews/p01.txt | Saleh |
| `my-category:another-code` |                            | "Another quote for a different code."    | interviews/p01.txt | Saleh |
| `other-topic:third-code`   | A memo for the third code. | "A final quote for another category."    | interviews/p02.txt | Saleh |

#### 2. Code Naming Format

All codes in the `Codename` column **must** be formatted as `category-name:code-name`, with the category and code separated by a colon (`:`).

* Use **kebab-case** for names (all lowercase, with words separated by hyphens).
* **Example:** A code named "Community Support" belonging to the "Social Factors" category should be written as `social-factors:community-support`.

---

## 🔧 Configuration

Before running the application, you may need to adjust settings in the configuration files.

### Chart Configuration

The interactive HTML report can generate up to three special, standalone charts for specific categories. To configure these, edit the `secret.py` file:

```python
CATEGORY_1_FOR_CHART = "your-category-name"
CATEGORY_1_FOR_CHART_TITLE = "Your Chart Title"
# ... repeat for categories 2 and 3
```

### Inter-Rater Reliability (IRR) Calculator

The `calculate_irr.py` script uses `config.py` to identify the correct columns in your CSV files. Ensure these match your data:

* **`INPUT_DIRECTORY`**: The folder where your codebooks are, usually `"irr_input"`.
* **`TEXT_COLUMN`**: The column with the text segment that was coded (e.g., `"Coded"`).
* **`CODE_COLUMN`**: The column with the code name (e.g., `"Codename"`).
* **`CODER_NAME_COLUMN`**: The column identifying the coder (e.g., `"Coder"`).

---

## 📦 Dependencies

This application requires the following Python packages.

* `plotly`
* `pandas==2.2.2`
* `matplotlib`
* `statsmodels`
* `numpy==1.26.4`
* `krippendorff`
* `thefuzz`
* `sentence-transformers`
* `simpledorff`
* `networkx`

---

## ▶️ How to Run This App

Follow the setup steps first. You will only need to do this setup once.

### Setup Steps (1-4)

#### Step 1: Add Your Data File(s)

* **For visualization or the LaTeX appendix:** Place your `codebook.csv` file into the `input` folder.
* **For IRR calculation:** Place *all* codebook CSV files (at least two) from the different coders into the `irr_input` folder.

#### Step 2: Create a Virtual Environment

```bash
python -m venv code
```

#### Step 3: Activate the Environment

* **On Linux or macOS:**
    ```bash
    source code/bin/activate
    ```
* **On Windows (in Command Prompt):**
    ```
    code\Scripts\activate
    ```
* **On Windows (in PowerShell):**
    ```powershell
    code\Scripts\Activate.ps1
    ```

#### Step 4: Install the Requirements

```bash
pip install -r requirements.txt
```

---

### Running the Main Application

Once the setup is complete, run the main application to access all functions.

* **Run the App:**
    ```bash
    python app.py
    ```
* **Choose Your Function:**
    The app will present a menu:
    1.  Generate HTML report
    2.  Merge, mark agreements, and calculate IRR scores
    3.  Create LaTeX appendix of codebook
    4.  Just Merge all codebooks
    5.  Merge code text CSV files
    0.  Exit

---

## 📄 Individual Function Details

#### Option 1: Interactive HTML Report

* **Features:**
    * Hierarchical code browser organized by categories
    * Interactive charts and visualizations
    * Participant and coder filtering
    * Dynamic chart updates based on filters
* **Output:**
    * `output/codes.html`: Main interactive report.

#### Option 2: Merge, Mark Agreements, and Calculate IRR

This option runs a sequence of scripts to perform a full IRR analysis.

1.  **`calculate_irr.py`**: Merges all codebooks from the `irr_input` directory into a single file (`output/merged_irr_data.csv`) and creates a preliminary log (`output/first_merge_notes.txt`).
2.  **`mark_agreements.py`**: Calculates agreement based on direct coding and subtext matching, and adds `_agreement` columns to the `output/merged_irr_data.csv` file.
3.  **`compare_agreement_columns.py`**: Calculates Cohen's Kappa and Krippendorff's Alpha based on the agreement columns and generates a final report (`output/agreements.txt`).

* **Output Files:**
    * `output/merged_irr_data.csv`: A CSV file combining all input codebooks, with agreement columns.
    * `output/first_merge_notes.txt`: A log of the initial merging process.
    * `output/agreements.txt`: A detailed report of the final IRR scores with interpretation.

#### Option 3: LaTeX Appendix Table

* **Choose a Format:**
    * Condensed, Very Short, Short, or Long.
* **Output:**
    * A `.tex` file in the `output` folder (e.g., `output/appendix_codebook_condensed.tex`).

#### Option 4: Just Merge All Codebooks

* Merges all `codebook.csv` files from the `input` directory into a single `input/codebook.csv` file.

#### Option 5: Merge code text CSV files

* Merges `code_text.csv` files (as specified in `config.py`) into `output/merged_code_text.csv`. This is useful for combining data from different QualCoder projects.

---

## 🤔 Troubleshooting

1.  **Missing Dependencies**: Ensure you've activated the virtual environment and installed the requirements.
2.  **File Not Found**: Check that your CSV files are in the correct directories (`input/` or `irr_input/`).
3.  **Column Mismatch**: Verify your CSV has the required columns: `Codename`, `Coded_Memo`, `Coded`, `File`, `Coder`.
4.  **Code Format**: Ensure all codes follow the `category:code` format with kebab-case naming.

For more detailed error messages, check the log files generated in the `output` directory.
