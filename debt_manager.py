# debt_manager.py
# Handles debt management UI, strategies, and simulations
# Corrected version removing all semicolon statement chaining

import sqlite3 # For exception handling if needed
import datetime
from decimal import Decimal, ROUND_HALF_UP
# Import necessary functions from db_utils
from db_utils import get_debts, add_debt, update_debt_details, remove_debt, get_budgets, get_categories, get_total_budgeted_expenses, get_total_minimum_debt_payments
# Import input helpers
from utils import get_string_input, get_decimal_input # Use Decimal input helper

ZERO_THRESHOLD = Decimal('0.005')

# --- Affordability Check ---
def check_debt_strategy_affordability(conn):
    """ Calculates potential surplus for extra debt payments after accounting for overlaps. """
    print("\n--- Debt Strategy Affordability Check ---")

    est_monthly_income = get_decimal_input("Enter your ESTIMATED average monthly income (after tax): $")
    total_budgeted = get_total_budgeted_expenses(conn) # From db_utils
    print(f"Total Budgeted Expenses (sum of all limits): ${total_budgeted:.2f}")
    total_min_debt_pmt = get_total_minimum_debt_payments(conn) # From db_utils
    print(f"Total Minimum Debt Payments (from Debts list): ${total_min_debt_pmt:.2f}")

    # Identify overlap
    debt_related_category_names_lower = {'credit card payment', 'auto payment', 'student loan payment', 'financial'}
    all_budgets = get_budgets(conn)
    overlapping_budget_sum = Decimal('0.00')
    print("Checking for budget overlaps with minimum debt payments...")

    overlapping_cats_found = []
    for budget_item in all_budgets:
        if budget_item['name'].lower() in debt_related_category_names_lower:
            overlap_amount = budget_item['monthly_limit']
            overlapping_budget_sum += overlap_amount
            overlapping_cats_found.append(f"{budget_item['name']} (${overlap_amount:.2f})")

    if overlapping_cats_found:
        print(f" -> Found budget limits for debt-related categories: {', '.join(overlapping_cats_found)}")
        print(f" -> Subtracting this overlapping total (${overlapping_budget_sum:.2f}) from general budgeted expenses.")
    else:
        print(" -> No overlapping budget categories found for adjustment.")

    # Calculate adjusted expenses and surplus
    adjusted_budgeted_expenses = max(Decimal('0.00'), total_budgeted - overlapping_budget_sum)
    surplus = est_monthly_income - adjusted_budgeted_expenses - total_min_debt_pmt

    print("-" * 40)
    print(f"Estimated Monthly Income:      ${est_monthly_income:.2f}")
    print(f"Adjusted Budgeted Expenses:    -${adjusted_budgeted_expenses:.2f}")
    print(f"Total Minimum Debt Payments: -${total_min_debt_pmt:.2f}")
    print("----------------------------------------")
    print(f"Estimated Surplus/Deficit:     ${surplus:.2f}")
    print("-" * 40)

    if surplus > ZERO_THRESHOLD:
        print("Result: Based on your inputs, you have an estimated surplus.")
        print(f"You could potentially allocate up to ${surplus:.2f} as EXTRA payments towards debt each month.")
    else:
        print("Result: Based on your inputs, there is no estimated surplus.")
        print("Consider reviewing income/expenses or using 'Tighten Budget' (Option 6)")
        print("before planning accelerated debt payments.")
    print("-" * 40)


# --- Debt Payoff Simulation ---
def simulate_payoff(conn, strategy, total_monthly_payment):
    """ Simulates debt payoff using Snowball or Avalanche method. """
    total_monthly_payment = Decimal(str(total_monthly_payment)) # Ensure Decimal
    current_debts_list = get_debts(conn) # Fetches list of dicts with Decimals
    if not current_debts_list: print("No debts to simulate."); return None, None

    debts_sim = [{k: v for k, v in debt.items()} for debt in current_debts_list] # Make mutable copies

    total_min_payment_sim = sum(d['minimum_payment'] for d in debts_sim)
    if total_monthly_payment < total_min_payment_sim: print(f"Error: Total payment (${total_monthly_payment:.2f}) < total minimums (${total_min_payment_sim:.2f})."); return None, None

    month_count = 0
    total_interest_paid = Decimal('0.00')
    schedule = [] # List to store monthly snapshots
    active_debts = [d.copy() for d in debts_sim] # Work on copies

    while active_debts:
        month_count += 1
        if month_count > 1000: print("Error: Simulation > 1000 months."); return None, None

        monthly_interest_this_month = Decimal('0.00')
        payments_this_month = {d['id']: Decimal('0.00') for d in active_debts}
        balances_before_payment = {} # Store balance after interest, before payment

        # 1. Calculate interest
        for debt in active_debts:
            monthly_rate = debt['interest_rate'] / Decimal('1200') # APR to monthly
            interest = (debt['current_balance'] * monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if debt['current_balance'] > ZERO_THRESHOLD: # Only accrue interest if there's a balance
                debt['current_balance'] += interest
                monthly_interest_this_month += interest
                total_interest_paid += interest
            balances_before_payment[debt['id']] = debt['current_balance'] # Store balance after interest

        # 2. Allocate minimum payments
        payment_pool = total_monthly_payment
        for debt in active_debts:
             min_pay_due = min(debt['minimum_payment'], debt['current_balance'])
             min_pay_due = max(Decimal('0.00'), min_pay_due) # Ensure non-negative
             actual_min_paid = min(min_pay_due, payment_pool)
             payments_this_month[debt['id']] += actual_min_paid
             debt['current_balance'] -= actual_min_paid
             payment_pool -= actual_min_paid

        # 3. Allocate extra payment
        extra_payment = payment_pool # What's left in the pool is extra
        if extra_payment > ZERO_THRESHOLD:
            # Sort active debts based on strategy for extra payment application
            if strategy.lower() == 'snowball':
                active_debts.sort(key=lambda d: (d['current_balance'], -d['interest_rate']))
            elif strategy.lower() == 'avalanche':
                active_debts.sort(key=lambda d: (-d['interest_rate'], d['current_balance']))
            else: print("Error: Unknown strategy."); return None, None # Should not happen

            # Apply extra payment pool according to sorted order
            for debt in active_debts:
                 if extra_payment <= ZERO_THRESHOLD: break # No more extra payment left
                 can_pay_extra = debt['current_balance'] # Pay up to remaining balance
                 pay_this_extra = min(extra_payment, can_pay_extra)
                 payments_this_month[debt['id']] += pay_this_extra
                 debt['current_balance'] -= pay_this_extra
                 extra_payment -= pay_this_extra

        # 4. Record monthly snapshot
        month_snapshot = {
            'month': month_count,
            'interest_paid': monthly_interest_this_month,
            'payments': payments_this_month.copy(),
            'balances_before': balances_before_payment,
            'balances_after': {d['id']: d['current_balance'] for d in active_debts}
        }
        schedule.append(month_snapshot)

        # 5. Remove paid off debts for next iteration
        active_debts = [d for d in active_debts if d['current_balance'] > ZERO_THRESHOLD]

    # Simulation finished
    total_paid_calc = sum(p for month in schedule for p_dict in month['payments'].values() for p in [p_dict] )
    summary_stats = {
        'total_months': month_count,
        'total_interest': total_interest_paid.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),
        'total_paid': total_paid_calc.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    }
    return schedule, summary_stats


def display_payoff_schedule(schedule, summary_stats, debts_info):
    """ Formats and prints the payoff schedule and summary """
    if not schedule or not summary_stats: print("Nothing to display."); return
    print("\n--- Payoff Simulation Results ---")
    print(f"Estimated Payoff Time: {summary_stats['total_months']} months")
    print(f"Estimated Total Interest Paid: ${summary_stats['total_interest']:.2f}")
    print(f"Estimated Total Principal Paid: ${summary_stats['total_paid'] - summary_stats['total_interest']:.2f}")
    print(f"Estimated Total Paid: ${summary_stats['total_paid']:.2f}")
    show_details = input("\nShow detailed month-by-month breakdown? (y/n): ").strip().lower()
    if show_details != 'y': return
    print("\n--- Monthly Breakdown ---")
    print("{:<5} | {:<25} | {:>13} | {:>12} | {:>13}".format("Month","Debt Name","Start Balance","Payment","End Balance"))
    print("-" * 78)
    debt_names = {d['id']: d['name'] for d in debts_info}; max_months = 240; count = 0
    for month_data in schedule:
        count += 1;
        if count > max_months: print(f"... (truncated after {max_months} months) ..."); break
        month = month_data['month']; first = True; sorted_ids = sorted(month_data['payments'].keys(), key=lambda did: debt_names.get(did, 'Z'))
        for did in sorted_ids:
             payment = month_data['payments'][did]
             if payment > ZERO_THRESHOLD or did in month_data['balances_before']:
                 name = debt_names.get(did, f"ID {did}"); start = month_data['balances_before'].get(did, Decimal('0.00')); end = month_data['balances_after'].get(did, Decimal('0.00'))
                 m_str = str(month) if first else ""; pay_str = f"${payment:.2f}" if payment > ZERO_THRESHOLD else "$0.00"
                 print("{:<5} | {:<25} | ${:>12.2f} | {:>12} | ${:>12.2f}".format(m_str, name, start, pay_str, end)); first = False
        # Print total interest for the month
        print("{:<5} | {:<25} | {:>13} | {:>12} | {:>13}".format("","--- Month Totals --->","","Interest:", f"${month_data['interest_paid']:.2f}"));
        print("-" * 78)

# --- REWRITTEN show_debt_payoff_strategies_and_schedule function ---
def show_debt_payoff_strategies_and_schedule(conn):
    """ UI Wrapper for showing strategies AND simulating payoff """
    print("\n--- Debt Payoff Strategy Planner ---")
    debts = get_debts(conn) # Fetches list of dicts with Decimals
    if not debts:
        print("No debts entered yet.")
        return

    total_min_payment = sum(d['minimum_payment'] for d in debts)
    print(f"\nTotal Minimum Monthly Payment: ${total_min_payment:.2f}")

    while True:
        total_payment_planned = get_decimal_input("Total amount you plan to pay towards ALL debts this month: $") # Use Decimal helper
        if total_payment_planned >= total_min_payment:
            break
        else:
            print(f"Planned payment must be >= total minimums (${total_min_payment:.2f}).")

    extra_payment = total_payment_planned - total_min_payment
    print(f"Extra payment available: ${extra_payment:.2f}")
    print("-" * 40)

    # --- Show Snowball Order ---
    print("\nSNOWBALL METHOD Order (Lowest Balance First)")
    snowball_order = sorted(debts, key=lambda d: (d['current_balance'], d['name']))
    # Print header
    print("{:<25} | {:>13} | {:>7}% | {:>13} | {}".format("Name","Balance","Rate","Min Payment","Action"))
    print("-" * 80)
    # Use standard loop
    for i, debt in enumerate(snowball_order):
        action = f"-> Pay ${debt['minimum_payment']:.2f} (Minimum)"
        payment = debt['minimum_payment'] # Initialize payment
        if i == 0 and extra_payment > ZERO_THRESHOLD:
            payment += extra_payment
            action = f"-> PAY ${payment:.2f} (Min + Extra)"
        # Print details for each debt
        print("{:<25} | ${:>12.2f} | {:>6.2f}% | ${:>12.2f} | {}".format(
            debt['name'], debt['current_balance'], debt['interest_rate'], debt['minimum_payment'], action
        ))
    print("-" * 80) # Print separator after loop

    # --- Show Avalanche Order ---
    print("\nAVALANCHE METHOD Order (Highest Interest Rate First)")
    avalanche_order = sorted(debts, key=lambda d: (-d['interest_rate'], d['current_balance']))
    # Print header
    print("{:<25} | {:>13} | {:>7}% | {:>13} | {}".format("Name","Balance","Rate","Min Payment","Action"))
    print("-" * 80)
    # Use standard loop
    for i, debt in enumerate(avalanche_order):
        action = f"-> Pay ${debt['minimum_payment']:.2f} (Minimum)"
        payment = debt['minimum_payment'] # Initialize payment
        if i == 0 and extra_payment > ZERO_THRESHOLD:
            payment += extra_payment
            action = f"-> PAY ${payment:.2f} (Min + Extra)"
        # Print details for each debt
        print("{:<25} | ${:>12.2f} | {:>6.2f}% | ${:>12.2f} | {}".format(
            debt['name'], debt['current_balance'], debt['interest_rate'], debt['minimum_payment'], action
        ))
    print("-" * 80) # Print separator after loop

    # --- Ask to Simulate ---
    print("\nSimulate full payoff schedule?")
    sim_choice = input("Choose strategy [snowball/avalanche/no]: ").strip().lower()

    if sim_choice in ['snowball', 'avalanche']:
        print(f"\nSimulating {sim_choice.title()} payoff with ${total_payment_planned:.2f} monthly...")
        schedule, summary = simulate_payoff(conn, sim_choice, total_payment_planned)
        if schedule and summary:
            display_payoff_schedule(schedule, summary, debts) # Pass original debt info for names
        else:
            print("Simulation failed or generated no results.")
    else:
        print("Simulation cancelled.")
# --- END REWRITTEN show_debt_payoff_strategies_and_schedule function ---


# --- Main Debt Menu ---
def manage_debts_menu(conn):
    """ UI for managing debt entries and viewing strategies/schedules. """
    while True:
        print("\n--- Manage Debts ---")
        debts = get_debts(conn)
        if debts:
            print(" ID | {:<25} | {:<15} | {:>13} | {:>7} | {:>13} | {}".format("Name","Lender","Balance","Rate %","Min Payment","Last Updated")); print("-" * 98)
            for d in debts: print("{:3} | {:<25} | {:<15} | ${:>12.2f} | {:>6.2f}% | ${:>12.2f} | {}".format(d['id'],d['name'],d['lender'] or "N/A",d['current_balance'],d['interest_rate'],d['minimum_payment'],d['last_updated'])); print("-" * 98)
        else: print("No debts entered yet.")
        print("\nOptions: [a] Add | [u] Update | [r] Remove | [s] Plan Payoff Strategy/Schedule | [c] Check Affordability | [b] Back"); choice = input("Choice: ").strip().lower()

        if choice == 'b': break
        elif choice == 'a':
            print("\n--- Add Debt ---"); name = get_string_input("Name: "); lender = get_string_input("Lender (opt): ", allow_empty=True); balance = get_decimal_input("Balance: $"); rate = get_decimal_input("Rate (%): "); min_pay = get_decimal_input("Min Pmt: $"); add_debt(conn, name, lender or None, balance, rate, min_pay)
        elif choice == 'u':
            if not debts: print("No debts to update."); continue
            debt_id_str = input("ID to update: ");
            try:
                debt_id = int(debt_id_str); cursor = conn.cursor(); cursor.execute("SELECT * FROM debts WHERE id=?", (debt_id,)); debt_row = cursor.fetchone(); cursor.close()
                if debt_row:
                    debt = {k: (Decimal(str(v)).quantize(Decimal('0.01')) if k in ['current_balance', 'minimum_payment'] else (Decimal(str(v)) if k == 'interest_rate' else v)) for k,v in dict(debt_row).items()}
                    print(f"\n--- Updating: {debt['name']} ---");
                    bal=get_decimal_input(f"New Bal (${debt['current_balance']:.2f}): $")
                    rate=get_decimal_input(f"New Rate ({debt['interest_rate']:.2f}%): ")
                    minp=get_decimal_input(f"New Min Pmt (${debt['minimum_payment']:.2f}): $")
                    lend=get_string_input(f"New Lender ('{debt['lender'] or ''}' - Enter text or '' to clear, Enter only to keep current): ", allow_empty=True)
                    lender_to_pass = None;
                    if lend is not None: lender_to_pass = lend
                    update_debt_details(conn, debt_id, bal, rate, minp, lender=lender_to_pass)
                else: print(f"Debt ID {debt_id} not found.")
            except ValueError: print("Invalid ID format.")
            except sqlite3.Error as e: print(f"DB error during update prep for ID {debt_id_str}: {e}")
        elif choice == 'r':
            if not debts: print("No debts to remove."); continue
            debt_id_str = input("ID to remove: ");
            try: debt_id = int(debt_id_str); remove_debt(conn, debt_id)
            except ValueError: print("Invalid ID format.")
        elif choice == 's':
            show_debt_payoff_strategies_and_schedule(conn) # Call corrected function
        elif choice == 'c':
            check_debt_strategy_affordability(conn)
        else: print("Invalid choice.")