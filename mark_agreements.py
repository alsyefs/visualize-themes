import pandas as pd
import os
import itertools
import config
# --- Configuration ---
INPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
OUTPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE


def calculate_agreement(input_file: str, output_file: str):
    try:
        df = pd.read_csv(input_file)
        df = df.reset_index(drop=True)
        print(f"Successfully loaded '{input_file}'.")
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        print("Please ensure the script and the CSV file are in the same directory.")
        return

    # --- Dynamically identify coders ---
    all_cols = df.columns
    coders = [col for col in all_cols if f'{col}_agreement' in all_cols]
    if not coders:
        # Fallback for first run if _agreement columns don't exist
        assumed_coders = config.CODERS_COLUMNS
        coders = [c for c in assumed_coders if c in all_cols]

    if not coders:
        print("Error: No valid coder columns found. Please check your CSV format.")
        return

    print(f"Identified coders: {coders}")
    agreement_cols = [f'{c}_agreement' for c in coders]

    # --- Phase 1: Initialize Agreement Columns ---
    print("Initializing agreement columns based on direct coding...")
    for coder in coders:
        agreement_col_name = f'{coder}_agreement'
        if agreement_col_name not in df.columns:
            df[agreement_col_name] = 0
        if coder in df.columns:
            df[agreement_col_name] = df[coder]

    # --- Phase 2: Calculate Subtext Agreement ---
    print("Calculating agreement based on subtext matching...")
    grouped = df.groupby(['p', 'code'])

    for _, group_df in grouped:
        if len(group_df) < 2:
            continue

        # Compare every pair of rows within the group
        for idx1, idx2 in itertools.combinations(group_df.index, 2):
            text1 = str(df.loc[idx1, 'text'])
            text2 = str(df.loc[idx2, 'text'])

            # Check for subtext relationship
            if text1 in text2 or text2 in text1:
                coders_idx1 = {c for c in coders if df.loc[idx1, c] == 1}
                coders_idx2 = {c for c in coders if df.loc[idx2, c] == 1}
                all_involved_coders = coders_idx1.union(coders_idx2)

                # Propagate agreement to both rows for all involved coders
                if all_involved_coders:
                    for coder_name in all_involved_coders:
                        df.loc[idx1, f'{coder_name}_agreement'] = 1
                        df.loc[idx2, f'{coder_name}_agreement'] = 1

    # --- Phase 3: Calculate Overall Agreement ---
    print("Calculating overall 'all_agree' column...")
    if 'all_agree' not in df.columns:
        df['all_agree'] = 0
    df['all_agree'] = df[agreement_cols].all(axis=1).astype(int)

    # --- Final Steps ---
    final_cols = ['id', 'p', 'text', 'code'] + coders + agreement_cols + ['all_agree']
    existing_final_cols = [col for col in final_cols if col in df.columns]
    df = df[existing_final_cols]

    df.to_csv(output_file, index=False)
    print(f"\nProcessing complete. Output saved to '{output_file}'.")

def main():
    print("--- Starting Agreement Calculation ---")
    calculate_agreement(INPUT_CSV_FILE, OUTPUT_CSV_FILE)
    print("--- Script Finished ---")

if __name__ == '__main__':
    main()