import sqlite3
from bs4 import BeautifulSoup
import re

DB_FILE = "app/content/glimprint.db"

def inspect():
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT slug, content FROM news LIMIT 1").fetchone()
    conn.close()
    
    if not row:
        print("No news found.")
        return

    slug, content = row
    print(f"Inspecting {slug}...")
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Check for body field
    body_div = soup.find(class_=re.compile("field--name-body"))
    if body_div:
        print("Found field--name-body!")
        print(f"Length: {len(str(body_div))}")
        print("Classes:", body_div.get("class"))
        print("Sample text:", body_div.get_text()[:100])
    else:
        print("field--name-body NOT found.")
        
    # Check for related links
    rel_fields = soup.find_all(class_=re.compile("field--name-field-related-links"))
    print(f"Found {len(rel_fields)} related link fields.")
    for rel in rel_fields:
        print(" - ", rel.encode('utf-8')[:200])
        
    # Check for "Submit Your Model" text
    if "Submit Your Model" in content:
        print("Found 'Submit Your Model' in content!")
        # Find parent
        found = soup.find(string=re.compile("Submit Your Model"))
        if found:
            print("Parent of text:", found.parent)
            try:
                print("Grandparent:", found.parent.parent)
            except: pass
        
    # Check what 'main' captured
    # The content stored in DB is str(main)
    # So soup IS main.
    print("Direct children of stored content:")
    for child in soup.recursiveChildGenerator():
        if child.name:
            print(f" - {child.name} (class: {child.get('class')}, id: {child.get('id')})")
            if child.name == 'div' and child.get('class') and 'field--name-body' in child.get('class'):
                break # Stop after finding body to avoid spam
                
if __name__ == "__main__":
    inspect()
