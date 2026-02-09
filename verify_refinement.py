import sqlite3

DB_FILE = "app/content/glimprint.db"

def verify_refinement():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT id, title, abstract, time, registration_link FROM seminars LIMIT 5").fetchall()
    
    print(f"Checking {len(rows)} rows...")
    
    for row in rows:
        print(f"\n--- ID: {row['id']} : {row['title']} ---")
        print(f"ABSTRACT: {row['abstract'][:200]}..." if row['abstract'] else "ABSTRACT: [EMPTY]")
        print(f"TIME: {row['time']}" if row['time'] else "TIME: [EMPTY]")
        print(f"LINK: {row['registration_link']}" if row['registration_link'] else "LINK: [EMPTY]")

    conn.close()

if __name__ == "__main__":
    verify_refinement()
