import csv
import os

# Global variables for input and output filenames
INPUT_FILENAME = 'notes/Merged_codebook1to6 - updated_merge.csv'
OUTPUT_FILENAME = 'output/fixed_merged_codebook.csv'
IRR_DATA_FILENAME = 'input/merged_irr_data_p01_to_p06.csv'

def fix_csv():
    """
    Fixes the format of the input CSV file by adding participant names,
    formatting them, removing spaces from the code column, and saving
    the result to a new CSV file.
    """
    # Create a dictionary to store participant names from merged_irr_data.csv
    participant_names = {}
    if os.path.exists(IRR_DATA_FILENAME):
        with open(IRR_DATA_FILENAME, 'r', newline='', encoding='utf-8') as irr_file:
            reader = csv.DictReader(irr_file)
            for row in reader:
                participant_names[row['id']] = row.get('p', '')

    if not os.path.exists(INPUT_FILENAME):
        print(f"Error: Input file '{INPUT_FILENAME}' not found.")
        return

    with open(INPUT_FILENAME, 'r', newline='', encoding='utf-8') as infile, \
         open(OUTPUT_FILENAME, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        # New header with 'p' column
        new_fieldnames = ['id', 'p'] + [field for field in reader.fieldnames if field != 'id']
        writer = csv.DictWriter(outfile, fieldnames=new_fieldnames)
        writer.writeheader()

        for row in reader:
            # Get participant name from the dictionary
            participant_name = participant_names.get(row['id'], '')
            # Format participant name
            formatted_participant_name = participant_name.lower().replace('.txt', '')
            row['p'] = formatted_participant_name

            # Remove spaces from the 'code' column
            if 'code' in row:
                row['code'] = row['code'].replace(' ', '')

            # Reorder the row to have 'p' as the second column
            new_row = {'id': row['id'], 'p': row['p']}
            new_row.update({k: v for k, v in row.items() if k not in ['id', 'p']})
            writer.writerow(new_row)

    print(f"Successfully processed '{INPUT_FILENAME}' and saved the output to '{OUTPUT_FILENAME}'")

if __name__ == '__main__':
    fix_csv()