import sqlite3
import re
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime
import pytz

DB_FILE = "app/content/glimprint.db"

def refine_seminars():
    conn = sqlite3.connect("app/content/glimprint.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT id, slug, title, content FROM seminars").fetchall()
    
    for row in rows:
        slug = row['slug']
        original_title = row['title']
        content_html = row['content']
        
        # 1. Clean Title and Extract Speaker
        speaker = None
        clean_title = original_title
        
        if "“" in original_title:
             parts = original_title.split("“", 1)
             if len(parts) == 2:
                 speaker_part = parts[0].strip()
                 title_part = parts[1].replace("”", "").strip()
                 if speaker_part.endswith(","): speaker_part = speaker_part[:-1].strip()
                 speaker = speaker_part
                 clean_title = title_part
        elif "\"" in original_title:
             parts = original_title.split("\"", 1)
             if len(parts) == 2:
                 speaker_part = parts[0].strip()
                 title_part = parts[1].replace("\"", "").strip()
                 if speaker_part.endswith(","): speaker_part = speaker_part[:-1].strip()
                 speaker = speaker_part
                 clean_title = title_part
        elif ":" in original_title:
             parts = original_title.split(":", 1)
             if len(parts) == 2:
                 if "Discussion" not in parts[0] and len(parts[0]) < 50:
                     speaker = parts[0].strip()
                     clean_title = parts[1].strip()
                 else:
                     clean_title = original_title
        elif " will discuss: " in original_title:
             parts = original_title.split(" will discuss: ", 1)
             if len(parts) == 2:
                  speaker = parts[0].strip()
                  clean_title = parts[1].strip()
        
        # 2. Extract content using User Markers or Fallback
        marker_pattern = re.compile(r'<!-- InstanceBeginEditable name="maincontentarea" -->(.*?)<!-- InstanceEndEditable -->', re.DOTALL)
        match = marker_pattern.search(content_html)
        
        target_html = ""
        if match:
            target_html = match.group(1)
        else:
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
        
        # --- DATE & TIME EXTRACTION ---
        iso_date = None
        time_str = ""
            
        # Extract Date: Look for "Thursday, February 5, 2026" pattern
        date_match = re.search(r'\w+,\s+\w+\s+\d{1,2},\s+\d{4}', full_text)
        date_str = date_match.group(0) if date_match else None
        
        # Extract Time: Look for "10:00 AM" or "2 PM" etc.
        # Regex for time like "10 AM", "2:00 pm EST", "10:00 AM (EST)", "10:00 AM US Eastern", "Noon"
        # Handling "Noon" specifically
        if "Noon" in full_text:
             time_str = "12:00 PM"
             # Try to find timezone after "Noon"
             # "Noon (US eastern)"
             tz_match = re.search(r'Noon\s*(\([A-Za-z\s]+\)|[A-Za-z]+)?', full_text, re.I)
             if tz_match and tz_match.group(1):
                 time_str += " " + tz_match.group(1).replace("(", "").replace(")", "")
        else:
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)\s*(?:[A-Z]{2,}|US [A-Za-z]+)?(?:\s*\(?[A-Z]{3}\)?)?)', full_text)
            if time_match:
                time_str = time_match.group(0)
            
        # Combine and ISO Format
        if date_str and time_str:
            try:
                full_dt_str = f"{date_str} {time_str}"
                # Tz mapping
                tz_map = {
                    "US Eastern": "US/Eastern", "EST": "US/Eastern", "EDT": "US/Eastern", "eastern": "US/Eastern",
                    "US Central": "US/Central", "CST": "US/Central", "CDT": "US/Central", "central": "US/Central",
                    "US Mountain": "US/Mountain", "MST": "US/Mountain", "MDT": "US/Mountain",
                    "US Pacific": "US/Pacific", "PST": "US/Pacific", "PDT": "US/Pacific"
                }
                
                tz_name = "US/Eastern" # Default
                for k, v in tz_map.items():
                    if k.lower() in time_str.lower():
                        tz_name = v
                        break
                
                dt = parser.parse(full_dt_str, fuzzy=True)
                if dt.tzinfo is None:
                    tz = pytz.timezone(tz_name)
                    dt = tz.localize(dt)
                
                iso_date = dt.isoformat()
            except Exception as e:
                print(f"  [Date Error] {e}")

        # Abstract
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) < 60 and (re.search(r'\d{4}', text) or re.search(r'AM|PM', text, re.I)):
                continue
            if speaker and text.startswith(speaker):
                continue
            if len(text) > 40:
                paragraphs.append(text)
        abstract_text = "\n\n".join(paragraphs)
        
        # Registration Link
        reg_link = ""
        for a in soup.find_all("a", href=True):
            href = a['href']
            text = a.get_text().lower()
            if "zoom.us" in href or "register" in text or "registration" in text:
                reg_link = href
                break
        
        print(f"Updating {slug} | Date: {iso_date}")
        cursor.execute('''
            UPDATE seminars 
            SET speaker = ?, title = ?, abstract = ?, date = ?, registration_link = ?
            WHERE slug = ?
        ''', (speaker, clean_title, abstract_text, iso_date, reg_link, slug))

    conn.commit()
    conn.close()
    print("Refinement complete.")

if __name__ == "__main__":
    refine_seminars()
