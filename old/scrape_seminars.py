import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://cms-wip.unl.edu/ianr/biochemistry/global-alliance-for-immune-prediction-and-intervention/seminars/"
IMAGE_DIR = "app/static/images/seminars"
JSON_FILE = "app/content/seminars.json"

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(JSON_FILE), exist_ok=True)

seminars = []

def scrape_page(page_num):
    url = f"{BASE_URL}?page={page_num}"
    print(f"Scraping list page: {url}")
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 200:
            print(f"Failed to fetch page {page_num}: {response.status_code}")
            return

        soup = BeautifulSoup(response.content, "html.parser")
        # Find the main content area
        main_content = soup.find(id="main-content") or soup.find(class_="block-system-main-block") or soup.body
        
        if not main_content:
            print("Could not find main content")
            return

        links = main_content.find_all("a", href=True)
        print(f"Found {len(links)} links in main content.")
        for link in links:
            href = link['href'].strip()
            
            # Debugging first few links
            # print(f"Checking: {href}")

            # Filter for seminar links
            # Must contain the site prefix
            if "global-alliance-for-immune-prediction-and-intervention" not in href:
                # print(f"Skipped (no prefix): {href}")
                continue
            
            # Exclude known non-seminar paths
            excluded_keywords = [
                "/seminars/", "?page=", "/about-us/", "/resources/", "/activities/", 
                "/news/", "/contact", "/home/", "/people", "/search", "/user", 
                "/sites/", "/files/", "/node/", "/submit-glimprint-news"
            ]
            if any(k in href for k in excluded_keywords):
                # print(f"Skipped (excluded keyword): {href}")
                continue
                
            # Exclude duplicates of base url
            if href.endswith("global-alliance-for-immune-prediction-and-intervention/"):
                # print(f"Skipped (base url): {href}")
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 10: 
                print(f"Skipped (short title): {title} - {href}")
                continue
            
            print(f"Possible seminar: {title} - {href}")
                
            # Normalize URL
            if href.startswith("/"):
                full_url = "https://cms-wip.unl.edu" + href
            elif not href.startswith("http"):
                 # Relative path without leading slash?
                 full_url = "https://cms-wip.unl.edu/" + href
            else:
                full_url = href

            # Filter out non-seminar pages
            if any(x in full_url for x in ["immune-systems-models", "publications", "membership"]):
                 # print(f"Skipped (non-seminar page): {full_url}")
                 continue

            # Duplicate check
            if any(s['link'] == full_url for s in seminars):
                continue

            print(f"Found seminar: {title}")
            print(f"  Fetching detail: {full_url}")
            
            try:
                detail_resp = requests.get(full_url, verify=False)
                if detail_resp.status_code == 200:
                    detail_soup = BeautifulSoup(detail_resp.content, "html.parser")
                    detail_content = detail_soup.find(id="main-content") or detail_soup.find(class_="block-system-main-block") or detail_soup.body
                    
                    # Extract data
                    full_title = detail_soup.find("h1").get_text(strip=True) if detail_soup.find("h1") else title
                    
                    # Image
                    image_url = ""
                    # Try to find an image in the content
                    images = detail_content.find_all("img")
                    for img in images:
                        src = img.get("src")
                        if src:
                            # Filter out common UI icons if necessary, but for now grab the first substantial one
                            if "icon" in src or "logo" in src: continue
                            
                            if not src.startswith("http"):
                                if src.startswith("/"):
                                    image_url = "https://cms-wip.unl.edu" + src
                                else:
                                    image_url = "https://cms-wip.unl.edu/" + src
                            else:
                                image_url = src
                            break # Take first image
                        
                    # Download Image
                    local_image_path = ""
                    if image_url:
                        try:
                            print(f"  Downloading image: {image_url}")
                            img_data = requests.get(image_url, verify=False).content
                            # Create filename
                            slug = href.split("/")[-2] if href.endswith("/") else href.split("/")[-1]
                            if not slug: slug = "seminar_" + str(len(seminars))
                            
                            ext = os.path.splitext(image_url.split("?")[0])[1] or ".jpg"
                            filename = f"Seminar_{slug}{ext}"
                            # Sanitize filename
                            filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
                            
                            local_path = os.path.join(IMAGE_DIR, filename)
                            with open(local_path, "wb") as f:
                                f.write(img_data)
                            local_image_path = f"/static/images/seminars/{filename}"
                        except Exception as e:
                            print(f"  Failed to download image {image_url}: {e}")

                        # Description/Abstract
                        # Remove H1 from content to avoid duplicate title
                        if detail_content.find("h1"):
                            detail_content.find("h1").decompose()
                        
                        # Also remove the "submitted by" or tags if possible
                        # For now, just keep the content
                        abstract_html = str(detail_content)

                        seminars.append({
                            "id": full_url.split("/")[-2] if full_url.endswith("/") else full_url.split("/")[-1],
                            "title": full_title,
                            "link": full_url,
                            "image": local_image_path,
                            "content": abstract_html,
                            "speakers": [], 
                            "date": "", 
                            "raw_url": full_url
                        })
                        print(f"  Successfully scraped: {full_title}")

            except Exception as e:
                print(f"  Error scraping detail {full_url}: {e}")

    except Exception as e:
        print(f"Error scraping list page {page_num}: {e}")

# Run for 4 pages
for i in range(4):
    scrape_page(i)

# Save to JSON
with open(JSON_FILE, "w") as f:
    json.dump(seminars, f, indent=4)

print(f"Total seminars scraped: {len(seminars)}")
