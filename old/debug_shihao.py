import sqlite3
import re
from bs4 import BeautifulSoup

def debug_shihao():
    conn = sqlite3.connect("app/content/glimprint.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    slug = "shihao-yang-georgia-institute-technology-big-data-infectious-disease-estimation-flu-covid-19"
    row = cursor.execute("SELECT content FROM seminars WHERE slug=?", (slug,)).fetchone()
    
    if not row:
        print("Row not found")
        return

    content_html = row['content']
    
    # 2. Extract content using User Markers or Fallback
    marker_pattern = re.compile(r'<!-- InstanceBeginEditable name="maincontentarea" -->(.*?)<!-- InstanceEndEditable -->', re.DOTALL)
    match = marker_pattern.search(content_html)
    
    target_html = ""
    if match:
        target_html = match.group(1)
        print("Found Marker Content")
    else:
        print("Marker NOT Found")
        # Reuse fallback logic from refine_seminars just in case
        soup = BeautifulSoup(content_html, "html.parser")
        body_field = soup.find(class_="field-name-body")
        if body_field:
             target_html = str(body_field)
        else:
             target_html = list(soup.body.children) if soup.body else content_html
             target_html = "".join([str(x) for x in target_html])

    soup = BeautifulSoup(target_html, "html.parser")
    
    # Cleanup
    for tag in soup.find_all(['h1', 'h2', 'script', 'style']):
        tag.decompose()
        
    full_text = soup.get_text(" ", strip=True)
    print(f"Full Text Length: {len(full_text)}")
    print(f"Full Text Snippet: {full_text[:500]}")
    
    # Test Regex
    regex = r'\w+,\s+\w+\s+\d{1,2},\s+\d{4}'
    match = re.search(regex, full_text)
    if match:
        print(f"MATCH: {match.group(0)}")
    else:
        print("NO MATCH")
        # Try to find what it actually looks like manually in the printed snippet

if __name__ == "__main__":
    debug_shihao()
