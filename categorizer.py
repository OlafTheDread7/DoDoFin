# categorizer.py
# Handles the manual transaction categorization workflow

import sqlite3 # Needed only for exception type hinting if desired
from db_utils import get_categories, add_category, update_transaction_category, add_gamification_points, get_gamification_points

def categorize_transactions(conn):
    """ Guides the user through categorizing uncategorized transactions. """
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, transaction_date, description, amount, is_income FROM transactions WHERE category_id IS NULL ORDER BY transaction_date")
        uncat = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error fetching uncategorized transactions: {e}")
        cursor.close()
        return
    # Close cursor after fetch before starting loop
    cursor.close()

    if not uncat:
        print("\n🎉 No transactions waiting to be categorized.")
        return

    print(f"\nFound {len(uncat)} transactions to categorize.")
    cat_c, pts_e = 0, 0
    categories = get_categories(conn) # Fetch initial list

    for i, tx in enumerate(uncat):
        print(f"\n--- Tx {i+1}/{len(uncat)} ---")
        tx_type = "Income" if tx['is_income'] else "Expense"
        print(f"Date: {tx['transaction_date']}, Desc: {tx['description']}, Amt: ${tx['amount']:.2f} ({tx_type})")
        print("--- Categories ---")
        for idx, c in enumerate(categories):
            print(f"  {idx + 1}: {c['name']}")
        print("\nOptions: [Num] Assign | [a] Add New | [s] Skip | [q] Quit")

        while True: # Loop for input for the current transaction
            choice = input("Choice: ").strip().lower()
            if choice == 'q':
                print("Quitting categorization.")
                conn.commit() # Save any progress made
                return # Exit function
            if choice == 's':
                print("Skipping.")
                break # Exit inner loop, go to next transaction
            if choice == 'a':
                n_cat = input("New category name: ").strip()
                if n_cat:
                    n_id = add_category(conn, n_cat) # Handles commit/cursor
                    if n_id and update_transaction_category(conn, tx['id'], n_id): # Handles commit/cursor
                        print(f"Categorized as '{n_cat}'.")
                        categories = get_categories(conn) # Refresh list
                        cat_c += 1
                        add_gamification_points(conn, 1) # Handles commit/cursor
                        pts_e += 1
                        break # Exit inner loop
                    else:
                        print("Failed to add category or update transaction.")
                else:
                    print("Empty category name entered.")
            else:
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(categories):
                        category_to_assign = categories[choice_idx]
                        if update_transaction_category(conn, tx['id'], category_to_assign['id']): # Handles commit/cursor
                            print(f"Categorized as '{category_to_assign['name']}'.")
                            cat_c += 1
                            add_gamification_points(conn, 1) # Handles commit/cursor
                            pts_e += 1
                            break
                        else:
                            print("Failed to update transaction category.")
                    else:
                        print("Invalid category number.")
                except ValueError:
                    print("Invalid input. Please enter a number, 'a', 's', or 'q'.")
    # After loop
    conn.commit() # Final commit (though most ops commit themselves now)
    print("\n--- Categorization Summary ---")
    print(f"Categorized: {cat_c}, Points earned: {pts_e}, Total points: {get_gamification_points(conn)}")
    rem = len(uncat) - cat_c
    if rem > 0:
        print(f"{rem} transactions still need categorization.")