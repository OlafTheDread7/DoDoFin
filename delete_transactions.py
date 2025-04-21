# delete_transactions.py
# Deletes specific transactions by ID after confirmation

import sqlite3
import db_utils # To get the DB file path and connection function

# --- Configuration ---
IDS_TO_DELETE = [7507, 7508, 7509, 7510, 7511, 7512] # Use the IDs you provided

def delete_specific_transactions(conn, ids_to_delete):
    """ Finds, confirms, and deletes transactions by ID """
    if not ids_to_delete:
        print("No IDs provided for deletion.")
        return

    cursor = conn.cursor()
    try:
        # Create placeholders for the IN clause (?,?,?...)
        placeholders = ','.join('?' * len(ids_to_delete))
        sql_select = f"""
            SELECT id, transaction_date, description, amount, is_income
            FROM transactions
            WHERE id IN ({placeholders})
            ORDER BY id;
        """
        cursor.execute(sql_select, ids_to_delete)
        transactions = cursor.fetchall()

        if not transactions:
            print("Did not find any transactions matching the specified IDs:")
            print(ids_to_delete)
            return

        print("\n--- Transactions to be DELETED ---")
        print("{:>5} | {:<10} | {:<40} | {:>10} | {}".format("ID", "Date", "Description", "Amount", "Type"))
        print("-" * 75)
        for tx in transactions:
            tx_type = "Inc" if tx['is_income'] else "Exp"
            amount_str = f"${tx['amount']:.2f}"
            desc_short = tx['description'][:37] + '...' if len(tx['description']) > 40 else tx['description']
            print("{:>5} | {:<10} | {:<40} | {:>10} | {}".format(tx['id'], tx['transaction_date'], desc_short, amount_str, tx_type))
        print("-" * 75)

        confirm = input(f"Are you absolutely sure you want to delete these {len(transactions)} transactions? (y/n): ").strip().lower()

        if confirm == 'y':
            sql_delete = f"DELETE FROM transactions WHERE id IN ({placeholders});"
            cursor.execute(sql_delete, ids_to_delete)
            conn.commit()
            deleted_count = cursor.rowcount
            print(f"\nSuccessfully deleted {deleted_count} transaction(s).")
        else:
            print("\nDeletion cancelled.")

    except sqlite3.Error as e:
        print(f"Database error during deletion process: {e}")
    finally:
        if cursor: cursor.close()


if __name__ == "__main__":
    print(f"Connecting to database: {db_utils.DB_FILE}")
    connection = db_utils.create_connection()
    if connection:
        delete_specific_transactions(connection, IDS_TO_DELETE)
        connection.close()
        print("\nConnection closed.")
    else:
        print("Failed to connect to the database.")