import sqlite3
import os
import csv

DATABASE = os.path.join(os.path.dirname(__file__), 'sterlingflow.db')

def get_db_connection():
    """Establish a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the users and transactions tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Create transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def migrate_csv_to_user(user_id, csv_file_path):
    """
    Migrate existing global transactions from transactions.csv to a specific user.
    To avoid duplication, only runs if the transactions table is currently empty.
    Moves transactions.csv to transactions.csv.bak after successful migration.
    """
    if not os.path.exists(csv_file_path):
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Only migrate if the transactions database table is completely empty
    cursor.execute('SELECT COUNT(*) FROM transactions')
    count = cursor.fetchone()[0]
    
    if count > 0:
        conn.close()
        return False
        
    imported = 0
    try:
        with open(csv_file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    amount = float(row['amount'])
                    cursor.execute('''
                        INSERT INTO transactions (id, user_id, date, description, type, category, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (row['id'], user_id, row['date'], row['description'].strip(), row['type'], row['category'].strip(), amount))
                    imported += 1
                except (ValueError, KeyError, sqlite3.Error) as e:
                    print(f"Skipping CSV row migration due to error: {e}")
                    continue
                    
        conn.commit()
        
        # Backup CSV file so we don't attempt migration again and user has backup
        backup_path = csv_file_path + '.bak'
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(csv_file_path, backup_path)
        print(f"Successfully migrated {imported} transactions from CSV to user {user_id}.")
    except Exception as e:
        print(f"Error during database CSV migration: {e}")
        conn.rollback()
    finally:
        conn.close()
    return imported > 0
