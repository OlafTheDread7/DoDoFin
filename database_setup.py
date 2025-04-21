# database_setup.py
import sqlite3
import os

DB_FILE = 'finance.db'

def create_connection(db_file):
    """ Create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"SQLite version: {sqlite3.version}")
        print(f"Successfully connected to {db_file}")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_table(conn, create_table_sql):
    """ Create a table from the create_table_sql statement """
    cursor = None
    table_name = "UnknownTable" # Default in case split fails
    try:
        cursor = conn.cursor()
        # Extract table name more robustly
        parts = create_table_sql.split('(', 1)[0].split()
        if len(parts) >= 3 and parts[0].upper() == 'CREATE' and parts[1].upper() == 'TABLE':
            table_name_parts = parts[2].split('.') # Handle schema.table if present
            table_name = table_name_parts[-1]
            if parts[2].upper() == 'IF': # Handle IF NOT EXISTS
               table_name = parts[5].split('.')[0]

        cursor.execute(create_table_sql)
        print(f"Table '{table_name}' checked/created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating table '{table_name}': {e}")
    finally:
         if cursor: cursor.close()


def main():
    # --- Define Table Schemas ---
    sql_create_categories_table = """ CREATE TABLE IF NOT EXISTS categories (...); """ # Keep existing schema
    sql_create_transactions_table = """ CREATE TABLE IF NOT EXISTS transactions (...); """ # Keep existing schema
    sql_add_unique_constraint = """ CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_transaction ON transactions (...); """ # Keep existing schema
    sql_create_budget_simple_table = """ CREATE TABLE IF NOT EXISTS budget_simple (...); """ # Keep existing schema
    sql_create_gamification_table = """ CREATE TABLE IF NOT EXISTS gamification (...); """ # Keep existing schema
    sql_create_debts_table = """ CREATE TABLE IF NOT EXISTS debts (...); """ # Keep existing schema

    # --- NEW: App Settings Table ---
    sql_create_app_settings_table = """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY NOT NULL UNIQUE,
        value TEXT
    );
    """

    # --- Fill in the full schema definitions here ---
    sql_create_categories_table = """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """
    sql_create_transactions_table = """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_date DATE NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category_id INTEGER,
        is_income BOOLEAN DEFAULT 0,
        import_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    );
    """
    sql_add_unique_constraint = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_transaction
    ON transactions (transaction_date, description, amount);
    """
    sql_create_budget_simple_table = """
    CREATE TABLE IF NOT EXISTS budget_simple (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL UNIQUE,
        monthly_limit REAL NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    );
    """
    sql_create_gamification_table = """
    CREATE TABLE IF NOT EXISTS gamification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        points INTEGER DEFAULT 0,
        last_upload_date DATE,
        upload_streak INTEGER DEFAULT 0
    );
    """
    sql_create_debts_table = """
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        lender TEXT,
        current_balance TEXT NOT NULL, -- Store as TEXT for Decimal
        interest_rate TEXT NOT NULL,   -- Store as TEXT for Decimal
        minimum_payment TEXT NOT NULL, -- Store as TEXT for Decimal
        last_updated DATE
    );
    """

    # --- Execution ---
    conn = create_connection(DB_FILE)
    if conn is not None:
        print("\nCreating tables...")
        create_table(conn, sql_create_categories_table)
        create_table(conn, sql_create_transactions_table)
        create_table(conn, sql_create_budget_simple_table)
        create_table(conn, sql_create_gamification_table)
        create_table(conn, sql_create_debts_table)
        create_table(conn, sql_create_app_settings_table) # Create the new table

        print("\nCreating indexes...")
        cursor = conn.cursor();
        try: cursor.execute(sql_add_unique_constraint); print("Index 'idx_unique_transaction' checked/created.")
        except sqlite3.Error as e: print(f"Index creation error: {e}")
        finally: cursor.close()

        # Add default categories (using executemany for efficiency)
        print("\nAdding default categories...")
        cursor = conn.cursor();
        try:
            default_categories = [ ('Uncategorized',), ('Income',), ('Paycheck',), ('Groceries',), ('Shopping',), ('Restaurants',), ('Fast Food',), ('Coffee Shops',), ('Entertainment',), ('Rent/Mortgage',), ('Utilities',), ('Gas',), ('Auto Payment',), ('Auto Insurance',), ('Service & Parts',), ('Health Insurance',), ('Doctor',), ('Pharmacy',), ('Gym',), ('Mobile Phone',), ('Internet',), ('Subscriptions',), ('Transfer',), ('Credit Card Payment',), ('Student Loan Payment',), ('Gifts & Donations',), ('Personal Care',), ('Home Repair',), ('Pets',), ('Travel',), ('Clothing',), ('Books',), ('Electronics & Software',), ('Alcohol & Bars',), ('Financial',) ]
            cursor.executemany('INSERT OR IGNORE INTO categories(name) VALUES(?)', default_categories); conn.commit(); print("Default categories checked/added.")
        except sqlite3.Error as e: print(f"Error adding default categories: {e}")
        finally: cursor.close()

        # Initialize gamification
        print("\nInitializing gamification...")
        cursor = conn.cursor();
        try: cursor.execute("INSERT OR IGNORE INTO gamification (user_id, points) VALUES (1, 0)"); conn.commit(); print("Gamification initialized.")
        except sqlite3.Error as e: print(f"Error initializing gamification: {e}")
        finally: cursor.close()

        conn.close()
        print("\nDatabase setup/update complete. Connection closed.")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()