import pandas as pd
import sys
import os

def escape_latex(text):
    """
    Escapes special LaTeX characters in a given string.
    Also removes specific Unicode and HTML tags.
    """
    if pd.isna(text):
        return ""
    text = str(text)

    # Remove problematic characters and simple HTML
    text = text.replace('\u2029', '')  # PARAGRAPH SEPARATOR
    text = text.replace('\x0c', '')    # FORM FEED
    text = text.replace('<span class="math-inline">', '')
    text = text.replace('</span>', '')

    # LaTeX special character escaping
    text = text.replace('\\', r'\textbackslash{}')
    text = text.replace('&', r'\&')
    text = text.replace('%', r'\%')
    text = text.replace('$', r'\$')
    text = text.replace('#', r'\#')
    text = text.replace('_', r'\_')
    text = text.replace('{', r'\{')
    text = text.replace('}', r'\}')
    text = text.replace('~', r'\textasciitilde{}')
    text = text.replace('^', r'\textasciicircum{}')
    return text

def load_and_prepare_data(file_path="input/codebook.csv"):
    """
    Loads the CSV, checks for required columns, and performs initial cleaning.
    
    Returns:
        - A pandas DataFrame if successful.
        - None if an error occurs (e.g., file not found, missing columns).
    """
    try:
        df = pd.read_csv(file_path)
        print(f"DEBUG: Successfully loaded '{file_path}'.", file=sys.stderr)
    except FileNotFoundError:
        print(f"ERROR: The file '{file_path}' was not found.", file=sys.stderr)
        print("Please ensure the CSV file exists in the 'input' directory.", file=sys.stderr)
        return None

    expected_columns = ['Codename', 'Coded_Memo', 'Coded']
    missing_cols = [col for col in expected_columns if col not in df.columns]

    if missing_cols:
        error_msg = f"CSV file is missing expected columns: {', '.join(missing_cols)}."
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return None
        
    if df.empty:
        print("DEBUG: CSV file is empty.", file=sys.stderr)
        return df

    # Basic processing: drop duplicates based on the code name
    df_processed = df.drop_duplicates(subset=['Codename'], keep='first').copy()
    return df_processed

def generate_condensed_table(df):
    """Generates a condensed LaTeX table, grouping codes by category."""
    parts = ['\\clearpage']
    parts.append(
        '\\begin{longtable}{p{0.25\\textwidth} p{0.4\\textwidth} p{0.35\\textwidth}}\n'
        '\\caption{Condensed Codebook for Thematic Analysis of Interview Data}\\label{tab:codebook} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} \\\\\n'
        '\\midrule\n'
        '\\endfirsthead\n'
        '\\multicolumn{3}{c}{\\tablename\\ \\thetable{}: Condensed Codebook (Continued)} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} \\\\\n'
        '\\midrule\n'
        '\\endhead\n'
        '\\endfoot\n'
        '\\bottomrule\n'
        '\\endlastfoot'
    )

    if df.empty or df['Codename'].notna().sum() == 0:
        parts.append("(No unique codes to display) & & \\\\")
    else:
        df['Category_Full'] = df['Codename'].astype(str)
        df['Coded_Memo'] = df['Coded_Memo'].fillna('')
        df['Category'] = df['Category_Full'].apply(lambda x: x.split(':')[0] if ':' in x else 'Uncategorized')
        df['SubCode'] = df['Category_Full'].apply(lambda x: ':'.join(x.split(':')[1:]) if ':' in x else x)
        df.sort_values(by=['Category', 'SubCode'], inplace=True)
        
        grouped = df.groupby('Category')
        first_category = True
        for category_name, group in grouped:
            if not first_category:
                parts.append("\\midrule")
            first_category = False
            
            cat_cell = escape_latex(category_name)
            
            # Codes with descriptions
            with_desc = group[group['Coded_Memo'].str.strip() != '']
            # Codes without descriptions
            without_desc = group[group['Coded_Memo'].str.strip() == '']['SubCode']

            # Row for combined codes without descriptions
            if not without_desc.empty:
                combined_codes = "; ".join([escape_latex(sc) for sc in without_desc])
                parts.append(f"{cat_cell} & {combined_codes} & \\\\")
                cat_cell = ""  # Clear category cell for subsequent rows in the same group

            # Individual rows for codes with descriptions
            for _, row in with_desc.iterrows():
                sub_code = escape_latex(row['SubCode'])
                desc = escape_latex(row['Coded_Memo'])
                parts.append(f"{cat_cell} & {sub_code} & {desc} \\\\")
                cat_cell = ""

    parts.append('\\end{longtable}')
    return "\n".join(parts)

def generate_veryshort_table(df):
    """Generates a 'very short' LaTeX table with Category, Code Name, and Description."""
    parts = []
    parts.append(
        '\\begin{longtable}{p{0.25\\textwidth} p{0.25\\textwidth} p{0.4\\textwidth}}\n'
        '\\caption{Codebook for Thematic Analysis (Summary)}\\label{tab:codebook} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} \\\\\n'
        '\\midrule\n'
        '\\endfirsthead\n'
        '\\multicolumn{3}{c}{\\tablename\\ \\thetable{}: Codebook Summary (Continued)} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} \\\\\n'
        '\\midrule\n'
        '\\endhead\n'
        '\\midrule\n'
        '\\multicolumn{3}{r}{{\\footnotesize\\textit{Continued on next page}}} \\\\\n'
        '\\endfoot\n'
        '\\bottomrule\n'
        '\\endlastfoot'
    )

    if df.empty or df['Codename'].notna().sum() == 0:
        parts.append("(No unique codes to display) & & \\\\")
    else:
        df['Category_Full'] = df['Codename'].astype(str)
        df['Category'] = df['Category_Full'].apply(lambda x: x.split(':')[0] if ':' in x else 'Uncategorized')
        df['SubCode'] = df['Category_Full'].apply(lambda x: ':'.join(x.split(':')[1:]) if ':' in x else x)
        df.sort_values(by=['Category', 'SubCode'], inplace=True)

        last_cat = None
        for _, row in df.iterrows():
            category = escape_latex(row['Category'])
            sub_code = escape_latex(row['SubCode'])
            description = escape_latex(row['Coded_Memo'])
            
            display_cat = category if category != last_cat else ""
            last_cat = category
            
            parts.append(f"{display_cat} & {sub_code} & {description} \\\\")
            parts.append("\\midrule")
        if parts[-1] == "\\midrule": parts.pop()

    parts.append('\\end{longtable}')
    return "\n".join(parts)

def generate_short_table(df):
    """Generates a 'short' LaTeX table including the Example column."""
    parts = []
    parts.append(
        '\\begin{longtable}{p{0.22\\textwidth} p{0.18\\textwidth} p{0.25\\textwidth} p{0.25\\textwidth}}\n'
        '\\caption{Aggregated Codebook for Thematic Analysis}\\label{tab:codebook} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} & \\textbf{Example} \\\\\n'
        '\\midrule\n'
        '\\endfirsthead\n'
        '\\multicolumn{4}{c}{\\tablename\\ \\thetable{}: Aggregated Codebook (Continued)} \\\\\n'
        '\\toprule\n'
        '\\textbf{Category} & \\textbf{Code Name} & \\textbf{Description} & \\textbf{Example} \\\\\n'
        '\\midrule\n'
        '\\endhead\n'
        '\\midrule\n'
        '\\multicolumn{4}{r}{{\\footnotesize\\textit{Continued on next page}}} \\\\\n'
        '\\endfoot\n'
        '\\bottomrule\n'
        '\\endlastfoot'
    )

    if df.empty or df['Codename'].notna().sum() == 0:
        parts.append("(No unique codes to display) & & & \\\\")
    else:
        df['Category_Full'] = df['Codename'].astype(str)
        df['Category'] = df['Category_Full'].apply(lambda x: x.split(':')[0] if ':' in x else 'Uncategorized')
        df['SubCode'] = df['Category_Full'].apply(lambda x: ':'.join(x.split(':')[1:]) if ':' in x else x)
        df.sort_values(by=['Category', 'SubCode'], inplace=True)

        last_cat = None
        for _, row in df.iterrows():
            category = escape_latex(row['Category'])
            sub_code = escape_latex(row['SubCode'])
            description = escape_latex(row['Coded_Memo'])
            example_raw = row['Coded']
            example = f"\"{escape_latex(example_raw)}\"" if pd.notna(example_raw) and str(example_raw).strip() else ""
            
            display_cat = category if category != last_cat else ""
            last_cat = category
            
            parts.append(f"{display_cat} & {sub_code} & {description} & {example} \\\\")
            parts.append("\\midrule")
        if parts[-1] == "\\midrule": parts.pop()

    parts.append('\\end{longtable}')
    return "\n".join(parts)
    
def generate_long_table(df):
    """Generates a 'long' LaTeX table without categories, showing full code names."""
    parts = []
    parts.append(
        '\\begin{longtable}{p{0.2\\textwidth} p{0.3\\textwidth} p{0.5\\textwidth}}\n'
        '\\caption{Codebook for Thematic Analysis of Interview Data}\\label{tab:codebook} \\\\\n'
        '\\toprule\n'
        '\\textbf{Code Name} & \\textbf{Description} & \\textbf{Example} \\\\\n'
        '\\midrule\n'
        '\\endfirsthead\n'
        '\\multicolumn{3}{c}{\\tablename\\ \\thetable{}: Codebook (Continued)} \\\\\n'
        '\\toprule\n'
        '\\textbf{Code Name} & \\textbf{Description} & \\textbf{Example} \\\\\n'
        '\\midrule\n'
        '\\endhead\n'
        '\\midrule\n'
        '\\multicolumn{3}{r}{{\\footnotesize\\textit{Continued on next page}}} \\\\\n'
        '\\endfoot\n'
        '\\bottomrule\n'
        '\\endlastfoot'
    )

    if df.empty or df['Codename'].notna().sum() == 0:
        parts.append("(No unique codes to display) & & \\\\")
    else:
        for _, row in df.iterrows():
            code_name = escape_latex(row['Codename'])
            description = escape_latex(row['Coded_Memo'])
            example_raw = row['Coded']
            example = f"\"{escape_latex(example_raw)}\"" if pd.notna(example_raw) and str(example_raw).strip() else ""
            
            parts.append(f"{code_name} & {description} & {example} \\\\")
            parts.append("\\midrule")
        if parts[-1] == "\\midrule": parts.pop()

    parts.append('\\end{longtable}')
    return "\n".join(parts)

def write_latex_file(content, output_path):
    """Writes the LaTeX string to a file, creating the directory if needed."""
    try:
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"DEBUG: Created directory '{output_dir}'.", file=sys.stderr)
            
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(content)
        print(f"\nSUCCESS: LaTeX table generated and saved to '{output_path}'")
        return True
    except Exception as e:
        print(f"\nERROR: Could not write to file '{output_path}': {e}", file=sys.stderr)
        return False

def main():
    """Main function to drive the script."""
    
    options = {
        '1': ("Condensed", generate_condensed_table, "output/appendix_codebook_condensed.tex"),
        '2': ("Very Short", generate_veryshort_table, "output/appendix_codebook_veryshort.tex"),
        '3': ("Short", generate_short_table, "output/appendix_codebook_short.tex"),
        '4': ("Long", generate_long_table, "output/appendix_codebook_long.tex"),
    }
    
    print("How would you like to create your LaTeX Appendix table output:")
    print("1) Condensed appendix table.")
    print("2) Very short appendix table.")
    print("3) Short appendix table.")
    print("4) Long appendix table.")
    
    choice = input("Select a number (default = 1): ").strip()
    
    if not choice:
        choice = '1'

    if choice not in options:
        print("Invalid selection. Exiting.", file=sys.stderr)
        sys.exit(1)
        
    style_name, generator_func, output_file = options[choice]
    print(f"INFO: You selected option {choice} ('{style_name}').", file=sys.stderr)

    df = load_and_prepare_data()

    if df is None:
        # Error messages are printed inside the loading function
        sys.exit(1)

    # Generate the LaTeX content using the chosen function
    latex_string = generator_func(df)

    # Write the content to the corresponding output file
    write_latex_file(latex_string, output_file)

if __name__ == "__main__":
    main()