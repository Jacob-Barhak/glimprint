import sqlite3

DB_FILE = "app/content/glimprint.db"

def dump_one():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get just one
    row = cursor.execute("SELECT id, title, content FROM seminars LIMIT 1").fetchone()
    
    print(f"--- ID: {row['id']} : {row['title']} ---")
    print(row['content'])

    conn.close()

if __name__ == "__main__":
    dump_one()
