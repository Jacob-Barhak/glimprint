import sqlite3
import json
from pathlib import Path

# Define DB Path relative to this script (glimprint/scripts/update_schema.py -> glimprint/db/glimprint.db)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "glimprint.db"

def update_schema():
    print(f"Updating schema for database at {DB_PATH}")
    
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- 0. News ---
    print("Checking 'news' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            slug TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            image_data BLOB,
            image_mime TEXT,
            body TEXT NOT NULL,
            related_links TEXT,
            approval_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 1. Seminars ---
    print("Checking 'seminars' table...")
    # Ensure table exists (basic schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seminars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            speaker TEXT NOT NULL,
            date TEXT NOT NULL,
            abstract TEXT NOT NULL,
            image_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add columns if missing
    columns = [
        ("location", "TEXT"),
        ("related_links", "TEXT"),
        ("start_datetime_utc", "TEXT"),
        ("affiliation", "TEXT"),
        ("end_datetime_utc", "TEXT") # Just in case
    ]
    
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(seminars)").fetchall()]
    
    for col_name, col_type in columns:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE seminars ADD COLUMN {col_name} {col_type}")
                print(f"  - Added column: {col_name}")
            except Exception as e:
                print(f"  - Error adding {col_name}: {e}")

    # Migrate 'link' to 'related_links' if exists
    if "link" in existing_cols:
        print("  - Migrating 'link' to 'related_links'...")
        rows = cursor.execute("SELECT id, link FROM seminars WHERE link IS NOT NULL AND link != ''").fetchall()
        for row in rows:
            # Check if related_links is empty to avoid overwriting? 
            # Current logic: append or overwrite? Let's check if empty.
            if "related_links" in existing_cols: # check row value
                 curr = cursor.execute("SELECT related_links FROM seminars WHERE id = ?", (row["id"],)).fetchone()
                 if not curr or not curr[0]:
                     links_json = json.dumps([{"title": "Registration / Link", "url": row["link"]}])
                     cursor.execute("UPDATE seminars SET related_links = ? WHERE id = ?", (links_json, row["id"]))
                     print(f"    - Migrated link for ID {row['id']}")

    # --- 2. Workshops ---
    print("Checking 'workshops' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workshops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            image_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Columns to check/add
    # Note: 'description' might have been 'details'
    w_cols = [row[1] for row in cursor.execute("PRAGMA table_info(workshops)").fetchall()]
    
    if "details" in w_cols and "description" not in w_cols:
        try:
            cursor.execute("ALTER TABLE workshops RENAME COLUMN details TO description")
            print("  - Renamed 'details' to 'description'")
            w_cols.append("description")
        except:
             pass

    if "external_link" in w_cols and "link" not in w_cols:
         try:
            cursor.execute("ALTER TABLE workshops RENAME COLUMN external_link TO link")
            print("  - Renamed 'external_link' to 'link'")
            w_cols.append("link")
         except:
             pass

    if "related_links" not in w_cols:
        cursor.execute("ALTER TABLE workshops ADD COLUMN related_links TEXT")
        print("  - Added column: related_links")
        
    if "description" not in w_cols:
         cursor.execute("ALTER TABLE workshops ADD COLUMN description TEXT")
         print("  - Added column: description")

    # Migrate link -> related_links
    if "link" in w_cols:
         print("  - Migrating 'link' to 'related_links'...")
         rows = cursor.execute("SELECT id, link FROM workshops WHERE link IS NOT NULL AND link != ''").fetchall()
         for row in rows:
             curr = cursor.execute("SELECT related_links FROM workshops WHERE id = ?", (row["id"],)).fetchone()
             if not curr or not curr[0]:
                 links_json = json.dumps([{"title": "Website", "url": row["link"]}])
                 cursor.execute("UPDATE workshops SET related_links = ? WHERE id = ?", (links_json, row["id"]))

    # --- 3. Publications ---
    print("Checking 'publications' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            year INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    p_cols = [row[1] for row in cursor.execute("PRAGMA table_info(publications)").fetchall()]
    
    if "journal" in p_cols and "description" not in p_cols:
        try:
             cursor.execute("ALTER TABLE publications RENAME COLUMN journal TO description")
             print("  - Renamed 'journal' to 'description'")
        except:
             pass

    p_cols = [row[1] for row in cursor.execute("PRAGMA table_info(publications)").fetchall()] # refresh
    
    if "description" not in p_cols:
        cursor.execute("ALTER TABLE publications ADD COLUMN description TEXT")
        print("  - Added column: description")

    if "link" not in p_cols:
        cursor.execute("ALTER TABLE publications ADD COLUMN link TEXT")
        print("  - Added column: link")

    # --- 4. Admins ---
    print("Checking 'admins' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT
        )
    ''')
    
    # --- 5. Contacts (Mailing) ---
    print("Checking 'contacts' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT,
            affiliation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c_cols = [row[1] for row in cursor.execute("PRAGMA table_info(contacts)").fetchall()]
    if "affiliation" not in c_cols:
        cursor.execute("ALTER TABLE contacts ADD COLUMN affiliation TEXT")
        print("  - Added column: affiliation")


    conn.commit()
    conn.close()
    print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
