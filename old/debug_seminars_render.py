from jinja2 import Environment, FileSystemLoader
import sqlite3
import os
from pathlib import Path

# Mimic the path setup in routes.py
BASE_DIR = Path("/home/work/glimprint")
CONTENT_DIR = BASE_DIR / "app" / "content"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

def get_db_connection():
    db_path = CONTENT_DIR / "glimprint.db"
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def  debug_render():
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    
    try:
        conn = get_db_connection()
        print("Executing query...")
        rows = conn.execute('SELECT * FROM seminars').fetchall()
        print(f"Query returned {len(rows)} rows.")
        
        # Verify row content
        for i, row in enumerate(rows[:3]):
             print(f"Row {i}: {dict(row)}")

        conn.close()

        print("Rendering template...")
        template = env.get_template("seminars.html")
        rendered = template.render(request={}, seminars=rows)
        
        print("--- Rendered Output Snippet ---")
        print(rendered[:2000]) # First 2000 chars
        print("...")
        
        # specific check
        if "seminar-item" in rendered:
             count = rendered.count("seminar-item")
             print(f"Found {count} 'seminar-item' elements in HTML.")
        else:
             print("ALERT: No 'seminar-item' found in HTML!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_render()
