# Codebook Visualization App

This application provides two main functionalities from a single `codebook.csv` file:

1.  It creates an interactive HTML report to help you explore and visualize your qualitative data. The report automatically groups all codes under their parent category for easy navigation.
2.  It generates a LaTeX table from the same data, suitable for use in an academic paper's appendix.

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
## Configuring the Analysis Charts

The interactive HTML report can generate up to three special, standalone charts for specific categories you want to highlight.

To configure these for your project, **open the `config.py` file** and edit the values.

```python
# In config.py:

# Chart 1 Settings
CATEGORY_1_FOR_CHART = 'your-category-name'
CATEGORY_1_FOR_CHART_TITLE = 'Your Title for Chart 1'

# Chart 2 Settings
CATEGORY_2_FOR_CHART = 'another-category-name'
CATEGORY_2_FOR_CHART_TITLE = 'Your Title for Chart 2'

# Chart 3 Settings
CATEGORY_3_FOR_CHART = 'another-category'
CATEGORY_3_FOR_CHART_TITLE = 'Another Title'
```

Simply replace the values with your own category names and desired chart titles. If you do not need all three charts, you can leave the `_FOR_CHART` variables empty (e.g., `CATEGORY_2_FOR_CHART = ''`).

---
## How to Run This App

Follow the setup steps first. You will only need to do this setup once.

### **Setup Steps (1-4)**

#### **Step 1: Add Your Data File**

Place your correctly formatted `codebook.csv` file into the `input` folder.

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

Once the setup is complete, you can run either of the following applications.

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
