import sqlite3
import re

DB_FILE = "app/content/glimprint.db"

def inspect_content():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT id, title, content FROM seminars LIMIT 5").fetchall()
    
    marker_start = 'InstanceBeginEditable name="maincontentarea"'
    marker_end = 'InstanceEndEditable'
    
    print(f"Checking {len(rows)} rows for markers...")
    
    for row in rows:
        content = row['content']
        print(f"\n--- ID: {row['id']} : {row['title']} ---")
        
        if marker_start in content:
            print(f"FOUND START MARKER")
            # Extract chunk
            try:
                start_idx = content.index(marker_start)
                end_idx = content.index(marker_end) if marker_end in content else len(content)
                chunk = content[start_idx:end_idx+len(marker_end)]
                print(f"CHUNK:\n{chunk[:500]} ...")
            except Exception as e:
                print(f"Error extracting chunk: {e}")
        else:
            print("MARKER NOT FOUND. Dumping first 500 chars:")
            print(content[:500])

    conn.close()

if __name__ == "__main__":
    inspect_content()
