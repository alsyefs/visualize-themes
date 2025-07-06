import os
import pandas as pd
import numpy as np
import krippendorff
from statsmodels.stats import inter_rater as irr
import config
from datetime import datetime
from thefuzz import fuzz

# --- Global variable for output directory ---
OUTPUT_DIR = "output"

def log_note(message, filepath, print_to_console=True):
    """
    Appends a message to the specified notes file and optionally prints to console.
    """
    with open(filepath, "a") as f:
        f.write(message + "\n")
    if print_to_console:
        print(message)

def initialize_output():
    """
    Creates the output directory.
    """
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

def initialize_notes_file(filepath):
    """Creates and initializes a new notes file."""
    with open(filepath, "w") as f:
        f.write("IRR Calculation Notes\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*40 + "\n\n")

def extract_keywords(text):
    """
    Extract key terms from text for matching purposes.
    """
    if not text:
        return set()
    words = text.lower().split()
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
        'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs',
        'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'some', 'any', 'all', 'every', 'each', 'no', 'not', 'very', 'really', 'quite', 'just',
        'like', 'know', 'think', 'say', 'said', 'tell', 'told', 'get', 'got', 'make', 'made',
        'go', 'went', 'gone', 'come', 'came', 'see', 'saw', 'seen', 'look', 'looked', 'want', 'wanted'
    }
    keywords = {word for word in words if word not in stop_words and len(word) >= 3}
    return keywords

def keyword_text_match(text1, text2, min_shared_keywords=2):
    """
    Returns True if the two text segments share enough key terms.
    """
    if not text1 or not text2:
        return False
    if text1 in text2 or text2 in text1:
        return True
    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)
    if not keywords1 or not keywords2:
        return False
    shared_keywords = keywords1.intersection(keywords2)
    min_keywords = min(len(keywords1), len(keywords2))
    if min_keywords == 0:
        return False
    shared_ratio = len(shared_keywords) / min_keywords
    return len(shared_keywords) >= min_shared_keywords or shared_ratio >= 0.4

def fuzzy_text_match(text1, text2, threshold=60):
    """
    Returns True if the two text segments are similar enough (by ratio/partial ratio),
    or if one is a substring of the other, or if they share key terms.
    """
    if not text1 or not text2:
        return False
    if text1 in text2 or text2 in text1:
        return True
    if keyword_text_match(text1, text2):
        return True
    return max(fuzz.ratio(text1, text2), fuzz.partial_ratio(text1, text2)) >= threshold

def fuzzy_code_match(code1, code2, threshold=80):
    """
    Returns True if the two codes are similar enough (by substring/fuzzy match)
    or if their categories (before colon) match.
    """
    if not code1 or not code2:
        return False
    cat1 = code1.split(':')[0]
    cat2 = code2.split(':')[0]
    if cat1 == cat2:
        return True
    if code1 in code2 or code2 in code1:
        return True
    return max(fuzz.ratio(code1, code2), fuzz.partial_ratio(code1, code2)) >= threshold

def load_and_merge_codebooks(input_dir, text_col, code_col, coder_col, notes_filepath):
    """
    Processes files by creating a unique identifier for each text-code pair, but allows for fuzzy text overlap.
    This preserves all coding decisions and prepares the data for IRR calculation.
    """
    log_note("STEP 1: Loading, Processing, and Merging Codebooks", notes_filepath)
    log_note("-" * 50, notes_filepath)
    log_note("Method: Keyword-based matching for text-segment/code combination.", notes_filepath)

    codebook_files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    if len(codebook_files) < 2:
        log_note(
            f"Error: Found {len(codebook_files)} in '{input_dir}'. At least two are required.",
            notes_filepath
        )
        return None, []

    log_note(
        f"Found {len(codebook_files)} codebooks to process: {', '.join(codebook_files)}",
        notes_filepath
    )

    # Load all codebooks into a list of dataframes
    dfs = []
    for filename in codebook_files:
        filepath = os.path.join(input_dir, filename)
        df = pd.read_csv(filepath)
        if not all(c in df.columns for c in [text_col, code_col, coder_col]):
            log_note(
                f"Error: File '{filename}' is missing required columns: "
                f"'{text_col}', '{code_col}', or '{coder_col}'.",
                notes_filepath
            )
            return None, []
        df = df.dropna(subset=[text_col, code_col, coder_col]).copy()
        df[text_col] = df[text_col].astype(str).str.strip()
        df[code_col] = df[code_col].astype(str).str.strip()
        df[coder_col] = df[coder_col].astype(str).str.strip()
        df['source_file'] = filename
        dfs.append(df)

    # Build a master list of all (text, code) pairs across all coders, using fuzzy matching for text
    master_pairs = []  # Each entry: {text, code, matches: {coder: idx}}
    for idx, df in enumerate(dfs):
        for _, row in df.iterrows():
            found = False
            for mp in master_pairs:
                if (fuzzy_code_match(row[code_col], mp['code']) and 
                    fuzzy_text_match(row[text_col], mp['text'])):
                    mp['matches'][row[coder_col]] = (idx, row.name)
                    found = True
                    break
            if not found:
                master_pairs.append({
                    'text': row[text_col],
                    'code': row[code_col],
                    'matches': {row[coder_col]: (idx, row.name)}
                })

    # Build merged DataFrame
    all_coders = set()
    for df in dfs:
        all_coders.update(df[coder_col].unique())
    all_coders = sorted(all_coders)

    rows = []
    for mp in master_pairs:
        row = {
            'text': mp['text'],
            'code': mp['code']
        }
        for coder in all_coders:
            if coder in mp['matches']:
                idx, row_idx = mp['matches'][coder]
                row[coder] = 1
            else:
                row[coder] = 0
        rows.append(row)

    merged_df = pd.DataFrame(rows)

    # Agreement logic: if more than one coder marked 1, and all marked 1, it's agreement; if some marked 1, some 0, it's partial/disagreement
    coder_cols = all_coders
    
    def determine_agreement_status(row):
        coder_values = row[coder_cols].dropna()
        num_coders_present = len(coder_values)
        if num_coders_present == 0:
            return np.nan
        if coder_values.sum() == num_coders_present and num_coders_present > 1:
            return 1
        elif coder_values.sum() > 0 and coder_values.sum() < num_coders_present:
            return 0
        elif num_coders_present == 1:
            return 2
        elif coder_values.sum() == 0:
            return 0
        return np.nan

    merged_df['agree'] = merged_df.apply(determine_agreement_status, axis=1)
    merged_df.insert(0, 'id', range(1, 1 + len(merged_df)))
    fixed_cols = ['id', 'agree', 'text', 'code']
    coder_cols = [col for col in merged_df.columns if col not in fixed_cols]
    final_cols = ['id', 'agree', 'text', 'code'] + coder_cols
    merged_df = merged_df[final_cols]

    log_note(
        f"\nSuccessfully merged all files. Found {len(merged_df)} total unique text/code pairs (with keyword matching).",
        notes_filepath
    )
    output_path = os.path.join(OUTPUT_DIR, "merged_codebook.csv")
    merged_df.to_csv(output_path, index=False)
    log_note(f"Full merged data saved to: '{output_path}'", notes_filepath, print_to_console=False)
    log_note("="*50, notes_filepath, print_to_console=False)

    return merged_df, coder_cols

def create_agreement_file(df):
    """
    Creates a file with only the segments where coders agreed.
    """
    agreement_mask = df['agree'] == 1
    agreement_df = df[agreement_mask].copy()
    
    if not agreement_df.empty:
        agreement_df.insert(0, 'n', range(1, 1 + len(agreement_df)))
        output_path = os.path.join(OUTPUT_DIR, "merged_agree_codebook.csv")
        agreement_df.to_csv(output_path, index=False)

def create_disagreement_file(df):
    """
    Identifies items that need discussion and saves them to a separate CSV file.
    """
    discussion_mask = df['agree'].isin([0, 2])
    discussion_df = df[discussion_mask].copy()

    discussion_df.insert(0, 'n', range(1, 1 + len(discussion_df)))
    
    if not discussion_df.empty:
        output_path = os.path.join(OUTPUT_DIR, "merged_disagree_codebook.csv")
        discussion_df.to_csv(output_path, index=False)

def log_agreement_summary(df, notes_filepath):
    """
    Logs the agreement summary in a clean format.
    """
    total_segments = len(df)
    agreed_count = (df['agree'] == 1).sum()
    disagreed_count = (df['agree'] == 0).sum() + (df['agree'] == 2).sum()

    log_note("\nSTEP 2: Agreement Summary", notes_filepath)
    log_note("-" * 50, notes_filepath)
    log_note(f"{'Total segments:':<15} {total_segments}", notes_filepath)
    log_note(f"{'Agreed on:':<15} {agreed_count}", notes_filepath)
    log_note(f"{'Disagreed on:':<15} {disagreed_count}", notes_filepath)
    
    if agreed_count > 0:
        log_note(f"\nAgreement file saved to: 'output/merged_agree_codebook.csv'", notes_filepath)
    if disagreed_count > 0:
        log_note(f"Disagreement file saved to: 'output/merged_disagree_codebook.csv'", notes_filepath)
    log_note("="*50, notes_filepath, print_to_console=False)

def calculate_krippendorffs_alpha(df, notes_filepath):
    log_note("\nSTEP 4: Calculating Krippendorff's Alpha", notes_filepath)
    log_note("-" * 50, notes_filepath)
    log_note("Formula: α = 1 - (Do / De)", notes_filepath)
    log_note("  Where Do is the observed disagreement and De is the disagreement expected by chance.", notes_filepath, print_to_console=False)
    log_note("  The library handles missing data by only comparing pairable values.", notes_filepath, print_to_console=False)
    log_note("\nConverting nominal codes to integers for calculation...", notes_filepath)

    df_numeric = df.copy()
    all_codes = pd.unique(df.values.ravel('K'))
    all_codes = [code for code in all_codes if pd.notna(code)]
    code_map = {code: i for i, code in enumerate(all_codes)}
    
    for col in df_numeric.columns:
        df_numeric[col] = df_numeric[col].map(code_map)
    
    score = krippendorff.alpha(df_numeric)
    log_note("Calculation successful.", notes_filepath)
    log_note("="*50, notes_filepath, print_to_console=False)
    return score

def calculate_fleiss_kappa(df, notes_filepath):
    log_note("\nSTEP 4: Calculating Fleiss' Kappa", notes_filepath)
    log_note("-" * 50, notes_filepath)
    log_note("Formula: κ = (P̄ - P̄e) / (1 - P̄e)", notes_filepath)
    log_note("  Where P̄ is the mean observed agreement and P̄e is the expected agreement by chance.", notes_filepath, print_to_console=False)
    log_note("\nAggregating data into 'subjects by categories' format...", notes_filepath)

    all_codes = pd.unique(df.values.ravel('K'))
    all_codes = [code for code in all_codes if pd.notna(code)]
    
    agg_data = df.apply(lambda row: [row.tolist().count(code) for code in all_codes], axis=1)
    agg_df = pd.DataFrame(agg_data.tolist(), columns=all_codes)
    
    score = irr.fleiss_kappa(agg_df.values, method='fleiss')
    log_note("Calculation successful.", notes_filepath)
    log_note("="*50, notes_filepath, print_to_console=False)
    return score

def print_and_log_interpretation(score, method, notes_filepath):
    log_note("\nSTEP 5: Final Result", notes_filepath)
    log_note("-" * 20, notes_filepath)

    if method == 'alpha':
        log_note(f"Final Krippendorff's Alpha (α): {score:.4f}", notes_filepath)
        # based on the paper titled "K-Alpha Calculator–Krippendorff's Alpha Calculator: A user-friendly tool for computing Krippendorff's Alpha inter-rater reliability coefficient"
        # [https://www.sciencedirect.com/science/article/pii/S2215016123005411]
        # Which has the following text:
        # "Overall, it is possible to delineate the following interpretations regarding the varying levels of Krippendorff's Alpha as suggested
        # by Krippendorff [1, p. 356]:
        # 1. Alpha = 1: Indicates perfect agreement among raters. It is the scenario where all raters have provided the exact same ratings for each item evaluated.
        # 2. Alpha ≥ 0.80: This value is generally considered a satisfactory level of agreement, indicating a reliable rating. In many research contexts, a Krippendorff's Alpha equal to or above 0.80 is acceptable for drawing triangulated conclusions based on the rated data.
        # 3. Alpha [0.67 - 0.79]: This range is often considered the lower bound for tentative conclusions. A Krippendorff's Alpha in this range suggests moderate agreement; thus, outcomes should be interpreted with concern, questioning the roots of such diverging ratings.
        # 4. Alpha < 0.67: This is indicative of poor agreement among raters. Data with a Krippendorff's Alpha below this threshold are often deemed unreliable for drawing triangulated conclusions. It suggests that the raters are not applying the coding scheme consistently or that the scheme itself may be flawed.
        # 5. Alpha = 0: Indicates no agreement among raters other than what would be expected by chance. It is similar to a random rating pattern.
        # 6. Alpha < 0: A negative value of Krippendorff's Alpha indicates systematic disagreement among raters. This situation might arise in cases where raters are systematically inclined in opposite rating directions."
        if score == 1.0: interpretation = "Perfect Agreement (all coders agreed on all codes)"
        elif score >= 0.80: interpretation = "Good to Excellent Agreement"
        elif score >= 0.67: interpretation = "Moderate Agreement"
        elif score < 0.67 and score > 0: interpretation = "Poor Agreement"
        elif score == 0: interpretation = "No Agreement (all coders disagreed on all codes)"
        else: interpretation = "Systematic Disagreement (coders systematically disagreed on codes)"
        log_note(f"Interpretation: {interpretation}", notes_filepath)
        log_note("\nReference for Krippendorff's Alpha interpretation:", notes_filepath, print_to_console=False)
        log_note("https://www.sciencedirect.com/science/article/pii/S2215016123005411", notes_filepath, print_to_console=False)

    elif method == 'kappa':
        log_note(f"Final Fleiss' Kappa: {score:.4f}", notes_filepath)
        # Based on [https://www.jstor.org/stable/2529310]
        if score < 0.00: interpretation = "Poor Agreement"
        elif score <= 0.20: interpretation = "Slight Agreement"
        elif score <= 0.40: interpretation = "Fair Agreement"
        elif score <= 0.60: interpretation = "Moderate Agreement"
        elif score <= 0.80: interpretation = "Substantial Agreement"
        elif score < 1.00: interpretation = "Almost Perfect Agreement"
        else: interpretation = "Perfect Agreement (all coders agreed on all codes)"
        log_note(f"Interpretation: {interpretation}", notes_filepath)
        log_note("\nReference for Fleiss' Kappa interpretation (Landis & Koch, 1977):", notes_filepath, print_to_console=False)
        log_note("https://www.jstor.org/stable/2529310", notes_filepath, print_to_console=False)

    log_note("="*50, notes_filepath, print_to_console=False)
    print(f"\nDetailed notes have been saved to 'output/{os.path.basename(notes_filepath)}'")

def main():
    initialize_output()
    merged_df = None
    coder_cols = []
    temp_notes_filepath = os.path.join(OUTPUT_DIR, "temp_notes.txt")
    
    print("--- Inter-Rater Reliability Calculator ---")
    while True:
        print("\nHow would you like to proceed?")
        print("1. Start fresh (process and merge all files from the 'irr_input' directory)")
        print("2. Use existing file (re-calculate IRR from 'output/merged_codebook.csv')")
        workflow_choice = input("Please enter 1 or 2 (or 'q' to quit): ").strip()

        if workflow_choice == '1':
            initialize_notes_file(temp_notes_filepath)
            merged_df, coder_cols = load_and_merge_codebooks(
                config.INPUT_DIRECTORY, config.TEXT_COLUMN, config.CODE_COLUMN, config.CODER_NAME_COLUMN, temp_notes_filepath
            )
            break
        
        elif workflow_choice == '2':
            merged_filepath = os.path.join(OUTPUT_DIR, "merged_codebook.csv")
            try:
                merged_df = pd.read_csv(merged_filepath)
                fixed_cols = ['id', 'agree', 'text', 'code']
                coder_cols = [col for col in merged_df.columns if col not in fixed_cols]
                print(f"\nSuccessfully loaded existing file: '{merged_filepath}'")
                
                initialize_notes_file(temp_notes_filepath)
                log_note(f"Re-calculating IRR using existing file: '{merged_filepath}'", temp_notes_filepath)
                log_note("="*50, temp_notes_filepath, print_to_console=False)
                break
            except FileNotFoundError:
                print(f"\nError: '{merged_filepath}' not found. You must 'Start fresh' first.")
        
        elif workflow_choice.lower() == 'q':
            print("User quit the process.")
            return
        else:
            print("Invalid choice. Please try again.")

    if merged_df is None:
        print("\nProcess halted due to errors or user quit.")
        return

    if 'agree' in merged_df.columns:
        create_agreement_file(merged_df)
        create_disagreement_file(merged_df)
    else:
        print("\nWarning: 'agree' column not found. Cannot generate agreement/disagreement files.")

    calc_df = merged_df[coder_cols]

    print("\nSTEP 3: User Selection")
    print("-" * 50)
    while True:
        print("\nWhich agreement score would you like to calculate?")
        print("1. Fleiss' Kappa")
        print("2. Krippendorff's Alpha")
        choice = input("Please enter 1 or 2 (or 'q' to quit): ")

        notes_filename = None
        if choice == '1':
            notes_filename = "fleiss_kappa_irr_notes.txt"
        elif choice == '2':
            notes_filename = "krippendorffs_alpha_irr_notes.txt"
        
        if notes_filename:
            final_notes_filepath = os.path.join(OUTPUT_DIR, notes_filename)
            if os.path.exists(temp_notes_filepath):
                with open(temp_notes_filepath) as f_in, open(final_notes_filepath, 'w') as f_out:
                    f_out.write(f_in.read())
            
            log_agreement_summary(merged_df, final_notes_filepath)

            log_note("\nSTEP 3: User Selection", final_notes_filepath, print_to_console=False)
            log_note("-" * 50, final_notes_filepath, print_to_console=False)
            
            if choice == '1':
                log_note("User selected: 1. Fleiss' Kappa", final_notes_filepath, print_to_console=False)
                fleiss_df = calc_df.dropna(how='all').fillna('__MISSING__')
                if len(calc_df) - len(fleiss_df) > 0:
                    log_note(f"\nNote: Rows with all-NaN values were excluded for Fleiss' Kappa.", final_notes_filepath)
                
                score = calculate_fleiss_kappa(fleiss_df, final_notes_filepath)
                print_and_log_interpretation(score, 'kappa', final_notes_filepath)
            
            elif choice == '2':
                log_note("User selected: 2. Krippendorff's Alpha", final_notes_filepath, print_to_console=False)
                score = calculate_krippendorffs_alpha(calc_df, final_notes_filepath)
                print_and_log_interpretation(score, 'alpha', final_notes_filepath)
            
            break
            
        elif choice.lower() == 'q':
            print("User quit the process.")
            break
        else:
            print("Invalid choice. Please try again.")
    
    if os.path.exists(temp_notes_filepath):
        os.remove(temp_notes_filepath)

if __name__ == "__main__":
    main()