import sqlite3

DB_FILE = "app/content/glimprint.db"

def update_schema():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if columns exist
    cursor = c.execute("PRAGMA table_info(seminars)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = {
        'speaker': 'TEXT',
        'abstract': 'TEXT',
        'time': 'TEXT',
        'registration_link': 'TEXT'
    }
    
    for col, dtype in new_cols.items():
        if col not in columns:
            print(f"Adding column {col}...")
            c.execute(f"ALTER TABLE seminars ADD COLUMN {col} {dtype}")
        else:
            print(f"Column {col} already exists.")
            
    conn.commit()
    conn.close()
    print("Schema updated.")

if __name__ == "__main__":
    update_schema()
