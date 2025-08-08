import os
import pandas as pd
import numpy as np
from datetime import datetime
import config

OUTPUT_DIR = "output"

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

def load_and_prepare_data(input_dir, file_col, text_col, code_col, coder_col, notes_filepath):
    """
    Loads data and creates a binary matrix for IRR, adding participant, manual review,
    and agreement summary columns.
    """
    CODERS_AGREEMENT_COLS = []
    log_note("STEP 1: Loading and Preparing Data", notes_filepath)
    log_note("-" * 50, notes_filepath)
    codebook_files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    if len(codebook_files) < 2:
        log_note(f"Error: Found {len(codebook_files)} files. At least two are required.", notes_filepath)
        return None, []
    log_note(f"Found {len(codebook_files)} codebooks to process: {', '.join(codebook_files)}", notes_filepath)
    all_ratings_df = pd.concat([
        pd.read_csv(os.path.join(input_dir, f)) for f in codebook_files
    ], ignore_index=True)

    if file_col not in all_ratings_df.columns:
        log_note(f"Error: The specified file column '{file_col}' was not found in the input CSVs.", notes_filepath)
        return None, []
    # Standardize participant identifiers to lowercase
    all_ratings_df['p'] = all_ratings_df[file_col].str.split('.').str[0].str.lower()
    required_cols = [text_col, code_col, coder_col, 'p']
    all_ratings_df.dropna(subset=required_cols, inplace=True)
    for col in required_cols:
        all_ratings_df[col] = all_ratings_df[col].astype(str).str.strip()
    # Remove all spaces from the code column to ensure consistent grouping
    all_ratings_df[code_col] = all_ratings_df[code_col].str.replace(' ', '', regex=False)
    all_coders = sorted(list(all_ratings_df[coder_col].unique()))
    # Group by both text and participant
    grouped = all_ratings_df.groupby([text_col, 'p'])
    log_note(f"\nFound {len(grouped)} unique text-participant pairs based on exact matching.", notes_filepath)

    irr_data = []
    for (text_segment, p_value), group_df in grouped:
        relevant_codes = sorted(group_df[code_col].unique())
        for code in relevant_codes:
            new_row = {'text': text_segment, 'p': p_value, 'code': code}
            for coder in all_coders:
                is_present = not group_df[
                    (group_df[coder_col] == coder) & (group_df[code_col] == code)
                ].empty
                new_row[coder] = 1 if is_present else 0
            irr_data.append(new_row)

    wide_df = pd.DataFrame(irr_data)
    wide_df.insert(0, 'id', range(1, 1 + len(wide_df)))

    num_coders = len(all_coders)
    sums = wide_df[all_coders].sum(axis=1)
    wide_df['all_agree'] = ((sums == 0) | (sums == num_coders)).astype(int)

    # Clear and populate the global list of agreement columns
    CODERS_AGREEMENT_COLS.clear()
    for coder in all_coders:
        col_name = f'{coder}_agreement'
        wide_df[col_name] = ""
        CODERS_AGREEMENT_COLS.append(col_name)

    # Use the now-populated global variable to define the final column order
    final_cols = ['id', 'p', 'text', 'code'] + all_coders + CODERS_AGREEMENT_COLS + ['all_agree']
    wide_df = wide_df[final_cols]

    log_note(f"\nSuccessfully created a merged data matrix with {len(wide_df)} judgements.", notes_filepath)
    output_path = os.path.join(OUTPUT_DIR, config.OUTPUT_MERGED_IRR_DATA_FILE)
    wide_df.to_csv(output_path, index=False)
    log_note(f"Full prepared data saved to: '{output_path}'", notes_filepath, print_to_console=False)
    log_note("="*50, notes_filepath, print_to_console=False)
    return wide_df, all_coders, CODERS_AGREEMENT_COLS

def create_agreement_disagreement_files(df, coder_cols, notes_filepath):
    """
    Identifies items with full agreement vs. any disagreement based on binary (1/0) ratings.
    """
    log_note("\nSTEP 2: Generating Agreement/Disagreement Files", notes_filepath)
    log_note("-" * 50, notes_filepath)
    agreement_mask = df['all_agree'] == 1
    agreement_df = df[agreement_mask].copy()
    disagreement_df = df[~agreement_mask].copy()
    total_judgements = len(df)
    agreed_count = len(agreement_df)
    disagreed_count = len(disagreement_df)
    log_note(f"{'Total judgements:':<20} {total_judgements}", notes_filepath)
    log_note(f"{'Full Agreement:':<20} {agreed_count}", notes_filepath)
    log_note(f"{'Disagreement:':<20} {disagreed_count}", notes_filepath)
    log_note("="*50, notes_filepath, print_to_console=False)

def main():
    initialize_output()
    notes_filepath = os.path.join(OUTPUT_DIR, "first_merge_notes.txt")
    print("--- Codebook Merging Utility ---")
    try:
        initialize_notes_file(notes_filepath)
        FILE_COLUMN = 'File'
        irr_df, coder_cols, CODERS_AGREEMENT_COLS = load_and_prepare_data(
            config.INPUT_DIRECTORY,
            FILE_COLUMN,
            config.TEXT_COLUMN,
            config.CODE_COLUMN,
            config.CODER_NAME_COLUMN,
            notes_filepath
        )
        if irr_df is None:
            print("\nData preparation failed. Please check the notes file for details.")
            return
        # Create agreement/disagreement file logs
        create_agreement_disagreement_files(irr_df, coder_cols, notes_filepath)
        print("\n✅ Merging process complete.")
        print(f"Merged data '{config.OUTPUT_MERGED_IRR_DATA_FILE}' and logs 'first_merge_notes.txt' have been saved in the '{OUTPUT_DIR}' directory.")
    except ImportError:
        print("\nError: Could not find the 'config.py' file. Please ensure it exists.")
    except Exception as e:
        print(f"An error occurred: {e}")
if __name__ == "__main__":
    main()    