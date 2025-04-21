# main.py
# Main entry point for the Personal Finance Application
# Updated to call view_spending_summary from budget_manager

import os
import sys
import sqlite3 # For exception handling during connection
# Import necessary functions from modules
from db_utils import create_connection, get_gamification_points
from csv_importer import import_csv
from categorizer import categorize_transactions
# Import budget functions AND the summary view now
from budget_manager import manage_budget_menu, set_budgets_from_averages_wrapper, set_budgets_to_minimums_wrapper, view_spending_summary
from debt_manager import manage_debts_menu, check_debt_strategy_affordability

DB_FILE = 'finance.db'

# --- Main Execution ---
if __name__ == '__main__':
    if not os.path.exists(DB_FILE): print(f"DB '{DB_FILE}' not found. Run 'python database_setup.py'."); sys.exit(1)
    db_conn = create_connection(DB_FILE)
    if db_conn:
        print("DB connection ok."); print(f"(Points: {get_gamification_points(db_conn)})")
        while True:
            print("\n--- Main Menu ---")
            print("1: Import CSV        2: Categorize Txns")
            print("3: Manage Budget     4: View Summary") # No longer placeholder
            print("5: Auto-Budget      6: Tighten Budget (Min Spend)")
            print("7: Manage Debts      8: Check Debt Affordability")
            print("p: Show Points       q: Quit")
            choice = input("Enter choice: ").strip().lower()

            try: # Wrap menu actions in a general try/except
                if choice == '1':
                    csv_path = input("Enter CSV file path: ").strip()
                    if csv_path:
                        imp, upd, skp = import_csv(db_conn, csv_path)
                        if imp > 0 or upd > 0: # Check if imported OR updated
                             print("\nRun option '2' to categorize any remaining uncategorized transactions.")
                    else: print("No path entered.")
                elif choice == '2': categorize_transactions(db_conn)
                elif choice == '3': manage_budget_menu(db_conn)
                elif choice == '4': # Call the imported summary function
                     view_spending_summary(db_conn)
                elif choice == '5': set_budgets_from_averages_wrapper(db_conn)
                elif choice == '6': set_budgets_to_minimums_wrapper(db_conn)
                elif choice == '7': manage_debts_menu(db_conn)
                elif choice == '8': check_debt_strategy_affordability(db_conn)
                elif choice == 'p': print(f"Current points: {get_gamification_points(db_conn)}")
                elif choice == 'q': break
                else: print("Invalid choice.")
            except Exception as e:
                 print(f"\n--- An Error Occurred ---")
                 print(f"Error: {e}")
                 print("Please check the input or data and try again.")
                 import traceback # Provide more detail on error
                 traceback.print_exc()
                 print("--------------------------")

        # Close connection when loop terminates
        try: db_conn.close(); print("\nDB connection closed. Goodbye!")
        except sqlite3.Error as e: print(f"Error closing DB: {e}")
    else: print("DB connection failed. Exiting."); sys.exit(1)