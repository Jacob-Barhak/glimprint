import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://cms-wip.unl.edu/ianr/biochemistry/global-alliance-for-immune-prediction-and-intervention/workshops/"
DB_FILE = "app/content/glimprint.db"

def scrape_workshops():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ensure table exists (redundant if already run, but safe)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workshops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE,
            title TEXT,
            content TEXT,
            image_data BLOB,
            image_mime TEXT,
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            external_link TEXT,
            details TEXT
        )
    ''')
    conn.commit()

    print(f"Scraping workshops list: {BASE_URL}")
    try:
        response = requests.get(BASE_URL, verify=False)
        if response.status_code != 200:
            print(f"Failed to fetch list: {response.status_code}")
            return

        soup = BeautifulSoup(response.content, "html.parser")
        main_content = soup.find(id="main-content") or soup.find(class_="block-system-main-block") or soup.body
        
        if not main_content:
            print("Could not find main content")
            return

        links = main_content.find_all("a", href=True)
        print(f"Found {len(links)} links.")
        
        processed_slugs = set()

        for link in links:
            href = link['href'].strip()
            
            # Filter logic similar to seminars but for workshops
            if "global-alliance-for-immune-prediction-and-intervention" not in href:
                continue
            
            # Additional filters
            if "/workshops/" in href and href.endswith("/workshops/"): continue # Base URL
            
            # Normalize URL
            if href.startswith("/"):
                full_url = "https://cms-wip.unl.edu" + href
            elif not href.startswith("http"):
                 full_url = "https://cms-wip.unl.edu/" + href
            else:
                full_url = href

            # Generate Slug
            slug = full_url.split("/")[-2] if full_url.endswith("/") else full_url.split("/")[-1]
            if not slug or slug in processed_slugs:
                continue
            
            processed_slugs.add(slug)
            
            title = link.get_text(strip=True)
            print(f"Found workshop: {title} ({slug})")
            
            # Check if already exists
            existing = cursor.execute("SELECT id FROM workshops WHERE slug=?", (slug,)).fetchone()
            if existing:
                print(f"  Skipping {slug}, already exists.")
                continue

            try:
                detail_resp = requests.get(full_url, verify=False)
                if detail_resp.status_code == 200:
                    detail_soup = BeautifulSoup(detail_resp.content, "html.parser")
                    detail_content = detail_soup.find(id="main-content") or detail_soup.find(class_="block-system-main-block") or detail_soup.body
                    
                    # Clean up
                    # Remove Title H1
                    if detail_content.find("h1"): detail_content.find("h1").decompose()
                    
                    full_html = str(detail_content)
                    
                    # Image Extraction
                    image_data = None
                    image_mime = None
                    
                    images = detail_content.find_all("img")
                    for img in images:
                        src = img.get("src")
                        if src and "icon" not in src and "logo" not in src:
                            if not src.startswith("http"):
                                img_url = "https://cms-wip.unl.edu" + src if src.startswith("/") else "https://cms-wip.unl.edu/" + src
                            else:
                                img_url = src
                            
                            try:
                                print(f"    Downloading image: {img_url}")
                                img_resp = requests.get(img_url, verify=False)
                                if img_resp.status_code == 200:
                                    image_data = img_resp.content
                                    image_mime = img_resp.headers.get("Content-Type", "image/jpeg")
                                    break
                            except Exception as e:
                                print(f"    Image download failed: {e}")

                    # Insert
                    cursor.execute('''
                        INSERT INTO workshops (slug, title, content, details, image_data, image_mime, external_link)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (slug, title, full_html, full_html, image_data, image_mime, full_url))
                    conn.commit()
                    print(f"  Saved {slug}")

            except Exception as e:
                print(f"  Error scraping {slug}: {e}")

    except Exception as e:
        print(f"Error scraping list: {e}")
    
    conn.close()

if __name__ == "__main__":
    scrape_workshops()
