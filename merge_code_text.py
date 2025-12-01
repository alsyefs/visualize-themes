import pandas as pd
import os
from config import CODETEXTS_BY_CODERS

INPUT_CODE_TEXT_FILES = CODETEXTS_BY_CODERS


def merge_csv_files(file_list, output_filename):
    """
    Merges a list of CSV files into a single CSV file, preserving the header
    and enforcing correct data types to prevent SQLite import errors.

    This script is designed to combine CSV files that share the same column structure.
    It reads each CSV, concatenates them into one dataset, and saves the result.

    Args:
        file_list (list): A list of paths to the CSV files to merge.
        output_filename (str): The path for the output merged CSV file.
    """
    # Data Type Definition
    # Define the expected data types for each column based on the SQLite schema.
    # Using pandas' nullable 'Int64' for integer columns is crucial as it can
    # handle missing values (NaNs) without forcing the column to a float type.
    # 'str' ensures text columns are treated as strings.
    column_types = {
        "ctid": "Int64",
        "cid": "Int64",
        "fid": "Int64",
        "seltext": "str",
        "pos0": "Int64",
        "pos1": "Int64",
        "owner": "str",
        "date": "str",
        "memo": "str",
        "avid": "Int64",
        "important": "Int64",
    }

    df_list = []

    # File Validation
    if not file_list:
        print("Error: The list of files to merge is empty.")
        return

    for f in file_list:
        if not os.path.exists(f):
            print(
                f"Error: The file '{f}' was not found. Please check the path and filename."
            )
            return
        print(f"Found file: '{f}'")

    # Merging Logic
    try:
        # Read each CSV into a pandas DataFrame, applying our type definitions
        for file in file_list:
            df = pd.read_csv(file, dtype=column_types)
            df_list.append(df)

        # Concatenate all DataFrames in the list into a single DataFrame
        merged_df = pd.concat(df_list, ignore_index=True)

        # Data Cleaning
        # For any text columns, explicitly fill any missing values with an empty string.
        for col in ["seltext", "owner", "date", "memo"]:
            if col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna("")

        # Primary Key Warning
        if "ctid" in merged_df.columns and merged_df["ctid"].duplicated().any():
            print("\n--- WARNING: Duplicate Primary Keys Found! ---")
            print("Duplicate values were found in the 'ctid' column.")
            print("Importing this file will fail because 'ctid' is a primary key.")
            print("You should fix the 'ctid' values in the original CSVs to be unique.")
            print("-------------------------------------------------")

        # Save the Merged File
        # index=False prevents pandas from writing its own row numbers into the CSV.
        merged_df.to_csv(output_filename, index=False)

        print(f"\nSuccessfully merged {len(file_list)} files into '{output_filename}'")
        print("\n--- Merged Data Preview (first 5 rows) ---")
        print(merged_df.head())
        print("------------------------------------------")

    except Exception as e:
        print(f"\nAn error occurred during the merging process: {e}")


def main():
    """
    Main function to execute the CSV merging process.
    It reads the configuration for input files and output file name,
    then calls the merge_csv_files function.
    """
    # Configuration
    # Put the names of your CSV files in this list.
    files_to_merge = INPUT_CODE_TEXT_FILES

    # This will be the name of your final, combined file.
    output_file = "output/merged_code_text.csv"
    # End Configuration

    merge_csv_files(files_to_merge, output_file)


if __name__ == "__main__":
    main()
