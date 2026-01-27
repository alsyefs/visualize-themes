# backend/mark_agreements.py
import pandas as pd
import os
import itertools
import backend.config as config
import re
import difflib
from datetime import datetime

# Configuration
INPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
OUTPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
NOTES_FILE = config.NOTES_FILE


def stitch_text(text1, text2):
    """
    Merges two texts by strictly returning the longer of the two.
    This avoids 'Frankenstein' sentences (mangled grammar) when
    merging distinct segments that technically met the fuzzy threshold.
    """
    t1, t2 = str(text1), str(text2)
    # Simple logic: Return the version with more characters
    return t1 if len(t1) >= len(t2) else t2


def calculate_agreement(input_file: str, output_file: str):
    try:
        df = pd.read_csv(input_file, encoding="utf-8-sig")
        # Ensure text columns are treated as strings (not 0) to prevent false-positive fuzzy matches on empty cells
        text_cols = ["text", "memo", "p", "code"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
        df = df.fillna(0)  # Fill remaining (coder columns) with 0
        print(f"Successfully loaded '{input_file}'.")
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        return

    # Identify Coders
    # Added "is_true_negative" to base_meta_cols to prevent it from being treated as a coder
    base_meta_cols = [
        "id",
        "p",
        "text",
        "code",
        "memo",
        "all_agree",
        "TN",
        "ignored",
    ]
    coders = [
        c
        for c in df.columns
        if c not in base_meta_cols
        and not c.endswith("_agreement")
        and not c.startswith("_")
    ]

    print(f"Identified coders: {coders}")

    def get_tokens(text):
        return set(re.findall(r"\w+", str(text).lower()))

    df["_tokens"] = df["text"].apply(get_tokens)

    # Initialize Label Columns to store specific codes per coder
    for coder in coders:
        # If coder has a 1, store the 'code'. Else store None.
        df[f"{coder}_label"] = df.apply(
            lambda x: x["code"] if x[coder] == 1 else None, axis=1
        )

    # Align Text Across Codes (Optional)
    if config.ALIGN_SEGMENTS_ACROSS_CODES:
        print(
            "Phase 1.5: Aligning text segments across DIFFERENT codes (Researcher Strategy)..."
        )
        # Group only by participant, ignoring code
        align_grouped = df.groupby(["p"])

        for _, group_df in align_grouped:
            if len(group_df) < 2:
                continue

            # Sort by length to prioritize stitching into the longest available version
            sorted_indices = group_df.index[group_df["text"].str.len().argsort()[::-1]]

            # We iterate to find overlaps and unify text.
            # Note: This is a greedy pairwise approach.
            for idx1, idx2 in itertools.combinations(sorted_indices, 2):
                # Re-fetch tokens as they might have been updated in a previous iteration
                tokens1 = df.loc[idx1, "_tokens"]
                tokens2 = df.loc[idx2, "_tokens"]

                if not tokens1 or not tokens2:
                    overlap = 0.0
                else:
                    intersection = len(tokens1 & tokens2)
                    union = len(tokens1 | tokens2)
                    overlap = intersection / union

                if overlap >= config.WORDS_OVERLAP_PERCENTAGE:
                    # Stitch texts
                    t1 = df.loc[idx1, "text"]
                    t2 = df.loc[idx2, "text"]

                    # Only update if they are actually different
                    if t1 != t2:
                        stitched = stitch_text(t1, t2)
                        new_tokens = get_tokens(stitched)

                        # Update BOTH rows to the stitched version
                        # We do NOT merge the rows (drop one) because they represent different codes/entries
                        df.at[idx1, "text"] = stitched
                        df.at[idx1, "_tokens"] = new_tokens

                        df.at[idx2, "text"] = stitched
                        df.at[idx2, "_tokens"] = new_tokens

                    # This caused an extra label for a coder to be added incorrectly!
                    # # Merge labels (Pull labels from idx2 into idx1 if idx1 is empty)
                    # # This ensures idx1 becomes the "master" row with both coders' labels
                    # for coder in coders:
                    #     if pd.isna(df.loc[idx1, f"{coder}_label"]) and not pd.isna(
                    #         df.loc[idx2, f"{coder}_label"]
                    #     ):
                    #         df.at[idx1, f"{coder}_label"] = df.loc[
                    #             idx2, f"{coder}_label"
                    #         ]
                    #         # Also mark the binary flag
                    #         df.at[idx1, coder] = 1

    # Phase 2: Calculate Subtext Agreement (Fuzzy Match) & MERGE ROWS
    print("Calculating agreement based on token overlap (fuzzy matching)...")
    grouped = df.groupby(["p", "code"])

    # Track rows that have been merged into another and should be removed
    indices_to_drop = set()

    for _, group_df in grouped:
        if len(group_df) < 2:
            continue

        # (Optional) You can keep the sort, it helps establish a good base
        group_df = group_df.iloc[group_df["text"].str.len().argsort()[::-1]]

        for idx1, idx2 in itertools.combinations(group_df.index, 2):
            if idx1 in indices_to_drop or idx2 in indices_to_drop:
                continue

            tokens1 = df.loc[idx1, "_tokens"]
            tokens2 = df.loc[idx2, "_tokens"]

            # Existing Fuzzy Logic
            if not tokens1 or not tokens2:
                overlap = 0.0
            else:
                intersection = len(tokens1 & tokens2)
                union = len(tokens1 | tokens2)
                overlap = intersection / union

            if overlap >= config.WORDS_OVERLAP_PERCENTAGE:
                # 1. Stitch the texts together
                current_text = df.loc[idx1, "text"]
                merge_text = df.loc[idx2, "text"]
                new_stitched_text = stitch_text(current_text, merge_text)

                # 2. Update the surviving row (idx1) with the new super-sentence
                df.loc[idx1, "text"] = new_stitched_text

                # 3. Re-calculate tokens for idx1 so it can match others later
                df.at[idx1, "_tokens"] = get_tokens(new_stitched_text)

                # 4. Merge Coders
                for coder in coders:
                    if df.loc[idx2, coder] == 1:
                        df.loc[idx1, coder] = 1
                        # Carry over the label string
                        if pd.isna(df.loc[idx1, f"{coder}_label"]):
                            df.at[idx1, f"{coder}_label"] = df.loc[
                                idx2, f"{coder}_label"
                            ]

                # Merge TN status
                # If one row was valid code (TN=0) and one was noise/TN (TN=1), the result is valid code (TN=0)
                # Logic: TN remains 1 only if BOTH were 1. Since we found overlap, likely they are coded.
                if df.loc[idx1, "TN"] == 0 or df.loc[idx2, "TN"] == 0:
                    df.loc[idx1, "TN"] = 0

                # 5. Merge Memos
                memo1 = str(df.loc[idx1, "memo"])
                memo2 = str(df.loc[idx2, "memo"])
                if memo2 and memo2.strip() and memo2 not in memo1:
                    df.loc[idx1, "memo"] = (memo1 + "; " + memo2).strip("; ")

                # 6. Mark idx2 for deletion
                indices_to_drop.add(idx2)

    # Log the fuzzy merge stats
    initial_count = len(df)
    drop_count = len(indices_to_drop)

    # Remove the duplicate rows
    if indices_to_drop:
        print(
            f"Merging and dropping {len(indices_to_drop)} duplicate fuzzy-match rows..."
        )
        df.drop(index=list(indices_to_drop), inplace=True)

    final_count = len(df)

    # Append detailed merge stats to the notes file for the HTML report
    try:
        if os.path.dirname(NOTES_FILE):
            os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
        with open(NOTES_FILE, "a", encoding="utf-8-sig") as f:
            f.write("\n" + "=" * 40 + "\n")
            f.write("      FUZZY MATCH MERGE PHASE\n")
            f.write("=" * 40 + "\n")
            f.write(f"Overlap Threshold : {config.WORDS_OVERLAP_PERCENTAGE * 100}%\n")
            f.write("-" * 40 + "\n")
            f.write(f"{'Initial Segments':<25} : {initial_count}\n")
            f.write(f"{'Merged/Dropped':<25} : -{drop_count}\n")
            f.write(f"{'Final Segments':<25} : {final_count}\n")
            f.write("-" * 40 + "\n\n")
            print(f"Appended fuzzy merge stats to '{NOTES_FILE}'")
    except Exception as e:
        print(f"Warning: Could not update notes file: {e}")

    # Ensure TN rows are removed if they overlap with ANY coded row (Cross-Code Check).
    # This handles cases where string matching failed in calculate_irr.py but tokens match.
    print("Phase 2.5: Pruning True Negatives that overlap with coded segments...")
    tn_indices_to_drop = set()

    if "TN" in df.columns:
        # 1. Build a Smart ID Map (Map 'p07-answers' -> 'p07')
        unique_ids = df["p"].dropna().unique()
        # Sort by length (shortest first) to find the "root" ID
        sorted_ids = sorted(unique_ids, key=lambda x: len(str(x)))
        id_map = {}

        for pid in unique_ids:
            pid_str = str(pid).lower()
            mapped = pid
            # Check if this ID starts with any shorter ID (e.g. 'p07-answers' starts with 'p07')
            for short_id in sorted_ids:
                s_str = str(short_id).lower()
                if pid == short_id:
                    continue
                # Match if it starts with the short ID followed by a separator or is roughly same
                if pid_str.startswith(s_str):
                    mapped = short_id
                    break
            id_map[pid] = mapped

        # 2. Create a temporary normalization column
        df["_norm_p"] = df["p"].map(id_map)

        # 3. Group by the NORMALIZED ID to compare 'p07' Coded vs 'p07-answers' TNs
        for norm_p, group_indices in df.groupby("_norm_p").groups.items():
            # Get the actual subset of the dataframe using indices
            p_group = df.loc[group_indices]

            tn_rows = p_group[p_group["TN"] == 1]
            coded_rows = p_group[p_group["TN"] == 0]

            if tn_rows.empty or coded_rows.empty:
                continue

            # Check every TN against every Coded row in this cluster
            for tn_idx, tn_row in tn_rows.iterrows():
                tn_tokens = df.loc[tn_idx, "_tokens"]
                if not isinstance(tn_tokens, set) or len(tn_tokens) == 0:
                    continue

                is_covered = False
                for coded_idx, coded_row in coded_rows.iterrows():
                    coded_tokens = df.loc[coded_idx, "_tokens"]
                    if not isinstance(coded_tokens, set) or not coded_tokens:
                        continue

                    intersection = len(tn_tokens & coded_tokens)
                    union = len(tn_tokens | coded_tokens)
                    if union == 0:
                        continue

                    overlap = intersection / union

                    if overlap >= config.WORDS_OVERLAP_PERCENTAGE:
                        is_covered = True
                        break

                if is_covered:
                    tn_indices_to_drop.add(tn_idx)

        # Clean up temp column
        if "_norm_p" in df.columns:
            df.drop(columns=["_norm_p"], inplace=True)

    if tn_indices_to_drop:
        print(
            f"   -> Dropping {len(tn_indices_to_drop)} True Negative rows that overlapped with coded segments."
        )
        df.drop(index=list(tn_indices_to_drop), inplace=True)

    if "_tokens" in df.columns:
        df.drop(columns=["_tokens"], inplace=True)

    # Phase 3: Calculate Overall Agreement
    print("Calculating overall 'all_agree' column...")

    num_coders = len(coders)
    # Calculate sums to determine agreement
    # Use coders list directly, not agreement_cols
    sums = df[coders].sum(axis=1)

    # 1. Standard Exact Agreement (all_agree = 1)
    df["all_agree"] = (sums == num_coders).astype(int)

    # 2. Weighted/Partial Agreement Logic (all_agree = 2)
    calc_mode = getattr(config, "AGREEMENT_CALCULATION_MODE", 1)
    if str(calc_mode) == "2":
        print("   -> Checking for PARTIAL (Category-level) Agreements...")

        # Extract Category (Assumes "Category: Code")
        df["_cat_temp"] = (
            df["code"].astype(str).apply(lambda x: x.split(":")[0].strip())
        )

        # Logic:
        # For a given (Participant + Text + Category),
        # did Coder A mark ANY code in this category AND Coder B mark ANY code in this category?

        # Create a mask of "Presence" per coder per category group
        # We group by P + Text + Category
        # transform('max') broadcasts the group-level maximum back to the original rows
        group_cols = ["p", "text", "_cat_temp"]

        # Determine if each coder is "active" in this category group
        for coder in coders:
            df[f"_has_{coder}_in_cat"] = df.groupby(group_cols)[coder].transform("max")

        # Sum the presence flags. If Sum == Num_Coders, it's a Category Match
        cat_presence_cols = [f"_has_{c}_in_cat" for c in coders]
        cat_agreement_sum = df[cat_presence_cols].sum(axis=1)

        # Mark as Partial (2) IF:
        # 1. It is NOT already an exact agreement (all_agree == 0)
        # 2. Everyone agreed on the Category (cat_agreement_sum == num_coders)
        # 3. It is NOT a True Negative (TN == 0)
        partial_mask = (
            (df["all_agree"] == 0)
            & (cat_agreement_sum == num_coders)
            & (df.get("TN", 0) == 0)
        )

        count_partials = partial_mask.sum()
        if count_partials > 0:
            print(
                f"   -> Found {count_partials} rows with Partial (Category) Agreement."
            )
            df.loc[partial_mask, "all_agree"] = 2

        # Cleanup temp columns
        drop_cols = ["_cat_temp"] + cat_presence_cols
        df.drop(columns=drop_cols, inplace=True)

    # Update TN based on sums (re-enforce consistency)
    df.loc[sums == 0, "TN"] = 1
    df.loc[sums > 0, "TN"] = 0

    print("Calculating 'ignored' column based on Strijbos Method...")
    df["ignored"] = 0
    method = getattr(config, "STRIJBOS_METHOD", "METHOD_C")

    # Helper to identify Omissions vs Conflicts (Only needed for Method A logic)
    if method == "METHOD_A":
        # Group by segment to analyze context
        for _, group in df.groupby(["p", "text"]):
            # Build code sets
            coder_code_sets = {c: set() for c in coders}
            for idx, row in group.iterrows():
                code = row["code"]
                for c in coders:
                    if row[c] == 1:
                        coder_code_sets[c].add(code)

            for idx, row in group.iterrows():
                # If True Negative, ignore in Method A
                if row.get("TN", 0) == 1:
                    df.at[idx, "ignored"] = 1
                    continue

                # If Full Agreement, keep (not ignored)
                if row[coders].sum() == len(coders):
                    continue

                # Check Conflict vs Omission
                is_conflict = False
                for c in coders:
                    if row[c] == 0:
                        my_codes = coder_code_sets[c]
                        # Get all codes used by ANYONE ELSE
                        other_coders = [oc for oc in coders if oc != c]
                        all_other_codes = set()
                        for oc in other_coders:
                            all_other_codes.update(coder_code_sets[oc])

                        # It is a CONFLICT if I have a code that nobody else has.
                        # It is an OMISSION if my codes are just a subset of the group's codes.
                        if not my_codes.issubset(all_other_codes):
                            is_conflict = True
                            break

                # If it's NOT a conflict (meaning it IS an omission), ignore it in Method A
                if not is_conflict:
                    df.at[idx, "ignored"] = 1

    elif method == "METHOD_B":
        # Method B ignores True Negatives, but keeps Omissions
        if "TN" in df.columns:
            df.loc[df["TN"] == 1, "ignored"] = 1

    # Method C keeps everything (ignored stays 0)

    # Filter Omissions (The "AnyDesk" & "Revenge" Fix)
    if config.CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY:
        print(
            "Applying Omission Filter (dropping rows where one coder missed a code that wasn't a conflict)..."
        )
        indices_to_keep = []

        # Group by p and text to analyze the full context of each segment
        for _, group in df.groupby(["p", "text"]):
            # 1. Build code sets for this specific segment
            coder_code_sets = {c: set() for c in coders}
            for idx, row in group.iterrows():
                code = row["code"]
                for c in coders:
                    if row[c] == 1:
                        coder_code_sets[c].add(code)

            # 2. Decide which rows to keep
            for idx, row in group.iterrows():
                # Rule A: Full Agreement -> Keep
                if row[coders].sum() == len(coders):
                    indices_to_keep.append(idx)
                    continue

                # Rule B: Check for Conflict vs Omission
                is_conflict = False
                for c in coders:
                    if row[c] == 0:
                        my_codes = coder_code_sets[c]

                        # Get all codes used by ANYONE ELSE
                        other_coders = [oc for oc in coders if oc != c]
                        all_other_codes = set()
                        for oc in other_coders:
                            all_other_codes.update(coder_code_sets[oc])

                        # It is a CONFLICT if I have a code that nobody else has.
                        # It is an OMISSION if my codes are just a subset of the group's codes.
                        if not my_codes.issubset(all_other_codes):
                            is_conflict = True
                            break

                if is_conflict:
                    indices_to_keep.append(idx)
                else:
                    # It is an Omission (Subset).
                    # Keep the row and treat as agreement for stats, but do NOT modify original coder columns.
                    indices_to_keep.append(idx)
                    df.at[idx, "all_agree"] = 1

    # Reset index and regenerate 'id' column so IDs match the new row count
    df.reset_index(drop=True, inplace=True)
    df["id"] = range(1, 1 + len(df))

    # Save
    # Added "TN" to base_cols so it is written to the final CSV
    base_cols = ["id", "p", "text", "code", "memo"]

    # Include the label columns in the output CSV
    label_cols = [f"{c}_label" for c in coders]
    final_cols = base_cols + coders + label_cols + ["all_agree", "TN", "ignored"]

    cols_to_save = [c for c in final_cols if c in df.columns]
    df = df[cols_to_save]

    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nProcessing complete. Output saved to '{output_file}'.")


def append_methodology_note(notes_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine Dynamic Explanations based on Config

    # 1. Alignment Strategy
    if config.ALIGN_SEGMENTS_ACROSS_CODES:
        align_status = "ENABLED"
        align_desc = (
            "We forced text segments to align across DIFFERENT codes. "
            "If Coder A coded 'Sentence 1' as Code X, and Coder B coded 'Sentence 1' as Code Y, "
            "the text boundaries were unified so they count as the same segment (Disagreement)."
        )
    else:
        align_status = "DISABLED (Default)"
        align_desc = (
            "Text segments were only compared if they shared the same Code Label. "
            "Cross-code comparison was not performed in this phase."
        )

    # 2. Omission Filter
    if config.CALCULATE_SCORES_ON_MUTUAL_SEGMENTS_ONLY:
        omission_status = "ENABLED (Mutual Segments Only)"
        omission_desc = (
            "We filtered the dataset to focus on CLASSIFICATION AGREEMENT. "
            "Rows where one coder applied a code and the other was silent (Omission) "
            "were treated as statistical agreements (ignored/imputed) rather than conflicts, "
            "unless the silent coder applied a DIFFERENT code to that same segment (Conflict)."
        )
    else:
        omission_status = "DISABLED (Strict coding)"
        omission_desc = (
            "Any instance where one coder applied a code and the other did not "
            "was strictly counted as a disagreement (0 vs 1)."
        )

    # 3. Transcript Margin
    margin_pct = getattr(config, "TRANSCRIPT_NON_CODABLE_MARGIN", 0.10) * 100

    # Build the Plain Text Report
    text = f"""
PROCESSING LOG & METHODOLOGY ({timestamp})
==========================================================================================
This log details the specific algorithms and parameters used 
to process the dataset.

1. FUZZY MATCHING (Jaccard Index)
---------------------------------
   PARAMETER : {config.WORDS_OVERLAP_PERCENTAGE * 100}% Word Overlap
   METHOD    : Token-based Jaccard similarity.
   ACTION 1  : Merged duplicate coded segments (within same code).
   ACTION 2  : Pruned 'True Negatives' that overlapped with coded segments 
               (fixing artifacts from strict string matching).
   REASONING : Qualitative coding often suffers from granularity differences 
               (e.g., selecting a sentence vs. a paragraph).
   OUTCOME   : Segments with >{config.WORDS_OVERLAP_PERCENTAGE * 100}% overlap were merged into a single unit 
               to prevent artificial duplication.

2. TEXT MERGING STRATEGY
------------------------
   METHOD    : Longest Segment Retention.
   REASONING : To ensure readability. When two fuzzy segments are merged, 
               the script keeps the longer version of the text rather than 
               attempting to "stitch" them (which often mangles grammar).

3. ALIGNMENT SCOPE
------------------
   STATUS    : {align_status}
   DETAILS   : {align_desc}

4. HANDLING OMISSIONS (The "Silence" Rule)
------------------------------------------
   STATUS    : {omission_status}
   DETAILS   : {omission_desc}

5. HANDLING TRUE NEGATIVES
--------------------------
   METHOD    : Derived from Transcripts.
   ADJUSTMENT: {margin_pct:.0f}% reduction for headers/metadata.
   DETAILS   : We estimated the volume of non-coded text (True Negatives) 
               by subtracting coded words from the total transcript length. 
               This is required to calculate Cohen's Kappa.

==========================================================================================
"""
    try:
        if os.path.dirname(notes_file):
            os.makedirs(os.path.dirname(notes_file), exist_ok=True)
        with open(notes_file, "a", encoding="utf-8-sig") as f:
            f.write(text)
        print(f"Appended methodology notes to '{notes_file}'")
    except Exception as e:
        print(f"Warning: Could not append methodology notes: {e}")


def main():
    print("--- Starting Agreement Calculation ---")
    calculate_agreement(INPUT_CSV_FILE, OUTPUT_CSV_FILE)
    append_methodology_note(NOTES_FILE)
    print("--- Script Finished ---")


if __name__ == "__main__":
    main()
