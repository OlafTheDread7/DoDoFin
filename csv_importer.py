# csv_importer.py
# Handles importing transactions from CSV files
# Updated to use UPSERT (ON CONFLICT...DO UPDATE)

import pandas as pd
import os
import datetime
import sqlite3 # Needed for exception type hinting if desired
from db_utils import get_categories, add_category # Import needed functions

def import_csv(conn, csv_filepath):
    """
    Imports transaction data from CSV. If a transaction with the same
    date, description, and amount exists, it updates the existing
    record's category_id and is_income flag instead of ignoring the row.

    :param conn: Database connection object
    :param csv_filepath: Path to the CSV file
    :return: Tuple (imported_count, updated_count, skipped_count)
    """
    if not os.path.exists(csv_filepath):
        print(f"Error: File not found: {csv_filepath}")
        return 0, 0, 0 # Imported, Updated, Skipped

    print(f"\n--- Importing: {csv_filepath} ---")
    print("Importing/Updating transactions based on CSV...")
    try:
        # Configuration (Update if your bank format changes)
        date_col, desc_col, amount_col, category_col = 'Date', 'Description', 'Amount', 'Category'
        try:
            df = pd.read_csv(csv_filepath, encoding='utf-8', keep_default_na=False)
        except UnicodeDecodeError:
            print("UTF-8 failed, trying latin1...")
            df = pd.read_csv(csv_filepath, encoding='latin1', keep_default_na=False)
        print(f"CSV loaded: {len(df)} rows.")

        # Data Cleaning and Preparation
        rename_map = {}
        required_cols_map = {date_col: 'std_date', desc_col: 'std_description', amount_col: 'std_amount'}
        for k, v in required_cols_map.items():
            if k in df.columns: rename_map[k] = v
            else: print(f"Error: Column '{k}' not found!"); return 0, 0, 0
        if category_col in df.columns: rename_map[category_col] = 'std_category_name'
        else: print(f"Warning: Column '{category_col}' not found."); df['std_category_name'] = ''
        df.rename(columns=rename_map, inplace=True)

        try:
            df['std_date'] = pd.to_datetime(df['std_date'])
            df['std_date_str'] = df['std_date'].dt.strftime('%Y-%m-%d')
        except Exception as e: print(f"Error converting date: {e}"); return 0, 0, 0
        try:
            if df['std_amount'].dtype == 'object': df['std_amount'] = df['std_amount'].astype(str).str.replace(r'[$,]', '', regex=True)
            df['std_amount'] = pd.to_numeric(df['std_amount'], errors='coerce');
            nan_count = df['std_amount'].isnull().sum()
            if nan_count > 0: print(f"Warning: {nan_count} Amount values invalid, rows skipped."); df.dropna(subset=['std_amount'], inplace=True)
        except Exception as e: print(f"Error converting amount: {e}"); return 0, 0, 0

        df['is_income'] = df['std_amount'] > 0
        df['abs_amount'] = df['std_amount'].abs()

        # Prepare Category IDs
        print("Processing categories...")
        existing_cats = {c['name'].lower(): c['id'] for c in get_categories(conn)}
        manual_review = {'', 'category pending', 'uncategorized'}
        cat_ids = []
        new_cats = set()
        for idx, row in df.iterrows():
            raw_cat = row.get('std_category_name', '')
            cat_name = str(raw_cat).strip()
            cat_lower = cat_name.lower()
            cat_id = None # Default to NULL if requires manual review
            if cat_lower not in manual_review: # Only process if not flagged for manual review
                if cat_lower in existing_cats:
                    cat_id = existing_cats[cat_lower]
                else:
                    # Only add if cat_name is not empty
                    if cat_name:
                        if cat_name not in new_cats: print(f"Adding new category: '{cat_name}'"); new_cats.add(cat_name)
                        new_id = add_category(conn, cat_name); # add_category handles DB interaction
                        if new_id: existing_cats[cat_lower] = new_id; cat_id = new_id
                        else: print(f"Warning: Could not add category '{cat_name}'.")
                    # If cat_name was empty but not in manual_review, cat_id remains None
            cat_ids.append(cat_id) # Append the determined ID (or None)
        df['std_category_id'] = cat_ids
        print("Category processing complete.");
        if new_cats: print(f"Added {len(new_cats)} new categories.")

        # Insert or Update Data into Database
        cursor = conn.cursor()
        imported_count = 0
        updated_count = 0
        skipped_count = 0 # Count rows skipped due to missing data pre-insert
        # --- MODIFIED SQL STATEMENT ---
        sql_upsert = """
        INSERT INTO transactions (transaction_date, description, amount, is_income, category_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(transaction_date, description, amount) DO UPDATE SET
          category_id = excluded.category_id,
          is_income = excluded.is_income,
          -- Update import timestamp to reflect when it was last seen/updated
          import_timestamp = CURRENT_TIMESTAMP
        WHERE
          -- Optional: Only update if the category is actually changing?
          -- Or always update to reflect latest CSV info. Let's always update for now.
          transactions.category_id IS NOT excluded.category_id OR transactions.is_income IS NOT excluded.is_income;
        """
        # The WHERE clause in DO UPDATE makes it conditional: only update if category or income flag differs.
        # Remove the WHERE clause if you want to always overwrite category/income on conflict.

        print(f"Attempting insert/update for {len(df)} txns...")
        for idx, row in df.iterrows():
             if pd.notna(row['std_date_str']) and pd.notna(row['std_description']) and pd.notna(row['abs_amount']):
                 try:
                     cursor.execute(sql_upsert, (
                         row['std_date_str'],
                         str(row['std_description']),
                         row['abs_amount'],
                         int(row['is_income']),
                         row['std_category_id'] # This can be None
                     ))
                     # cursor.rowcount isn't reliable for detecting insert vs update here easily.
                     # We might need separate SELECT + INSERT/UPDATE logic for precise counts,
                     # but for now, let's just commit. We can infer based on changes later if needed.

                 except sqlite3.Error as e:
                     print(f"DB Error row {idx}: {e}")
                     skipped_count += 1 # Count errors as skipped
             else:
                 print(f"Skipping row {idx} due to missing data.")
                 skipped_count += 1

        # Commit all changes at the end
        conn.commit()

        # Get approximate counts (less accurate without pre-checking)
        # For now, just report success/skips based on processing
        # We need a different approach to accurately count inserts vs updates with ON CONFLICT
        print(f"\n--- Import complete ---")
        # print(f"Processed: {len(df) - skipped_count} rows (inserted or updated).") # Approximate
        print(f"Skipped: {skipped_count} rows (due to errors or missing data).")
        # Add a check for remaining uncategorized items
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE category_id IS NULL");
        needs_cat = cursor.fetchone()[0];
        cursor.close()
        if needs_cat > 0:
            print(f"\nNOTE: {needs_cat} txns need manual categorization (Opt 2).")

        # Return dummy values for updated/imported until we implement better counting
        return len(df) - skipped_count, 0, skipped_count

    except Exception as e:
        print(f"Import Error: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0, len(df) if 'df' in locals() else 0 # Skip all on major error