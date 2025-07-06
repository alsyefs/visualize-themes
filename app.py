import create_html_report as create_html_report
import calculate_irr as calculate_irr
import create_latex_appendix_of_codebook as create_latex_appendix_of_codebook

def main():
    print("--- Main script started ---")
    while True:
        print("\nHow would you like to proceed?")
        print("1. Generate HTML report")
        print("2. Create LaTeX appendix of codebook")
        print("3. Calculate Inter-Rater Reliability (IRR)")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ")
        if choice == '1':  # Generate HTML report
            create_html_report.main()
        elif choice == '2':  # Create LaTeX appendix of codebook
            create_latex_appendix_of_codebook.main()
        elif choice == '3':  # Calculate Inter-Rater Reliability (IRR)
            calculate_irr.main()
        elif choice == '4':  # Exit
            print("Exiting the script. Goodbye!")
            break
        else:  # Invalid choice
            print("Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    main()
