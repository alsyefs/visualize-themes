# Codebook Visualization App

This application provides three main functionalities from a single `codebook.csv` file:

1.  It creates an interactive HTML report to help you explore and visualize your qualitative data. The report automatically groups all codes under their parent category for easy navigation.
2.  It generates a LaTeX table from the same data, suitable for use in an academic paper's appendix.
3.  It calculates inter-rater reliability (IRR) scores (Fleiss' Kappa or Krippendorff's Alpha) from multiple codebook files.

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

Before running the applications, you may need to adjust settings in the `config.py` file.

### **Analysis Charts**

The interactive HTML report can generate up to three special, standalone charts for specific categories you want to highlight. To configure these, open the `config.py` file and edit the chart settings.

### **Inter-Rater Reliability (IRR) Calculator**

The `calculate_irr.py` script also uses `config.py` to identify the correct columns in your CSV files. Ensure these match your data:
* `INPUT_DIRECTORY`: The folder where your codebooks are, usually `"input"`.
* `TEXT_COLUMN`: The column with the text segment that was coded (e.g., `"Coded"`).
* `CODE_COLUMN`: The column with the code name (e.g., `"Codename"`).
* `CODER_NAME_COLUMN`: The column identifying the coder (e.g., `"Coder"`).

---
## How to Run This App

Follow the setup steps first. You will only need to do this setup once.

### **Setup Steps (1-4)**

#### **Step 1: Add Your Data File(s)**

* **For visualization or the LaTeX appendix:** Place your `codebook.csv` file into the `input` folder.
* **For IRR calculation:** Place *all* codebook CSV files (at least two) from the different coders into the `input` folder.

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

### **Running the Main Applications**

Once the setup is complete, you can run any of the following applications.

#### **Option A: Running the Interactive HTML Report**

This is the main application for data visualization.

* **Run the App:**
    ```
    python app.py
    ```

* **View Your Report:**
    Navigate to the **`output`** folder and double-click the HTML file to open it in your web browser.

#### **Option B: Creating a LaTeX Appendix Table (Optional)**

This script is for academic use. It takes your codebook and generates a `.tex` file.

* **Run the Script:**
    ```
    python create_latex_appendix_of_codebook.py
    ```

* **Choose a Format:**
    The script will prompt you to select a table format in the terminal.

* **Find Your Output:**
    The output will be saved in the **`output`** folder as a LaTeX (`.tex`) file. You can include this file in your paper using the `\input{...}` command in your main LaTeX document.

#### **Option C: Calculating Inter-Rater Reliability (IRR)**

This script processes multiple codebooks to calculate an agreement score.

* **Run the Script:**
    ```
    python calculate_irr.py
    ```

* **Choose a Score:**
    The script will prompt you to select either Fleiss' Kappa or Krippendorff's Alpha.

* **Find Your Output:**
    The script generates three files in the **`output`** folder:
    * `irr_notes.txt`: A detailed log of the calculation steps and the final score with interpretation.
    * `merged_codebook.csv`: A CSV file combining all input codebooks, showing how codes align across coders.
    * `merged_disagree_codebook.csv`: A file containing only the text segments where coders disagreed or that need review, useful for reconciliation meetings.