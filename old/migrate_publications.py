import sqlite3
import requests
from bs4 import BeautifulSoup
import re

DB_FILE = "app/content/glimprint.db"
TEMPLATE_FILE = "app/templates/publications.html"

def migrate_publications():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Create Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            authors TEXT,
            description TEXT,
            link TEXT,
            year TEXT
        )
    ''')
    conn.commit()
    
    # Check if empty, if not, maybe clear it? Or just append/update?
    # User said "standardize... it has the correct publications", implying current HTML is source of truth.
    # I'll clear it to ensure clean state from HTML.
    cursor.execute("DELETE FROM publications")
    conn.commit()

    # 2. Parse HTML
    print("Parsing existing publications.html...")
    with open(TEMPLATE_FILE, "r") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        
    items = soup.find_all("div", class_="publication-item")
    print(f"Found {len(items)} items.")
    
    for item in items:
        h3 = item.find("h3")
        a = h3.find("a") if h3 else None
        
        if not a: continue
        
        title = a.get_text(" ", strip=True)
        link = a['href']
        
        paras = item.find_all("p")
        authors = ""
        description = ""
        
        if len(paras) >= 2:
            authors = paras[0].get_text(" ", strip=True)
            description = paras[1].get_text(" ", strip=True)
        elif len(paras) == 1:
            # Heuristic: Is it authors or description?
            # "Richard Laubenbacher" -> Authors
            # "A comprehensive design..." -> Description
            text = paras[0].get_text(" ", strip=True)
            if len(text) < 50 and "," not in text and "model" not in text.lower():
                 authors = text
            else:
                 description = text
        
        print(f"Adding: {title}")
        cursor.execute("INSERT INTO publications (title, authors, description, link) VALUES (?, ?, ?, ?)", 
                       (title, authors, description, link))
    
    conn.commit()
    
    # 3. Enrich Data
    print("\nEnriching data from links...")
    rows = cursor.execute("SELECT id, link, title, authors, description FROM publications").fetchall()
    
    for row in rows:
        link = row['link']
        
        # If we have basic info, maybe skip? 
        # But descriptions in HTML were short, maybe we can get better ones?
        # User said "some details may be missing".
        
        needs_authors = not row['authors']
        needs_desc = not row['description'] or len(row['description']) < 50
        
        if not needs_authors and not needs_desc:
            print(f"Skipping enrichment for {row['title'][:20]}... (already has data)")
            continue
            
        print(f"Fetching {link}...")
        try:
            # Set a User-Agent
            headers = {"User-Agent": "Mozilla/5.0 (compatible; GlimprintBot/1.0)"}
            resp = requests.get(link, headers=headers, timeout=10)
            if resp.status_code == 200:
                p_soup = BeautifulSoup(resp.content, "html.parser")
                
                new_authors = row['authors']
                new_desc = row['description']
                
                # Specialized parsing based on domain
                if "ncbi.nlm.nih.gov" in link:
                    # PubMed / PMC
                    # Authors: .citation-authors or .contrib-group
                    if needs_authors:
                        auth_div = p_soup.find(class_="contrib-group")
                        if auth_div:
                            new_authors = auth_div.get_text(", ", strip=True)
                            
                    # Abstract: .abstract or #abstract
                    if needs_desc:
                        abs_div = p_soup.find(id="abstract") or p_soup.find(class_="abstract") # or .tsec
                        if abs_div:
                             # Remove "Abstract" title
                             for h in abs_div.find_all(re.compile("^h[1-6]")): h.decompose()
                             new_desc = abs_div.get_text(" ", strip=True)

                elif "arxiv.org" in link:
                    # Arxiv
                    # Authors: .authors
                    if needs_authors:
                        auth_div = p_soup.find(class_="authors")
                        if auth_div:
                            new_authors = auth_div.get_text(" ", strip=True).replace("Authors:", "").strip()
                    
                    # Abstract: .abstract
                    if needs_desc:
                        abs_div = p_soup.find(class_="abstract")
                        if abs_div:
                            new_desc = abs_div.get_text(" ", strip=True).replace("Abstract:", "").strip()

                elif "mdpi.com" in link:
                     # MDPI
                     # Authors: .art-authors
                     if needs_authors:
                         auth_div = p_soup.find(class_="art-authors")
                         if auth_div:
                             new_authors = auth_div.get_text(", ", strip=True)
                     
                     # Abstract: .art-abstract
                     if needs_desc:
                         abs_div = p_soup.find(class_="art-abstract")
                         if abs_div:
                             new_desc = abs_div.get_text(" ", strip=True)
                             
                elif "scientificamerican.com" in link:
                    # SciAm - Metadata usually in head
                    if needs_desc:
                        meta_desc = p_soup.find("meta", attrs={"name": "description"})
                        if meta_desc:
                            new_desc = meta_desc['content']
                    if needs_authors:
                        meta_author = p_soup.find("meta", attrs={"name": "author"})
                        if meta_author:
                            new_authors = meta_author['content']

                # Update if changed
                # Generic Meta Tags (Fallback)
                if needs_authors and not new_authors:
                     # <meta name="citation_author" content="...">
                     # <meta name="author" content="...">
                     authors_list = []
                     for meta in p_soup.find_all("meta", attrs={"name": "citation_author"}):
                         if meta.get("content"): authors_list.append(meta["content"])
                     if authors_list:
                         new_authors = ", ".join(authors_list)
                     
                     if not new_authors:
                         meta_auth = p_soup.find("meta", attrs={"name": "author"})
                         if meta_auth: new_authors = meta_auth["content"]

                if needs_desc and not new_desc:
                    # <meta name="description" content="...">
                    # <meta property="og:description" content="...">
                    meta_desc = p_soup.find("meta", attrs={"name": "description"}) or p_soup.find("meta", property="og:description")
                    if meta_desc: new_desc = meta_desc["content"]

                if new_authors != row['authors'] or new_desc != row['description']:
                    print(f"  Updating {row['title'][:20]}...")
                    # clean up authors
                    # remove explicit "Authors:" prefix if present
                    if new_authors and new_authors.lower().startswith("authors:"): 
                        new_authors = new_authors[8:].strip()
                        
                    cursor.execute("UPDATE publications SET authors=?, description=? WHERE id=?", (new_authors, new_desc, row['id']))
                    conn.commit()
                else:
                    print("  No better data found.")

        except Exception as e:
            print(f"  Failed to enrich {link}: {e}")

    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_publications()
