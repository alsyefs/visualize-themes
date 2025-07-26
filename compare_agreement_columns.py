import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score
import simpledorff
import sys
import os
import config


OUTPUT_DIRECTORY = "output"
OUTPUT_FILENAME = "agreements.txt"

def interpret_kappa(kappa_value):
    """Provides a qualitative interpretation of a Kappa score."""
    if pd.isna(kappa_value):
        return "Not applicable"
    if kappa_value < 0:
        return "Poor agreement"
    elif 0 <= kappa_value <= 0.20:
        return "Slight agreement"
    elif 0.21 <= kappa_value <= 0.40:
        return "Fair agreement"
    elif 0.41 <= kappa_value <= 0.60:
        return "Moderate agreement"
    elif 0.61 <= kappa_value <= 0.80:
        return "Substantial agreement"
    elif 0.81 <= kappa_value < 1.00:
        return "Almost perfect agreement"
    elif kappa_value == 1.00:
        return "Perfect agreement"
    else:
        return "Could not interpret kappa value"

def calculate_agreement(file_path, coder_cols):
    """
    Calculates and prints multiple inter-rater reliability metrics,
    treating blank cells in specified columns as 0.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return

    # --- KEY CHANGE: Fill blank cells (NaN) with 0 in the specified columns ---
    for col in coder_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            print(f"Warning: Column '{col}' not found in the file.")
            # Create the column and fill with 0 if it doesn't exist
            df[col] = 0

    # Convert columns to integer type for robustness
    df[coder_cols] = df[coder_cols].astype(int)

    # --- Calculations proceed as before ---
    analyzed_segments = len(df)

    if analyzed_segments == 0:
        print(f"Error: No data to analyze in '{file_path}'.")
        return

    # --- Basic Agreement ---
    agreements = (df[coder_cols[0]] == df[coder_cols[1]]).sum()
    agreement_percentage = (agreements / analyzed_segments) * 100

    # --- Cohen's Kappa ---
    kappa = cohen_kappa_score(df[coder_cols[0]], df[coder_cols[1]])

    # --- Krippendorff's Alpha ---
    df_long = pd.melt(df.reset_index(), id_vars='index', value_vars=coder_cols,
                      var_name='rater', value_name='label')
    try:
        kripp_alpha = simpledorff.calculate_krippendorffs_alpha_for_df(df_long,
                                                                       experiment_col='index',
                                                                       annotator_col='rater',
                                                                       class_col='label')
    except Exception as e:
        kripp_alpha = np.nan
        print(f"\nCould not calculate Krippendorff's Alpha. Error: {e}\n")


    # --- Generate Report ---
    report = []
    report.append("="*46)
    report.append("            AGREEMENT SUMMARY")
    report.append("="*46)
    report.append(f"File: '{file_path}'")
    report.append(f"Coders: {', '.join(coder_cols)}")
    report.append("\n(Note: Blank cells have been treated as 0)")
    report.append(f"\nTotal Segments Analyzed: {analyzed_segments}")
    report.append(f"Agreed on: {agreements}")
    report.append(f"Disagreed on: {analyzed_segments - agreements}")
    report.append(f"Percentage of Agreement: {agreement_percentage:.2f}%")
    report.append("="*46)

    report.append("\n--- Inter-Rater Reliability Metrics ---")
    report.append(f"Cohen's Kappa (κ):       {kappa:.4f} ({interpret_kappa(kappa)})")
    report.append(f"Krippendorff's Alpha (α):{kripp_alpha:.4f} ({interpret_kappa(kripp_alpha)})")
    report.append("-"*40)

    final_report = "\n".join(report)

    # --- Save and Print ---
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    output_file_path = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)
    with open(output_file_path, 'w') as f:
        f.write(final_report)

    print(final_report)
    print(f"\nReport successfully saved to '{output_file_path}'")

def main():
    """Main function to trigger the analysis."""
    calculate_agreement(config.IRR_AGREEMENT_INPUT_FILE, config.IRR_AGREEMENT_COLUMNS)

if __name__ == "__main__":
    main()