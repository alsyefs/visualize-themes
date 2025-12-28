# /app.py
import backend.create_html_report as create_html_report
import backend.calculate_irr as calculate_irr
import backend.create_latex_appendix_of_codebook as create_latex_appendix_of_codebook
import backend.merge_codebooks as merge_codebooks
import backend.merge_code_text as merge_code_text
import backend.compare_agreement_columns as compare_agreement_columns
import backend.mark_agreements as mark_agreements
import backend.config as config
import os
import glob


def main():
    run_without_options()
    # run_with_options()  # If you need to run specific functions, uncomment this.


def run_without_options():
    print("--- Starting Automated Analysis ---")

    # Step 1: Merge Codebooks
    print(f"1/4: Merging codebooks from '{config.INPUT_DIRECTORY}'...")
    merge_codebooks.main()

    # Step 2: IRR Preparation
    print("2/4: Processing agreements and calculating IRR data...")
    calculate_irr.main()
    mark_agreements.main()

    # Step 3: Statistical Analysis
    print("3/4: Generating statistical agreement report...")
    compare_agreement_columns.main()

    # Step 4: HTML Report
    print("4/4: Generating interactive HTML report...")
    create_html_report.main()

    print("\n" + "=" * 50)
    print("✅ SUCCESS! Analysis Complete.")
    print(f"📂 Open the following file in your browser to view results:")
    print(f"   {config.HTML_OUTPUT_FILENAME}")
    print("=" * 50)


def run_with_options():
    csv_files = glob.glob(os.path.join(config.INPUT_DIRECTORY, "*.csv"))
    codetext_files = glob.glob(os.path.join(config.CODETEXTS_INPUT_DIR, "*.csv"))

    while True:
        print("\nHow would you like to proceed?")
        print(
            f"1. Just merge all codebooks (inputs='{config.INPUT_DIRECTORY}/*.csv'; output='{config.OUTPUT_MERGED_FILE}')..."
        )
        print(
            f"2. (Data Preparation phase) Merge and mark agreements. (inputs='{config.INPUT_DIRECTORY}/{[os.path.basename(f) for f in csv_files]}'; output=[{config.NOTES_FILE}, {config.IRR_AGREEMENT_INPUT_FILE}])"
        )
        print(
            f"3. (Statistical Analysis phase) Compare agreement columns in a CSV file. (input='{config.IRR_AGREEMENT_INPUT_FILE}'; output='{config.OUTPUT_DETAILED_AGREEMENT_FILE_PATH}')"
        )
        print(
            f"4. Generate HTML report. (input='{config.OUTPUT_MERGED_FILE}'; output='{config.HTML_OUTPUT_FILENAME}')"
        )
        print(
            f"5. Create LaTeX appendix of codebook. (input='{config.OUTPUT_MERGED_FILE}'; output='{config.OUTPUT_DIRECTORY}/appendix_codebook_[selected size].tex')"
        )
        print(
            f"6. Merge code text CSV files (Specific to QualCoder code_text table format). (inputs='{config.CODETEXTS_INPUT_DIR}/{[os.path.basename(f) for f in codetext_files]}'; output='{config.CODETEXT_OUTPUT_FILE}')"
        )

        print("0. Exit")
        choice = input("Enter your choice (0-6): ")
        if choice == "1":
            merge_codebooks.main()
        elif choice == "2":
            calculate_irr.main()
            mark_agreements.main()
        elif choice == "3":
            compare_agreement_columns.main()
        elif choice == "4":
            create_html_report.main()
        elif choice == "5":
            create_latex_appendix_of_codebook.main()
        elif choice == "6":
            merge_code_text.main()
        elif choice == "0":  # Exit
            print("Exiting the script. Goodbye!")
            break
        else:  # Invalid choice
            print("Invalid choice. Please enter a number between 0 and 6.")


if __name__ == "__main__":
    main()
