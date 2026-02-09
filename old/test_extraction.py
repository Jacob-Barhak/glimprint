import sqlite3
import re
from bs4 import BeautifulSoup

DB_FILE = "app/content/glimprint.db"

def test_extraction():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Let's check the first few rows
    rows = cursor.execute("SELECT id, title, content FROM seminars LIMIT 5").fetchall()
    
    for row in rows:
        print(f"\n=== ID {row['id']} : {row['title']} ===")
        content = row['content']
        
        # Strategy 1: User Hint (InstanceBeginEditable)
        # Using regex to capture content between markers
        marker_pattern = re.compile(r'<!-- InstanceBeginEditable name="maincontentarea" -->(.*?)<!-- InstanceEndEditable -->', re.DOTALL)
        match = marker_pattern.search(content)
        
        target_html = ""
        if match:
            print("[✓] Found User Marker")
            target_html = match.group(1)
        else:
            print("[x] User Marker NOT found. Trying fallback...")
            # Fallback: finding the main content div
            soup = BeautifulSoup(content, "html.parser")
            
            # Try specific drupal fields
            # field-name-body contains the abstract usually
            body_field = soup.find(class_="field-name-body")
            if body_field:
                 print("[✓] Found .field-name-body")
                 target_html = str(body_field)
            else:
                 # Try region-content
                 region = soup.find(class_="region-content")
                 if region:
                     print("[✓] Found .region-content")
                     target_html = str(region)
                 else:
                     print("[!] No standard content container found. Using raw body.")
                     target_html = str(soup.body) if soup.body else content

        # Now parse the target_html
        soup = BeautifulSoup(target_html, "html.parser")
        
        # Clean up
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # 1. Extract Abstract (Paragraphs)
        # Usually the first few <p> tags are the abstract.
        # But sometimes Time/Location are in <p> tags too.
        
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        # Filter out empty or "metadata" looking paragraphs (simple heuristic)
        abstract_paragraphs = []
        time_found = ""
        
        for p in paragraphs:
            # Check for Time
            # Regex for time like "10 AM", "2:00 pm EST"
            if re.search(r'\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)', p) and len(p) < 100:
                print(f"  [Time Candidate]: {p}")
                if not time_found: time_found = p
            # Check for generic "Date" if strictly looking for that
            # Check for typical abstract content (longer text)
            elif len(p) > 50:
                 abstract_paragraphs.append(p)
        
        abstract_text = "\n\n".join(abstract_paragraphs)
        print(f"  [Abstract Preview]: {abstract_text[:150]}..." if abstract_text else "  [No Abstract Found]")
        
        # 2. Registration Link
        # Search distinct link texts
        reg_link = ""
        for a in soup.find_all("a", href=True):
            text = a.get_text().lower()
            href = a['href']
            if "zoom.us" in href or "register" in text or "registration" in text:
                print(f"  [Link Candidate]: {text} -> {href}")
                reg_link = href
                break

    conn.close()

if __name__ == "__main__":
    test_extraction()
