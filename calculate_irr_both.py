import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score
import simpledorff
import sys
import os
import config

# GLOBALS: Define input file and columns to be analyzed.
IRR_AGREEMENT_INPUT_FILE = config.IRR_AGREEMENT_INPUT_FILE
IRR_AGREEMENT_COLUMNS = config.IRR_AGREEMENT_COLUMNS
OUTPUT_DIRECTORY = "output"
OUTPUT_FILENAME = "agreements.txt"


def interpret_kappa(kappa_value):
    """Provides a qualitative interpretation of a Cohen's Kappa or Fleiss' Kappa score."""
    if np.isnan(kappa_value):
        return "Could not interpret kappa value"
    if kappa_value < 0:
        return "Poor agreement (less than chance)"
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

def calculate_fleiss_kappa(df, coder_cols):
    """
    Calculates Fleiss' Kappa for multiple raters.
    """
    data = df[coder_cols]
    n_raters = len(coder_cols)
    n_subjects = len(data)
    categories = sorted(pd.unique(data.values.ravel('K')))
    n_categories = len(categories)

    if n_raters < 2 or n_subjects == 0 or n_categories < 2:
        return 1.0, 1.0, 1.0 if n_categories < 2 else (0.0, 0.0, 0.0)

    count_matrix = np.zeros((n_subjects, n_categories))
    for i in range(n_subjects):
        for j in range(n_raters):
            val = data.iloc[i, j]
            if val in categories:
                cat_index = categories.index(val)
                count_matrix[i, cat_index] += 1

    P_i = (np.sum(count_matrix * (count_matrix - 1), axis=1)) / (n_raters * (n_raters - 1))
    P_bar = np.mean(P_i)
    p_j = np.sum(count_matrix, axis=0) / (n_subjects * n_raters)
    P_e_fleiss = np.sum(p_j**2)

    if 1 - P_e_fleiss == 0:
        return 1.0 if P_bar == 1.0 else 0.0, P_bar, P_e_fleiss

    kappa = (P_bar - P_e_fleiss) / (1 - P_e_fleiss)
    return kappa, P_bar, P_e_fleiss

def generate_detailed_report(df, coder_cols, results):
    """Generates a report explaining the calculation steps."""
    print("\n" + "="*50)
    print(" DETAILED CALCULATION REPORT")
    print("="*50)

    if 'cohen_kappa' in results:
        print("\n--- 1. Cohen's Kappa (for 2 coders) ---")
        p_o = results['cohen_po']
        p_e = results['cohen_pe']
        kappa = results['cohen_kappa']
        print(f"a. Observed Agreement (P_o): {p_o:.4f}")
        print(f"   Calculation: {results['agreements']} (agreements) / {results['total_segments_analyzed']} (total) = {p_o:.4f}\n")
        print(f"b. Expected Agreement by Chance (P_e): {p_e:.4f}\n")
        print(f"c. Cohen's Kappa (κ) Formula: κ = (P_o - P_e) / (1 - P_e)")
        print(f"   κ = ({p_o:.4f} - {p_e:.4f}) / (1 - {p_e:.4f}) = {kappa:.4f}")

    if 'fleiss_kappa' in results:
        print("\n--- 2. Fleiss' Kappa (for 2+ coders) ---")
        p_bar = results['fleiss_po']
        p_e_fleiss = results['fleiss_pe']
        fleiss_k = results['fleiss_kappa']
        print(f"a. Observed Agreement (P̄): {p_bar:.4f}\n")
        print(f"b. Expected Agreement by Chance (P_e): {p_e_fleiss:.4f}\n")
        print(f"c. Fleiss' Kappa (κ) Formula: κ = (P̄ - P_e) / (1 - P_e)")
        print(f"   κ = ({p_bar:.4f} - {p_e_fleiss:.4f}) / (1 - {p_e_fleiss:.4f}) = {fleiss_k:.4f}")

    if 'kripp_alpha' in results:
        print("\n--- 3. Krippendorff's Alpha ---")
        alpha_val = results.get('kripp_alpha', np.nan)
        print("   Krippendorff's Alpha is a flexible metric that works with any number of coders and handles missing data.\n")
        print("a. Observed Disagreement (D_o) & Expected Disagreement (D_e):")
        print("   The simpledorff library does not expose these intermediate values.")
        print("   They are used internally to calculate the final score.\n")
        print(f"c. Krippendorff's Alpha (α) Formula: α = 1 - (D_o / D_e)")
        print(f"   The calculated value for your data is {alpha_val:.4f}.")

    print("\n" + "="*50)

def calculate_agreement(file_path, coder_cols):
    """
    Calculates and prints multiple inter-rater reliability metrics from a CSV file.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        sys.exit(1)

    initial_segments = len(df)
    df.dropna(subset=coder_cols, inplace=True)
    analyzed_segments = len(df)
    
    results = {
        'total_segments_initial': initial_segments,
        'total_segments_analyzed': analyzed_segments
    }

    if len(coder_cols) == 2:
        c1, c2 = coder_cols[0], coder_cols[1]
        agreements = (df[c1] == df[c2]).sum()
        p_o = agreements / analyzed_segments
        p_c1 = df[c1].value_counts(normalize=True)
        p_c2 = df[c2].value_counts(normalize=True)
        p_e = sum(p_c1.get(cat, 0) * p_c2.get(cat, 0) for cat in set(df[c1]) | set(df[c2]))
        
        results.update({
            'cohen_kappa': (p_o - p_e) / (1 - p_e),
            'agreements': agreements,
            'disagreements': analyzed_segments - agreements,
            'agreement_percentage': (agreements / analyzed_segments) * 100 if analyzed_segments > 0 else 0,
            'cohen_po': p_o, 'cohen_pe': p_e
        })

    fleiss_k, fleiss_po, fleiss_pe = calculate_fleiss_kappa(df, coder_cols)
    results.update({'fleiss_kappa': fleiss_k, 'fleiss_po': fleiss_po, 'fleiss_pe': fleiss_pe})
    
    df_long = pd.melt(df.reset_index(), id_vars='index', value_vars=coder_cols, var_name='rater', value_name='label')
    
    try:
        k_alpha_result = simpledorff.calculate_krippendorffs_alpha_for_df(
            df_long,
            experiment_col='index',
            annotator_col='rater',
            class_col='label'
        )
        if isinstance(k_alpha_result, pd.DataFrame):
            results['kripp_alpha'] = k_alpha_result['alpha'].iloc[0]
        else:
            results['kripp_alpha'] = k_alpha_result
    except Exception as e:
        print(f"\nCould not calculate Krippendorff's Alpha. Error: {e}\n")
        results['kripp_alpha'] = np.nan

    print("="*46)
    print("            AGREEMENT SUMMARY")
    print("="*46)
    print(f"File: '{file_path}'")
    print(f"Coders: {', '.join(coder_cols)}")
    print(f"\nTotal segments in file: {results['total_segments_initial']}")
    print(f"Segments with missing data: {results['total_segments_initial'] - results['total_segments_analyzed']}")
    print("-"*46)
    print(f"Segments Analyzed: {results['total_segments_analyzed']}")
    if 'agreements' in results:
        print(f"Agreed on: {results['agreements']}")
        print(f"Disagreed on: {results['disagreements']}")
        print(f"Percentage of Agreement: {results['agreement_percentage']:.2f}%")
    print("="*46)

    print("\n--- Inter-Rater Reliability Metrics ---")
    if 'cohen_kappa' in results:
        print(f"Cohen's Kappa (κ):       {results['cohen_kappa']:.4f} ({interpret_kappa(results['cohen_kappa'])})")
    print(f"Fleiss' Kappa (κ):       {results['fleiss_kappa']:.4f} ({interpret_kappa(results['fleiss_kappa'])})")
    print(f"Krippendorff's Alpha (α):{results.get('kripp_alpha', np.nan):.4f} ({interpret_kappa(results.get('kripp_alpha', np.nan))})")
    print("-"*40)

    generate_detailed_report(df, coder_cols, results)

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    output_file_path = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)
    
    with open(output_file_path, 'w') as f:
        original_stdout = sys.stdout
        sys.stdout = f
        calculate_agreement(IRR_AGREEMENT_INPUT_FILE, IRR_AGREEMENT_COLUMNS)
        sys.stdout = original_stdout