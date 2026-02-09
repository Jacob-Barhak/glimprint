import sqlite3
import re
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime
import pytz

DB_FILE = "app/content/glimprint.db"

def refine_workshops():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Cleanup known garbage
    print("Cleaning up non-workshop entries...")
    garbage_slugs = [
        'home', 'about-us', 'contact-us', 'submit-glimprint-news', 
        'people', 'search', 'user', 'semiramis', 'news', 
        'immune-systems-models', 'publications', 'membership', 'members',
        'activities', 'seminars', 'modeling-cell-cell-interactions', 
        'multiscale-modeling-immunity', 'resources', 'global-alliance-for-immune-prediction-and-intervention'
    ]
    formatted_slugs = [s for s in garbage_slugs]
    # Also clear anything ending in -0 or matching generic names if needed
    for slug in formatted_slugs:
        cursor.execute("DELETE FROM workshops WHERE slug = ?", (slug,))
        cursor.execute("DELETE FROM workshops WHERE slug LIKE ?", (f"{slug}-%",))
    
    conn.commit()
    
    rows = cursor.execute("SELECT id, slug, title, content, details FROM workshops").fetchall()
    print(f"Refining {len(rows)} workshops...")
    
    for row in rows:
        slug = row['slug']
        title = row['title']
        content = row['content'] # This is the full HTML
        
        # Parse content
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(" ", strip=True)
        
        start_date = None
        end_date = None
        location = ""
        
        # --- Date Extraction ---
        # Look for date patterns in Title or Text
        # Format examples:
        # "July 28th to August 10th, 2025"
        # "14-16th October 2025"
        # "September 30 - October 2, 2024"
        # "October 2025"
        
        # cleanup text for regex
        # Remove "th", "st", "nd", "rd" from dates to help parser? 
        # Actually dateutil.parser matches fuzzy.
        
        # Heuristic: Find year first?
        # Let's try to find a date range string.
        
        date_range_str = ""
        
        # Pattern 1: Month DD-DD, YYYY
        # Pattern 2: Month DD - Month DD, YYYY
        # Pattern 3: Month DD, YYYY
        
        # Helper Regexes
        months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        
        # 1. "September 30 - October 2, 2024"
        # 2. "July 28th to August 10th, 2025"
        range_pattern_1 = re.compile(rf"({months})\s+(\d{{1,2}}(?:st|nd|rd|th)?)\s*(?:-|to|–)\s*({months})\s+(\d{{1,2}}(?:st|nd|rd|th)?),?\s+(\d{{4}})", re.IGNORECASE)
        
        # 3. "14-16th October 2025" or "14-16 October 2025"
        range_pattern_2 = re.compile(rf"(\d{{1,2}}(?:st|nd|rd|th)?)\s*(?:-|to|–)\s*(\d{{1,2}}(?:st|nd|rd|th)?)\s+({months})\s+(\d{{4}})", re.IGNORECASE)
        
        # 4. "October 14, 2025"
        single_pattern = re.compile(rf"({months})\s+(\d{{1,2}}(?:st|nd|rd|th)?),?\s+(\d{{4}})", re.IGNORECASE)

        # Check Title then Text
        check_text = title + " " + text
        
        m1 = range_pattern_1.search(check_text)
        m2 = range_pattern_2.search(check_text)
        m3 = single_pattern.search(check_text)
        
        if m1:
            # Month1 Day1 - Month2 Day2, Year
            # Groups: 1=M1, 2=D1, 3=M2, 4=D2, 5=Year
            m1_txt, d1_txt, m2_txt, d2_txt, y_txt = m1.groups()
            d1_clean = re.sub(r"\D", "", d1_txt)
            d2_clean = re.sub(r"\D", "", d2_txt)
            start_str = f"{m1_txt} {d1_clean}, {y_txt}"
            end_str = f"{m2_txt} {d2_clean}, {y_txt}"
            try:
                start_date = parser.parse(start_str).isoformat()
                end_date = parser.parse(end_str).isoformat()
            except: pass
            
        elif m2:
            # Day1 - Day2 Month, Year
            # Groups: 1=D1, 2=D2, 3=Month, 4=Year
            d1_txt, d2_txt, m_txt, y_txt = m2.groups()
            d1_clean = re.sub(r"\D", "", d1_txt)
            d2_clean = re.sub(r"\D", "", d2_txt)
            start_str = f"{m_txt} {d1_clean}, {y_txt}"
            end_str = f"{m_txt} {d2_clean}, {y_txt}"
            try:
                start_date = parser.parse(start_str).isoformat()
                end_date = parser.parse(end_str).isoformat()
            except: pass
            
        elif m3:
            # Month Day, Year
            m_txt, d_txt, y_txt = m3.groups()
            d_clean = re.sub(r"\D", "", d_txt)
            start_str = f"{m_txt} {d_clean}, {y_txt}"
            try:
                start_date = parser.parse(start_str).isoformat()
                end_date = start_date
            except: pass
            
        # Fallback: specific fix for "2-Day Kinetic Modeling" which might not have date in text clearly?
        # If no date found, check if it's the "2-Day Kinetic Modeling" one which seemed to fail
        # Actually that one has "Virtual" and might not have a year in the title.
        
        # Clean up locations
        loc_match = re.search(r"(?:in|at)\s+([A-Z][a-zA-Z\s,]+(?:University|Center|Institute|Hotel|Conference|School|France|Germany|USA|Canada|UK|Kingdom))", text)
        if loc_match:
             location = loc_match.group(1).strip()
        if "Online" in text or "Virtual" in title:
             if not location: location = "Online"

        # Update
        print(f"Updating {slug}: {start_date} | {location}")
        cursor.execute("UPDATE workshops SET start_date=?, end_date=?, location=? WHERE id=?", (start_date, end_date, location, row['id']))
        
        # --- Details Extraction ---
        # Extract content between markers
        marker_pattern = re.compile(r'<!-- InstanceBeginEditable name="maincontentarea" -->(.*?)<!-- InstanceEndEditable -->', re.DOTALL)
        match = marker_pattern.search(content)
        
        details_html = ""
        if match:
            raw_details = match.group(1)
            d_soup = BeautifulSoup(raw_details, "html.parser")
            
            # Clean up
            # Remove H1 (Title)
            for h1 in d_soup.find_all("h1"):
                h1.decompose()
            
            # Remove Images (already stored/displayed separately)
            for img in d_soup.find_all("img"):
                img.decompose()
                
            # Remove "Related links" block if present inside
            for div in d_soup.find_all("div", id="block-unl-five-herbie-relatedlinks"):
                div.decompose()

            # Remove Date Block (dcf-txt-sm dcf-clearfix ...)
            # Use select or find_all with exact class match or partial
            for div in d_soup.find_all("div", class_="dcf-txt-sm"):
                div.decompose()
            
            # Remove Location/Subhead blocks
            for div in d_soup.find_all("div", class_="dcf-subhead"):
                 div.decompose()
            
            # Remove empty dcf-subhead?
            # Sometimes class is just "dcf-subhead"
            
            # Remove "Additional Information" block if it exists
            # It's usually a span or div with text "Additional Information:" followed by a div
            for span in d_soup.find_all("span", class_="dcf-subhead"):
                if "Additional Information" in span.get_text():
                    span.decompose()
            
            # Remove the div following it? Hard to target without next_sibling logic which is brittle.
            # But the "Additional Information" link is also technically redundant if we have it in external_link.
            # Let's see if we can just remove the specific container.
            
            details_html = str(d_soup).strip()
        else:
            # Fallback if marker not found (shouldn't happen based on user input, but safe)
            details_html = row['details'] # Keep existing or use full content cleaned

        # Update
        print(f"Updating {slug}: {start_date} | {location}")
        cursor.execute("UPDATE workshops SET start_date=?, end_date=?, location=?, details=? WHERE id=?", (start_date, end_date, location, details_html, row['id']))
        
        # Cleanup garbage that might have persisted?
        # history-glimprint, glimprint-runnable-model-page
        if slug in ['history-glimprint', 'glimprint-runnable-model-page']:
             cursor.execute("DELETE FROM workshops WHERE id=?", (row['id'],))


    conn.commit()
    conn.close()
    print("Workshops refined.")

if __name__ == "__main__":
    refine_workshops()
