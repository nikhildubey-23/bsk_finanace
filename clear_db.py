import sqlite3
import os
import shutil

DB_FILE = 'documents.db'
UPLOAD_FOLDER = 'uploads'

def clear_database():
    """
    This function clears all data from the specified database tables and deletes 
    associated uploaded files. It's designed to reset the application's data 
    to a clean state.
    """
    print("Clearing database and uploaded files as requested.")

    try:
        # Check if the database file exists before trying to connect
        if not os.path.exists(DB_FILE):
            print(f"Database file '{DB_FILE}' not found. Nothing to clear.")
            return

        # Establish a connection to the SQLite database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # List of tables to be cleared
        tables_to_clear = [
            'daily_entries', 
            'documents', 
            'clients', 
            'whatsapp_sent',
            'mf_companies',
            'mf_funds',
            'hi_companies',
            'hi_products'
        ]

        print("Clearing database tables...")
        for table in tables_to_clear:
            try:
                # Delete all records from the table
                cursor.execute(f"DELETE FROM {table};")
                # Reset the auto-increment counter for the table
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")
                print(f" - Table '{table}' cleared.")
            except sqlite3.OperationalError as e:
                # Handle cases where the table might not exist or doesn't have an auto-increment key
                if 'no such table' in str(e):
                    print(f" - Table '{table}' does not exist, skipping.")
                else:
                    # This error is ignored if the table exists but lacks an auto-increment key
                    pass

        # Commit all changes to the database
        conn.commit()
        conn.close()
        print("Database tables cleared successfully.")

        # Section to clear the uploads folder
        print(f"Clearing '{UPLOAD_FOLDER}' folder...")
        if os.path.exists(UPLOAD_FOLDER):
            # Iterate over all items in the uploads directory
            for item in os.listdir(UPLOAD_FOLDER):
                item_path = os.path.join(UPLOAD_FOLDER, item)
                # Skip reserved items like 'temp' directory or hidden files
                if item.lower() in ['temp', '.gitkeep'] or item.startswith('.'): 
                    continue
                try:
                    # Remove directories and files
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                    print(f" - Removed {item_path}")
                except Exception as e:
                    print(f" - Could not remove {item_path}: {e}")
        print(f"'{UPLOAD_FOLDER}' folder cleared.")
        
        print("\nOperation complete. Please restart the main application to re-initialize the database structure.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    clear_database()
