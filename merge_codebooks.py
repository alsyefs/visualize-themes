import pandas as pd
import os
from typing import List
from config import CODEBOOK_A, CODEBOOK_B, OUTPUT_MERGEED_FILE

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

def main():
    files_to_merge = [CODEBOOK_A, CODEBOOK_B]
    output_filename = OUTPUT_MERGEED_FILE
    print("Starting the CSV merge process...\n")
    merge_csv_files(files_to_merge, output_filename)
    if os.path.exists(output_filename):
        print(f"\nProcess complete. You can find the merged data in '{output_filename}'.")
    else:
        print("\nProcess finished, but the output file was not created. Please check for errors above.")

if __name__ == '__main__':
    main()
    

