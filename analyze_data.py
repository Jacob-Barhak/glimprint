import sqlite3
import re

DB_FILE = "app/content/glimprint.db"
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

rows = cursor.execute("SELECT id, title, content FROM seminars").fetchall()

print(f"Total rows: {len(rows)}")

for row in rows[:5]:
    print(f"--- ID: {row['id']} ---")
    print(f"ORIGINAL TITLE: {row['title']}")
    print(f"CONTENT START: {row['content'][:200]}...")
    print("-" * 20)

conn.close()
