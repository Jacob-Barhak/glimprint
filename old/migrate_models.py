import sqlite3
import json
from pathlib import Path

DB_PATH = Path("db/glimprint.db")
JSON_PATH = Path("db/models.json")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        link TEXT
    );
    """)
    
    # Load JSON
    if JSON_PATH.exists():
        with open(JSON_PATH, 'r') as f:
            data = json.load(f)
            
        print(f"Migrating {len(data)} models...")
        for item in data:
            cursor.execute("""
            INSERT INTO models (title, description, link)
            VALUES (?, ?, ?)
            """, (item['title'], item['description'], item['link']))
            
        conn.commit()
        print("Migration complete.")
    else:
        print("models.json not found.")
        
    conn.close()

if __name__ == "__main__":
    migrate()
