import sqlite3
import json
import os

JSON_FILE = "app/content/seminars.json"
DB_FILE = "app/content/glimprint.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS seminars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            link TEXT,
            content TEXT,
            image_data BLOB,
            image_mime TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    return conn

def migrate():
    if not os.path.exists(JSON_FILE):
        print(f"JSON file {JSON_FILE} not found.")
        return

    with open(JSON_FILE, "r") as f:
        seminars = json.load(f)

    conn = init_db()
    c = conn.cursor()

    for s in seminars:
        slug = s.get("id")
        title = s.get("title")
        link = s.get("link")
        content = s.get("content")
        image_path = s.get("image")
        
        image_data = None
        image_mime = None
        
        if image_path:
            # image_path in json is like "/static/images/seminars/File.jpg"
            # We need to map it to "app/static/images/seminars/File.jpg"
            # Since the script runs from root, and app is in root.
            
            # Remove leading slash if present
            if image_path.startswith("/"):
                rel_path = "app" + image_path 
            else:
                 rel_path = "app/" + image_path
                 
            if os.path.exists(rel_path):
                try:
                    with open(rel_path, "rb") as f:
                        image_data = f.read()
                    
                    ext = os.path.splitext(rel_path)[1].lower()
                    if ext in [".jpg", ".jpeg"]:
                        image_mime = "image/jpeg"
                    elif ext == ".png":
                        image_mime = "image/png"
                    elif ext == ".gif":
                        image_mime = "image/gif"
                    else:
                        image_mime = "application/octet-stream"
                except Exception as e:
                    print(f"Error reading image {rel_path}: {e}")
            else:
                print(f"Image not found: {rel_path}")

        try:
            c.execute('''
                INSERT OR REPLACE INTO seminars (slug, title, link, content, image_data, image_mime, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (slug, title, link, content, image_data, image_mime, ""))
            print(f"Inserted: {title}")
        except sqlite3.Error as e:
            print(f"Error inserting {slug}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
