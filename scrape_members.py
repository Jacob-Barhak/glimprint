import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import re
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://cms-wip.unl.edu/ianr/biochemistry/global-alliance-for-immune-prediction-and-intervention/members/"
DB_FILE = "app/content/glimprint.db"

def scrape_members():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Clean table? 
    # cursor.execute("DELETE FROM members")
    # conn.commit()
    # Or just use INSERT OR IGNORE / UPDATE logic.
    # User said "Make the members page... extract... creating a database table"
    # I'll clear and refill to ensure freshness.
    cursor.execute("DELETE FROM members")
    conn.commit()

    print(f"Scraping members list: {BASE_URL}")
    try:
        response = requests.get(BASE_URL, verify=False)
        if response.status_code != 200:
            print(f"Failed to fetch list: {response.status_code}")
            return

        soup = BeautifulSoup(response.content, "html.parser")
        main_content = soup.find(id="main-content") or soup.find(class_="block-system-main-block") or soup.body
        
        # Structure seems to be a list of views-rows or similar div structure.
        # Based on markdown view:
        # [Frederick R. Adler](url)
        # Professor...
        # Email: ...
        
        # Let's find all links to /person/ or similar
        # But specifically those in the content area.
        
        links = main_content.find_all("a", href=True)
        # Preserve order from page
        unique_urls = []
        seen = set()
        
        for link in links:
            href = link['href']
            if "/person/" in href:
                full_url = "https://cms-wip.unl.edu" + href if href.startswith("/") else href
                if full_url not in seen:
                    seen.add(full_url)
                    unique_urls.append(full_url)
                
        print(f"Found {len(unique_urls)} unique member profiles.")
        
        for i, url in enumerate(unique_urls):
            scrape_member_detail(cursor, url, i)
            conn.commit()

    except Exception as e:
        print(f"Error scraping list: {e}")
    
    conn.close()

def scrape_member_detail(cursor, url, sort_order=0):
    slug = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
    print(f"Scraping {slug}...")
    
    try:
        resp = requests.get(url, verify=False)
        if resp.status_code != 200:
            print(f"  Failed: {resp.status_code}")
            return
            
        soup = BeautifulSoup(resp.content, "html.parser")
        main = soup.find(id="main-content") or soup.body
        
        # Name (H1)
        name = soup.find("h1").get_text(strip=True) if soup.find("h1") else slug
        
        # Email
        email = ""
        field_email = main.find(class_=re.compile("field--name-field-email"))
        if field_email:
             # Protected email or mailto link
             mailto = field_email.find("a", href=re.compile(r"^mailto:"))
             if mailto:
                 email = mailto.get("href").replace("mailto:", "").strip()
             else:
                 email = field_email.get_text(strip=True)
                 
        if not email:
            # Fallback scan for mailto
            mailto = main.find("a", href=re.compile(r"^mailto:"))
            if mailto:
                email = mailto.get("href").replace("mailto:", "").strip()

        # Image
        image_data = None
        image_mime = None
        
        # Drupal often puts person image in a specific field-image div
        img_tag = None
        field_img = main.find(class_=re.compile("field--name-field-image"))
        if field_img:
            img_tag = field_img.find("img")
            
        if not img_tag:
            # Try to find a profile-looking image (not logo)
            for img in main.find_all("img"):
                 src = img.get("src")
                 if src and ("person" in src or "styles/numeric" in src or "media/image" in src):
                     if "icon" in src: continue
                     img_tag = img
                     break
        
        if img_tag:
            src = img_tag.get("src")
            if not src.startswith("http"):
                src = "https://cms-wip.unl.edu" + src if src.startswith("/") else "https://cms-wip.unl.edu/" + src
            
            try:
                img_resp = requests.get(src, verify=False)
                if img_resp.status_code == 200:
                    image_data = img_resp.content
                    image_mime = img_resp.headers.get("Content-Type", "image/jpeg")
            except: pass

        # Content
        content = str(main)

        # Helper
        def get_field_text(s, class_pattern):
            f = s.find(class_=re.compile(class_pattern))
            if f:
                lbl = f.find(class_=re.compile("label"))
                if lbl: lbl.decompose()
                # Return HTML if it's body or education to keep formatting?
                # User asked for text but education often has list items.
                # Let's keep HTML for education/statement.
                return str(f) 
            return ""
            
        # Affiliation
        affiliation_div = main.find(class_=re.compile(r"field--name-field-(professional-)?title"))
        affiliation = affiliation_div.get_text(" ", strip=True) if affiliation_div else ""
        if affiliation_div and affiliation_div.find(class_="label"):
             # Remove label "Title"
             lbl = affiliation_div.find(class_="label")
             if lbl: 
                 affiliation = affiliation.replace(lbl.get_text(strip=True), "").strip()

        # Parsing Logic for Body/Statement & Education
        statement = ""
        education = ""
        
        # 1. Try Specific Fields
        stmt_div = main.find(class_=re.compile(r"field--name-body"))
        if stmt_div: statement = str(stmt_div)
        
        edu_div = main.find(class_=re.compile(r"field--name-field-education"))
        if edu_div: education = str(edu_div)
        
        # 2. Heuristic Parsing if Fields Missing
        if not education and not statement:
            # Look for Headers
            # Clean soup
            soup_clean = BeautifulSoup(str(main), "html.parser")
            if soup_clean.find("h1"): soup_clean.find("h1").decompose() # Remove name
            
            # Find Education Header
            edu_header = soup_clean.find(lambda t: t.name in ['h2', 'h3'] and "Education" in t.get_text())
            
            if edu_header:
                print(f"    Found Education Header: {edu_header.name}")
                # Education is everything after until next header
                edu_parts = []
                for sib in edu_header.next_siblings:
                    if sib.name in ['h2', 'h3', 'div'] and ("Contact" in sib.get_text() or "Related" in sib.get_text()):
                        break
                    edu_parts.append(str(sib))
                education = "".join(edu_parts)
                
                # Statement is content BEFORE Education (and after Contact if present)
                parent = edu_header.parent
                bio_parts = []
                
                for child in parent.children:
                    if child == edu_header: 
                        break # Stop at Education
                    
                    # exclude contact block if identifiable?
                    if child.name in ['div'] and ("contact" in str(child).lower() or "field--name-field-email" in str(child)):
                        continue
                    if child.name in ['h2'] and "Contact" in child.get_text():
                        continue
                        
                    # Add to bio
                    if child.name: # Skip empty strings/newlines
                        text = child.get_text(strip=True)
                        if len(text) > 3 and "email" not in text.lower():
                             bio_parts.append(str(child))
                statement = "".join(bio_parts)
            else:
                # No Education Header found.
                # Fallback: Content after "Contact" header until Footer
                contact_header = soup_clean.find(lambda t: t.name in ['h2', 'h3'] and "Contact" in t.get_text() and "Contact us" not in t.get_text())
                 
                if contact_header:
                    bio_parts = []
                    # Content after contact header
                    for sib in contact_header.next_siblings:
                        if not sib.name and not sib.strip(): continue
                        if sib.name in ['h2', 'h3', 'div'] and ("Contact us" in sib.get_text() or "Related" in sib.get_text()): break
                        if sib.name == 'address': continue
                        
                        text = sib.get_text(strip=True)
                        if len(text) < 5: continue
                        if "email" in text.lower() and "@" in text: continue
                        
                        bio_parts.append(str(sib))
                    
                    # If nothing found, try parent's siblings (wrapper case)
                    if not bio_parts and contact_header.parent:
                         parent = contact_header.parent
                         for sib in parent.next_siblings:
                              if not sib.name and not sib.strip(): continue
                              if sib.name in ['h2', 'h3', 'div'] and ("Contact us" in sib.get_text() or "Related" in sib.get_text()): break
                                  
                              text = sib.get_text(strip=True)
                              if len(text) < 5: continue
                              if "email" in text.lower() and "@" in text: continue # redundancy check
                              
                              bio_parts.append(str(sib))

                    statement = "".join(bio_parts)

        # Links - Refined
        links_list = []
        
        # Look for explicit link fields: field--name-field-website or similar
        web_field = main.find(class_=re.compile(r"field--name-field-(website|lab-url)"))
        if web_field:
            for a in web_field.find_all("a", href=True):
                links_list.append({"text": a.get_text(strip=True) or "Website", "url": a['href']})
        
        # Fallback Links if empty
        if not links_list:
            all_links = main.find_all("a", href=True)
            for l in all_links:
                href = l['href']
                text = l.get_text(strip=True)
                if "mailto:" in href: continue
                if href == url: continue # self link
                if "unl.edu" in href and "cms-wip" in href: continue # internal nav
                
                # Simple heuristic for personal profiles
                if "lab" in text.lower() or "website" in text.lower() or "google" in href or "scholar" in href:
                    links_list.append({"text": text, "url": href})

        cursor.execute("INSERT OR REPLACE INTO members (slug, name, affiliation, email, statement, education, links, image_data, image_mime, content, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (slug, name, affiliation, email, statement, education, json.dumps(links_list), image_data, image_mime, content, sort_order))
        print(f"  Saved {name} | Bio: {len(statement)} | Edu: {len(education)} | Order: {sort_order}")

    except Exception as e:
        print(f"  Error scraping {slug}: {e}")

if __name__ == "__main__":
    scrape_members()
