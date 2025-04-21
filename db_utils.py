# db_utils.py
# Functions for direct database interaction
# Corrected version focusing on update_debt_details structure

import sqlite3
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
import math

DB_FILE = 'finance.db'

# --- Connection ---
def create_connection(db_file=DB_FILE):
    """ Create a database connection to the SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

# --- Category Functions ---
def get_categories(conn):
    """ Fetches all categories from the database, ordered by name. """
    cursor = conn.cursor()
    results = []
    try:
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        results = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB error fetching categories: {e}")
    finally:
        if cursor: cursor.close()
    return results

def add_category(conn, category_name):
    """ Adds a new category if it doesn't exist (case-insensitive). Returns ID. """
    cat_name = category_name.strip()
    if not cat_name: print("Category name cannot be empty."); return None
    cursor = conn.cursor(); new_id = None
    try:
        cursor.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (cat_name,))
        existing = cursor.fetchone()
        if existing:
            new_id = existing['id']
        else:
            sql = "INSERT INTO categories (name) VALUES (?)"
            cursor.execute(sql, (cat_name,))
            conn.commit()
            new_id = cursor.lastrowid
            print(f"Category '{cat_name}' added (ID: {new_id}).")
    except sqlite3.Error as e: print(f"DB error adding category '{cat_name}': {e}")
    finally:
        if cursor: cursor.close()
    return new_id

def update_transaction_category(conn, transaction_id, category_id):
    """ Updates the category for a single transaction. """
    sql = "UPDATE transactions SET category_id = ? WHERE id = ?"; cursor = conn.cursor(); success = False
    try:
        cursor.execute(sql, (category_id, transaction_id)); conn.commit(); success = True
    except sqlite3.Error as e: print(f"DB error updating tx {transaction_id}: {e}")
    finally:
        if cursor: cursor.close()
    return success

# --- Budget Functions ---
def get_budgets(conn):
    """ Fetches categories with currently set budget limits. Returns list of dicts with Decimals. """
    sql = "SELECT c.id, c.name, b.monthly_limit FROM categories c JOIN budget_simple b ON c.id = b.category_id ORDER BY c.name;"
    cursor = conn.cursor(); budgets = []
    try:
        cursor.execute(sql)
        for row in cursor.fetchall():
             try: limit = Decimal(str(row['monthly_limit'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
             except Exception: limit = Decimal('0.00')
             budgets.append({'id': row['id'], 'name': row['name'], 'monthly_limit': limit})
    except sqlite3.Error as e: print(f"DB error fetching budgets: {e}")
    except Exception as e: print(f"Error converting budget data: {e}")
    finally:
        if cursor: cursor.close()
    return budgets

def set_budget(conn, category_id, limit_amount):
    """ Sets or updates a budget limit. Expects Decimal, stores as float. """
    try: limit = max(0.0, float(Decimal(str(limit_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    except Exception: limit = 0.0
    sql = "INSERT OR REPLACE INTO budget_simple (category_id, monthly_limit) VALUES (?, ?);"; cursor = conn.cursor(); success = False
    try: cursor.execute(sql, (category_id, limit)); conn.commit(); success = True
    except sqlite3.Error as e: print(f"DB error set budget cat {category_id}: {e}")
    finally:
        if cursor: cursor.close()
    return success

def remove_budget(conn, category_id):
    """ Removes a budget limit for a given category ID. """
    sql = "DELETE FROM budget_simple WHERE category_id = ?;"; cursor = conn.cursor(); success = False
    try:
        cursor.execute("SELECT 1 FROM budget_simple WHERE category_id = ?", (category_id,))
        exists = cursor.fetchone()
        if exists:
            cursor.execute(sql, (category_id,)); conn.commit(); rows_affected = cursor.rowcount
            if rows_affected > 0: print(f"Budget removed for category ID {category_id}."); success = True
            else: print(f"Budget for category ID {category_id} found but not removed.")
        else: print(f"No budget found for category ID {category_id} to remove.")
    except sqlite3.Error as e: print(f"Database error removing budget cat {category_id}: {e}")
    finally:
        if cursor: cursor.close()
    return success

# --- Budget/Debt Totals for Affordability Check ---
def get_total_budgeted_expenses(conn):
    """ Calculates the sum of all monthly budget limits (as Decimal). """
    budgets = get_budgets(conn)
    total = Decimal('0.00')
    for b in budgets: total += b['monthly_limit']
    return total

def get_total_minimum_debt_payments(conn):
    """ Calculates the sum of all minimum debt payments (as Decimal). """
    debts = get_debts(conn)
    total = Decimal('0.00')
    for d in debts: total += d['minimum_payment']
    return total

# --- Debt Functions ---
def get_debts(conn):
    """ Fetches all debt records, converting amounts to Decimal, ordered by name. """
    sql = "SELECT id, name, lender, current_balance, interest_rate, minimum_payment, last_updated FROM debts ORDER BY name;"
    cursor = conn.cursor(); debts_list = []
    try:
        cursor.execute(sql)
        for row in cursor.fetchall():
             try:
                 debt_item = {
                     'id': row['id'], 'name': row['name'], 'lender': row['lender'],
                     'current_balance': Decimal(str(row['current_balance'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                     'interest_rate': Decimal(str(row['interest_rate'])),
                     'minimum_payment': Decimal(str(row['minimum_payment'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                     'last_updated': row['last_updated']
                 }
                 debts_list.append(debt_item)
             except Exception as conversion_e: print(f"Error converting data for debt ID {row['id']} ('{row['name']}'): {conversion_e}")
    except sqlite3.Error as e: print(f"DB error fetching debts: {e}")
    finally:
        if cursor: cursor.close()
    return debts_list

def add_debt(conn, name, lender, balance, rate, min_payment):
    """ Adds a new debt record. Expects Decimals for amounts/rate. """
    sql = "INSERT INTO debts (name, lender, current_balance, interest_rate, minimum_payment, last_updated) VALUES (?, ?, ?, ?, ?, ?);"
    cursor = conn.cursor(); today = datetime.date.today().strftime('%Y-%m-%d'); last_id = None
    try: cursor.execute(sql, (name, lender, float(balance), float(rate), float(min_payment), today)); conn.commit(); last_id = cursor.lastrowid; print(f"Debt '{name}' added.");
    except sqlite3.IntegrityError: print(f"Error: Debt name '{name}' already exists.");
    except sqlite3.Error as e: print(f"DB error adding debt '{name}': {e}")
    finally:
        if cursor: cursor.close()
    return last_id

# --- REWRITTEN update_debt_details function ---
def update_debt_details(conn, debt_id, balance, rate, min_payment, lender=None):
    """ Updates debt details. Expects Decimals for amounts/rate. """
    cursor = conn.cursor() # Open cursor once for the function
    today = datetime.date.today().strftime('%Y-%m-%d')
    lender_to_save = lender
    success = False

    try:
        # Determine the lender value if None was passed (keep original)
        if lender is None:
            cursor.execute("SELECT lender FROM debts WHERE id = ?", (debt_id,))
            result = cursor.fetchone()
            if result:
                 lender_to_save = result['lender']
            else:
                 # If debt doesn't exist during lender check, we can't update.
                 print(f"Error: Debt ID {debt_id} not found when checking lender.")
                 cursor.close() # Close before returning
                 return False # Can't proceed

        # Prepare the SQL statement
        sql = "UPDATE debts SET current_balance = ?, interest_rate = ?, minimum_payment = ?, lender = ?, last_updated = ? WHERE id = ?;"

        # Execute the update
        cursor.execute(sql, (float(balance), float(rate), float(min_payment), lender_to_save, today, debt_id))
        conn.commit()
        rows = cursor.rowcount # Check if any row was actually updated

        # Check results
        if rows > 0:
            print(f"Debt ID {debt_id} updated.")
            success = True
        else:
            # This means the ID didn't exist during the UPDATE, even if it existed during lender check (unlikely but possible)
            print(f"Error: Debt ID {debt_id} not found during update.")
            success = False

    except sqlite3.Error as e:
        print(f"DB error updating debt {debt_id}: {e}")
        success = False # Ensure success is False on error
    except Exception as e:
        print(f"Unexpected error updating debt {debt_id}: {e}")
        success = False # Ensure success is False on error
    finally:
        # Always close the cursor
        if cursor:
            cursor.close()

    return success
# --- END REWRITTEN update_debt_details function ---


def remove_debt(conn, debt_id):
    """ Removes a debt record after confirmation. """
    sql = "DELETE FROM debts WHERE id = ?;"
    cursor = conn.cursor()
    success = False
    name = f"ID {debt_id}" # Default name if lookup fails
    try:
        cursor.execute("SELECT name FROM debts WHERE id = ?", (debt_id,))
        result = cursor.fetchone()
        if result:
             name = result['name']
             confirm = input(f"Remove debt '{name}' (ID: {debt_id})? (y/n): ").lower()
             if confirm == 'y':
                 cursor.execute(sql, (debt_id,))
                 conn.commit()
                 rows = cursor.rowcount
                 if rows > 0: print(f"Debt '{name}' removed."); success = True
                 else: print("Removal failed (no rows affected).")
             else:
                 print("Removal cancelled.")
        else:
             print(f"Error: Debt ID {debt_id} not found.")
    except sqlite3.Error as e: print(f"DB error removing debt {debt_id}: {e}")
    except Exception as e: print(f"Unexpected error removing debt {debt_id}: {e}")
    finally:
        if cursor: cursor.close()
    return success

# --- Gamification Functions ---
def add_gamification_points(conn, points_to_add):
    """ Adds points to the user's score (user_id=1 assumed). """
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO gamification (user_id, points) VALUES (1, 0)")
        sql = "UPDATE gamification SET points = points + ? WHERE user_id = ?"
        cursor.execute(sql, (points_to_add, 1))
        conn.commit()
    except sqlite3.Error as e: print(f"DB error adding points: {e}")
    finally:
        if cursor: cursor.close()

def get_gamification_points(conn):
    """ Gets the current points for the user (user_id=1 assumed). """
    cursor = conn.cursor(); points = 0
    try:
        cursor.execute("SELECT points FROM gamification WHERE user_id = ?", (1,))
        result = cursor.fetchone(); points = result['points'] if result else 0
    except sqlite3.Error as e: print(f"DB error getting points: {e}")
    finally:
        if cursor: cursor.close()
    return points

# --- Transaction / Spending / Analysis Functions ---
def get_spending_for_month(conn, year, month):
    """ Calculates total spending per category (as Decimal) for a given month/year, excluding certain types. """
    m_str = f"{year:04d}-{month:02d}"; exclude = ('transfer', 'credit card payment', 'income', 'paycheck', 'returned purchase', 'gifts & donations', 'atm fee'); ph = ','.join('?'*len(exclude)); cursor = conn.cursor(); results = {}
    try:
        cursor.execute(f"SELECT id FROM categories WHERE LOWER(name) IN ({ph})", exclude); ex_ids = {r['id'] for r in cursor.fetchall()}
        id_placeholders = ','.join('?'*len(ex_ids)); not_in_clause = f"AND t.category_id NOT IN ({id_placeholders})" if ex_ids else ""
        sql = f"SELECT t.category_id, SUM(t.amount) total FROM transactions t WHERE t.is_income=0 AND strftime('%Y-%m', t.transaction_date)=? AND t.category_id IS NOT NULL {not_in_clause} GROUP BY t.category_id;"
        cursor.execute(sql, (m_str, *tuple(ex_ids)));
        results = {r['category_id']: Decimal(str(r['total'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for r in cursor.fetchall()}
    except sqlite3.Error as e: print(f"DB error get spending {m_str}: {e}")
    finally:
        if cursor: cursor.close()
    return results

def calculate_average_monthly_spend(conn):
    """ Calculates average monthly spending (as Decimal) for eligible categories. """
    print("\nCalculating average spending..."); cursor = conn.cursor(); avgs = None
    try:
        cursor.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM transactions WHERE is_income = 0"); r = cursor.fetchone()
        if not r or not r[0] or not r[1]: print("No expense data found."); cursor.close(); return None
        min_d = datetime.datetime.strptime(r[0], '%Y-%m-%d').date(); max_d = datetime.datetime.strptime(r[1], '%Y-%m-%d').date(); delta = relativedelta(max_d.replace(day=1), min_d.replace(day=1)); months = max(1, delta.years*12 + delta.months + 1)
        print(f"Data spans {r[0]} to {r[1]} ({months} months)."); exclude = ('transfer', 'credit card payment', 'income', 'uncategorized', 'paycheck', 'returned purchase', 'gifts & donations', 'atm fee'); ph = ','.join('?'*len(exclude)); cursor.execute(f"SELECT id FROM categories WHERE LOWER(name) IN ({ph})", exclude); ex_ids = {row['id'] for row in cursor.fetchall()}; print(f"Excluding IDs: {ex_ids}")
        id_placeholders = ','.join('?'*len(ex_ids)); not_in_clause = f"AND category_id NOT IN ({id_placeholders})" if ex_ids else ""
        sql = f"SELECT category_id, SUM(amount) as total FROM transactions WHERE is_income=0 AND category_id IS NOT NULL {not_in_clause} GROUP BY category_id;"
        cursor.execute(sql, tuple(ex_ids)); totals = cursor.fetchall();
        if not totals: print("No categorized expense data found (excluding specified categories)."); cursor.close(); return {}
        avgs = {}; print("\nAverage Monthly Spend:"); cats = {c['id']: c['name'] for c in get_categories(conn)} # Uses get_categories own cursor handling
        for row in totals:
            try: avg = (Decimal(str(row['total'])) / Decimal(months)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP); avgs[row['category_id']] = avg; category_name = cats.get(row['category_id'], f"ID {row['category_id']}"); print(f"  - {category_name}: ${avg:.2f}")
            except Exception as calc_e: print(f"Error calculating average for category ID {row.get('category_id', 'N/A')}: {calc_e}")
    except Exception as e: print(f"Error during average calculation setup: {e}"); avgs = None
    finally:
        if cursor: cursor.close()
    return avgs

def get_min_monthly_spend(conn, category_id):
    """ Finds the minimum non-zero monthly spending sum (as Decimal) for a given category ID. """
    sql = "SELECT SUM(amount) as total FROM transactions WHERE category_id=? AND is_income=0 AND amount>0 GROUP BY strftime('%Y-%m', transaction_date) HAVING total > 0 ORDER BY total ASC LIMIT 1;"
    cursor = conn.cursor(); min_spend = None
    try:
        cursor.execute(sql, (category_id,)); result = cursor.fetchone();
        if result: min_spend = Decimal(str(result['total'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else: min_spend = Decimal('0.00')
    except Exception as e: print(f"Error get min spend cat {category_id}: {e}")
    finally:
        if cursor: cursor.close()
    return min_spend
    
def get_one_uncategorized_transaction(conn):
    """ Fetches the details of a single uncategorized transaction (oldest first). """
    sql = """
        SELECT id, transaction_date, description, amount, is_income
        FROM transactions
        WHERE category_id IS NULL
        ORDER BY transaction_date, id
        LIMIT 1;
    """
    cursor = conn.cursor()
    result = None
    try:
        cursor.execute(sql)
        result = cursor.fetchone() # Returns a Row object or None
    except sqlite3.Error as e:
        print(f"DB error fetching uncategorized transaction: {e}")
    finally:
        if cursor: cursor.close()
    return result # Returns Row or None

def find_category_id_by_name(conn, category_name):
    """ Helper to find category ID by name (case-insensitive). """
    cursor = conn.cursor()
    category_id = None
    try:
        cursor.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (category_name,))
        result = cursor.fetchone()
        if result:
            category_id = result['id']
    except sqlite3.Error as e:
        print(f"DB error finding category ID for '{category_name}': {e}")
    finally:
        if cursor: cursor.close()
    return category_id
    
# --- ADD THIS FUNCTION to db_utils.py ---

def get_next_uncategorized_transaction(conn, exclude_ids=None):
    """
    Fetches the details of the next single uncategorized transaction,
    optionally excluding a list of IDs.
    """
    cursor = conn.cursor()
    result = None
    try:
        base_sql = """
            SELECT id, transaction_date, description, amount, is_income
            FROM transactions
            WHERE category_id IS NULL
        """
        params = []
        if exclude_ids:
            # Add clause to exclude specific IDs for the current session
            placeholders = ','.join('?' * len(exclude_ids))
            base_sql += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        # Add ordering and limit
        base_sql += " ORDER BY transaction_date, id LIMIT 1;"

        cursor.execute(base_sql, params)
        result = cursor.fetchone() # Returns a Row object or None

    except sqlite3.Error as e:
        print(f"DB error fetching next uncategorized transaction: {e}")
    finally:
        if cursor: cursor.close()
    return result # Returns Row or None

# --- END OF FUNCTION TO ADD ---

# --- ADD THESE FUNCTIONS to db_utils.py ---

def get_setting(conn, key, default=None):
    """ Retrieves a setting value from the app_settings table. """
    sql = "SELECT value FROM app_settings WHERE key = ?;"
    cursor = conn.cursor()
    value = default
    try:
        cursor.execute(sql, (key,))
        result = cursor.fetchone()
        if result:
            value = result['value'] # Value stored as TEXT
    except sqlite3.Error as e:
        print(f"DB error getting setting '{key}': {e}")
    finally:
        if cursor: cursor.close()
    return value

def set_setting(conn, key, value):
    """ Inserts or replaces a setting in the app_settings table. Value stored as TEXT. """
    sql = "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?);"
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute(sql, (key, str(value))) # Ensure value is stored as text
        conn.commit()
        success = True
    except sqlite3.Error as e:
        print(f"DB error setting setting '{key}': {e}")
    finally:
        if cursor: cursor.close()
    return success

# --- END OF FUNCTIONS TO ADD ---