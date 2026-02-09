from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown
import json
import frontmatter
import re
from datetime import datetime, timedelta
import pytz
import sqlite3

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
DB_PATH = BASE_DIR.parent / "db" / "glimprint.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
    files_list = []
    # Walk from current directory
    for root, dirs, files in os.walk("."):
        for file in files:
            files_list.append(os.path.join(root, file))
    
    # Also check BASE_DIR specifically
    base_dir_files = []
    try:
        if BASE_DIR.exists():
             for root, dirs, files in os.walk(str(BASE_DIR)):
                for file in files:
                    base_dir_files.append(os.path.join(root, file))
    except Exception as e:
        base_dir_files.append(str(e))

    return {
        "cwd": os.getcwd(),
        "base_dir": str(BASE_DIR),
        "files_in_cwd": files_list,
        "files_in_base_dir": base_dir_files,
        "template_dir": str(templates.env.loader.searchpath)
    }

def get_aggregated_news(limit=None):
    conn = get_db_connection()
    items = []
    
    # News
    try:
        news_rows = conn.execute("SELECT * FROM news").fetchall()
        for r in news_rows:
            d = dict(r)
            # Create a summary from body if safe
            summary = ""
            if d.get("body"):
                # Strip HTML for summary (naive)
                clean_text = re.sub('<[^<]+?>', '', d["body"])
                summary = clean_text[:150] + "..." if len(clean_text) > 150 else clean_text
            
            items.append({
                "type": "News",
                "title": d["title"],
                "date": d["date"] or "", # ISO or empty
                "image_url": f"/news/image/{d['slug']}" if d["image_data"] else None,
                "url": f"/news/{d['slug']}",
                "summary": summary
            })
    except Exception as e: print(f"News error: {e}")

    # Seminars
    try:
        sem_rows = conn.execute("SELECT * FROM seminars").fetchall()
        for r in sem_rows:
            d = dict(r)
            items.append({
                "type": "Seminar",
                "title": d["title"],
                "date": d["date"] or "",
                "announcement_date": d.get("announcement_date"),
                "image_url": f"/seminars/image/{d['slug']}" if d["image_data"] else None, # Use seminar image
                "url": f"/activities/seminars/{d['slug']}",
                "summary": f"Speaker: {d.get('speaker', 'Unknown')}"
            })
    except: pass

    # Workshops
    try:
        work_rows = conn.execute("SELECT * FROM workshops").fetchall()
        for r in work_rows:
            d = dict(r)
            items.append({
                "type": "Workshop",
                "title": d["title"],
                "date": d["start_date"] or "",
                "announcement_date": d.get("announcement_date"),
                "image_url": f"/workshops/image/{d['slug']}" if d["image_data"] else None,
                "url": f"/activities/workshops/{d['slug']}",
                "summary": d.get("location", "")
            })
    except: pass
    
    conn.close()
    
    # Sort
    from datetime import datetime
    
    def parse_date(date_str):
        if not date_str:
            return datetime.min
        try:
            # Try ISO format first (for seminars/workshops)
            # Handle potential Z or +00:00
            dt = datetime.fromisoformat(date_str)
            return dt.replace(tzinfo=None) # Make naive for comparison
        except ValueError:
            pass
            
        try:
            # Try "Month DD, YYYY" (for scraped news)
            # Sometimes there might be extra spaces or weird chars
            clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str) # Remove ordinal suffixes if any
            dt = datetime.strptime(clean_date.strip(), "%B %d, %Y")
            return dt
        except ValueError:
            pass
            
        return datetime.min

    # Sort key: use announcement_date if available (for seminars/workshops), fall back to date
    def get_sort_date(item):
        if item.get("type") in ["Seminar", "Workshop"] and item.get("announcement_date"):
            return parse_date(item["announcement_date"])
        return parse_date(item["date"])

    items.sort(key=get_sort_date, reverse=True)
    
    if limit:
        return items[:limit]
    return items

@router.get("/")
async def home(request: Request):
    all_items = get_aggregated_news(limit=None)
    
    # Filter by type
    news = [i for i in all_items if i['type'] == 'News'][:3]
    seminars = [i for i in all_items if i['type'] == 'Seminar'][:3]
    workshops = [i for i in all_items if i['type'] == 'Workshop'][:3]
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "latest_news": news,
        "latest_seminars": seminars,
        "latest_workshops": workshops
    })

@router.get("/news")
async def news_list(request: Request):
    all_items = get_aggregated_news()
    # Filter for only News type
    news = [i for i in all_items if i['type'] == 'News']
    return templates.TemplateResponse("news.html", {
        "request": request,
        "news_items": news
    })

@router.get("/news/{slug}")
async def news_detail(request: Request, slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM news WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if not row:
         raise HTTPException(status_code=404, detail="News item not found")
         
    item = dict(row)
    if item['related_links']:
        try: item['related_links'] = json.loads(item['related_links'])
        except: item['related_links'] = []
        
    return templates.TemplateResponse("news_detail.html", {
        "request": request,
        "item": item
    })

@router.get("/news/image/{slug}")
async def news_image(slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT image_data, image_mime FROM news WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if row and row['image_data']:
         return Response(content=row['image_data'], media_type=row['image_mime'])
    else:
         raise HTTPException(status_code=404, detail="Image not found")

@router.get("/resources")
async def resources(request: Request):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM models").fetchall()
    conn.close()
    
    models = [dict(row) for row in rows]
            
    return templates.TemplateResponse("resources.html", {
        "request": request,
        "models": models
    })

@router.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("generic.html", {"request": request, "title": "About Us"})

@router.get("/about/history")
async def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})

@router.get("/about/submit-news")
async def submit_news(request: Request):
    return templates.TemplateResponse("submit_news.html", {"request": request})

@router.get("/about/contact")
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@router.get("/basic-viral-sir-model-lorenzo-felletti")
async def sir_model(request: Request):
    return templates.TemplateResponse("sir_model.html", {"request": request})

@router.get("/resources/runnable-model")
async def runnable_model(request: Request):
    return templates.TemplateResponse("sir_model.html", {"request": request})

@router.get("/resources/publications")
async def publications(request: Request):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM publications").fetchall()
    conn.close()
    
    pubs = [dict(row) for row in rows]
    return templates.TemplateResponse("publications.html", {"request": request, "publications": pubs})



@router.get("/activities/seminars", response_class=HTMLResponse)
async def seminars_page(request: Request):
    conn = get_db_connection()
    # Sort by date DESC so newest first
    seminars_rows = conn.execute("SELECT * FROM seminars ORDER BY date DESC").fetchall()
    conn.close()
    
    # Process for display
    seminars = []
    eastern = pytz.timezone('US/Eastern')
    
    for row in seminars_rows:
        s = dict(row)
        # Format date if present
        if s.get("date"):
            try:
                dt = datetime.fromisoformat(s["date"])
                # Convert to Eastern Time
                if dt.tzinfo is None:
                    # Assume UTC if naive? Or assume already ET? 
                    # Refinement script localized it, so it should be aware.
                     # If it's naive, we might have an issue, but let's assume aware.
                     pass
                else:
                    dt = dt.astimezone(eastern)
                
                # Format: Thursday, February 5, 2026 at 10:00 AM EST
                # Using %-d for no-zero-pad day (linux specific, usually fine)
                # Using %-I for no-zero-pad hour
                s["display_date"] = dt.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
            except ValueError:
                s["display_date"] = s["date"] # Fallback
        else:
             s["display_date"] = "Date TBD"
        seminars.append(s)

    return templates.TemplateResponse("seminars.html", {"request": request, "seminars": seminars})

@router.get("/activities/seminars/{slug}", response_class=HTMLResponse)
async def seminar_detail(request: Request, slug: str):
    conn = get_db_connection()
    seminar_row = conn.execute("SELECT * FROM seminars WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if seminar_row is None:
        raise HTTPException(status_code=404, detail="Seminar not found")
        
    s = dict(seminar_row)
    s['is_over'] = False
    
    if s.get("date"):
        try:
            dt = datetime.fromisoformat(s["date"])
            eastern = pytz.timezone('US/Eastern')
            if dt.tzinfo:
                dt_aware = dt.astimezone(eastern)
            else:
                dt_aware = eastern.localize(dt)
            
            s["display_date"] = dt_aware.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
            
            # Check if over (now > date + 24h)
            now_eastern = datetime.now(eastern)
            if now_eastern > dt_aware + timedelta(hours=24):
                s['is_over'] = True
        except:
            s["display_date"] = s["date"]
    else:
        s["display_date"] = "Date TBD"
        
    # Process recording URL for embed
    s['has_recording'] = False
    if s.get('recording_url'):
        vid_id = None
        if "youtube.com/watch?v=" in s['recording_url']:
            vid_id = s['recording_url'].split("v=")[1].split("&")[0]
        elif "youtu.be/" in s['recording_url']:
            vid_id = s['recording_url'].split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/live/" in s['recording_url']:
            vid_id = s['recording_url'].split("/live/")[1].split("?")[0]
            
        if vid_id:
            s['embed_url'] = f"https://www.youtube.com/embed/{vid_id}"
            s['has_recording'] = True
    
    return templates.TemplateResponse("seminar_detail.html", {"request": request, "seminar": s})

@router.get("/seminars/image/{slug}")
async def seminar_image(slug: str):
    conn = get_db_connection()
    seminar = conn.execute('SELECT image_data, image_mime FROM seminars WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    
    if seminar is None or seminar['image_data'] is None:
        raise HTTPException(status_code=404, detail="Image not found")
        
    return Response(content=seminar['image_data'], media_type=seminar['image_mime'])

@router.get("/activities/workshops", response_class=HTMLResponse)
async def workshops(request: Request):
    conn = get_db_connection()
    # Sort by start_date DESC
    rows = conn.execute("SELECT * FROM workshops ORDER BY start_date DESC").fetchall()
    conn.close()
    
    workshops = []
    for row in rows:
        w = dict(row)
        # Format dates
        # start_date, end_date are ISO strings or None
        if w.get("start_date"):
            try:
                dt1 = datetime.fromisoformat(w["start_date"])
                start_fmt = dt1.strftime("%B %-d, %Y")
                
                if w.get("end_date"):
                    dt2 = datetime.fromisoformat(w["end_date"])
                    if dt1.year == dt2.year:
                        if dt1.month == dt2.month:
                             # July 28 - 30, 2025
                             date_str = f"{dt1.strftime('%B %-d')} - {dt2.strftime('%-d, %Y')}"
                        else:
                             # July 28 - August 10, 2025
                             date_str = f"{dt1.strftime('%B %-d')} - {dt2.strftime('%B %-d, %Y')}"
                    else:
                        # Dec 2024 - Jan 2025
                        date_str = f"{dt1.strftime('%B %-d, %Y')} - {dt2.strftime('%B %-d, %Y')}"
                else:
                    date_str = start_fmt
                
                w["display_date"] = date_str
            except:
                w["display_date"] = w["start_date"]
        else:
             w["display_date"] = "Date TBD"
        
        workshops.append(w)

    return templates.TemplateResponse("workshops.html", {"request": request, "workshops": workshops})

@router.get("/activities/workshops/{slug}", response_class=HTMLResponse)
async def workshop_detail(request: Request, slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM workshops WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Workshop not found")
    
    w = dict(row)
    # Reuse formatting logic (should ideally be a helper function)
    if w.get("start_date"):
        try:
            dt1 = datetime.fromisoformat(w["start_date"])
            if w.get("end_date"):
                dt2 = datetime.fromisoformat(w["end_date"])
                if dt1.year == dt2.year:
                    if dt1.month == dt2.month:
                         w["display_date"] = f"{dt1.strftime('%B %-d')} - {dt2.strftime('%-d, %Y')}"
                    else:
                         w["display_date"] = f"{dt1.strftime('%B %-d')} - {dt2.strftime('%B %-d, %Y')}"
                else:
                    w["display_date"] = f"{dt1.strftime('%B %-d, %Y')} - {dt2.strftime('%B %-d, %Y')}"
            else:
                w["display_date"] = dt1.strftime("%B %-d, %Y")
        except:
             w["display_date"] = w["start_date"]
    else:
         w["display_date"] = "Date TBD"

    return templates.TemplateResponse("workshop_detail.html", {"request": request, "workshop": w})

@router.get("/workshops/image/{slug}")
async def workshop_image(slug: str):
    conn = get_db_connection()
    row = conn.execute('SELECT image_data, image_mime FROM workshops WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    
    if row is None or row['image_data'] is None:
        # Return a placeholder or 404? 
        # For now 404
        raise HTTPException(status_code=404, detail="Image not found")
        
    return Response(content=row['image_data'], media_type=row['image_mime'])

@router.get("/membership")
async def membership(request: Request):
    return templates.TemplateResponse("membership.html", {"request": request})

@router.get("/members", response_class=HTMLResponse)
async def members_list(request: Request):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM members ORDER BY sort_order ASC").fetchall()
    conn.close()
    
    members_list = []
    for row in rows:
        m = dict(row)
        if m['links']:
            try:
                m['links_list'] = json.loads(m['links'])
            except:
                m['links_list'] = []
        members_list.append(m)
        
    return templates.TemplateResponse("members.html", {"request": request, "members": members_list})

@router.get("/members/{slug}", response_class=HTMLResponse)
async def member_detail(request: Request, slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM members WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
            
    m = dict(row)
    if m['links']:
         try:
             m['links_list'] = json.loads(m['links'])
         except:
             m['links_list'] = []
             
    return templates.TemplateResponse("member_detail.html", {"request": request, "member": m})

@router.get("/members/image/{slug}")
async def member_image(slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT image_data, image_mime FROM members WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if row and row['image_data']:
         return Response(content=row['image_data'], media_type=row['image_mime'])
    else:
         raise HTTPException(status_code=404, detail="Image not found")
