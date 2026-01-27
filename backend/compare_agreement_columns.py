# backend/compare_agreement_columns.py
import glob
import pandas as pd
import numpy as np
import simpledorff
import sys
import os
import backend.config as config
import warnings
from collections import Counter
from sklearn.metrics import cohen_kappa_score, f1_score
from sklearn.preprocessing import LabelEncoder

OUTPUT_DIRECTORY = config.OUTPUT_DIRECTORY
OUTPUT_FILENAME = config.OUTPUT_FILENAME


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


def generate_math_section(
    df,
    coder_cols,
    f1_score_val,
    kappa_score_val,
    tn_count,
    alpha_val=None,
    is_multi_class=False,
    label_cols=None,
):
    """
    Generates a text block that breaks down the math.
    Handles both Binary (1/0) and Multi-Class (Label A/Label B) logic.
    """
    lines = []
    lines.append("\n3. TRANSPARENCY & CALCULATIONS (SHOWING THE MATH)")
    lines.append("-" * 60)
    lines.append("To ensure transparency, here are the exact numbers used to")
    lines.append("calculate the scores above.")
    lines.append("")

    if is_multi_class and label_cols:
        c1_col, c2_col = label_cols[0], label_cols[1]

        # Filter out 'No Code' for calculation if desired, or keep them.
        # For Kappa, we usually keep them if they are relevant to the Method.
        # Here we use the dataframe passed in (which is already filtered by Method).

        # 1. Raw Counts
        # Calculate Agreements vs Disagreements on LABELS
        agreements = len(df[df[c1_col] == df[c2_col]])
        disagreements = len(df) - agreements
        total_analyzed = len(df)

        lines.append(f"A. RAW COUNTS (Multi-Class Confusion)")
        lines.append(
            f"   Mode: Comparing specific labels (e.g. '{df[c1_col].iloc[0] if len(df)>0 else 'A'}' vs '{df[c2_col].iloc[0] if len(df)>0 else 'B'}')"
        )
        lines.append(f"   (1) Agreements (Same Label)    : {agreements}")
        lines.append(f"   (2) Disagreements (Diff Label) : {disagreements}")
        lines.append(f"   ----------------------------------------")
        lines.append(f"   Total Analyzed Segments        : {total_analyzed}")
        lines.append("")

        lines.append("B. F1-SCORE CALCULATION")
        lines.append("   (Calculated as weighted average of per-label F1 scores)")
        lines.append(f"   Result : {f1_score_val:.4f}")
        lines.append("")

        # 2. Kappa Math
        lines.append("C. COHEN'S KAPPA CALCULATION")
        lines.append("   Formula: (Po - Pe) / (1 - Pe)")

        # Step 1: Po
        po = agreements / total_analyzed if total_analyzed > 0 else 0
        lines.append("")
        lines.append("   Step 1: Observed Agreement (Po)")
        lines.append(
            f"       Po = Agreements / Total = {agreements} / {total_analyzed} = {po:.4f}"
        )

        # Step 2: Pe
        # Get all unique labels across both columns
        # Ensure we convert to string and handle potential NaNs before creating the set
        all_labels = set(df[c1_col].fillna("No Code").astype(str).unique()) | set(
            df[c2_col].fillna("No Code").astype(str).unique()
        )
        all_labels = sorted(list(all_labels))

        lines.append("")
        lines.append("   Step 2: Expected Agreement by Chance (Pe)")
        lines.append("       Marginals (Frequency of each label):")

        pe_sum = 0

        # Header for marginals table
        # lines.append(
        #     f"       {'Label':<20} | {'Coder 1':<10} | {'Coder 2':<10} | {'Probability Product'}"
        # )
        # lines.append(f"       {'-'*20} | {'-'*10} | {'-'*10} | {'-'*19}")

        c1_counts = Counter(df[c1_col].astype(str))
        c2_counts = Counter(df[c2_col].astype(str))

        for label in all_labels:
            n1 = c1_counts.get(label, 0)
            n2 = c2_counts.get(label, 0)
            p1 = n1 / total_analyzed if total_analyzed > 0 else 0
            p2 = n2 / total_analyzed if total_analyzed > 0 else 0
            prod = p1 * p2
            pe_sum += prod

        #     # Truncate label if too long
        #     disp_label = (label[:17] + "..") if len(label) > 19 else label
        #     lines.append(
        #         f"       {disp_label:<20} | {n1:<10} | {n2:<10} | ({p1:.3f} * {p2:.3f}) = {prod:.4f}"
        #     )

        lines.append("")
        lines.append(f"       Pe (Sum of products) = {pe_sum:.4f}")

        # Step 3: Result
        lines.append("")
        lines.append("   Step 3: Final Kappa Score")
        if (1 - pe_sum) != 0:
            k_calc = (po - pe_sum) / (1 - pe_sum)
            lines.append(f"       k = ({po:.4f} - {pe_sum:.4f}) / (1 - {pe_sum:.4f})")
            lines.append(f"       k = {po-pe_sum:.4f} / {1-pe_sum:.4f} = {k_calc:.4f}")
        else:
            lines.append(f"       k = Undefined (Pe=1, Perfect Chance Agreement)")

        lines.append(f"       Result : {kappa_score_val:.4f}")
        lines.append("")

    else:
        # BINARY LOGIC (Legacy)
        c1, c2 = coder_cols[0], coder_cols[1]
        tp = len(df[(df[c1] == 1) & (df[c2] == 1)])
        fp = len(df[(df[c1] == 1) & (df[c2] == 0)])
        fn = len(df[(df[c1] == 0) & (df[c2] == 1)])
        tn = int(tn_count)

        total_analyzed = tp + fp + fn
        total_universe = total_analyzed + tn
        disagreements = fp + fn

        lines.append(f"A. RAW COUNTS (Binary Confusion Matrix)")
        lines.append(f"   (1) Mutual Agreements (Both=1) : {tp}")
        lines.append(f"   (2) Coder '{c1}' Only (1-0)    : {fp}")
        lines.append(f"   (3) Coder '{c2}' Only (0-1)    : {fn}")
        lines.append(f"   (4) True Negatives (Both=0)    : {tn} (Virtual/Derived)")
        lines.append(f"   ----------------------------------------")
        lines.append(f"   Active Segments (TP+FP+FN)     : {total_analyzed}")
        lines.append(f"   Total Universe (u)             : {total_universe}")
        lines.append("")

        # F1 MATH
        f1_calc = (2 * tp) / ((2 * tp) + fp + fn) if ((2 * tp) + fp + fn) > 0 else 0
        lines.append("B. F1-SCORE CALCULATION")
        lines.append("   Formula: 2 * Mutual / (2 * Mutual + Disagreements)")
        lines.append(f"   Step 1 : 2 * {tp} = {2 * tp}")
        lines.append(f"   Step 2 : {2 * tp} + {fp} + {fn} = {(2 * tp) + fp + fn}")
        lines.append(f"   Step 3 : {2 * tp} / {(2 * tp) + fp + fn} = {f1_calc:.4f}")
        lines.append(f"   Result : {f1_score_val:.4f}")
        lines.append("")

        # KAPPA MATH
        agreements = tp + tn
        po = agreements / total_universe if total_universe > 0 else 0

        p_c1_yes = (tp + fp) / total_universe
        p_c1_no = (tn + fn) / total_universe
        p_c2_yes = (tp + fn) / total_universe
        p_c2_no = (tn + fp) / total_universe

        pe = (p_c1_yes * p_c2_yes) + (p_c1_no * p_c2_no)
        pe_yes = p_c1_yes * p_c2_yes
        pe_no = p_c1_no * p_c2_no

        lines.append("C. COHEN'S KAPPA CALCULATION")
        lines.append("   Formula: (Po - Pe) / (1 - Pe)")
        lines.append("")
        lines.append("   Step 1: Observed Agreement (Po)")
        lines.append(
            f"       Agreements = Mutual ({tp}) + True Negatives ({tn}) = {agreements}"
        )
        lines.append(f"       Po = {agreements} / {total_universe} = {po:.4f}")
        lines.append("")
        lines.append("   Step 2: Expected Agreement by Chance (Pe)")
        lines.append("       Marginals (Total frequency of codes):")
        lines.append(
            f"         - Coder '{c1}' Yes: {tp+fp} ({p_c1_yes:.4f}) | No: {tn+fn} ({p_c1_no:.4f})"
        )
        lines.append(
            f"         - Coder '{c2}' Yes: {tp+fn} ({p_c2_yes:.4f}) | No: {tn+fp} ({p_c2_no:.4f})"
        )
        lines.append("")
        lines.append("       Probability of Random Agreement:")
        lines.append(f"       Pe = (P_c1_yes * P_c2_yes) + (P_c1_no * P_c2_no)")
        lines.append(
            f"       Pe = ({p_c1_yes:.4f} * {p_c2_yes:.4f}) + ({p_c1_no:.4f} * {p_c2_no:.4f})"
        )
        lines.append(f"       Pe = {pe_yes:.4f} + {pe_no:.4f} = {pe:.4f}")
        lines.append("")
        lines.append("   Step 3: Final Kappa Score")
        if (1 - pe) != 0:
            denom = 1 - pe
            lines.append(f"       k = ({po:.4f} - {pe:.4f}) / (1 - {pe:.4f})")
            lines.append(
                f"       k = {po-pe:.4f} / {denom:.4f} = {kappa_score_val:.4f}"
            )
        else:
            lines.append(f"       k = Undefined (Pe=1, Perfect Chance Agreement)")
            lines.append(f"       Result : {kappa_score_val}")
        lines.append("")

    # KRIPPENDORFF'S ALPHA MATH
    lines.append("D. KRIPPENDORFF'S ALPHA CALCULATION")
    lines.append("   Formula: 1 - (Do / De)")
    lines.append("   Note   : Uses sample-size correction (1 / N-1) unlike Kappa.")

    # 1. Prepare Data Vectors
    if is_multi_class and label_cols:
        col_a, col_b = df[label_cols[0]], df[label_cols[1]]
    else:
        col_a, col_b = df[coder_cols[0]], df[coder_cols[1]]

    # 2. Calculate N and Counts
    # Flatten both columns to count frequencies of every label (0/1 or Text)
    # Using simple Nominal logic (applicable to standard binary/nominal coding)
    total_units = len(df)
    num_coders = 2
    N = total_units * num_coders

    # Combine and count
    all_values = pd.concat([col_a, col_b]).astype(str)
    counts = Counter(all_values)

    lines.append("")
    lines.append("   Step 1: Count total judgments (N)")
    lines.append(f"       N = {num_coders} coders * {total_units} segments = {N}")

    # # Sort counts for consistent display
    # for label, count in sorted(counts.items()):
    #     # Truncate label if too long
    #     lbl_display = (label[:15] + "..") if len(label) > 17 else label
    #     lines.append(f"       Total '{lbl_display}' (n) = {count}")

    # 3. Calculate Do (Observed Disagreement)
    # For Nominal data, Do is simply the fraction of mismatches
    disagreements_count = (col_a != col_b).sum()
    do_val = disagreements_count / total_units if total_units > 0 else 0

    lines.append("")
    lines.append("   Step 2: Calculate Observed Disagreement (Do)")
    lines.append(f"       Do = Disagreements / Universe")
    lines.append(f"       Do = {disagreements_count} / {total_units} = {do_val:.4f}")

    # 4. Calculate De (Expected Disagreement)
    # Formula for Nominal Metric: De = [Sum of nc * (N - nc)] / [N * (N - 1)]
    # This is mathematically equivalent to the 2*n0*n1 / N(N-1) binary shortcut but works for any number of classes

    numerator_sum = sum(c * (N - c) for c in counts.values())
    denominator = N * (N - 1) if N > 1 else 1
    de_val = numerator_sum / denominator

    lines.append("")
    lines.append("   Step 3: Calculate Expected Disagreement (De)")
    if len(counts) == 2:
        # Show specific binary formula if only 2 classes (easier to read)
        keys = list(counts.keys())
        lines.append(f"       De = (2 * n_{keys[0]} * n_{keys[1]}) / (N * (N - 1))")
    else:
        lines.append(f"       De = [Sum of n * (N - n)] / [N * (N - 1)]")

    lines.append(f"       De = {numerator_sum} / {denominator} = {de_val:.4f}")

    # 5. Final Calculation
    lines.append("")
    lines.append("   Step 4: Final Calculation")

    final_alpha = alpha_val
    if de_val != 0:
        calc_alpha = 1 - (do_val / de_val)
        lines.append(f"       Alpha = 1 - ({do_val:.4f} / {de_val:.4f})")
        lines.append(f"       Alpha = 1 - {do_val/de_val:.4f} = {calc_alpha:.4f}")
        # If we didn't have a pre-calculated alpha_val (from simpledorff), use this manual one
        if final_alpha is None:
            final_alpha = calc_alpha
    else:
        lines.append(f"       Alpha = Undefined (De=0, No Variance)")

    lines.append(f"       Result : {final_alpha:.4f}")

    if not is_multi_class and alpha_val is not None:
        pass  # Already added result above

    lines.append("-" * 60)

    return "\n".join(lines)


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

    # Clean coder_cols: Ensure 'TN' or metadata columns didn't sneak in
    coder_cols = [
        c
        for c in coder_cols
        if "TN" not in c and "is_true_negative" not in c and "id" not in c
    ]

    # Fill blank cells (NaN) with 0 in the specified columns
    for col in coder_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            print(f"Warning: Column '{col}' not found in the file. Created one.")
            df[col] = 0

    # Convert columns to integer type for robustness
    df[coder_cols] = df[coder_cols].astype(int)

    # --------------------------------------------------------------------------
    # MODE CHECK: HIERARCHY / WEIGHTED CALCULATION
    # --------------------------------------------------------------------------
    calc_mode = getattr(config, "AGREEMENT_CALCULATION_MODE", 1)
    is_weighted_mode = str(calc_mode) == "2"

    if is_weighted_mode:
        print("\n" + "!" * 60)
        print(f"   ACTIVATING WEIGHTED MODE (HIERARCHY MAPPING)")
        print(f"   Codes will be collapsed to Categories for calculation.")
        print("!" * 60 + "\n")

        # 1. Parse Category from Code
        # Assumes format "Category: Code". If no colon, keeps original text.
        df["_category_temp"] = (
            df["code"].astype(str).apply(lambda x: x.split(":")[0].strip())
        )

        # 2. Re-Group Data by (Participant, Text, Category)
        # We take the MAX of the coder columns.
        # Example:
        # Row 1: Code "A:1", Coder1=1, Coder2=0
        # Row 2: Code "A:2", Coder1=0, Coder2=1
        # Result Group "A": Coder1=1, Coder2=1 -> Agreement!

        # Preserve 'TN' if it exists
        agg_dict = {c: "max" for c in coder_cols}
        if "TN" in df.columns:
            agg_dict["TN"] = "max"

        # We must keep 'text' to distinguish segments
        df_grouped = df.groupby(["p", "text", "_category_temp"], as_index=False).agg(
            agg_dict
        )

        # 3. Replace the 'code' column with the category for the rest of the script
        df_grouped["code"] = df_grouped["_category_temp"]
        df_grouped.drop(columns=["_category_temp"], inplace=True)

        # Replace main df
        df = df_grouped
        print(f"   -> Data grouped by Category. Rows reduced to: {len(df)}")

    # We must check for TNs here, because Strijbos filters (Method A/B) might drop them later.
    estimated_tn = 0
    tn_source = "None"
    prevalence_percentage = None

    # Check if True Negatives were already injected (Column exists and has 1s)
    has_injected_tns = "TN" in df.columns and df["TN"].sum() > 0

    if has_injected_tns:
        estimated_tn = df["TN"].sum()
        tn_source = "Injected from Master List"
        print(f"   -> Found {estimated_tn} injected True Negatives in raw dataset.")
        total_rows_raw = len(df)
        coded_rows_count_raw = len(df[df["TN"] == 0])
        prevalence_percentage = (coded_rows_count_raw / total_rows_raw) * 100

    # --------------------------------------------------------------------------
    # STRIJBOS CALCULATION (Method Selection)
    # --------------------------------------------------------------------------
    method = getattr(config, "STRIJBOS_METHOD", "METHOD_C")
    print(f"\nApplying Strijbos Calculation: {method}")
    initial_len = len(df)

    # Calculate Unit-Level Masks (Segment Masks)
    grouped = df.groupby(["p", "text"])

    # Boolean Series matching the DataFrame index: Did Coder X code this text?
    has_code_series = {}
    for c in coder_cols:
        has_code_series[c] = grouped[c].transform("sum") > 0

    if method == "METHOD_A":
        # (a) Mutual: Only units coded by ALL coders.
        print("   -> Filtering for MUTUAL coded units only (Intersection of Units).")
        mask = pd.Series(True, index=df.index)
        for c in coder_cols:
            mask = mask & has_code_series[c]
        if "TN" in df.columns:
            mask = mask & (df["TN"] == 0)
        df = df[mask]

    elif method == "METHOD_B":
        # (b) Union: Include missing values as 'No Code' (Exclude True Negatives).
        print("   -> Filtering for UNION of coded units (Excluding True Negatives).")
        mask = pd.Series(False, index=df.index)
        for c in coder_cols:
            mask = mask | has_code_series[c]
        if "TN" in df.columns:
            mask = mask & (df["TN"] == 0)
        df = df[mask]

    elif method == "METHOD_C":
        # (c) Full: Include non-coded units.
        print("   -> Using FULL MASTER LIST (Including True Negatives).")
        pass

    # Filter for Mutual Segments Only (Advanced Subset Logic)
    if config.CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY:
        print(
            "   -> (!) 'CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY' is active. This overrides Strijbos settings."
        )
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

            # 3. Decide which rows to keep
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
    elif method != "METHOD_C" and len(df) < initial_len:
        print(f"   -> Dropped {initial_len - len(df)} rows based on Method selection.")

    analyzed_segments = len(df)
    dropped_count = initial_len - analyzed_segments

    # Try to Calculate True Negatives from Transcripts:
    adjusted_kappa = None

    # We only inject virtual TNs into the stats if the Method demands it.
    # Method A (Intersection) and Method B (Union) usually EXCLUDE pure silence.
    # Method C (Full) INCLUDES silence.
    should_inject_virtual_tns = method == "METHOD_C"

    # Logic: If we found injected TNs earlier, use that count.
    # Otherwise, try to estimate from transcripts (Fallback for old CSVs).

    if has_injected_tns:
        # We already have the count from the top of the function
        print(
            f"   -> Using pre-calculated TN count: {estimated_tn} (Source: {tn_source})"
        )

        # Check if the current DataFrame *already* has these zeros (Method C)
        # If the df has 0-0 rows, we should NOT add virtual zeros, or we will double-count them.
        current_tn_in_df = (df[coder_cols] == 0).all(axis=1).sum()

        if current_tn_in_df > 0:
            print(
                f"   -> Dataset currently contains {current_tn_in_df} True Negative rows. Skipping virtual injection to prevent double-counting."
            )
            # We skip adjusted_kappa calculation here because 'kappa' calculated later
            # on 'df' will already include these True Negatives.
            adjusted_kappa = None
        elif should_inject_virtual_tns:
            # The DF was stripped of TNs (Method A/B), OR we are in Method C but they were stripped?
            # Actually, if we are in Method C, they shouldn't have been stripped.
            # This block mainly handles cases where we want to FORCE the stat to include TNs
            # even if the DF doesn't have them.
            print("   -> Injecting virtual True Negatives for Kappa calculation.")

            zeros_df = pd.DataFrame(
                {
                    coder_cols[0]: [0] * estimated_tn,
                    coder_cols[1]: [0] * estimated_tn,
                }
            )
            # Combine actual filtered data (Agreements/Disagreements) + the virtual zeros
            combined_col1 = pd.concat(
                [df[coder_cols[0]], zeros_df[coder_cols[0]]], ignore_index=True
            )
            combined_col2 = pd.concat(
                [df[coder_cols[1]], zeros_df[coder_cols[1]]], ignore_index=True
            )

            try:
                adjusted_kappa = cohen_kappa_score(combined_col1, combined_col2)
            except Exception:
                adjusted_kappa = np.nan
        else:
            print(
                f"   -> Method is '{method}', so we are IGNORING the {estimated_tn} True Negatives in the statistic."
            )

    # Only run transcript estimation if we DO NOT have injected TNs
    else:
        # Check if config has the directory and it exists
        transcripts_dir = getattr(config, "TRANSCRIPTS_DIRECTORY", None)

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

                    # 4. Calculate Adjusted Kappa ONLY if Method C is active
                    if should_inject_virtual_tns:
                        # Create a virtual dataset of zeros
                        zeros_df = pd.DataFrame(
                            {
                                coder_cols[0]: [0] * estimated_tn,
                                coder_cols[1]: [0] * estimated_tn,
                            }
                        )
                        # Combine actual data + zeros
                        combined_col1 = pd.concat(
                            [df[coder_cols[0]], zeros_df[coder_cols[0]]],
                            ignore_index=True,
                        )
                        combined_col2 = pd.concat(
                            [df[coder_cols[1]], zeros_df[coder_cols[1]]],
                            ignore_index=True,
                        )

                        adjusted_kappa = cohen_kappa_score(combined_col1, combined_col2)

                        # Calculate Prevalence %
                        # (Rows that actually had data) / (Total Rows including Silence)
                        total_virtual_rows = len(combined_col1)
                        coded_rows_count = len(df)
                        prevalence_percentage = (
                            coded_rows_count / total_virtual_rows
                        ) * 100
                    else:
                        print(
                            f"   -> Method is '{method}': Skipping virtual TN injection (Silence Ignored)."
                        )
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
            if transcripts_dir:
                os.makedirs(transcripts_dir, exist_ok=True)

    # Check for True Negatives (rows where ALL coders have 0)
    true_negatives = (df[coder_cols] == 0).all(axis=1).sum()

    # Only override with estimated_tn IF the current df actually contains TN rows
    # (i.e. Method C), or if we specifically injected virtual TNs for stats.
    # Method A/B filters them out, so true_negatives should remain 0 (or close to 0) for them.
    if "TN" in df.columns and has_injected_tns:
        # Check if the dataframe actually HAS the rows currently
        current_zero_rows = (df[coder_cols] == 0).all(axis=1).sum()
        if current_zero_rows > 0:
            true_negatives = estimated_tn

    has_missing_negatives = true_negatives == 0
    # If we didn't calculate prevalence via transcripts, but we have 0s in the CSV, calculate it here
    if prevalence_percentage is None and not has_missing_negatives and len(df) > 0:
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

    # Check Multi-Class Mode
    # Check if we have Multi-Class Label columns
    label_cols = [f"{c}_label" for c in coder_cols]
    has_labels = all(col in df.columns for col in label_cols)

    is_multi_class = False
    mc_df = None
    # Cohen's Kappa (Only valid for exactly 2 coders)
    kappa = np.nan

    if len(coder_cols) == 2:
        if has_labels:
            print(
                f"   -> Calculating MULTI-CLASS Kappa ({method}) using specific code labels."
            )
            is_multi_class = True

            # Collapse sparse rows (where coders disagree on the code for the same text) into single rows
            # Group by p + text. Take the first non-null label for each coder.
            # This ensures that a 1-0 row and a 0-1 row become a single row with valid labels for both.
            # We use 'first' because Phase 1.5 in mark_agreements ensures text is identical for fuzzy matches.
            mc_df = df.groupby(["p", "text"], as_index=False).agg(
                {
                    label_cols[0]: "first",
                    label_cols[1]: "first",
                    coder_cols[0]: "max",
                    coder_cols[1]: "max",
                    "TN": "max",  # Preserve TN status if needed
                }
            )

            # DYNAMIC FILTERING BASED ON METHOD (Multi-Class specific)
            if method == "METHOD_A":
                # Method A: Intersection (Exclude Omissions and TNs)
                # Keep only rows where BOTH coders have a label
                mc_df = mc_df.dropna(subset=label_cols)

            elif method == "METHOD_B":
                # Method B: Union
                mask = (mc_df[coder_cols] == 1).any(axis=1)
                mc_df = mc_df[mask].copy()
                mc_df[label_cols] = mc_df[label_cols].fillna("No Code")

            elif method == "METHOD_C":
                # Method C: Full Universe
                mc_df[label_cols] = mc_df[label_cols].fillna("No Code")

            if len(mc_df) > 0:
                le = LabelEncoder()
                all_labels = (
                    pd.concat([mc_df[label_cols[0]], mc_df[label_cols[1]]])
                    .astype(str)
                    .unique()
                )
                le.fit(all_labels)
                encoded_c1 = le.transform(mc_df[label_cols[0]].astype(str))
                encoded_c2 = le.transform(mc_df[label_cols[1]].astype(str))
                kappa = cohen_kappa_score(encoded_c1, encoded_c2)

                # IMPORTANT: Update analyzed segments to reflect the Multi-Class subset
                analyzed_segments = len(mc_df)
            else:
                kappa = np.nan
        else:
            # Fallback to Binary Kappa
            try:
                kappa = cohen_kappa_score(df[coder_cols[0]], df[coder_cols[1]])
            except:
                kappa = np.nan

    # EDGE CASE HANDLING: Perfect Agreement on Single Label
    if pd.isna(kappa) and analyzed_segments > 0:
        # Check if it's perfect agreement
        # If Multi-Class
        if is_multi_class and mc_df is not None:
            if (mc_df[label_cols[0]] == mc_df[label_cols[1]]).all():
                kappa = 1.0
        # If Binary
        elif (df[coder_cols[0]] == df[coder_cols[1]]).all():
            kappa = 1.0

    # Calculate F1 Score (Pairwise average or binary if 2 coders)
    # If > 2 coders, this computes the average F1 of all pairs, or you can skip it.
    # For simplicity here, we stick to the first two if available, or skip.
    f1 = np.nan
    if len(coder_cols) >= 2:
        f1 = f1_score(df[coder_cols[0]], df[coder_cols[1]], pos_label=1)
        # Note: This is Binary F1 (Presence).
        # If Multi-Class is active, we might want Weighted F1 on labels?
        # Standard practice is often to report Binary F1 (Detection) + Multi-Class Kappa (Classification).
        # But if the user wants Multi-Class F1, we should compute it on mc_df.
        if is_multi_class and mc_df is not None and len(mc_df) > 0:
            # Use weighted F1 for multi-class
            try:
                f1 = f1_score(
                    mc_df[label_cols[0]].astype(str),
                    mc_df[label_cols[1]].astype(str),
                    average="weighted",
                    zero_division=0,
                )
            except:
                pass

    # Krippendorff's Alpha
    kripp_alpha = np.nan
    try:
        alpha_source_df = mc_df if is_multi_class and mc_df is not None else df
        target_cols = label_cols if is_multi_class else coder_cols

        # Ensure we have data
        if len(alpha_source_df) > 0:
            df_long = pd.melt(
                alpha_source_df.reset_index(),
                id_vars="index",
                value_vars=target_cols,
                var_name="rater",
                value_name="label",
            )
            kripp_alpha = simpledorff.calculate_krippendorffs_alpha_for_df(
                df_long,
                experiment_col="index",
                annotator_col="rater",
                class_col="label",
            )
    except Exception as e:
        print(f"\nCould not calculate Krippendorff's Alpha. Error: {e}\n")

    # Macro Metrics
    macro_f1, macro_kappa, per_code_df = calculate_per_code_metrics(df, coder_cols)
    effective_prevalence = (df[coder_cols].mean().mean()) * 100

    agreements_count = 0
    if is_multi_class and mc_df is not None:
        # Multi-Class Agreement: Labels must match
        agreements_count = (mc_df[label_cols[0]] == mc_df[label_cols[1]]).sum()
        # analyzed_segments is already len(mc_df)
    else:
        # Binary Agreement: Columns must match (0-0 or 1-1)
        agreements_count = (
            df[coder_cols].eq(df[coder_cols].iloc[:, 0], axis=0).all(axis=1)
        ).sum()

    disagreements_count = analyzed_segments - agreements_count
    agreement_percentage = (
        (agreements_count / analyzed_segments * 100) if analyzed_segments > 0 else 0
    )

    # Generate Report
    report = []
    # ==============================================================================
    # ================= INTER-RATER RELIABILITY REPORT (START) =====================
    # ==============================================================================
    report.append("=" * 90)
    report.append(f"{'INTER-RATER RELIABILITY REPORT':^90}")
    report.append("=" * 90)

    report.append(f"\nMETHODOLOGY USED: {method}")
    if method == "METHOD_A":
        report.append(
            "Description: (Intersection) True Negatives = ignored, and coded MATCHING segments = agreement or disagreement. We ignored cases where one coder missed a segment (Omissions)."
        )
    elif method == "METHOD_B":
        report.append(
            "Description: (Union) True Negatives = ignored, and EVERY coded segment is counted as either agreement or disagreement."
        )
    elif method == "METHOD_C":
        report.append(
            "Description: (Full) True Negatives = agreements, and EVERY coded segment is counted as either agreement or disagreement."
        )

    report.append("\n1. DATASET SUMMARY")
    report.append("-" * 30)
    report.append(f"{'File Name':<25} : {os.path.basename(file_path)}")
    display_coders = [c.replace("_agreement", "") for c in coder_cols]
    report.append(f"{'Coders':<25} : {', '.join(display_coders)}")
    report.append(
        f"{'Fuzzy-Match Threshold':<25} : {overlap_percentage:.2f} (Jaccard) {('(Exact Match used instead of Fuzzy-Match)' if overlap_percentage==1.0 else str(overlap_percentage * 100)  + '% Words Overlap')}"
    )
    report.append(f"{'Initial Loaded Segments':<25} : {initial_len}")
    report.append(
        f"{'Excluded Segments':<25} : -{dropped_count} (Rows dropped by Method rules)"
    )
    report.append(f"{'Final Analyzed Segments':<25} : {analyzed_segments}")

    report.append(f"{'Perfect Agreement':<25} : {agreements_count}")
    report.append(f"{'Disagreements':<25} : {disagreements_count}")

    if adjusted_kappa is not None:
        report.append(
            f"{'Est. True Negatives':<25} : {estimated_tn} (derived from transcripts)"
        )
    elif has_injected_tns and method == "METHOD_C":
        # For Method C where we skipped adjusted_kappa but have them in DF
        report.append(
            f"{'Est. True Negatives':<25} : {estimated_tn} (included in dataset)"
        )
    elif method != "METHOD_C":
        report.append(
            f"{'Est. True Negatives':<25} : {estimated_tn} (Ignored by Method)"
        )

    if prevalence_percentage is not None:
        report.append(f"{'Code Prevalence':<25} : {prevalence_percentage:.2f}%")
    else:
        report.append(f"{'Code Prevalence':<25} : N/A")

    report.append("\n2. RELIABILITY METRICS")
    report.append("-" * 60)
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
        k_note = " "
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
        f"{'Average F1-Score':<27} | {macro_f1:<10.4f} | {interpret_f1(macro_f1)}"
    )
    report.append(
        f"{'Average Kappa':<27} | {macro_kappa:<10.4f} | {interpret_kappa(macro_kappa)}"
    )

    report.append("-" * 60)

    # Explanation Text
    # explanation_text = get_results_explanation(
    #     agreement_percentage,
    #     k_val,
    #     f1,
    #     has_missing_negatives and adjusted_kappa is None,
    #     prevalence_percentage,  # Theoretical/Original prevalence
    #     effective_prevalence,  # Actual saturation of the analyzed subset
    # )
    # report.append(explanation_text)
    # ==============================================================================
    # ================= INTER-RATER RELIABILITY REPORT (END) =======================
    # ==============================================================================

    # ==============================================================================
    # ================= MATH EXPLANATION (START) ===================================
    # ==============================================================================
    report.append("-" * 60)

    # Determine which Kappa value to validate in the Math section
    if adjusted_kappa is not None:
        final_k_val = adjusted_kappa
        tn_display_val = estimated_tn
    elif has_injected_tns and method == "METHOD_C":
        final_k_val = kappa
        tn_display_val = estimated_tn
    else:
        final_k_val = kappa
        tn_display_val = (df[coder_cols] == 0).all(axis=1).sum()

    if len(coder_cols) == 2:
        # Pass the Multi-Class DF and Label Cols if active
        math_df = mc_df if is_multi_class and mc_df is not None else df

        math_section = generate_math_section(
            math_df,
            coder_cols,
            f1,
            kappa,
            0,  # TNs handled inside
            kripp_alpha,
            is_multi_class=is_multi_class,
            label_cols=label_cols if is_multi_class else None,
        )
        report.append(math_section)
    else:
        report.append("\n3. TRANSPARENCY & CALCULATIONS")
        report.append("   (Skipped: Math breakdown requires exactly 2 coders)")

    # Rename Section 3 to 4 in the explanation text since we inserted a new Section 3
    explanation_text = get_results_explanation(
        agreement_percentage,
        final_k_val,
        f1,
        has_missing_negatives and adjusted_kappa is None,
        prevalence_percentage,
    )
    # Simple replace to bump the numbering
    explanation_text = explanation_text.replace(
        "3. RECOMMENDATION", "4. RECOMMENDATION"
    )

    report.append(explanation_text)
    # ==============================================================================
    # ================= MATH EXPLANATION (END) =====================================
    # ==============================================================================

    # ==============================================================================
    # ================= REFERENCE GUIDELINES (START) ===============================
    # ==============================================================================
    report.append("\n" + "=" * 90)
    report.append(f"{'REFERENCE GUIDELINES':^90}")
    report.append("=" * 90)
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
    report.append("=" * 90)
    # ==============================================================================
    # ================= REFERENCE GUIDELINES (END) =================================
    # ==============================================================================

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
    agreement_pct,
    kappa,
    f1,
    has_missing_negatives,
    prevalence_pct=None,
    effective_prevalence_pct=None,
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

    # 2. Paradox Check
    # Low Prevalence Paradox (Method C context)
    is_low_prev_paradox = (
        not has_missing_negatives
        and prevalence_pct is not None
        and prevalence_pct < 15.0
        and kappa < 0.40
        and f1 > 0.50
    )

    # High Saturation Paradox (Method A context - High Effective Prevalence)
    # If > 85% of the data is "1", Kappa fails because Expected Agreement becomes ~100%
    is_high_prev_paradox = (
        effective_prevalence_pct is not None
        and effective_prevalence_pct > 85.0
        and kappa < 0.40
        and f1 > 0.80
    )

    explanation.append("\n2. STATISTICAL OBSERVATIONS:")

    if is_low_prev_paradox:
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
    elif is_high_prev_paradox:
        explanation.append(
            f"   * PARADOX DETECTED: Low Kappa ({kappa:.2f}) vs High F1 ({f1:.2f})."
        )
        explanation.append(
            f"   * CAUSE: High Data Saturation ({effective_prevalence_pct:.2f}% Positives)."
        )
        explanation.append(
            "     The dataset (after filtering) consists almost entirely of 'Agreements'."
        )
        explanation.append(
            "     Because there is no variance (no 'Negatives' to distinguish skill from chance),"
        )
        explanation.append(
            "     Kappa assumes the high agreement is due to chance probability."
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
    if is_low_prev_paradox:
        explanation.append("   > PRIMARY METRIC: Report F1-Score (Dice Coefficient).")
        explanation.append(
            "   > REASONING: Due to the 'Prevalence Paradox' (Rare Codes), Kappa underestimates reliability."
        )
    elif is_high_prev_paradox:
        explanation.append("   > PRIMARY METRIC: Report F1-Score (Dice Coefficient).")
        explanation.append(
            "   > REASONING: Due to the 'Prevalence Paradox' (Saturation), Kappa is mathematically invalid."
        )
        explanation.append(
            "     (The formula fails when the dataset lacks negative examples)."
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

        # Identify columns: Exclude known metadata to find coders
        metadata_cols = [
            "id",
            "p",
            "text",
            "code",
            "memo",
            "all_agree",
            "TN",
            "is_true_negative",
            "ignored",
        ]
        coder_cols = [
            c
            for c in df_head.columns
            if c not in metadata_cols
            and not c.startswith("Unnamed")
            and not c.endswith("_label")
        ]

        if not coder_cols:
            print("Error: No coder columns found in the CSV.")
            return

        print(f"Dynamically identified coder columns: {coder_cols}")
        calculate_agreement(input_file, coder_cols, config.WORDS_OVERLAP_PERCENTAGE)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
