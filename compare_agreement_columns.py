import glob
import pandas as pd
import numpy as np
import simpledorff
import sys
import os
import config
import warnings
from sklearn.metrics import cohen_kappa_score, f1_score

OUTPUT_DIRECTORY = "output"
OUTPUT_FILENAME = "agreements.txt"


def interpret_kappa(kappa_value):
    """Provides a qualitative interpretation of a Kappa score."""
    if pd.isna(kappa_value):
        return "Not applicable"
    if kappa_value < 0:
        return "Poor agreement"
    elif kappa_value <= 0.20:
        return "Slight agreement"
    elif kappa_value <= 0.40:
        return "Fair agreement"
    elif kappa_value <= 0.60:
        return "Moderate agreement"
    elif kappa_value <= 0.80:
        return "Substantial agreement"
    elif kappa_value < 1.00:
        return "Almost perfect agreement"
    elif kappa_value == 1.00:
        return "Perfect agreement"
    else:
        return "Could not interpret kappa value"


def interpret_f1(f1_value):
    """Provides a qualitative interpretation of F1 Score."""
    if pd.isna(f1_value):
        return "Not applicable"
    elif f1_value >= 0.8:
        return "Strong/Excellent agreement"
    elif 0.6 <= f1_value < 0.8:
        return "Good/Substantial agreement"
    elif 0.4 <= f1_value < 0.6:
        return "Moderate agreement"
    else:
        return "Weak/Poor agreement"


def get_simple_verdict(f1_value):
    """Returns a single-word verdict based on F1 score."""
    if pd.isna(f1_value):
        return "N/A"
    elif f1_value == 1.0:
        return "Perfect"
    elif f1_value >= 0.8:
        return "Strong"
    elif f1_value >= 0.6:
        return "Good"
    elif f1_value >= 0.4:
        return "Moderate"
    elif f1_value > 0.0:
        return "Weak"
    else:
        return "No Agreement"


def count_words(text):
    """Simple word count helper."""
    if pd.isna(text):
        return 0
    return len(str(text).split())


def calculate_per_code_metrics(df, coder_cols):
    """
    Calculates reliability metrics for each unique code individually
    and computes the Macro-Average (unweighted mean of all codes).
    """
    unique_codes = df["code"].unique()
    metrics_list = []

    for code in unique_codes:
        # Filter data for this specific code
        subset = df[df["code"] == code].copy()

        # We need at least some data to calculate metrics
        if len(subset) == 0:
            continue

        # Calculate F1 for this code
        # Uses the first two coders found
        f1 = np.nan
        if len(coder_cols) >= 2:
            try:
                f1 = f1_score(
                    subset[coder_cols[0]],
                    subset[coder_cols[1]],
                    pos_label=1,
                    zero_division=0,
                )
            except Exception:
                f1 = 0.0

        # Calculate Kappa for this code
        kappa = np.nan
        if len(coder_cols) == 2:
            # Suppress warnings for constant data (e.g., if a code is present in ALL rows or NO rows of the subset)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    # labels=[0, 1] ensures sklearn handles cases where only 0s or only 1s exist in the subset
                    kappa = cohen_kappa_score(
                        subset[coder_cols[0]], subset[coder_cols[1]], labels=[0, 1]
                    )
                except Exception:
                    kappa = np.nan

        metrics_list.append({"code": code, "n": len(subset), "f1": f1, "kappa": kappa})

    metrics_df = pd.DataFrame(metrics_list)

    # Calculate Macro Averages (ignoring NaNs)
    avg_f1 = metrics_df["f1"].mean()
    avg_kappa = metrics_df["kappa"].mean()

    return avg_f1, avg_kappa, metrics_df


def calculate_agreement(file_path, coder_cols, overlap_percentage):
    """
    Calculates and prints multiple inter-rater reliability metrics,
    treating blank cells in specified columns as 0.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return

    # Fill blank cells (NaN) with 0 in the specified columns
    for col in coder_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            print(f"Warning: Column '{col}' not found in the file. Created one.")
            # Create the column and fill with 0 if it doesn't exist
            df[col] = 0

    # Convert columns to integer type for robustness
    df[coder_cols] = df[coder_cols].astype(int)

    # Filter for Mutual Segments Only (Advanced Subset Logic)
    if config.CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY:
        print(f"\n[MODE] Filtering for Mutual Segments (Ignoring Omissions/Subsets)...")
        initial_len = len(df)

        # We need to determine which rows to KEEP based on "Conflict vs Omission"
        # Group by Text+Participant to see the full coding picture for each segment
        indices_to_keep = []

        # 1. Group by segment (using 'p' and 'text')
        # We iterate over the groups to make context-aware decisions
        for _, group in df.groupby(["p", "text"]):

            # 2. Identify the set of codes applied by each coder for this specific segment
            # Structure: { 'coder1': {'codeA', 'codeB'}, 'coder2': {'codeA'} }
            coder_code_sets = {col: set() for col in coder_cols}

            for idx, row in group.iterrows():
                code = row["code"]
                for col in coder_cols:
                    if row[col] == 1:
                        coder_code_sets[col].add(code)

            # 3. Decide which rows in this group to keep
            for idx, row in group.iterrows():
                code = row["code"]

                # Rule A: If EVERY coder marked this specific row (1, 1), it's an agreement. KEEP IT.
                if row[coder_cols].sum() == len(coder_cols):
                    indices_to_keep.append(idx)
                    continue

                # Rule B: If it's a disagreement (1, 0) or (0, 1), is it a CONFLICT or an OMISSION?
                # It is a conflict ONLY if the "silent" coder has a DIFFERENT code elsewhere for this text.

                is_conflict = False

                # Check each coder
                for col in coder_cols:
                    # If this coder missed this code (value is 0)
                    if row[col] == 0:
                        # Check if they have ANY codes for this segment that the other coders DO NOT have.
                        # If they have a "Unique Code", it implies they chose X instead of Y (Conflict).
                        # If they have NO "Unique Codes" (their codes are a subset of others), it is Omission.

                        my_codes = coder_code_sets[col]

                        # Get all codes used by ANYONE ELSE
                        other_coders = [c for c in coder_cols if c != col]
                        all_other_codes = set()
                        for oc in other_coders:
                            all_other_codes.update(coder_code_sets[oc])

                        # Does this coder have a code that nobody else used?
                        # Example ("some text segment"): Me={Y}, Others={X}. Y is not in {X}. -> Unique Code Exists -> CONFLICT.
                        # Example ("some text segment"): Me={A}, Others={A, B}. My codes are all in Others. -> No Unique -> OMISSION.
                        has_unique_code = not my_codes.issubset(all_other_codes)

                        if has_unique_code:
                            is_conflict = True
                            break

                if is_conflict:
                    indices_to_keep.append(idx)
                else:
                    # It is an Omission (Subset).
                    # treat as statistical agreement.
                    indices_to_keep.append(idx)

                    # Force values to 1 for statistical calculation in memory
                    # (This matches the logic applied in mark_agreements.py)
                    for col in coder_cols:
                        df.at[idx, col] = 1

        # Apply the filter
        df = df.loc[indices_to_keep]

        print(
            f"Dropped {initial_len - len(df)} rows (Omissions). Analyzed subset: {len(df)} rows."
        )
        if len(df) == 0:
            print(
                "Warning: No mutually identified segments found! Agreement will be 0/NaN."
            )

    # Calculations proceed as before
    analyzed_segments = len(df)

    # Try to Calculate True Negatives from Transcripts:
    adjusted_kappa = None
    estimated_tn = 0
    tn_source = "None"
    prevalence_percentage = None

    # Check if config has the directory and it exists
    transcripts_dir = getattr(config, "TRANSCRIPTS_DIRECTORY", None)

    # Check existence before creating to provide accurate feedback
    if transcripts_dir and os.path.exists(transcripts_dir):
        txt_files = glob.glob(os.path.join(transcripts_dir, "*.txt"))

        if txt_files:
            print(
                f"Found {len(txt_files)} transcript files. Calculating True Negatives..."
            )

            # 1. Calculate Coded Volume
            unique_coded_texts = df["text"].unique()
            coded_word_count = sum(count_words(t) for t in unique_coded_texts)
            avg_segment_len = (
                int(coded_word_count / len(unique_coded_texts))
                if len(unique_coded_texts) > 0
                else 0
            )

            # 2. Calculate Total Volume
            total_source_words = 0
            for filepath in txt_files:
                try:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        total_source_words += count_words(f.read())
                except Exception as e:
                    print(f"Warning reading {filepath}: {e}")

            # Apply safety margin for headers/footers/metadata
            # This reduces the "Silence" volume to ensure we don't inflate Kappa with non-codable text
            margin = getattr(config, "TRANSCRIPT_NON_CODABLE_MARGIN", 0.0)
            if margin > 0:
                deduction = int(total_source_words * margin)
                total_source_words -= deduction
                print(
                    f"Applied {margin*100}% reduction for non-codable text (headers/footers). Adjusted source words: {total_source_words}"
                )

            # 3. Estimate Silence
            uncoded_words = total_source_words - coded_word_count
            if uncoded_words > 0 and avg_segment_len > 0:
                estimated_tn = int(uncoded_words / avg_segment_len)
                tn_source = "Estimated from Transcripts"

                # 4. Calculate Adjusted Kappa
                # Create a virtual dataset of zeros
                zeros_df = pd.DataFrame(
                    {
                        coder_cols[0]: [0] * estimated_tn,
                        coder_cols[1]: [0] * estimated_tn,
                    }
                )
                # Combine actual data + zeros
                combined_col1 = pd.concat(
                    [df[coder_cols[0]], zeros_df[coder_cols[0]]], ignore_index=True
                )
                combined_col2 = pd.concat(
                    [df[coder_cols[1]], zeros_df[coder_cols[1]]], ignore_index=True
                )

                adjusted_kappa = cohen_kappa_score(combined_col1, combined_col2)
                # Calculate Prevalence %
                # (Rows that actually had data) / (Total Rows including Silence)
                total_virtual_rows = len(combined_col1)
                coded_rows_count = len(df)
                prevalence_percentage = (coded_rows_count / total_virtual_rows) * 100
            else:
                print(
                    "Warning: Coded words > Source words or empty data. Cannot calc TNs."
                )
        else:
            print(
                f"Transcripts directory '{transcripts_dir}' is empty. Skipping TN calculation."
            )
    else:
        print("Transcripts directory not found. Skipping TN calculation.")
        # Create the directory now for future use
        if transcripts_dir:
            os.makedirs(transcripts_dir, exist_ok=True)

    # Check for True Negatives (rows where ALL coders have 0)
    # This works for any number of coder columns
    true_negatives = (df[coder_cols] == 0).all(axis=1).sum()
    has_missing_negatives = true_negatives == 0
    # If we didn't calculate prevalence via transcripts, but we have 0s in the CSV, calculate it here
    if prevalence_percentage is None and not has_missing_negatives and len(df) > 0:
        # Prevalence = (Rows with at least one coding) / Total Rows
        rows_with_coding = (df[coder_cols].sum(axis=1) > 0).sum()
        prevalence_percentage = (rows_with_coding / len(df)) * 100
    if analyzed_segments == 0:
        print(f"Error: No data to analyze in '{file_path}'.")
        return

    # Basic Agreement
    if len(coder_cols) >= 2:
        agreements = (df[coder_cols[0]] == df[coder_cols[1]]).sum()
        agreement_percentage = (agreements / analyzed_segments) * 100
    else:
        # Single coder implies internal consistency (trivial agreement)
        agreements = analyzed_segments
        agreement_percentage = 100.0

    # Cohen's Kappa (Only valid for exactly 2 coders)
    kappa = np.nan
    if len(coder_cols) == 2:
        kappa = cohen_kappa_score(df[coder_cols[0]], df[coder_cols[1]])
    elif len(coder_cols) > 2:
        print(
            f"Info: Skipping Cohen's Kappa (Requires exactly 2 coders, found {len(coder_cols)})."
        )
    else:
        print("Info: Skipping Cohen's Kappa (Not enough coders).")

    # Calculate F1 Score (Pairwise average or binary if 2 coders)
    # If > 2 coders, this computes the average F1 of all pairs, or you can skip it.
    # For simplicity here, we stick to the first two if available, or skip.
    f1 = np.nan
    if len(coder_cols) >= 2:
        f1 = f1_score(df[coder_cols[0]], df[coder_cols[1]], pos_label=1)

    # Krippendorff's Alpha
    df_long = pd.melt(
        df.reset_index(),
        id_vars="index",
        value_vars=coder_cols,
        var_name="rater",
        value_name="label",
    )
    try:
        kripp_alpha = simpledorff.calculate_krippendorffs_alpha_for_df(
            df_long, experiment_col="index", annotator_col="rater", class_col="label"
        )
    except Exception as e:
        kripp_alpha = np.nan
        print(f"\nCould not calculate Krippendorff's Alpha. Error: {e}\n")

    # Calculate Per-Code (Macro) Metrics
    macro_f1, macro_kappa, per_code_df = calculate_per_code_metrics(df, coder_cols)

    # Generate Report
    report = []
    report.append("=" * 60)
    report.append(f"{'INTER-RATER RELIABILITY REPORT':^60}")
    report.append("=" * 60)

    report.append("\n1. DATASET SUMMARY")
    report.append("-" * 30)
    report.append(f"{'File Name':<25} : {os.path.basename(file_path)}")
    # Clean coder names for display (remove '_agreement')
    display_coders = [c.replace("_agreement", "") for c in coder_cols]
    report.append(f"{'Coders':<25} : {', '.join(display_coders)}")
    report.append(f"{'Fuzzy-Match Threshold':<25} : {overlap_percentage:.2f} (Jaccard)")
    report.append(f"{'Total Segments':<25} : {analyzed_segments}")

    # Calculate raw agreements for the report
    agreements_count = (
        df[coder_cols].eq(df[coder_cols].iloc[:, 0], axis=0).all(axis=1)
    ).sum()
    disagreements_count = analyzed_segments - agreements_count

    report.append(f"{'Perfect Agreement':<25} : {agreements_count}")
    report.append(f"{'Disagreements':<25} : {disagreements_count}")

    if adjusted_kappa is not None:
        report.append(
            f"{'Est. True Negatives':<25} : {estimated_tn} (derived from transcripts)"
        )

    if prevalence_percentage is not None:
        report.append(f"{'Code Prevalence':<25} : {prevalence_percentage:.2f}%")
    else:
        report.append(f"{'Code Prevalence':<25} : N/A")

    report.append("\n2. RELIABILITY METRICS")
    report.append("-" * 30)
    report.append(f"{'Metric':<27} | {'Value':<10} | {'Interpretation'}")
    report.append("-" * 60)

    # F1 Score Row
    report.append(f"{'F1-Score (Dice)':<27} | {f1:<10.4f} | {interpret_f1(f1)}")

    # Agreement Row
    report.append(f"{'Percent Agreement':<27} | {agreement_percentage:<9.2f}% | -")

    # Kappa Row configuration
    if adjusted_kappa is not None:
        k_name = "Cohen's Kappa (Pooled, Adj)"
        k_val = adjusted_kappa
        k_note = ""
    elif has_missing_negatives:
        k_name = "Cohen's Kappa (Pooled, Raw)"
        k_val = kappa
        k_note = " [INVALID - Missing Negatives]"
    else:
        k_name = "Cohen's Kappa (Pooled)"
        k_val = kappa
        k_note = ""

    report.append(f"{k_name:<27} | {k_val:<10.4f} | {interpret_kappa(k_val)}{k_note}")

    # Alpha Row
    alpha_label = "Krippendorff's Alpha"
    report.append(
        f"{alpha_label:<27} | {kripp_alpha:<10.4f} | {interpret_kappa(kripp_alpha)}"
    )

    report.append("-" * 60)
    report.append(f"{'MACRO-AVERAGE (Mean of all codes)':^60}")
    report.append("-" * 60)
    report.append(
        f"{'Average F1-Score':<25} | {macro_f1:<10.4f} | {interpret_f1(macro_f1)}"
    )
    report.append(
        f"{'Average Kappa':<25} | {macro_kappa:<10.4f} | {interpret_kappa(macro_kappa)}"
    )

    report.append("-" * 60)

    # Explanation Text
    explanation_text = get_results_explanation(
        agreement_percentage,
        k_val,  # Pass the kappa we decided to show
        f1,
        has_missing_negatives and adjusted_kappa is None,
        prevalence_percentage,
    )
    report.append(explanation_text)

    # Appending per-code details to the report for debugging/deep dive
    report.append("\n" + "=" * 105)
    report.append(f"{'DETAILED PER-CODE BREAKDOWN':^75}")
    report.append("=" * 105)
    # Adjusted widths and added Verdict column
    report.append(f"{'Code':<60} | {'N':<5} | {'F1':<6} | {'Kappa':<6} | {'Verdict'}")
    report.append("-" * 105)

    # Sort by worst F1 score to highlight problem areas
    per_code_df = per_code_df.sort_values(by="f1", ascending=True)

    for _, row in per_code_df.iterrows():
        c_name = str(row["code"])[:60]  # Truncate for display
        k_str = f"{row['kappa']:.3f}" if pd.notna(row["kappa"]) else "nan"

        # Get simple verdict
        verdict = get_simple_verdict(row["f1"])

        report.append(
            f"{c_name:<60} | {row['n']:<5} | {row['f1']:<6.3f} | {k_str:<6} | {verdict}"
        )

    report.append("-" * 105)

    # Reference Ranges Section
    report.append("\n" + "=" * 75)
    report.append(f"{'REFERENCE GUIDELINES':^75}")
    report.append("=" * 75)
    report.append("F1-Score (Dice):")
    report.append("  > 0.80 : Strong/Excellent")
    report.append("  > 0.60 : Good/Substantial")
    report.append("  > 0.40 : Moderate")
    report.append("  < 0.40 : Weak/Poor")

    report.append("\nKappa (κ) & Alpha (α):")
    report.append("  > 0.80 : Almost Perfect")
    report.append("  > 0.60 : Substantial")
    report.append("  > 0.40 : Moderate")
    report.append("  > 0.20 : Fair")
    report.append("  < 0.20 : Slight/Poor")

    # Added Technical Notes to explain the confusing values
    report.append("\nTECHNICAL NOTES:")
    report.append(
        "  * Kappa = nan   : Mathematical artifact. Usually means 'Perfect Agreement'"
    )
    report.append(
        "                    (Both coders selected this code for every item in this subset)."
    )
    report.append("  * Kappa < 0     : Disagreement is worse than random chance.")
    report.append(
        "  * Verdict       : Based on F1-Score (Dice), which is generally more reliable"
    )
    report.append("                    for rare codes than Kappa.")
    report.append("=" * 75)

    final_report = "\n".join(report)
    # Save and Print
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    output_file_path = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)
    # with open(output_file_path, 'w') as f:
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    print(final_report)
    print(f"\nReport successfully saved to '{output_file_path}'")


def get_results_explanation(
    agreement_pct, kappa, f1, has_missing_negatives, prevalence_pct=None
):
    """
    Generates a structured research explanation for the results.
    """
    explanation = []
    explanation.append("\nINTERPRETATION & ANALYSIS")
    explanation.append("-" * 30)

    # 1. Data Structure Context
    explanation.append("1. DATASET CONTEXT:")
    if has_missing_negatives:
        explanation.append("   - Dataset lacks 'True Negatives' (non-coded segments).")
        explanation.append(
            "   - IMPLICATION: Cohen's Kappa is mathematically unreliable here."
        )
    else:
        explanation.append(
            "   - Dataset includes 'True Negatives' (silence/non-coded areas)."
        )
        explanation.append("   - IMPLICATION: Cohen's Kappa is mathematically valid.")

    # 2. Paradox Check (High F1, Low Kappa, Low Prevalence)
    is_paradox = (
        not has_missing_negatives
        and prevalence_pct is not None
        and prevalence_pct < 15.0
        and kappa < 0.40
        and f1 > 0.50
    )

    explanation.append("\n2. STATISTICAL OBSERVATIONS:")
    if is_paradox:
        explanation.append(
            f"   * PARADOX DETECTED: Low Kappa ({kappa:.2f}) vs High F1 ({f1:.2f})."
        )
        explanation.append(f"   * CAUSE: Low Code Prevalence ({prevalence_pct:.2f}%).")
        explanation.append(
            "     When specific codes are rare in a large text, Kappa is excessively"
        )
        explanation.append(
            "     penalized by the high volume of agreement on empty space."
        )
    else:
        diff = (f1 * 100) - agreement_pct
        if diff > 10:
            explanation.append("   * F1-Score significantly exceeds Percent Agreement.")
            explanation.append(
                "     This is common in coding tasks; F1 focuses on the target codes,"
            )
            explanation.append(
                "     while Agreement is sensitive to exact row-by-row matching."
            )
        elif diff < -10:
            explanation.append("   * High Agreement but Low F1-Score.")
            explanation.append(
                "     This usually indicates high agreement on what *not* to code,"
            )
            explanation.append("     but disagreement on the specific codes applied.")
        else:
            explanation.append(
                "   * Metrics are consistent (F1 and Agreement are aligned)."
            )

    # 3. Final Recommendation
    explanation.append("\n3. RECOMMENDATION FOR REPORTING:")
    if is_paradox:
        explanation.append("   > PRIMARY METRIC: Report F1-Score (Dice Coefficient).")
        explanation.append(
            "   > REASONING: Due to the 'Prevalence Paradox', Kappa underestimates reliability."
        )
        explanation.append(
            f"   > NOTE: You may cite the low prevalence ({prevalence_pct:.1f}%) as context."
        )
    elif has_missing_negatives:
        explanation.append("   > PRIMARY METRIC: F1-Score.")
        explanation.append(
            "   > REASONING: Kappa requires true negatives (silence), which are missing."
        )
    else:
        explanation.append(
            "   > PRIMARY METRIC: You may report both Kappa and F1-Score."
        )
        explanation.append(
            "   > CONTEXT: Both metrics are statistically valid for this dataset."
        )

    return "\n".join(explanation)


def main():
    # Main function to trigger the analysis
    input_file = config.IRR_AGREEMENT_INPUT_FILE
    try:
        # Read just the header to find columns dynamically
        df_head = pd.read_csv(input_file, nrows=0)
        # Identify columns ending in '_agreement'
        agreement_cols = [c for c in df_head.columns if c.endswith("_agreement")]
        if not agreement_cols:
            print("Error: No '_agreement' columns found in the CSV.")
            return
        print(f"Dynamically identified coder columns: {agreement_cols}")
        # Pass the overlap percentage from config to the calculation function
        calculate_agreement(input_file, agreement_cols, config.WORDS_OVERLAP_PERCENTAGE)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
