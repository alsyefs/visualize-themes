# Codebook Visualization App

This application provides three main functionalities for qualitative data analysis:

1.  It creates an interactive HTML report to help you explore and visualize your qualitative data from a `codebook.csv` file. The report automatically groups all codes under their parent category for easy navigation and includes participant filtering.
2.  It generates a LaTeX table from the same codebook data, suitable for use in an academic paper's appendix.
3.  It calculates inter-rater reliability (IRR) scores (Fleiss' Kappa or Krippendorff's Alpha) from multiple codebook files using advanced fuzzy matching algorithms.

## Project Structure

```
visualize-themes/
├── app.py                          # Main application entry point
├── create_html_report.py           # HTML report generator
├── create_latex_appendix_of_codebook.py  # LaTeX table generator
├── calculate_irr.py                # Inter-rater reliability calculator
├── merge_codebooks.py              # Codebook merging utility
├── config.py                       # Configuration settings
├── secret.py                       # Chart configuration (project-specific)
├── requirements.txt                # Python dependencies
├── input/                          # Main input directory for codebook.csv
├── irr_input/                      # Input directory for IRR calculation files
├── output/                         # Generated reports and files
├── code/                           # Virtual environment directory
└── notes/                          # Additional documentation
```

## Important: Input File Requirements

For the application to work correctly, your `codebook.csv` file **must** adhere to the following structure and formatting rules.

#### 1. File Origin

This application is specifically designed to parse CSV files exported from **QualCoder**. While you can create the CSV manually, using a QualCoder export is highly recommended.

The CSV file must have at least these headers: `Codename`, `Coded_Memo`, `Coded`, `File`, and `Coder`. The structure should look like this:

| Codename                  | Coded_Memo                  | Coded                                      | File               | Coder |
| ------------------------- | --------------------------- | ------------------------------------------ | ------------------ | ----- |
| `my-category:some-code`   | A description for this code | "This is a direct quote from the source."  | interviews/p01.txt | Saleh |
| `my-category:another-code`|                             | "Another quote for a different code."      | interviews/p01.txt | Saleh |
| `other-topic:third-code`  | A memo for the third code.  | "A final quote for another category."      | interviews/p02.txt | Saleh |

#### 2. Code Naming Format

All codes in the `Codename` column **must** be formatted as `category-name:code-name`, with the category and code separated by a colon (`:`).

* It is required to use **kebab-case** for names (all lowercase, with words separated by hyphens).
* **Example:** A code named "Community Support" belonging to the "Social Factors" category should be written as `social-factors:community-support`.

---
## Configuring the Analysis and IRR

Before running the applications, you may need to adjust settings in the configuration files.

### **Chart Configuration**

The interactive HTML report can generate up to three special, standalone charts for specific categories you want to highlight. To configure these, edit the `secret.py` file:

```python
CATEGORY_1_FOR_CHART = "your-category-name"
CATEGORY_1_FOR_CHART_TITLE = "Your Chart Title"
# ... repeat for categories 2 and 3
```

### **Inter-Rater Reliability (IRR) Calculator**

The `calculate_irr.py` script uses `config.py` to identify the correct columns in your CSV files. Ensure these match your data:
* `INPUT_DIRECTORY`: The folder where your codebooks are, usually `"irr_input"`.
* `TEXT_COLUMN`: The column with the text segment that was coded (e.g., `"Coded"`).
* `CODE_COLUMN`: The column with the code name (e.g., `"Codename"`).
* `CODER_NAME_COLUMN`: The column identifying the coder (e.g., `"Coder"`).

### **Advanced IRR Matching**

The IRR calculator uses sophisticated matching algorithms:
- **Fuzzy Text Matching**: Compares text segments using similarity ratios and substring relationships
- **Keyword-Based Matching**: Extracts key terms and matches based on shared keywords
- **Code Matching**: Compares code categories and names using fuzzy matching

---
## Dependencies

This application requires the following Python packages:
- `plotly` - Interactive charts and visualizations
- `pandas==2.2.2` - Data manipulation and analysis
- `matplotlib` - Additional plotting capabilities
- `statsmodels` - Statistical analysis for IRR calculations
- `numpy==1.26.4` - Numerical computing
- `krippendorff` - Krippendorff's Alpha calculation
- `thefuzz` - Fuzzy string matching
- `sentence-transformers` - Semantic similarity calculations

---
## How to Run This App

Follow the setup steps first. You will only need to do this setup once.

### **Setup Steps (1-4)**

#### **Step 1: Add Your Data File(s)**

* **For visualization or the LaTeX appendix:** Place your `codebook.csv` file into the `input` folder.
* **For IRR calculation:** Place *all* codebook CSV files (at least two) from the different coders into the `irr_input` folder.

#### **Step 2: Create a Virtual Environment**

Create an isolated environment for the app. In your terminal or command prompt, run:
```
python -m venv code
```

#### **Step 3: Activate the Environment**

Activate the environment you just created. **You only need to run the one command that matches your system.**

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

*(After activating, you should see `(code)` at the beginning of your command prompt.)*

#### **Step 4: Install the Requirements**

With the environment active, install the necessary Python packages by running:
```
pip install -r requirements.txt
```
---

### **Running the Main Application**

Once the setup is complete, you can run the main application which provides access to all three functions.

#### **Main Application Interface**

* **Run the App:**
    ```
    python app.py
    ```

* **Choose Your Function:**
    The app will present a menu with four options:
    1. Generate HTML report
    2. Create LaTeX appendix of codebook
    3. Calculate Inter-Rater Reliability (IRR)
    4. Exit

---

### **Individual Function Details**

#### **Option 1: Interactive HTML Report**

This is the main application for data visualization with advanced features.

* **Features:**
    - Hierarchical code browser organized by categories
    - Interactive charts and visualizations
    - Participant filtering dropdown
    - Dynamic chart updates based on participant selection
    - Code frequency analysis
    - Participant-specific segment views

* **View Your Report:**
    Navigate to the **`output`** folder and double-click the HTML file to open it in your web browser.

* **Output Files:**
    - `codes.html` - Main interactive report
    - Participant-specific HTML files (e.g., `tss_codes_saleh.html`)

#### **Option 2: LaTeX Appendix Table**

This script is for academic use. It takes your codebook and generates a `.tex` file.

* **Choose a Format:**
    The script will prompt you to select a table format in the terminal:
    - Condensed: Category, Code Name, Description
    - Very Short: Summary format
    - Short: Includes example quotes
    - Long: Comprehensive format

* **Find Your Output:**
    The output will be saved in the **`output`** folder as a LaTeX (`.tex`) file. You can include this file in your paper using the `\input{...}` command in your main LaTeX document.

#### **Option 3: Inter-Rater Reliability (IRR)**

This script processes multiple codebooks to calculate an agreement score using advanced matching algorithms.

* **Choose a Score:**
    The script will prompt you to select either Fleiss' Kappa or Krippendorff's Alpha.

* **Choose Processing Method:**
    - Start fresh: Process all codebooks from scratch
    - Use existing merged file: Continue from a previous calculation

* **Matching Algorithms:**
    - **Fuzzy Text Matching**: Compares text segments using similarity ratios (threshold: 60%)
    - **Keyword-Based Matching**: Matches based on shared key terms (minimum 2 shared keywords or 40% keyword overlap)
    - **Code Matching**: Compares code categories and names (threshold: 80%)

* **Find Your Output:**
    The script generates multiple files in the **`output`** folder:
    * `irr_notes.txt`: A detailed log of the calculation steps and the final score with interpretation.
    * `merged_codebook.csv`: A CSV file combining all input codebooks, showing how codes align across coders.
    * `merged_agree_codebook.csv`: A file containing only the text segments where coders agreed.
    * `merged_disagree_codebook.csv`: A file containing only the text segments where coders disagreed or that need review, useful for reconciliation meetings.

---

## Troubleshooting

### **Common Issues:**

1. **Missing Dependencies**: Ensure you've activated the virtual environment and installed requirements
2. **File Not Found**: Check that your CSV files are in the correct directories (`input/` for main analysis, `irr_input/` for IRR)
3. **Column Mismatch**: Verify your CSV has the required columns: `Codename`, `Coded_Memo`, `Coded`, `File`, `Coder`
4. **Code Format**: Ensure all codes follow the `category:code` format with kebab-case naming

### **Getting Help:**

If you encounter issues, check the generated log files in the `output` directory for detailed error messages and processing information.