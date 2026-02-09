import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import json
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://cms-wip.unl.edu"
NEWS_URL = "https://cms-wip.unl.edu/ianr/biochemistry/global-alliance-for-immune-prediction-and-intervention/news/"
DB_FILE = "app/content/glimprint.db"

def get_existing_titles(cursor):
    titles = set()
    try:
        rows = cursor.execute("SELECT title FROM seminars").fetchall()
        for r in rows: titles.add(r[0].lower().strip())
        
        rows = cursor.execute("SELECT title FROM workshops").fetchall()
        for r in rows: titles.add(r[0].lower().strip())
    except Exception as e:
        print(f"Warning reading existing DB: {e}")
    return titles

def scrape_news():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get existing exclusions
    existing_titles = get_existing_titles(cursor)
    print(f"Loaded {len(existing_titles)} existing seminar/workshop titles to exclude.")
    
    # Scrape all pages
    page = 0
    unique_urls = []
    seen_urls = set()
    
    while True:
        url = f"{NEWS_URL}?page={page}"
        print(f"Scraping list page {page}: {url}")
        try:
            resp = requests.get(url, verify=False)
            if resp.status_code != 200:
                print("  End of pages or error.")
                break
                
            soup = BeautifulSoup(resp.content, "html.parser")
            main = soup.find(id="main-content") or soup.find(class_="block-system-main-block") or soup.find("main") or soup.body
            
            if not main:
                print("  Could not find main content container.")
                continue

            # Find news links
            # Usually in h3 > a
            found_on_page = 0
            articles = main.find_all("div", class_="views-row")
            if not articles:
                # Fallback: maybe they aren't in views-row?
                # Look for any link that has /news/ in href inside main
                print("  No views-row found, scanning all links...")
                articles = main.find_all("div") # Dummy iteration, we'll scan links below
                
                for link in main.find_all("a", href=True):
                     href = link['href']
                     if "/news/" in href and len(link.get_text(strip=True)) > 10:
                        # Found a likely news link
                        full_url = BASE_URL + href if href.startswith("/") else href
                        if full_url in seen_urls: continue
                        
                        title = link.get_text(strip=True)
                        if title.lower().strip() in existing_titles:
                             print(f"  Skipping existing: {title[:30]}...")
                             continue
                             
                        seen_urls.add(full_url)
                        unique_urls.append({"url": full_url, "title": title})
                        found_on_page += 1
            else:
                for article in articles:
                     link = article.find("a", href=True)
                     if not link: continue
                     
                     href = link['href']
                     full_url = BASE_URL + href if href.startswith("/") else href
                     
                     if "news" not in full_url: continue
                     
                     title = link.get_text(strip=True)
                     
                     # duplicate check
                     if full_url in seen_urls: continue
                     
                     # Exclusion check
                     if title.lower().strip() in existing_titles:
                         print(f"  Skipping existing seminar/workshop: {title[:30]}...")
                         continue
                     
                     seen_urls.add(full_url)
                     unique_urls.append({"url": full_url, "title": title})
                     found_on_page += 1
            
            if found_on_page == 0 and page > 0:
                break
                
            page += 1
            # Safety break
            if page > 10: break
            
        except Exception as e:
            print(f"Error scraping list: {e}")
            break

    print(f"Found {len(unique_urls)} unique news items to process.")
    
    # Process details
    for item in unique_urls:
        scrape_news_detail(cursor, item['url'], item['title'])
        conn.commit()
        
    conn.close()

def scrape_news_detail(cursor, url, title):
    slug = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
    print(f"Scraping {slug}...")
    
    try:
        resp = requests.get(url, verify=False)
        if resp.status_code != 200:
            print(f"  Failed: {resp.status_code}")
            return
            
        soup = BeautifulSoup(resp.content, "html.parser")
        main = soup.find(id="main-content") or soup.find(class_="block-system-main-block") or soup.body
        
        # Raw content
        content_raw = str(main)
        
        date_str = ""
        date_elem = main.find("time")
        if date_elem:
            date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
            
        if not date_str:
            # Fallback: look for p.dcf-txt-xs in main
            for p in main.find_all("p", class_="dcf-txt-xs"):
                txt = p.get_text(strip=True)
                if len(txt) > 5 and len(txt) < 30 and not txt.startswith("by ") and any(c.isdigit() for c in txt):
                    date_str = txt
                    break

        # Image
        image_data = None
        image_mime = None
        img_tag = None
        
        # Try finding field-image
        field_img = main.find(class_=re.compile("field--name-field-image"))
        if field_img:
            img_tag = field_img.find("img")
        
        if not img_tag:
            # Check for other images but avoid icons
            for img in main.find_all("img"):
                src = img.get("src")
                if src and ("styles" in src or "media" in src) and "icon" not in src:
                    img_tag = img
                    break
        
        if img_tag:
            src = img_tag.get("src")
            if src.startswith("/"): src = BASE_URL + src
            try:
                img_resp = requests.get(src, verify=False)
                if img_resp.status_code == 200:
                    image_data = img_resp.content
                    image_mime = img_resp.headers.get("Content-Type", "image/jpeg")
            except: pass

        # Body Content (Clean)
        # Target the node specifically
        # Try unlcms-article-body first (most specific to this site)
        article = main.find(class_="unlcms-article-body")
        if not article:
             article = main.find("article", class_="node--type-news")
        if not article:
             article = main
             
        # Create a copy to clean up
        import copy
        body_soup = copy.copy(article)
        
        # Try to find date in body if not found yet
        # usually in a p.dcf-txt-xs that is NOT "by ..."
        if not date_str:
            for p in body_soup.find_all("p", class_="dcf-txt-xs"):
                txt = p.get_text(strip=True)
                if len(txt) > 5 and len(txt) < 30 and not txt.startswith("by ") and any(c.isdigit() for c in txt):
                    date_str = txt
                    break
        
        # Remove Unwanted Elements
        for trash in body_soup.find_all(
            ["footer", "script", "noscript", "style", "iframe", "svg", "header"] + 
            [re.compile("^h1")] # Remove main title as we have it separately
        ):
            trash.decompose()
            
        # Remove specific Drupal/UNL blocks
        for trash in body_soup.find_all(id=re.compile("relatedlinks|footer|contactinfo|dcf-noscript")):
            trash.decompose()
            
        for trash in body_soup.find_all(class_=re.compile(
            "field--name-field-related-links|field--name-field-image|dcf-footer|unl-footer|back-link|field--name-created|field--name-uid|field--name-title|dcf-txt-xs|unlcms-article-share"
        )):
            trash.decompose()
            
        # Extract content
        # Check if there is a specific body field now
        body_field = body_soup.find(class_=re.compile("field--name-body"))
        if body_field:
            body = str(body_field)
        else:
            # Check if we have unlcms-article-body directly
            # The structure is unlcms-article-body > div > div > p...
            # If we selected unlcms-article-body, we might want to just output its children?
            if "unlcms-article-body" in str(article.get("class", [])):
                 # Get inner content
                 body = body_soup.decode_contents()
            else:
                 # Fallback: get all remaining children that are valid content
                 # Filters out empty divs
                 content_parts = []
                 for child in body_soup.find_all(["p", "ul", "ol", "div", "blockquote", "h2", "h3", "h4", "h5", "h6"], recursive=False):
                      if child.name == 'div' and not child.get_text(strip=True): continue
                      # Check if div contains only ignored stuff
                      # Check if the child *is* part of a known ignored container class
                      if child.get("id") == "dcf-noscript": continue 
                      
                      content_parts.append(str(child))
                 
                 if content_parts:
                     body = "\n".join(content_parts)
                 else:
                      # Last resort: just text
                      body = body_soup.encode_contents().decode('utf-8')
        
        # Clean up empty tags and excessive newlines
        body = re.sub(r'<div[^>]*>\s*</div>', '', body)
        body = re.sub(r'\s+id="[^"]*"', '', body) # Remove IDs to be clean? Maybe not.
        body = body.strip()

        # Related Links (Re-extract from original main to be safe)
        links_list = []
        # Check for field--name-field-related-links in main FIRST
        rel_links = main.find(class_=re.compile("field--name-field-related-links"))
        
        # If not found in main, try searching global soup for that specific class
        # (It might be in a sidebar region outside main)
        if not rel_links:
             rel_links = soup.find(class_=re.compile("field--name-field-related-links"))

        if rel_links:
            for a in rel_links.find_all("a", href=True):
                links_list.append({"text": a.get_text(strip=True), "url": a['href']})
        
        # Fallback: Look for "Related Links" header
        if not links_list:
            headers = soup.find_all(re.compile("^h[2-6]"), string=re.compile("Related Links", re.I))
            for h in headers:
                # Look at next siblings for a list
                curr = h.next_sibling
                while curr:
                    if curr.name in ['ul', 'ol', 'div']:
                        for a in curr.find_all("a", href=True):
                            links_list.append({"text": a.get_text(strip=True), "url": a['href']})
                        break # Found the list
                    curr = curr.next_sibling
                    if curr and curr.name and curr.name.startswith("h"): break # Hit next header

        
        # Also check block-unl-five-herbie-relatedlinks (Sidebar)
        # Search widely if not found yet
        extra_links = soup.find(id="block-unl-five-herbie-relatedlinks")
        if extra_links:
             for a in extra_links.find_all("a", href=True):
                 # Filter out common UNL footer links if they appear here?
                 # Usually these are "Office of Chancellor" etc. content specific?
                 # User said "without links associated withe durpal and university of Nebrasca"
                 # These sound like generic links.
                 href = a['href']
                 text = a.get_text(strip=True).lower()
                 if "unl.edu" in href and ("chancellor" in text or "communication" in text or "directory" in text):
                     continue
                 
                 # Check if we already have this link
                 if any(l['url'] == href for l in links_list): continue
                 
                 links_list.append({"text": a.get_text(strip=True), "url": href})

        # Save
        cursor.execute("INSERT OR REPLACE INTO news (slug, title, date, image_data, image_mime, body, content, related_links) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (slug, title, date_str, image_data, image_mime, body, content_raw, json.dumps(links_list)))
        print(f"  Saved {title[:20]}... | Date: {date_str} | Body: {len(body)} | Links: {len(links_list)}")
        
    except Exception as e:
        print(f"  Error scraping {slug}: {e}")

if __name__ == "__main__":
    scrape_news()
