import os
import pandas as pd
import numpy as np
from datetime import datetime

OUTPUT_DIR = "output"

# --- Utility and Setup functions ---
def log_note(message, filepath, print_to_console=True):
    """Appends a message to the specified notes file and optionally prints to console."""
    with open(filepath, "a", encoding='utf-8') as f:
        f.write(message + "\n")
    if print_to_console:
        print(message)

def initialize_output():
    """Creates the output directory."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

def initialize_notes_file(filepath):
    """Creates and initializes a new notes file."""
    with open(filepath, "w", encoding='utf-8') as f:
        f.write("IRR Calculation Notes\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*40 + "\n\n")

# --- Data Preparation (Unchanged) ---
def load_and_prepare_data(input_dir, text_col, code_col, coder_col, notes_filepath):
    """
    Loads data and creates a binary matrix for multi-label IRR using exact text matching.
    """
    log_note("STEP 1: Loading and Preparing Data (Using Exact Text Matching)", notes_filepath)
    log_note("-" * 50, notes_filepath)

    codebook_files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    if len(codebook_files) < 2:
        log_note(f"Error: Found {len(codebook_files)} files. At least two are required.", notes_filepath)
        return None, []

    log_note(f"Found {len(codebook_files)} codebooks to process: {', '.join(codebook_files)}", notes_filepath)

    all_ratings_df = pd.concat([
        pd.read_csv(os.path.join(input_dir, f)) for f in codebook_files
    ], ignore_index=True)

    all_ratings_df.dropna(subset=[text_col, code_col, coder_col], inplace=True)
    for col in [text_col, code_col, coder_col]:
        all_ratings_df[col] = all_ratings_df[col].astype(str).str.strip()

    all_coders = sorted(list(all_ratings_df[coder_col].unique()))
    grouped = all_ratings_df.groupby(text_col)
    log_note(f"\nFound {len(grouped)} unique text segments based on exact matching.", notes_filepath)

    irr_data = []
    for text_segment, group_df in grouped:
        relevant_codes = group_df[code_col].unique()
        for code in sorted(relevant_codes):
            new_row = {'text': text_segment, 'code': code}
            for coder in all_coders:
                is_present = not group_df[
                    (group_df[coder_col] == coder) & (group_df[code_col] == code)
                ].empty
                new_row[coder] = 1 if is_present else 0
            irr_data.append(new_row)

    wide_df = pd.DataFrame(irr_data)
    wide_df.insert(0, 'id', range(1, 1 + len(wide_df)))

    log_note(f"\nSuccessfully created a binary matrix with {len(wide_df)} relevant judgements.", notes_filepath)
    output_path = os.path.join(OUTPUT_DIR, "merged_irr_data.csv")
    wide_df.to_csv(output_path, index=False)
    log_note(f"Full prepared data saved to: '{output_path}'", notes_filepath, print_to_console=False)
    log_note("="*50, notes_filepath, print_to_console=False)
    return wide_df, all_coders

def create_agreement_disagreement_files(df, coder_cols, notes_filepath):
    """
    Identifies items with full agreement vs. any disagreement based on binary (1/0) ratings.
    """
    log_note("\nSTEP 2: Generating Agreement/Disagreement Files", notes_filepath)
    log_note("-" * 50, notes_filepath)
    
    num_coders = len(coder_cols)
    sums = df[coder_cols].sum(axis=1)
    agreement_mask = (sums == 0) | (sums == num_coders)
    
    agreement_df = df[agreement_mask].copy()
    disagreement_df = df[~agreement_mask].copy()

    total_judgements = len(df)
    agreed_count = len(agreement_df)
    disagreed_count = len(disagreement_df)

    log_note(f"{'Total judgements:':<20} {total_judgements}", notes_filepath)
    log_note(f"{'Full Agreement:':<20} {agreed_count}", notes_filepath)
    log_note(f"{'Disagreement:':<20} {disagreed_count}", notes_filepath)

    if not agreement_df.empty:
        output_path = os.path.join(OUTPUT_DIR, "agreed_judgements.csv")
        agreement_df.to_csv(output_path, index=False)
        log_note(f"\nAgreement file saved to: '{output_path}'", notes_filepath)
        
    if not disagreement_df.empty:
        output_path = os.path.join(OUTPUT_DIR, "disagreed_judgements.csv")
        disagreement_df.to_csv(output_path, index=False)
        log_note(f"Disagreement file saved to: '{output_path}'", notes_filepath)

    log_note("="*50, notes_filepath, print_to_console=False)


# --- CORRECTED CALCULATION FUNCTIONS WITH STEP-BY-STEP LOGGING ---

def calculate_fleiss_kappa(df, notes_filepath):
    """
    Calculates Fleiss' Kappa with correct vote counting and detailed logging.
    This version implements the standard formula for binary data.
    """
    log_note("\nSTEP 4: Calculating Fleiss' Kappa", notes_filepath)
    log_note("-" * 50, notes_filepath, print_to_console=False)
    log_note("Formula: κ = (Po - Pe) / (1 - Pe)\n", notes_filepath, print_to_console=False)

    # Convert the ratings DataFrame to a NumPy integer array for calculation.
    ratings_matrix = df.to_numpy(dtype=int)
    N, n = ratings_matrix.shape  # N = number of items (subjects), n = number of raters

    if n < 2:
        log_note("Error: Fleiss' Kappa requires at least 2 raters.", notes_filepath)
        return np.nan

    # Handle the edge case of perfect agreement.
    # Agreement exists if the sum of ratings for an item is 0 (all 'No') or n (all 'Yes').
    agreement_sums = ratings_matrix.sum(axis=1)
    if np.all((agreement_sums == 0) | (agreement_sums == n)):
        log_note("All judgements are in perfect agreement. Score is 1.0 by definition.", notes_filepath)
        return 1.0

    log_note("--- Calculation Breakdown ---", notes_filepath, print_to_console=False)
    log_note(f"1. Total items (judgements): N = {N}", notes_filepath, print_to_console=False)
    log_note(f"2. Number of raters: n = {n}", notes_filepath, print_to_console=False)

    # 3. Calculate Po (Observed Agreement): The proportion of items where raters agreed.
    num_agreed_items = np.sum((agreement_sums == 0) | (agreement_sums == n))
    Po = num_agreed_items / N
    log_note(f"\n3. Observed Agreement (Po)", notes_filepath, print_to_console=False)
    log_note(f"   Po = Items with full agreement / Total Items", notes_filepath, print_to_console=False)
    log_note(f"   Po = {num_agreed_items} / {N} = {Po:.4f}", notes_filepath, print_to_console=False)

    # 4. Calculate Pe (Expected Agreement): P(yes)^2 + P(no)^2
    # FIX: Correctly count total 'Yes' and 'No' votes from the entire matrix.
    total_ratings = N * n
    # The sum of the entire matrix gives the count of all '1's ('Yes' votes).
    num_yes_votes = np.sum(ratings_matrix)
    num_no_votes = total_ratings - num_yes_votes
    
    # Calculate proportions
    prop_yes = num_yes_votes / total_ratings
    prop_no = num_no_votes / total_ratings
    Pe = prop_yes**2 + prop_no**2
    
    log_note(f"\n4. Expected Agreement by Chance (Pe)", notes_filepath, print_to_console=False)
    log_note(f"   Total 'Yes' votes (1s): {num_yes_votes}", notes_filepath, print_to_console=False)
    log_note(f"   Total 'No' votes (0s):  {num_no_votes}", notes_filepath, print_to_console=False)
    log_note(f"   Pe = P(yes)² + P(no)² = ({prop_yes:.4f})² + ({prop_no:.4f})² = {Pe:.4f}", notes_filepath, print_to_console=False)

    # 5. Final Kappa Calculation
    if Pe == 1.0: return 1.0 # Avoid division by zero if Pe is 1
    kappa = (Po - Pe) / (1 - Pe)
    
    log_note(f"\n5. Final Calculation", notes_filepath, print_to_console=False)
    log_note(f"   κ = (Po - Pe) / (1 - Pe)", notes_filepath, print_to_console=False)
    log_note(f"   κ = ({Po:.4f} - {Pe:.4f}) / (1 - {Pe:.4f}) = {kappa:.4f}", notes_filepath, print_to_console=False)
    log_note("="*50, notes_filepath, print_to_console=False)
    
    return kappa

def calculate_krippendorffs_alpha(df, notes_filepath):
    """
    Calculates Krippendorff's Alpha with correct vote counting and detailed logging.
    This version implements the specified manual formula for 2 raters and binary nominal data.
    """
    log_note("\nSTEP 4: Calculating Krippendorff's Alpha (Manual Calculation)", notes_filepath)
    log_note("-" * 50, notes_filepath, print_to_console=False)
    log_note("Formula: α = 1 - (Do / De)\n", notes_filepath, print_to_console=False)

    ratings_matrix = df.to_numpy(dtype=int)
    num_items, num_raters = ratings_matrix.shape

    if num_raters != 2:
        log_note("Error: This manual Alpha calculation is designed for exactly 2 raters.", notes_filepath)
        return np.nan

    # Handle the edge case of perfect agreement.
    if np.all(ratings_matrix[:, 0] == ratings_matrix[:, 1]):
        log_note("All judgements are in perfect agreement. Score is 1.0 by definition.", notes_filepath)
        return 1.0

    log_note("--- Calculation Breakdown ---", notes_filepath, print_to_console=False)
    log_note(f"1. Total items (judgements): N = {num_items}", notes_filepath, print_to_console=False)
    log_note(f"   Number of raters: n = {num_raters}", notes_filepath, print_to_console=False)

    # 2. Calculate Do (Observed Disagreement): The proportion of items where raters disagreed.
    num_disagreements = np.sum(ratings_matrix[:, 0] != ratings_matrix[:, 1])
    Do = num_disagreements / num_items
    log_note(f"\n2. Observed Disagreement (Do)", notes_filepath, print_to_console=False)
    log_note(f"   Do = Items with disagreement / Total Items", notes_filepath, print_to_console=False)
    log_note(f"   Do = {num_disagreements} / {num_items} = {Do:.4f}", notes_filepath, print_to_console=False)

    # 3. Calculate De (Expected Disagreement)
    # FIX: Correctly count total 'Yes' and 'No' votes using a robust method.
    # np.unique with return_counts is a reliable way to get counts of all 0s and 1s.
    values, counts = np.unique(ratings_matrix, return_counts=True)
    value_counts = dict(zip(values, counts))
    n_no = value_counts.get(0, 0)   # Number of 'No' votes (0s)
    n_yes = value_counts.get(1, 0)  # Number of 'Yes' votes (1s)
    
    N_total = n_no + n_yes # Total number of individual ratings
    
    # This formula calculates the probability of drawing two different ratings
    # from the pool of all ratings.
    De = (2.0 * n_yes * n_no) / (N_total * (N_total - 1))
    
    log_note(f"\n3. Expected Disagreement by Chance (De)", notes_filepath, print_to_console=False)
    log_note(f"   Total 'Yes' votes (n_yes): {n_yes}", notes_filepath, print_to_console=False)
    log_note(f"   Total 'No' votes (n_no):   {n_no}", notes_filepath, print_to_console=False)
    log_note(f"   Total ratings (N_total): {N_total}", notes_filepath, print_to_console=False)
    log_note(f"   De = (2 * n_yes * n_no) / (N_total * (N_total - 1))", notes_filepath, print_to_console=False)
    log_note(f"   De = (2 * {n_yes} * {n_no}) / ({N_total} * {N_total - 1}) = {De:.4f}", notes_filepath, print_to_console=False)

    # 4. Final Alpha Calculation
    if De == 0: return 1.0 # Avoid division by zero if De is 0
    alpha = 1.0 - (Do / De)
    
    log_note(f"\n4. Final Calculation", notes_filepath, print_to_console=False)
    log_note(f"   α = 1 - (Do / De)", notes_filepath, print_to_console=False)
    log_note(f"   α = 1 - ({Do:.4f} / {De:.4f}) = {alpha:.4f}", notes_filepath, print_to_console=False)
    log_note("="*50, notes_filepath, print_to_console=False)
    
    return alpha


# --- Main and Interpretation functions (Unchanged) ---
def print_and_log_interpretation(score, method, notes_filepath):
    log_note("\nSTEP 5: Final Result", notes_filepath)
    log_note("-" * 20, notes_filepath)
    if pd.isna(score):
        log_note("The calculated score is NaN.", notes_filepath)
        return

    if score >= 0.81: interpretation = "Almost Perfect Agreement"
    elif score >= 0.61: interpretation = "Substantial Agreement"
    elif score >= 0.41: interpretation = "Moderate Agreement"
    elif score >= 0.21: interpretation = "Fair Agreement"
    elif score >= 0.01: interpretation = "Slight Agreement"
    else: interpretation = "Poor to No Agreement"

    if method == 'alpha':
        log_note(f"Final Krippendorff's Alpha (α): {score:.4f}", notes_filepath)
    elif method == 'kappa':
        log_note(f"Final Fleiss' Kappa: {score:.4f}", notes_filepath)
    
    log_note(f"Interpretation: {interpretation}", notes_filepath)
    log_note("="*50, notes_filepath, print_to_console=False)
    print(f"\nDetailed notes have been saved to 'output/{os.path.basename(notes_filepath)}'")

def main():
    initialize_output()
    irr_df = None
    coder_cols = []
    temp_notes_filepath = os.path.join(OUTPUT_DIR, "temp_notes.txt")
    
    print("--- Inter-Rater Reliability Calculator ---")
    while True:
        print("\nHow would you like to proceed?")
        print("1. Start fresh (process and merge all files from the 'irr_input' directory)")
        print("2. Use existing file (re-calculate IRR from 'output/merged_irr_data.csv')")
        workflow_choice = input("Please enter 1 or 2 (or 'q' to quit): ").strip()

        if workflow_choice == '1':
            try:
                import config
                initialize_notes_file(temp_notes_filepath)
                irr_df, coder_cols = load_and_prepare_data(
                    config.INPUT_DIRECTORY, config.TEXT_COLUMN, config.CODE_COLUMN, config.CODER_NAME_COLUMN, temp_notes_filepath
                )
                break
            except ImportError:
                print("\nError: Could not find the 'config.py' file. Please ensure it exists.")
                return
            except Exception as e:
                print(f"An error occurred during data preparation: {e}")
                return

        elif workflow_choice == '2':
            merged_filepath = os.path.join(OUTPUT_DIR, "merged_irr_data.csv")
            try:
                irr_df = pd.read_csv(merged_filepath)
                coder_cols = [col for col in irr_df.columns if col not in ['id', 'text', 'code']]
                print(f"\nSuccessfully loaded existing file: '{merged_filepath}'")
                initialize_notes_file(temp_notes_filepath)
                log_note(f"Re-calculating IRR using existing file: '{merged_filepath}'", temp_notes_filepath)
                break
            except FileNotFoundError:
                print(f"\nError: '{merged_filepath}' not found. You must 'Start fresh' first.")
                continue
            except Exception as e:
                print(f"An error occurred while loading the file: {e}")
                return
        
        elif workflow_choice.lower() == 'q':
            print("User quit the process.")
            return
        else:
            print("Invalid choice. Please try again.")

    if irr_df is None or not coder_cols:
        print("\nProcess halted due to errors.")
        return

    final_notes_filepath = temp_notes_filepath
    create_agreement_disagreement_files(irr_df, coder_cols, final_notes_filepath)
    calc_df = irr_df[coder_cols]

    print("\nSTEP 3: User Selection")
    print("-" * 50)
    while True:
        print("\nWhich agreement score would you like to calculate?")
        print("1. Fleiss' Kappa")
        print("2. Krippendorff's Alpha")
        choice = input("Please enter 1 or 2 (or 'q' to quit): ").strip()
        notes_filename = None
        if choice == '1': notes_filename = "fleiss_kappa_irr_notes.txt"
        elif choice == '2': notes_filename = "krippendorffs_alpha_irr_notes.txt"
        
        if notes_filename:
            final_notes_filepath = os.path.join(OUTPUT_DIR, notes_filename)
            if os.path.exists(temp_notes_filepath):
                with open(temp_notes_filepath, 'r', encoding='utf-8') as f_in, open(final_notes_filepath, 'w', encoding='utf-8') as f_out:
                    f_out.write(f_in.read())
            
            if choice == '1':
                score = calculate_fleiss_kappa(calc_df.copy(), final_notes_filepath)
                print_and_log_interpretation(score, 'kappa', final_notes_filepath)
            elif choice == '2':
                score = calculate_krippendorffs_alpha(calc_df.copy(), final_notes_filepath)
                print_and_log_interpretation(score, 'alpha', final_notes_filepath)
            break
            
        elif choice.lower() == 'q':
            print("User quit the process.")
            break
        else:
            print("Invalid choice. Please try again.")
    
    if os.path.exists(temp_notes_filepath):
        try: os.remove(temp_notes_filepath)
        except OSError: pass

if __name__ == "__main__":
    main()