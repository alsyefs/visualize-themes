# backend/calculate_irr.py
import os
import pandas as pd
import numpy as np
from datetime import datetime
import backend.config as config
import re
import glob

OUTPUT_DIR = config.OUTPUT_DIRECTORY


def log_note(message, filepath, print_to_console=True):
    with open(filepath, "a", encoding="utf-8-sig") as f:
        f.write(message + "\n")
    if print_to_console:
        print(message)


def initialize_output():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


def initialize_notes_file(filepath):
    with open(filepath, "w", encoding="utf-8-sig") as f:
        f.write("IRR Calculation Notes\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 90 + "\n\n")


def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text)

    # Fix encoding artifacts and standardize quotes
    replacements = {
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
        "â€˜": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "…": "...",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Collapse multiple spaces and strip whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_transcripts_and_inject_negatives(
    df, transcript_dir, coder_cols, notes_filepath
):
    """
    Matches coded segments to Master List and fills unmatched
    sentences with 0 (True Negatives).
    """
    if not os.path.exists(transcript_dir):
        log_note(
            f"Notice: Transcript directory '{transcript_dir}' not found. Skipping Master List generation.",
            notes_filepath,
        )
        return df

    log_note(
        "Phase 2: Processing Master Sentence List from Transcripts...", notes_filepath
    )

    transcript_files = glob.glob(os.path.join(transcript_dir, "*.txt"))
    if not transcript_files:
        log_note("Notice: No .txt files found in transcript directory.", notes_filepath)
        return df

    new_rows = []
    # Create a lookup set of existing normalized text to avoid duplicates
    # We group by participant to ensure we only match within the correct file
    existing_text_map = {}
    for p_id in df["p"].unique():
        # Get all text currently coded for this participant
        p_texts = df[df["p"] == p_id]["text"].astype(str).str.lower().tolist()
        existing_text_map[p_id] = p_texts

    injected_count = 0

    for filepath in transcript_files:
        # Extract participant ID from filename (assuming 'P07.txt' -> 'p07')
        filename = os.path.basename(filepath)
        p_id = filename.split(".")[0].lower()

        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()

            # Rule 1: Code at the single sentence level.
            # Handle mixed formatting (paragraphs vs lines) by first normalizing line endings
            content = content.replace("\r\n", "\n").replace("\r", "\n")

            # Split into initial chunks (paragraphs or manual lines)
            raw_chunks = [line.strip() for line in content.split("\n") if line.strip()]

            sentences = []
            for chunk in raw_chunks:
                # Regex to split sentences while respecting quotes:
                # Splits by [.!?] optionally followed by a quote ["”’], then whitespace.
                # We capture the delimiter (punctuation) to re-attach it to the sentence.
                parts = re.split(r'([.!?]["”’]?)\s+', chunk)

                # Re-assemble: parts[0] is text, parts[1] is punctuation, parts[2] is text...
                if len(parts) == 1:
                    # No split occurred
                    sentences.append(parts[0])
                else:
                    current_sent = parts[0]
                    # Loop through delimiters and next segments
                    for i in range(1, len(parts), 2):
                        delimiter = parts[i]
                        next_text = parts[i + 1] if i + 1 < len(parts) else ""

                        # Re-attach punctuation to the current sentence
                        current_sent += delimiter
                        if current_sent.strip():
                            sentences.append(current_sent.strip())

                        current_sent = next_text

                    # Append any remaining text after the last punctuation
                    if current_sent.strip():
                        sentences.append(current_sent.strip())

            current_coded_texts = existing_text_map.get(p_id, [])

            for sentence in sentences:
                clean_sent = clean_text(sentence)
                if not clean_sent:
                    continue

                norm_sent = clean_sent.lower()

                # MATCHING LOGIC:
                # Check if this transcript sentence is already "covered" by a coded segment.
                # strict match OR substring match (if coder selected part of sentence)
                is_matched = False

                # 1. Exact/Substring check against existing codes
                # This prevents adding a "True Negative" for a sentence that was actually coded
                for existing in current_coded_texts:
                    # If the coded text is inside the master sentence, or master is inside coded
                    # we assume it's "matched" (coded) and do NOT add a 0-0 row.
                    if existing in norm_sent or norm_sent in existing:
                        is_matched = True
                        break

                if not is_matched:
                    row = {
                        "p": p_id,
                        "text": clean_sent,
                        "code": "None",
                        "memo": "",
                        "all_agree": 0,
                        "TN": 1,
                    }
                    # Set all coders to 0
                    for c in coder_cols:
                        row[c] = 0

                    new_rows.append(row)
                    injected_count += 1

        except Exception as e:
            log_note(f"Error reading transcript {filename}: {e}", notes_filepath)

    if new_rows:
        negatives_df = pd.DataFrame(new_rows)
        # Combine and ensure ID is unique later
        df = pd.concat([df, negatives_df], ignore_index=True)
        log_note(
            f"   -> Injected {injected_count} 'True Negative' (0-0) rows from Master List.",
            notes_filepath,
        )
    else:
        log_note(
            "   -> No unmatched sentences found (or matching failed).", notes_filepath
        )

    return df


def load_and_prepare_data(
    input_dir, file_col, text_col, code_col, coder_col, memo_col, notes_filepath
):
    log_note("Step 1: Loading and Preparing Data", notes_filepath)

    # Ensure input directory exists
    if not os.path.exists(input_dir):
        log_note(
            f"Error: Input directory '{input_dir}' not found. Created it. Please place CSV files there.",
            notes_filepath,
        )
        os.makedirs(input_dir, exist_ok=True)
        return None, [], [], {}

    codebook_files = [f for f in os.listdir(input_dir) if f.endswith(".csv")]
    # Check for at least one file instead of two
    if len(codebook_files) < 1:
        log_note(
            f"Error: No CSV files found in '{input_dir}'.",
            notes_filepath,
        )
        return None, [], [], {}

    if len(codebook_files) == 1:
        log_note(
            f"Notice: Only 1 file found. Running in Single-Coder mode (Agreement metrics will be trivial/NA).",
            notes_filepath,
        )

    # Read files with utf-8-sig to handle BOM
    all_ratings_df = pd.concat(
        [
            pd.read_csv(
                os.path.join(input_dir, f), encoding="utf-8-sig", on_bad_lines="skip"
            )
            for f in codebook_files
        ],
        ignore_index=True,
    )

    if file_col not in all_ratings_df.columns:
        log_note(f"Error: Column '{file_col}' not found.", notes_filepath)
        return None, [], [], {}

    raw_stats = {
        "total_raw_events": len(all_ratings_df),
        "by_coder": all_ratings_df[coder_col].value_counts().to_dict(),
    }

    # Standardize Identifiers
    all_ratings_df["p"] = all_ratings_df[file_col].str.split(".").str[0].str.lower()
    required_cols = [text_col, code_col, coder_col, "p"]
    all_ratings_df.dropna(subset=required_cols, inplace=True)

    # Normalize and clean text
    log_note("Normalizing and cleaning text...", notes_filepath)
    all_ratings_df[text_col] = all_ratings_df[text_col].apply(clean_text)

    # Handle Memo Column if it exists
    has_memo = False
    if memo_col and memo_col in all_ratings_df.columns:
        has_memo = True
        all_ratings_df[memo_col] = all_ratings_df[memo_col].apply(clean_text)

    all_ratings_df[code_col] = (
        all_ratings_df[code_col]
        .astype(str)
        .str.strip()
        .str.replace(" ", "", regex=False)
    )

    all_coders = sorted(list(all_ratings_df[coder_col].unique()))

    # Group data by text and participant
    grouped = all_ratings_df.groupby([text_col, "p"])

    irr_data = []
    for (text_segment, p_value), group_df in grouped:
        relevant_codes = sorted(group_df[code_col].unique())
        for code in relevant_codes:
            new_row = {"text": text_segment, "p": p_value, "code": code}

            # Extract memo if available (concatenate unique memos for this segment/code)
            if memo_col and memo_col in all_ratings_df.columns:
                memos = group_df[group_df[code_col] == code][memo_col].unique()
                valid_memos = [m for m in memos if m]
                new_row["memo"] = "; ".join(valid_memos)
            else:
                new_row["memo"] = ""

            for coder in all_coders:
                is_present = not group_df[
                    (group_df[coder_col] == coder) & (group_df[code_col] == code)
                ].empty
                new_row[coder] = 1 if is_present else 0
            irr_data.append(new_row)

    wide_df = pd.DataFrame(irr_data)
    if wide_df.empty:
        return None, [], [], {}

    # Initialize True Negative tracker
    wide_df["TN"] = 0

    # Initialize TN with 0 (int) for all existing coded rows
    wide_df["TN"] = 0

    # Match and Fill True Negatives
    # We do this BEFORE calculating 'all_agree' or saving, so the 0-0 rows exist in the raw file
    transcripts_dir = getattr(config, "TRANSCRIPTS_DIRECTORY", "backend/transcripts")
    wide_df = load_transcripts_and_inject_negatives(
        wide_df, transcripts_dir, all_coders, notes_filepath
    )

    # Force clean types after injection
    wide_df["TN"] = wide_df["TN"].fillna(0).astype(int)
    # Ensure coder columns are ints (handle potential NaNs from merge)
    for c in all_coders:
        wide_df[c] = wide_df[c].fillna(0).astype(int)

    # Recalculate ID after injection
    wide_df["id"] = range(1, 1 + len(wide_df))

    # Calculate Agreement Flags
    num_coders = len(all_coders)
    sums = wide_df[all_coders].sum(axis=1)

    # User Request: all_agree is 1 ONLY if everyone agrees active coding.
    # If sums == 0 (TN), all_agree should be 0.
    wide_df["all_agree"] = (sums == num_coders).astype(int)

    # Ensure TN is 1 if sums is 0 (just in case they came from raw data not injection)
    wide_df.loc[sums == 0, "TN"] = 1
    # Ensure all_agree is 0 for TNs
    wide_df.loc[wide_df["TN"] == 1, "all_agree"] = 0

    # Removed: Loop to create _agreement columns

    final_cols = ["id", "p", "text", "code", "memo"] + all_coders + ["all_agree", "TN"]
    for c in final_cols:
        if c not in wide_df.columns:
            wide_df[c] = 0

    wide_df = wide_df[final_cols]

    output_path = os.path.join(OUTPUT_DIR, config.OUTPUT_MERGED_IRR_DATA_FILE)
    wide_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log_note(f"Saved merged data to '{output_path}'", notes_filepath)

    # Return raw_stats as the 4th element
    # Pass empty list for agreement cols to maintain signature compatibility if needed
    return wide_df, all_coders, [], raw_stats


def create_agreement_disagreement_files(df, coder_cols, notes_filepath, raw_stats):
    agreement_mask = df["all_agree"] == 1
    agreement_df = df[agreement_mask]
    disagreement_df = df[~agreement_mask]

    # Calculate percentages
    total_rows = len(df)
    agree_count = len(agreement_df)
    disagree_count = len(disagreement_df)
    agree_pct = (agree_count / total_rows * 100) if total_rows > 0 else 0
    disagree_pct = (disagree_count / total_rows * 100) if total_rows > 0 else 0

    # Write the detailed report
    log_note("\n" + "=" * 90, notes_filepath)
    log_note(f"{'EXACT MATCH MERGE SUMMARY':^90}", notes_filepath)
    log_note("=" * 90, notes_filepath)

    log_note("1. RAW INPUT DATA (Coding Events)", notes_filepath)
    log_note("-" * 60, notes_filepath)

    # Get total from the raw_stats dictionary passed from the previous function
    total_raw = raw_stats.get("total_raw_events", 0)

    # Sort coders by count for nicer display
    sorted_coders = sorted(
        raw_stats.get("by_coder", {}).items(), key=lambda x: x[1], reverse=True
    )

    for coder, count in sorted_coders:
        log_note(f"   - {coder:<20} : {count} segments", notes_filepath)
    log_note(f"   TOTAL CODING EVENTS    : {total_raw}", notes_filepath)

    log_note("\n2. EXACT MATCH PROCESSING", notes_filepath)
    log_note("-" * 60, notes_filepath)
    log_note(
        f"   The script grouped the {total_raw} raw events by [Participant + Text + Code].",
        notes_filepath,
    )
    log_note(
        "   If both coders marked the EXACT same text, it becomes 1 row.",
        notes_filepath,
    )
    log_note(
        "   If they marked different text, they remain separate rows (for now).",
        notes_filepath,
    )

    log_note("\n3. RESULTING DATASET (Units of Analysis)", notes_filepath)
    log_note("-" * 60, notes_filepath)
    log_note(f"   Total Unique Rows      : {total_rows}", notes_filepath)
    log_note(
        f"   - Full Agreements      : {agree_count:<6} ({agree_pct:.1f}%)",
        notes_filepath,
    )
    log_note(
        f"   - Disagreements        : {disagree_count:<6} ({disagree_pct:.1f}%)",
        notes_filepath,
    )
    log_note("-" * 60 + "\n", notes_filepath)


def main():
    initialize_output()
    notes_filepath = os.path.join(OUTPUT_DIR, "first_merge_notes.txt")
    print("--- Codebook Merging Utility ---")
    try:
        initialize_notes_file(notes_filepath)

        FILE_COLUMN = getattr(config, "FILE_COLUMN", "File")
        MEMO_COLUMN = getattr(config, "MEMO_COLUMN", "Coded_Memo")

        # Update unpacking to receive the 4th variable: raw_stats
        irr_df, coder_cols, _, raw_stats = load_and_prepare_data(
            config.INPUT_DIRECTORY,
            FILE_COLUMN,
            config.TEXT_COLUMN,
            config.CODE_COLUMN,
            config.CODER_NAME_COLUMN,
            MEMO_COLUMN,
            notes_filepath,
        )

        if irr_df is not None:
            # Pass raw_stats to the reporting function
            create_agreement_disagreement_files(
                irr_df, coder_cols, notes_filepath, raw_stats
            )
            print("\nMerge process complete.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
