import sqlite3

DB_FILE = "app/content/glimprint.db"

def check_title():
    # We need to get the ORIGINAL title, but verify_refinement showed the UPDATED title.
    # Since I updated the DB in place, the original might be lost if I overwrote it.
    # checking what is currently in the DB.
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    row = cursor.execute("SELECT id, title FROM seminars WHERE id=1").fetchone()
    print(f"Current Title (ID 1): '{row['title']}'")
    
    # Check ID 3
    row3 = cursor.execute("SELECT id, title FROM seminars WHERE id=3").fetchone()
    print(f"Current Title (ID 3): '{row3['title']}'")

    conn.close()

if __name__ == "__main__":
    check_title()
