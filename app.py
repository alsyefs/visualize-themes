import create_html_report as create_html_report
import calculate_irr as calculate_irr
import create_latex_appendix_of_codebook as create_latex_appendix_of_codebook
import merge_codebooks as merge_codebooks
import merge_code_text as merge_code_text
import compare_agreement_columns as compare_agreement_columns
import mark_agreements as mark_agreements
import config


def main():
    run_without_options()
    # run_with_options() # If you need to run specific functions, uncomment this.


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
    print(f"   output/codes.html")
    print("=" * 50)


def run_with_options():
    while True:
        print("\nHow would you like to proceed?")
        print(
            f"1. Just merge all codebooks (inputs='{config.INPUT_DIRECTORY}/*.csv'; output='input/codebook.csv')..."
        )
        print(
            "2. (Data Preparation phase) Merge and mark agreements. (inputs='irr_input/[all CSVs]'; output=[output/first_merge_notes.txt, output/merged_irr_data.csv])"
        )
        print(
            "3. (Statistical Analysis phase) Compare agreement columns in a CSV file. (input='output/merged_irr_data.csv'; output=output/agreements.txt)"
        )
        print(
            "4. Generate HTML report. (input='input/codebook.csv'; output='output/codes.html')"
        )
        print(
            "5. Create LaTeX appendix of codebook. (input='input/codebook.csv'; output=output/appendix_codebook_[selected size].tex)"
        )
        print(
            "6. Merge code text CSV files (Specific to QualCoder code_text table format). (inputs='input/[CODETEXTS_BY_CODERS]'; output='output/merged_code_text.csv')"
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
