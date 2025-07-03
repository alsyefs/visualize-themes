import pandas as pd
import os
from typing import List

CODEBOOK_A = 'input/saleh_codebook.csv'
CODEBOOK_B = 'input/anish_codebook.csv'
OUTPUT_MERGEED_FILE = 'input/codebook.csv'

def merge_csv_files(input_files: List[str], output_file: str):
    """
    Merges multiple CSV files into a single CSV file.

    Args:
        input_files: A list of paths to the input CSV files.
        output_file: The path to save the merged CSV file.
    
    Returns:
        None
    """
    # List to hold dataframes
    df_list = []

    # Loop through the list of input files
    for file in input_files:
        try:
            # Check if file exists before attempting to read
            if not os.path.exists(file):
                print(f"Warning: File not found at {file}. Skipping.")
                continue
            
            # Read the CSV file into a pandas DataFrame
            # Added error_bad_lines=False and warn_bad_lines=True to handle potential parsing issues
            df = pd.read_csv(file, on_bad_lines='warn')
            df_list.append(df)
            print(f"Successfully loaded {file} with {len(df)} rows.")

        except Exception as e:
            print(f"Error reading {file}: {e}")

    # Check if we have any dataframes to merge
    if not df_list:
        print("No valid dataframes to merge. Exiting.")
        return

    # Concatenate all dataframes in the list into a single dataframe
    # ignore_index=True re-indexes the new dataframe from 0 to n-1
    merged_df = pd.concat(df_list, ignore_index=True)
    print(f"\nTotal rows in merged dataframe: {len(merged_df)}")

    try:
        # Write the merged dataframe to the specified output CSV file
        # index=False prevents pandas from writing the dataframe index as a column
        merged_df.to_csv(output_file, index=False)
        print(f"Successfully merged files into {output_file}")
    except Exception as e:
        print(f"Error writing to {output_file}: {e}")


if __name__ == '__main__':
    # --- Example Usage ---
    # This block demonstrates how to use the merge_csv_files function.
    
    # 1. Provide the names of the CSV files you want to merge.
    #    For this example, we'll use the codebooks you uploaded.
    #    In your actual use, you would replace these with your file names.
    #    Ensure the files are in the same directory as this script,
    #    or provide the full file path.
    files_to_merge = [CODEBOOK_A, CODEBOOK_B]
    
    # 2. Define the name for your new, merged file.
    output_filename = OUTPUT_MERGEED_FILE

    # 3. Call the function to perform the merge.
    print("Starting the CSV merge process...\n")
    merge_csv_files(files_to_merge, output_filename)

    # 4. (Optional) Check if the output file was created.
    if os.path.exists(output_filename):
        print(f"\nProcess complete. You can find the merged data in '{output_filename}'.")
    else:
        print("\nProcess finished, but the output file was not created. Please check for errors above.")

