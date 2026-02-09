import sqlite3
import os

DB_FILE = "app/content/glimprint.db"

if not os.path.exists(DB_FILE):
    print(f"Database {DB_FILE} does not exist!")
    exit(1)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Check seminars count
cursor.execute("SELECT COUNT(*) FROM seminars")
count = cursor.fetchone()[0]
print(f"Total seminars: {count}")

# Check one seminar with image
cursor.execute("SELECT slug, title, length(image_data) FROM seminars WHERE image_data IS NOT NULL LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"Sample seminar with image: {row[0]}, Title: {row[1]}, Image Size: {row[2]} bytes")
else:
    print("No seminars with images found!")

conn.close()
