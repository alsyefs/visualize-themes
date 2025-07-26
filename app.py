import create_html_report as create_html_report
import calculate_irr as calculate_irr
import create_latex_appendix_of_codebook as create_latex_appendix_of_codebook
import merge_codebooks as merge_codebooks
import merge_code_text as merge_code_text
import compare_agreement_columns as compare_agreement_columns
import mark_agreements as mark_agreements


def main():
    print("--- Main script started ---")
    while True:
        print("\nHow would you like to proceed?")
        print("1. Generate HTML report. (Requires 'input/codebook.csv' file)")
        print("2. Merge, mark agreements, and calculate scores. (Requires CSV files in 'irr_input' directory)")
        print("3. Create LaTeX appendix of codebook. (Requires 'input/codebook.csv' file)")
        print("4. Just Merge all codebooks. (Requires 'input/codebook.csv' file)")
        print("5. Merge code text CSV files (Specific to QualCoder code_text table format). (Requires 'input/code_text.csv' files)")
        print("0. Exit")
        choice = input("Enter your choice (0-5): ")
        if choice == '1':  # Generate HTML report
            create_html_report.main()
        elif choice == '2':
            calculate_irr.main()
            mark_agreements.main()
            compare_agreement_columns.main()
        elif choice == '3':
            create_latex_appendix_of_codebook.main()
        elif choice == '4':
            merge_codebooks.main()
        elif choice == '5':
            merge_code_text.main()
        elif choice == '0':  # Exit
            print("Exiting the script. Goodbye!")
            break
        else:  # Invalid choice
            print("Invalid choice. Please enter a number between 0 and 5.")

if __name__ == "__main__":
    main()
