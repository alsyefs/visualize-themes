import pandas as pd
import os
import itertools
import config
import re
import difflib
from datetime import datetime

# Configuration
INPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
OUTPUT_CSV_FILE = config.IRR_AGREEMENT_INPUT_FILE
NOTES_FILE = "output/first_merge_notes.txt"


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
    base_meta_cols = ["id", "p", "text", "code", "memo", "all_agree"]
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

                # 4. Merge Coders (as before)
                for coder in coders:
                    if df.loc[idx2, coder] == 1:
                        df.loc[idx1, coder] = 1

                # 5. Merge Memos (as before)
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

    if "_tokens" in df.columns:
        df.drop(columns=["_tokens"], inplace=True)

    # Phase 3: Initialize/Update Agreement Columns
    # Now that rows are merged, we simply mirror the coder columns to agreement columns
    agreement_cols = []
    for coder in coders:
        ag_col = f"{coder}_agreement"
        agreement_cols.append(ag_col)
        df[ag_col] = df[coder]

    # Phase 4: Calculate Overall Agreement
    print("Calculating overall 'all_agree' column...")

    num_coders = len(coders)
    # Calculate sums to determine agreement
    sums = df[agreement_cols].sum(axis=1)

    # Mark as agreed if ALL coders matched (sum == num_coders) OR if ALL were silent (sum == 0)
    df["all_agree"] = ((sums == num_coders) | (sums == 0)).astype(int)

    # Filter Omissions (The "AnyDesk" & "Revenge" Fix)
    # This physically removes the rows from the CSV if one coder missed them (and didn't conflict).
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

                    # 1. Force global agreement flag
                    df.at[idx, "all_agree"] = 1

                    # 2. Update ONLY the hidden agreement columns to 1.
                    # This ensures stats (Kappa/F1) count this as an agreement,
                    # while the UI/CSV still shows the coder didn't actually click this code.
                    for c in coders:
                        ag_col = f"{c}_agreement"
                        if ag_col in df.columns:
                            df.at[idx, ag_col] = 1

        initial_count = len(df)
        df = df.loc[indices_to_keep]
        print(f"Filtered {initial_count - len(df)} rows. Remaining: {len(df)}.")

    # Reset index and regenerate 'id' column so IDs match the new row count
    df.reset_index(drop=True, inplace=True)
    df["id"] = range(1, 1 + len(df))

    # Save
    # Added "memo" to base_cols so it is written to the final CSV
    base_cols = ["id", "p", "text", "code", "memo"]
    final_cols = base_cols + coders + agreement_cols + ["all_agree"]
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
============================================================
This log details the specific algorithms and parameters used 
to process the dataset.

1. FUZZY MATCHING (Jaccard Index)
---------------------------------
   PARAMETER : {config.WORDS_OVERLAP_PERCENTAGE * 100}% Word Overlap
   METHOD    : Token-based Jaccard similarity.
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

============================================================
"""
    try:
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
