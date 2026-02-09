import sqlite3
import re
from bs4 import BeautifulSoup
from datetime import datetime
import dateutil.parser
import pytz

DB_FILE = "app/content/glimprint.db"

def test_date_extraction():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT id, title, content FROM seminars LIMIT 5").fetchall()
    
    print(f"Checking {len(rows)} rows for dates...")
    
    for row in rows:
        print(f"\n--- ID: {row['id']} ---")
        content = row['content']
        soup = BeautifulSoup(content, "html.parser")
        
        # Strategy: Look for the date line. 
        # In the dump: <div class="dcf-float-left dcf-d-inline"><div>Thursday, February 5, 2026</div></div>
        
        date_str = ""
        # Try finding the specific container
        # The structure seems to be: 
        # <div class="dcf-txt-sm dcf-clearfix dcf-mt-4 dcf-mb-4">
        #   <div class="dcf-float-left dcf-d-inline"><div>DATE</div></div>
        #   ...
        #   <div class="dcf-float-left dcf-d-inline"><div>TIME</div></div>
        # </div>
        
        meta_divs = soup.find_all(class_="dcf-float-left")
        for div in meta_divs:
            text = div.get_text(" ", strip=True)
            # Check if it looks like a date
            # Regex for "Day, Month DD, YYYY"
            if re.search(r'\w+,\s+\w+\s+\d{1,2},\s+\d{4}', text):
                print(f"  [Date Candidate]: {text}")
                date_str = text
                break
        
        # Time extraction (we already have this logic, but need to combine)
        time_str = ""
        # Searching the text again or using previously extracted logic
        # For this test, just finding it in the same meta block
        for div in meta_divs:
             text = div.get_text(" ", strip=True)
             if re.search(r'\d{1,2}:\d{2}\s*(?:AM|PM)', text):
                 print(f"  [Time Candidate]: {text}")
                 time_str = text
                 break
                 
        if date_str and time_str:
            # Combine and parse
            full_str = f"{date_str} {time_str}"
            try:
                # Cleaning up "US Eastern" etc from time string if present for parser, 
                # but dateutil is usually smart.
                # However, timezones need care.
                # "10:00 AM US Eastern" -> "10:00 AM" and "US Eastern"
                
                # Normalize timezone names for dateutil or pytz
                tz_map = {
                    "US Eastern": "US/Eastern",
                    "EST": "US/Eastern",
                    "EDT": "US/Eastern",
                    "CST": "US/Central",
                    "CDT": "US/Central",
                    "US Central": "US/Central",
                    "Mountain": "US/Mountain",
                    "Pacific": "US/Pacific"
                }
                
                # Check for TZ in time_str
                tz_name = "US/Eastern" # Default if not found? Or assume content implies it?
                # The text says "US Eastern"
                for key in tz_map:
                    if key in time_str:
                        tz_name = tz_map[key]
                        # Remove the timezone part from string to let parser handle the rest clearly?
                        # actually dateutil might just ignore it or parse it if standard.
                        break
                
                dt = dateutil.parser.parse(full_str, fuzzy=True)
                
                # Set timezone
                tz = pytz.timezone(tz_name)
                dt = tz.localize(dt) if dt.tzinfo is None else dt
                
                print(f"  [ISO Format]: {dt.isoformat()}")
            except Exception as e:
                print(f"  [Parse Error]: {e}")

    conn.close()

if __name__ == "__main__":
    test_date_extraction()
