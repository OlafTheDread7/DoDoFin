# list_transactions.py
# Simple script to list recent transactions with their IDs

import sqlite3
import db_utils # To get the DB file path easily

def list_recent_transactions(conn, limit=50):
    """ Fetches and prints recent transactions """
    cursor = conn.cursor()
    try:
        sql = """
            SELECT id, transaction_date, description, amount, is_income, category_id
            FROM transactions
            ORDER BY transaction_date DESC, id DESC
            LIMIT ?;
        """
        cursor.execute(sql, (limit,))
        transactions = cursor.fetchall()

        if not transactions:
            print(f"No transactions found in the database.")
            return

        print(f"\n--- Last {len(transactions)} Transactions ---")
        print("{:>5} | {:<10} | {:<40} | {:>10} | {:<6} | {}".format(
            "ID", "Date", "Description", "Amount", "Type", "Cat ID"
        ))
        print("-" * 85)
        for tx in transactions:
            tx_type = "Inc" if tx['is_income'] else "Exp"
            amount_str = f"${tx['amount']:.2f}"
            # Handle potential None for category_id gracefully
            cat_id_str = str(tx['category_id']) if tx['category_id'] is not None else "None"
            # Truncate long descriptions for display
            desc_short = tx['description'][:37] + '...' if len(tx['description']) > 40 else tx['description']

            print("{:>5} | {:<10} | {:<40} | {:>10} | {:<6} | {}".format(
                tx['id'], tx['transaction_date'], desc_short, amount_str, tx_type, cat_id_str
            ))
        print("-" * 85)

    except sqlite3.Error as e:
        print(f"Database error listing transactions: {e}")
    finally:
        if cursor: cursor.close()

if __name__ == "__main__":
    print(f"Connecting to database: {db_utils.DB_FILE}")
    connection = db_utils.create_connection() # Use connection func from db_utils
    if connection:
        list_recent_transactions(connection)
        connection.close()
        print("\nConnection closed.")
    else:
        print("Failed to connect to the database.")