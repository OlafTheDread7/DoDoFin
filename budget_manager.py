# budget_manager.py
# Handles budget management UI and logic
# Added view_spending_summary function

import sqlite3 # For exception handling if needed
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
# Import necessary functions from db_utils
from db_utils import ( get_budgets, set_budget, remove_budget, get_categories,
                       get_min_monthly_spend, calculate_average_monthly_spend,
                       get_spending_for_month #<-- Import needed for summary
                     )
from utils import get_string_input, get_decimal_input

ZERO_THRESHOLD = Decimal('0.005') # Define threshold if not globally available

# --- Budget Management Menu ---
def manage_budget_menu(conn):
    """ UI for manually setting, updating, or removing budgets. """
    while True:
        print("\n--- Manage Budgets (Manual) ---")
        budgets = get_budgets(conn) # Returns list of dicts with Decimals
        budgeted_ids = {b['id'] for b in budgets}

        if budgets:
            print("Current Budgets:")
            for i, b in enumerate(budgets):
                 print(f"  {i+1}: {b['name']} ${b['monthly_limit']:.2f}")
        else:
            print("No budgets set.")

        all_cats = get_categories(conn) # Returns list of Row objects
        budget_list = budgets # Already a list of dicts

        print("\nOptions: [s] Set/Update | [r] Remove | [b] Back")
        choice = input("Choice: ").strip().lower()

        if choice == 'b':
            break
        elif choice == 's':
            cats_to_budget_rows = [c for c in all_cats if c['name'].lower() not in ('income','transfer','credit card payment','paycheck','uncategorized','returned purchase','gifts & donations','atm fee')]
            if not cats_to_budget_rows:
                print("No categories available for budgeting.")
                continue

            print("\nSelect category to set/update budget:")
            display_list = [] # Store the Row objects being displayed
            budget_dict = {b['id']: b['monthly_limit'] for b in budget_list}
            for i, cat_row in enumerate(cats_to_budget_rows):
                cat_id = cat_row['id']
                cat_name = cat_row['name']
                limit = budget_dict.get(cat_id)
                info = f" (Current: ${limit:.2f})" if limit is not None else ""
                print(f"  {i+1}: {cat_name}{info}")
                display_list.append(cat_row)

            cat_choice = input("Category #: ")
            try:
                idx = int(cat_choice) - 1
                if 0 <= idx < len(display_list):
                    cat = display_list[idx] # Get the selected category Row object
                    limit_decimal = get_decimal_input(f"Monthly limit for '{cat['name']}': $") # Use Decimal helper
                    if set_budget(conn, cat['id'], limit_decimal): # Pass Decimal to set_budget
                        print(f"Budget for '{cat['name']}' set to ${limit_decimal:.2f}.")
                    else:
                        print(f"Failed to set budget for '{cat['name']}'.")
                else:
                    print("Invalid category number.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        elif choice == 'r':
            if not budgets:
                print("No budgets to remove.")
                continue
            print("\nSelect budget to remove:")
            for i, b in enumerate(budget_list):
                print(f"  {i+1}: {b['name']}") # Display only name for removal selection

            cat_choice = input("Category #: ")
            try:
                idx = int(cat_choice) - 1
                if 0 <= idx < len(budget_list):
                    b = budget_list[idx] # Get the selected budget dict
                    confirm = input(f"Remove budget for '{b['name']}'? (y/n): ").lower()
                    if confirm == 'y':
                        remove_budget(conn, b['id']) # remove_budget prints result
                    else:
                        print("Removal cancelled.")
                else:
                    print("Invalid category number.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        else:
            print("Invalid choice.")

# --- Auto-Budget Wrappers ---
def set_budgets_from_averages_wrapper(conn):
    """ Wrapper to confirm and call set_budgets_from_averages logic using db_utils function. """
    if input("This will overwrite existing budgets with calculated averages. Continue? (y/n): ").lower() == 'y':
        avgs = calculate_average_monthly_spend(conn) # From db_utils
        if avgs is None: print("Cannot set budgets from averages (calculation failed)."); return
        if not avgs: print("No average spending data found to set budgets."); return
        print("\nSetting budgets based on averages..."); count = 0
        for cat_id, avg in avgs.items():
            if set_budget(conn, cat_id, avg): count += 1
        print(f"\n--- Auto-Budget Complete: Set/updated {count} limits based on averages. ---")
    else: print("Cancelled.")

def set_budgets_to_minimums_wrapper(conn):
    """ Wrapper to confirm and call set_budgets_to_minimums logic using db_utils function. """
    target_cats = ['Entertainment', 'Fast Food', 'Restaurants', 'Shopping', 'Coffee Shops', 'Alcohol & Bars', 'Books', 'Clothing']
    print("\nSet budgets for minimum spend in: " + ", ".join(target_cats))
    if input("Are you sure? This might be very strict. (y/n): ").lower() == 'y':
        print("\nSetting budgets to minimum historical monthly spend...")
        cats_dict = {c['name'].lower(): c['id'] for c in get_categories(conn)}
        target_map = {cats_dict[n.lower()]: n for n in target_cats if n.lower() in cats_dict}
        if not target_map: print("Target categories not found."); return
        print(f"Targeting: {', '.join(target_map.values())}"); succ_c, fail_c = 0, 0; updated = {}
        for cat_id, cat_name in target_map.items():
            print(f" -> Processing '{cat_name}'...")
            min_s = get_min_monthly_spend(conn, cat_id) # From db_utils
            if min_s is not None:
                 print(f"    Lowest monthly spend found: ${min_s:.2f}")
                 if set_budget(conn, cat_id, min_s): succ_c += 1; updated[cat_name] = min_s
                 else: fail_c += 1
            else: print(f"    Could not determine minimum spend for '{cat_name}'."); fail_c += 1
        print("\n--- Minimum Budget Setting Complete ---"); print(f"Set {succ_c} limits:")
        for n, a in updated.items(): print(f"  - {n}: ${a:.2f}")
        if fail_c > 0: print(f"Failed to set/determine minimums for {fail_c} categories.")
    else: print("Cancelled.")

# --- NEW: Spending Summary Function ---
def view_spending_summary(conn):
    """ Displays spending vs budget summary for the current month. """
    today = datetime.date.today()
    year, month = today.year, today.month
    print(f"\n--- Spending Summary: {today.strftime('%B %Y')} ---")

    # Use functions from db_utils
    spending = get_spending_for_month(conn, year, month) # Returns dict {id: Decimal}
    budgets_list = get_budgets(conn) # Returns list of dicts with Decimals
    budgets = {b['id']: b['monthly_limit'] for b in budgets_list} # Convert to dict {id: Decimal}

    # Define excluded categories for summary view consistency
    exclude = ('transfer','credit card payment','income','uncategorized','paycheck','returned purchase','gifts & donations','atm fee')
    all_cats_rows = get_categories(conn) # List of Row objects
    all_cats = {c['id']: c['name'] for c in all_cats_rows if c['name'].lower() not in exclude}

    print("\n{:<25} | {:>12} | {:>12} | {:>15}".format("Category", "Spent", "Budget", "Remaining/Over"))
    print("-" * 70)

    # Combine keys from spending and budgets, filtering by allowed categories
    relevant_category_ids = (set(spending.keys()) | set(budgets.keys())) & set(all_cats.keys())
    total_s, total_b, over_c = Decimal('0.00'), Decimal('0.00'), 0
    # Sort by category name for consistent display
    sorted_ids = sorted(list(relevant_category_ids), key=lambda i: all_cats.get(i, "ZZZ")) # Use ZZZ to put missing names last

    for cid in sorted_ids:
        name = all_cats.get(cid)
        # Should not happen with intersection, but safe check
        if not name: continue

        spent = spending.get(cid, Decimal('0.00')) # Default to 0 if no spending
        budget = budgets.get(cid) # Returns Decimal or None
        total_s += spent

        if budget is not None:
            total_b += budget
            rem = budget - spent
            rem_s = f"${rem:.2f}" if rem >= 0 else f"(${abs(rem):.2f})" # Format negative in parentheses
            over_c += (rem < 0) # Increment over_c if remaining is negative
            bud_s = f"${budget:.2f}"
        else:
            rem_s, bud_s = "N/A", "N/A" # No budget set

        # Print formatted line
        print("{:<25} | ${:>11.2f} | {:>12} | {:>15}".format(name, spent, bud_s, rem_s))

    # Print Totals
    print("-" * 70)
    rem_o = total_b - total_s
    rem_o_s = f"${rem_o:.2f}" if rem_o >= 0 else f"(${abs(rem_o):.2f})"
    print("{:<25} | ${:>11.2f} | ${:>11.2f} | {:>15}".format("OVERALL TOTALS", total_s, total_b, rem_o_s))
    print("-" * 70)
    if over_c > 0:
        print(f"Attention: Over budget in {over_c} categories.")