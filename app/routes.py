from fastapi import APIRouter, Request, HTTPException, Response, Depends, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown
import json
import frontmatter
import re
from datetime import datetime, timedelta
import pytz
import sqlite3
import json
from .database import get_db_connection
from .auth import verify_password, get_password_hash, get_current_admin, require_admin

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Custom filter for JSON parsing
def from_json(value):
    try:
        return json.loads(value)
    except:
        return {}

templates.env.filters["from_json"] = from_json
# get_db_connection is imported from .database

def get_aggregated_news(limit=None):
    conn = get_db_connection()
    items = []
    
    # News
    try:
        # Fetch all, filter in python for json 'status': 'approved'
        news_rows = conn.execute("SELECT * FROM news").fetchall()
        for r in news_rows:
            d = dict(r)
            # Check approval
            status = d.get("approval_status")
            is_approved = False
            if status:
                try:
                    s_json = json.loads(status)
                    if s_json.get("status") == "approved":
                        is_approved = True
                except: pass
            else:
                # Fallback for old data if any (though we updated schema)
                # If None, assume approved? No, strictly require approval now.
                # But migration script set it.
                pass
            
            if not is_approved: continue

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
            status = d.get("approval_status")
            is_approved = False
            if status:
                try:
                    s_json = json.loads(status)
                    if s_json.get("status") == "approved": is_approved = True
                except: pass
            if not is_approved: continue

            items.append({
                "type": "Seminar",
                "title": d["title"],
                "date": d["date"] or "",
                "announcement_date": d.get("announcement_date"),
                "image_url": f"/seminars/image/{d['slug']}" if d["image_data"] else None, # Use seminar image
                "url": f"/activities/seminars/{d['id']}",
                "summary": f"Speaker: {d.get('speaker', 'Unknown')}"
            })
    except: pass

    # Workshops
    try:
        work_rows = conn.execute("SELECT * FROM workshops").fetchall()
        for r in work_rows:
            d = dict(r)
            status = d.get("approval_status")
            is_approved = False
            if status:
                try:
                    s_json = json.loads(status)
                    if s_json.get("status") == "approved": is_approved = True
                except: pass
            if not is_approved: continue

            items.append({
                "type": "Workshop",
                "title": d["title"],
                "date": d["start_date"] or "",
                "announcement_date": d.get("announcement_date"),
                "image_url": f"/workshops/image/{d['slug']}" if d["image_data"] else None,
                "url": f"/activities/workshops/{d['id']}",
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

# --- Admin Routes ---

@router.get("/admin/login")
async def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.post("/admin/login")
async def login_submit(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if not admin or not verify_password(password, admin['password_hash']):
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    # Login success
    request.session["user"] = {"username": admin["username"]}
    return RedirectResponse(url="/admin", status_code=303)

@router.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)

@router.get("/admin")
async def admin_dashboard(request: Request, user = Depends(require_admin)):
    conn = get_db_connection()
    categories = ['news', 'seminars', 'workshops', 'publications', 'members']
    counts = {}
    
    for c in categories:
        try:
            # Count total
            total = conn.execute(f"SELECT COUNT(*) FROM {c}").fetchone()[0]
            
            # Count pending.
            # Using LIKE for simplicity
            pending = conn.execute(f"SELECT COUNT(*) FROM {c} WHERE approval_status LIKE '%\"status\": \"pending_approval\"%'").fetchone()[0]
            
            counts[c] = {"total": total, "pending": pending}
        except Exception as e:
            print(f"Error counting {c}: {e}")
            counts[c] = {"total": 0, "pending": 0}
            
    conn.close()
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, 
        "user": user,
        "counts": counts
    })


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
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM news ORDER BY date DESC").fetchall()
    
    news_items = []
    for row in rows:
        d = dict(row)
        d['type'] = 'News'
        d['url'] = f"/news/{d['slug']}"
        d['image_url'] = f"/news/image/{d['slug']}"
        
        # Create summary from body (strip HTML)
        clean_body = re.sub(r'<[^>]+>', '', d.get('body', ''))
        d['summary'] = clean_body[:200] + '...' if len(clean_body) > 200 else clean_body
        
        if d.get('date'):
            try:
                # Convert ISO YYYY-MM-DD to "Month DD, YYYY"
                dt = datetime.strptime(d['date'], "%Y-%m-%d")
                d['display_date'] = dt.strftime("%B %d, %Y")
            except:
                d['display_date'] = d['date']
        else:
            d['display_date'] = ""
        news_items.append(d)
        
    conn.close()
    return templates.TemplateResponse("news.html", {"request": request, "news_items": news_items})

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
         return Response(content=row['image_data'], media_type=row['image_mime'], headers={"Cache-Control": "public, max-age=31536000, immutable"})
    else:
         raise HTTPException(status_code=404, detail="Image not found")



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
    
    pubs = []
    for row in rows:
        p = dict(row)
        status = p.get("approval_status")
        is_approved = False
        if status:
            try:
                s_json = json.loads(status)
                if s_json.get("status") == "approved": is_approved = True
            except: pass
        if is_approved:
            pubs.append(p)

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
        
        # Check approval
        status = s.get("approval_status")
        is_approved = False
        if status:
            try:
                s_json = json.loads(status)
                if s_json.get("status") == "approved": is_approved = True
            except: pass
        if not is_approved: continue
        
        # Format date for display
        s["display_date"] = "Date TBD"
        if s.get("start_datetime_utc"):
            try:
                utc_dt = datetime.fromisoformat(s["start_datetime_utc"])
                if utc_dt.tzinfo is None:
                    utc_dt = pytz.UTC.localize(utc_dt)
                et_dt = utc_dt.astimezone(eastern)
                s["display_date"] = et_dt.strftime("%B %d, %Y, %I:%M %p %Z")
            except:
                pass
        elif s.get("date") and s.get("time"):
             # Fallback to date + time (naive)
             try:
                 # Assume existing time is whatever the user entered, display as is
                 dt = datetime.strptime(f"{s['date']} {s['time']}", "%Y-%m-%d %H:%M")
                 s["display_date"] = dt.strftime("%B %d, %Y, %I:%M %p")
             except:
                 s["display_date"] = f"{s['date']} at {s['time']}"
        elif s.get("date"):
             s["display_date"] = s["date"]

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
    
    # Unpack related links
    s['related_links_list'] = []
    if s.get('related_links'):
        try:
            s['related_links_list'] = json.loads(s['related_links'])
        except: pass

    # Date Display Logic
    eastern = pytz.timezone('US/Eastern')
    s["display_date"] = "Date TBD"
    dt_aware = None

    if s.get("start_datetime_utc"):
        try:
            utc_dt = datetime.fromisoformat(s["start_datetime_utc"])
            if utc_dt.tzinfo is None:
                utc_dt = pytz.UTC.localize(utc_dt)
            dt_aware = utc_dt.astimezone(eastern)
            s["display_date"] = dt_aware.strftime("%B %d, %Y, %I:%M %p %Z")
        except: pass
    elif s.get("date") and s.get("time"):
         try:
             dt = datetime.strptime(f"{s['date']} {s['time']}", "%Y-%m-%d %H:%M")
             # Naive fallback
             s["display_date"] = dt.strftime("%B %d, %Y, %I:%M %p")
             dt_aware = eastern.localize(dt) # Assume ET for is_over check if naive?
         except:
             s["display_date"] = f"{s['date']} at {s['time']}"

    # Check if over
    if dt_aware:
        now_eastern = datetime.now(eastern)
        if now_eastern > dt_aware + timedelta(hours=24):
            s['is_over'] = True
        
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
        
    return Response(content=seminar['image_data'], media_type=seminar['image_mime'], headers={"Cache-Control": "public, max-age=31536000, immutable"})

@router.get("/activities/workshops", response_class=HTMLResponse)
async def workshops(request: Request):
    conn = get_db_connection()
    # Sort by start_date DESC
    rows = conn.execute("SELECT * FROM workshops ORDER BY start_date DESC").fetchall()
    conn.close()
    
    workshops = []
    for row in rows:
        w = dict(row)
        
        # Check approval
        status = w.get("approval_status")
        is_approved = False
        if status:
            try:
                s_json = json.loads(status)
                if s_json.get("status") == "approved": is_approved = True
            except: pass
        if not is_approved: continue

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
    
    # Unpack related links
    if w.get('related_links'):
        try:
             w['related_links_list'] = json.loads(w['related_links'])
        except:
             w['related_links_list'] = []

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
        
    return Response(content=row['image_data'], media_type=row['image_mime'], headers={"Cache-Control": "public, max-age=31536000, immutable"})

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
        
        # Check approval
        status = m.get("approval_status")
        is_approved = False
        if status:
            try:
                s_json = json.loads(status)
                if s_json.get("status") == "approved": is_approved = True
            except: pass
        if not is_approved: continue

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
             # Ensure it's a list
             if not isinstance(m['links_list'], list):
                 m['links_list'] = []
         except:
             m['links_list'] = []
             
    return templates.TemplateResponse("member_detail.html", {"request": request, "member": m})

@router.get("/members/image/{slug}")
async def member_image(slug: str):
    conn = get_db_connection()
    row = conn.execute("SELECT image_data, image_mime FROM members WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    
    if row and row['image_data']:
         return Response(content=row['image_data'], media_type=row['image_mime'], headers={"Cache-Control": "public, max-age=31536000, immutable"})
    else:
         raise HTTPException(status_code=404, detail="Image not found")

@router.get("/admin/approvals")
async def admin_approvals(request: Request, user = Depends(require_admin)):
    conn = get_db_connection()
    tables = ['news', 'seminars', 'workshops', 'publications', 'members']
    pending_items = []
    
    for t in tables:
        rows = conn.execute(f"SELECT *, '{t}' as table_name FROM {t}").fetchall()
        for r in rows:
            d = dict(r)
            try:
                s = json.loads(d['approval_status'])
                if s.get('status') == 'pending_approval':
                    pending_items.append(d)
            except: pass
    conn.close()
    
    return templates.TemplateResponse("admin/approvals.html", {
        "request": request,
        "items": pending_items
    })

@router.post("/admin/approve/{table}/{slug}")
async def approve_item(request: Request, table: str, slug: str, user = Depends(require_admin)):
    if table not in ['news', 'seminars', 'workshops', 'publications', 'members']:
        raise HTTPException(status_code=400, detail="Invalid table")
        
    conn = get_db_connection()
    # Update status to approved
    approved_status = json.dumps({
        "status": "approved",
        "by": user['username'],
        "at": datetime.now().isoformat()
    })
    
    conn.execute(f"UPDATE {table} SET approval_status = ? WHERE slug = ?", (approved_status, slug))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/admin/approvals", status_code=303)

# --- Submission Routes ---

def generate_slug(title_or_name: str):
    return re.sub(r'[^a-z0-9]+', '-', title_or_name.lower()).strip('-') + "-" + datetime.now().strftime("%Y%m%d%H%M%S")

@router.get("/submit/news")
@router.get("/submit/news")
async def submit_news_form(request: Request):
    today = datetime.now().date().isoformat()
    return templates.TemplateResponse("news_form.html", {
        "request": request, 
        "today": today,
        "title_text": "Submit News",
        "form_action": "/submit/news",
        "is_admin": False
    })

@router.post("/submit/news")
async def submit_news_post(
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    body: str = Form(...),
    related_links: str = Form(None), # JSON string or text
    image: UploadFile = File(None)
):
    slug = generate_slug(title)
        
    # Handle Image
    image_data = None
    image_mime = None
    if image and image.filename:
        image_data = await image.read()
        image_mime = image.content_type

    # Handle related links
    clean_links = []
    if related_links:
        try:
            parsed = json.loads(related_links)
            if isinstance(parsed, list):
                clean_links = parsed
        except:
             pass
    
    links_json = json.dumps(clean_links) if clean_links else None

    status = json.dumps({"status": "pending_approval", "at": datetime.now().isoformat()})
    created_at = datetime.now().isoformat()
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO news (slug, title, date, body, image_data, image_mime, related_links, approval_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, title, date, body, image_data, image_mime, links_json, status, created_at)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        today = datetime.now().date().isoformat()
        return templates.TemplateResponse("news_form.html", {
            "request": request, 
            "error": str(e), 
            "today": today,
            "title_text": "Submit News",
            "form_action": "/submit/news",
            "is_admin": False
        })
        
    conn.close()
    return templates.TemplateResponse("submit_success.html", {"request": request})

@router.get("/submit/seminars")
async def submit_seminar_form(request: Request):
    return templates.TemplateResponse("seminar_form.html", {
        "request": request,
        "title_text": "Submit Seminar",
        "form_action": "/submit/seminars",
        "is_admin": False,
        "timezones": pytz.common_timezones
    })

@router.post("/submit/seminars")
async def submit_seminar(
    request: Request,
    title: str = Form(...),
    speaker: str = Form(...),
    affiliation: str = Form(...),
    abstract: str = Form(None),
    date: str = Form(...),
    time: str = Form(...),
    timezone: str = Form(None),
    location: str = Form(None), # Optional now
    related_links: str = Form(None), # Replaces link
    image: UploadFile = File(None)
):
    conn = get_db_connection()
    
    # Handle Image
    image_data = None
    image_mime = None
    if image and image.filename:
        image_data = await image.read()
        image_mime = image.content_type

    # Handle related links
    clean_links_json = None
    if related_links:
        try:
             clean_links = json.loads(related_links)
             clean_links_json = json.dumps(clean_links)
        except: pass

    # Timezone conversion
    start_datetime_utc = None
    try:
        # Combine date and time
        local_dt_str = f"{date} {time}"
        local_dt = datetime.strptime(local_dt_str, "%Y-%m-%d %H:%M")
        
        if timezone:
            tz = pytz.timezone(timezone)
            local_dt = tz.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.UTC)
            start_datetime_utc = utc_dt.isoformat()
        else:
            # Fallback if no timezone, assume server time or just store as is? 
            # User said "merged... stored as utc". If no TZ, we might default to UTC or keep null?
            # Let's default to UTC if no TZ provided
            start_datetime_utc = local_dt.isoformat() 
    except Exception as e:
        print(f"Date conversion error: {e}")

    slug = re.sub(r'[^a-z0-9]+', '-', f"{speaker} {title}".lower()).strip('-')
    
    status = json.dumps({"status": "pending_approval", "submitted_at": datetime.now().isoformat()})
    
    try:
        conn.execute(
            "INSERT INTO seminars (slug, title, speaker, affiliation, abstract, date, time, location, related_links, start_datetime_utc, image_data, image_mime, approval_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, title, speaker, affiliation, abstract, date, time, location, clean_links_json, start_datetime_utc, image_data, image_mime, status, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return templates.TemplateResponse("seminar_form.html", {
            "request": request, 
            "error": str(e),
            "title_text": "Submit Seminar",
            "form_action": "/submit/seminars",
            "is_admin": False
        })
    
    conn.close()
    return templates.TemplateResponse("submit_success.html", {"request": request})

@router.get("/submit/workshops")
async def submit_workshop_form(request: Request):
    return templates.TemplateResponse("workshop_form.html", {
        "request": request,
        "title_text": "Submit Workshop",
        "form_action": "/submit/workshops",
        "is_admin": False
    })

@router.post("/submit/workshops")
async def submit_workshop(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(None),
    location: str = Form(...),
    related_links: str = Form(None), # Replaces link
    image: UploadFile = File(None)
):
    conn = get_db_connection()
    
    # Handle Image
    image_data = None
    image_mime = None
    if image and image.filename:
        image_data = await image.read()
        image_mime = image.content_type

    # Handle related links
    clean_links_json = None
    if related_links:
        try:
             clean_links = json.loads(related_links)
             clean_links_json = json.dumps(clean_links)
        except: pass

    slug = re.sub(r'[^a-z0-9]+', '-', f"{title}".lower()).strip('-')
    status = json.dumps({"status": "pending_approval", "submitted_at": datetime.now().isoformat()})

    try:
        conn.execute(
            "INSERT INTO workshops (slug, title, description, start_date, end_date, location, related_links, image_data, image_mime, approval_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, title, description, start_date, end_date, location, clean_links_json, image_data, image_mime, status, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return templates.TemplateResponse("workshop_form.html", {
            "request": request, 
            "error": str(e),
            "title_text": "Submit Workshop",
            "form_action": "/submit/workshops",
            "is_admin": False
        })
    
    conn.close()
    return templates.TemplateResponse("submit_success.html", {"request": request, "message": "Workshop submitted for approval!"})

@router.get("/submit/publications")
async def submit_publication_form(request: Request):
    return templates.TemplateResponse("publication_form.html", {
        "request": request,
        "title_text": "Submit Publication",
        "form_action": "/submit/publications",
        "is_admin": False
    })

@router.post("/submit/publications")
async def submit_publication_post(request: Request):
    form = await request.form()
    title = form.get("title")
    authors = form.get("authors")
    description = form.get("description") # Replacing journal
    year = form.get("year") # Optional
    link = form.get("link")
    
    slug = generate_slug(title)
    status = json.dumps({"status": "pending_approval", "at": datetime.now().isoformat()})
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO publications (slug, title, authors, description, year, link, approval_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, title, authors, description, year, link, status, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return templates.TemplateResponse("publication_form.html", {
            "request": request, 
            "error": str(e),
            "title_text": "Submit Publication",
            "form_action": "/submit/publications",
            "is_admin": False
        })
    conn.close()
    return templates.TemplateResponse("submit_success.html", {"request": request})

@router.get("/submit/members")
async def submit_member_form(request: Request):
    return templates.TemplateResponse("member_form.html", {
        "request": request,
        "title_text": "Submit Member Profile",
        "form_action": "/submit/members",
        "is_admin": False
    })

@router.post("/submit/members")
async def submit_member_post(
    request: Request,
    name: str = Form(None),
    affiliation: str = Form(None),
    email: str = Form(None),
    education: str = Form(None),
    statement: str = Form(None),
    links: str = Form(None), # Valid JSON expected
    image: UploadFile = File(None)
):
    # Manual Validation
    field_errors = {}
    if not name or not name.strip(): field_errors["name"] = "Name is required."
    if not affiliation or not affiliation.strip(): field_errors["affiliation"] = "Affiliation is required."
    if not email or not email.strip(): field_errors["email"] = "Email is required."
    if not statement or not statement.strip(): field_errors["statement"] = "Statement/Bio is required."
    
    if field_errors:
        return templates.TemplateResponse("member_form.html", {
            "request": request,
            "error": "Please correct the errors below.",
            "field_errors": field_errors,
            "title_text": "Submit Member Profile",
            "form_action": "/submit/members",
            "is_admin": False,
            "item": {
                "name": name or "",
                "affiliation": affiliation or "",
                "email": email or "",
                "education": education or "",
                "statement": statement or "",
                "links": links or ""
            }
        })

    slug = generate_slug(name)
    status = json.dumps({"status": "pending_approval", "at": datetime.now().isoformat()})
    
    # Handle Image
    image_data = None
    image_mime = None
    if image and image.filename:
        image_data = await image.read()
        image_mime = image.content_type

    # Validate links JSON
    clean_links_str = None
    if links:
        try:
             l = json.loads(links)
             if isinstance(l, list):
                 clean_links_str = links
        except:
             pass
             
    clean_links_json = json.dumps(json.loads(clean_links_str)) if clean_links_str else None

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO members (slug, name, affiliation, email, education, statement, links, image_data, image_mime, approval_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, name, affiliation, email, education, statement, clean_links_json, image_data, image_mime, status, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return templates.TemplateResponse("member_form.html", {
            "request": request, 
            "error": str(e),
            "title_text": "Submit Member Profile",
            "form_action": "/submit/members",
            "is_admin": False,
            "item": {
                "name": name,
                "affiliation": affiliation,
                "email": email,
                "education": education,
                "statement": statement,
                "links": links
            }
        })
        
    conn.close()
    return templates.TemplateResponse("submit_success.html", {"request": request})




@router.get("/admin/contacts")
async def admin_contacts(request: Request, user = Depends(require_admin)):
    conn = get_db_connection()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()
    conn.close()
    return templates.TemplateResponse("admin/contacts.html", {"request": request, "contacts": [dict(c) for c in contacts]})

@router.post("/admin/contacts/add")
async def add_contact(request: Request, user = Depends(require_admin)):
    form = await request.form()
    name = form.get("name")
    email = form.get("email")
    affiliation = form.get("affiliation")
    
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO contacts (name, email, affiliation) VALUES (?, ?, ?)", (name, email, affiliation))
        conn.commit()
    except Exception as e:
        # Handle duplicate email or other error
        pass
    conn.close()
    return RedirectResponse(url="/admin/contacts", status_code=303)


@router.post("/admin/contacts/delete/{contact_id}")
async def delete_contact(request: Request, contact_id: int, user = Depends(require_admin)):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting contact: {e}")
    conn.close()
    return RedirectResponse(url="/admin/contacts", status_code=303)


# --- Generic Admin Routes (Must be last to avoid capturing specific routes) ---

@router.get("/admin/{category}")
async def admin_list_category(request: Request, category: str, user = Depends(require_admin)):
    allowed_categories = ['news', 'seminars', 'workshops', 'publications', 'members']
    if category not in allowed_categories:
        raise HTTPException(status_code=404, detail="Category not found")
    
    conn = get_db_connection()
    try:
        items = conn.execute(f"SELECT * FROM {category} ORDER BY created_at DESC").fetchall()
    except Exception as e:
        print(f"Error fetching {category}: {e}")
        items = []
    conn.close()
    
    return templates.TemplateResponse("admin/list_generic.html", {
        "request": request, 
        "category": category, 
        "items": [dict(i) for i in items]
    })

@router.post("/admin/{category}/{item_id}/approve")
async def admin_approve_item(request: Request, category: str, item_id: str, user = Depends(require_admin)):
    allowed_categories = ['news', 'seminars', 'workshops', 'publications', 'members']
    if category not in allowed_categories:
        raise HTTPException(status_code=404, detail="Category not found")
        
    conn = get_db_connection()
    status = json.dumps({"status": "approved", "at": datetime.now().isoformat(), "by": user['username']})
    
    pk_col = "slug" if category == "news" else "id"
    # Ensure item_id is treated as string for slug, int for id if needed?
    conn.execute(f"UPDATE {category} SET approval_status = ? WHERE {pk_col} = ?", (status, item_id))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url=f"/admin/{category}", status_code=303)

@router.get("/admin/{category}/{item_id}/delete") # Support GET for delete? No, strictly POST usually, but for simple links... let's stick to POST form.
async def admin_delete_item_get(request: Request, category: str, item_id: str, user = Depends(require_admin)):
    # Fallback if someone tries GET, or show confirmation?
    return RedirectResponse(url=f"/admin/{category}", status_code=303)

@router.post("/admin/{category}/{item_id}/delete")
async def admin_delete_item(request: Request, category: str, item_id: str, user = Depends(require_admin)):
    allowed_categories = ['news', 'seminars', 'workshops', 'publications', 'members']
    if category not in allowed_categories:
        raise HTTPException(status_code=404, detail="Category not found")
        
    conn = get_db_connection()
    pk_col = "slug" if category == "news" else "id"
    # Ensure item_id string/int?
    conn.execute(f"DELETE FROM {category} WHERE {pk_col} = ?", (item_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url=f"/admin/{category}", status_code=303)


@router.get("/admin/{category}/{item_id}/edit")
async def admin_edit_category(request: Request, category: str, item_id: str, user = Depends(require_admin)):
    allowed_categories = ['news', 'seminars', 'workshops', 'publications', 'members']
    if category not in allowed_categories:
        raise HTTPException(status_code=404, detail="Category not found")

    conn = get_db_connection()
    pk_col = "slug" if category == "news" else "id"
    item = conn.execute(f"SELECT * FROM {category} WHERE {pk_col} = ?", (item_id,)).fetchone()
    conn.close()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    template_name = f"admin/edit_{category}.html"
    
    if category == 'seminars':
         return templates.TemplateResponse("seminar_form.html", {
             "request": request, 
             "item": dict(item), 
             "category": category,
             "title_text": "Edit Seminar",
             "form_action": f"/admin/seminars/{item['id']}/edit",
             "is_admin": True,
             "timezones": pytz.common_timezones
         })
    elif category == 'news':
         return templates.TemplateResponse("news_form.html", {
             "request": request, 
             "item": dict(item), 
             "category": category,
             "title_text": "Edit News",
             "form_action": f"/admin/news/{item['slug']}/edit",
             "is_admin": True
         })
    elif category == 'publications':
         return templates.TemplateResponse("publication_form.html", {
             "request": request, 
             "item": dict(item), 
             "category": category,
             "title_text": "Edit Publication",
             "form_action": f"/admin/publications/{item['id']}/edit",
             "is_admin": True
         })
    elif category == 'members':
         return templates.TemplateResponse("member_form.html", {
             "request": request, 
             "item": dict(item), 
             "category": category,
             "title_text": "Edit Member",
             "form_action": f"/admin/members/{item['id']}/edit",
             "is_admin": True
         })
    
    elif category == 'workshops':
         return templates.TemplateResponse("workshop_form.html", {
             "request": request, 
             "item": dict(item), 
             "category": category,
             "title_text": "Edit Workshop",
             "form_action": f"/admin/workshops/{item['id']}/edit",
             "is_admin": True
         })
    
    return Response(f"Edit form for {category} not implemented yet.", status_code=501)

@router.post("/admin/{category}/{item_id}/edit")
async def admin_save_category(request: Request, category: str, item_id: str, user = Depends(require_admin)):
    form = await request.form()
    conn = get_db_connection()
    
    approval_status = form.get("approval_status")
    
    status_dict = {"status": approval_status, "at": datetime.now().isoformat()}
    if approval_status == 'approved':
        status_dict["by"] = user['username']
        
    status_json = json.dumps(status_dict)

    # Handle Image Upload if present
    image = form.get("image")
    image_data = None
    image_mime = None
    if image and hasattr(image, 'filename') and image.filename:
        image_data = await image.read()
        image_mime = image.content_type

    if category == 'seminars':
        title = form.get("title")
        speaker = form.get("speaker")
        affiliation = form.get("affiliation")
        date = form.get("date")
        time = form.get("time") 
        location = form.get("location")
        related_links = form.get("related_links")
        recording_url = form.get("recording_url")
        abstract = form.get("abstract")
        timezone = form.get("timezone")

        # Sanitize JSON
        clean_links_json = None
        if related_links:
            try:
                clean_links = json.loads(related_links)
                clean_links_json = json.dumps(clean_links)
            except: pass

        # Timezone conversion
        start_datetime_utc = None
        try:
            local_dt_str = f"{date} {time}"
            local_dt = datetime.strptime(local_dt_str, "%Y-%m-%d %H:%M")
            if timezone:
                tz = pytz.timezone(timezone)
                local_dt = tz.localize(local_dt)
                utc_dt = local_dt.astimezone(pytz.UTC)
                start_datetime_utc = utc_dt.isoformat()
            else:
                 start_datetime_utc = local_dt.isoformat() 
        except: pass

        # Ensure recording_url is not None
        if recording_url is None:
            recording_url = ""

        if image_data:
            conn.execute("""
                UPDATE seminars SET 
                    title=?, speaker=?, affiliation=?, date=?, time=?, location=?, related_links=?, start_datetime_utc=?, recording_url=?, abstract=?, approval_status=?,
                    image_data=?, image_mime=?
                WHERE id=?
            """, (title, speaker, affiliation, date, time, location, clean_links_json, start_datetime_utc, recording_url, abstract, status_json, image_data, image_mime, item_id))
        else:
            conn.execute("""
                UPDATE seminars SET 
                    title=?, speaker=?, affiliation=?, date=?, time=?, location=?, related_links=?, start_datetime_utc=?, recording_url=?, abstract=?, approval_status=?
                WHERE id=?
            """, (title, speaker, affiliation, date, time, location, clean_links_json, start_datetime_utc, recording_url, abstract, status_json, item_id))
        
    elif category == 'news':
        title = form.get("title")
        date = form.get("date")
        body = form.get("body")
        related_links = form.get("related_links")
        
        # Sanitize JSON
        if related_links:
            try:
                related_links = json.dumps(json.loads(related_links))
            except:
                try:
                    import ast
                    related_links = json.dumps(ast.literal_eval(related_links))
                except:
                    related_links = None

        if image_data:
            conn.execute("""
                UPDATE news SET title=?, date=?, body=?, related_links=?, approval_status=?, image_data=?, image_mime=? WHERE slug=?
            """, (title, date, body, related_links, status_json, image_data, image_mime, item_id))
        else:
             conn.execute("""
                UPDATE news SET title=?, date=?, body=?, related_links=?, approval_status=? WHERE slug=?
            """, (title, date, body, related_links, status_json, item_id))

    elif category == 'workshops':
        title = form.get("title")
        start_date = form.get("start_date")
        end_date = form.get("end_date")
        location = form.get("location")
        # link = form.get("link") # Removed
        description = form.get("description")
        related_links = form.get("related_links")
        
        # Sanitize JSON
        clean_links_json = None
        if related_links:
            try:
                clean_links = json.loads(related_links)
                clean_links_json = json.dumps(clean_links)
            except: pass

        if image_data:
             conn.execute("""
                UPDATE workshops SET 
                    title=?, start_date=?, end_date=?, location=?, description=?, related_links=?, approval_status=?,
                    image_data=?, image_mime=?
                WHERE id=?
            """, (title, start_date, end_date, location, description, clean_links_json, status_json, image_data, image_mime, item_id))
        else:
             conn.execute("""
                UPDATE workshops SET 
                    title=?, start_date=?, end_date=?, location=?, description=?, related_links=?, approval_status=?
                WHERE id=?
            """, (title, start_date, end_date, location, description, clean_links_json, status_json, item_id))
            
    elif category == 'publications':
        title = form.get("title")
        authors = form.get("authors")
        description = form.get("description")
        year = form.get("year")
        link = form.get("link")
        
        conn.execute("""
            UPDATE publications SET title=?, authors=?, description=?, year=?, link=?, approval_status=? WHERE id=?
        """, (title, authors, description, year, link, status_json, item_id))

    elif category == 'members':
        name = form.get("name")
        affiliation = form.get("affiliation")
        email = form.get("email")
        statement = form.get("statement")
        education = form.get("education")
        links = form.get("links")
        
        # Sanitize JSON
        if links:
            try:
                links = json.dumps(json.loads(links))
            except:
                try:
                    import ast
                    links = json.dumps(ast.literal_eval(links))
                except:
                    links = None
        
        if image_data:
             conn.execute("""
                UPDATE members SET name=?, affiliation=?, email=?, statement=?, education=?, links=?, approval_status=?, image_data=?, image_mime=? WHERE id=?
            """, (name, affiliation, email, statement, education, links, status_json, image_data, image_mime, item_id))
        else:
             conn.execute("""
                UPDATE members SET name=?, affiliation=?, email=?, statement=?, education=?, links=?, approval_status=? WHERE id=?
            """, (name, affiliation, email, statement, education, links, status_json, item_id))

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/{category}", status_code=303)

@router.get("/admin/mailing/announcement")
async def mailing_announcement(request: Request, user = Depends(require_admin)):
    return templates.TemplateResponse("admin/mailing_announcement.html", {"request": request})

@router.post("/admin/mailing/send")
async def send_announcement(request: Request, user = Depends(require_admin)):
    form = await request.form()
    subject = form.get("subject")
    body = form.get("body")
    test_only = form.get("test_only") == "on"
    
    from .mailing import send_email, send_bulk_email
    
    conn = get_db_connection()
    admin = conn.execute("SELECT email FROM admins WHERE username = ?", (user['username'],)).fetchone()
    
    # Check if admin has email (should be required now)
    admin_email = admin['email'] if admin and admin['email'] else None
    
    if not admin_email:
        conn.close()
        return templates.TemplateResponse("admin/mailing_announcement.html", {
            "request": request, 
            "message": "Error: Your admin account does not have an email address configured.",
            "subject": subject,
            "body": body
        })

    if test_only:
        try:
            conn.close()
            # Format with admin/dummy data for test
            dummy_context = {
                "name": "Admin Test",
                "email": admin_email,
                "affiliation": "Glimprint Admin"
            }
            try:
                formatted_subject = subject.format(**dummy_context)
                formatted_body = body.format(**dummy_context)
            except KeyError as e:
                # If template uses keys we didn't provide
                formatted_subject = subject
                formatted_body = body + f"\n\n[Warning: Could not replace placeholder {e}]"

            success = send_email(admin_email, admin_email, f"[TEST] {formatted_subject}", formatted_body, is_html=True)
            if success:
                message = f"Test email sent to {admin_email}"
            else:
                 message = f"Failed to send test email to {admin_email}. Check logs."
        except ConnectionRefusedError:
             message = "Connection refused. Please check your SMTP configuration (server address and port)."
        except Exception as e:
             message = f"Error sending test email: {e}"
    else:
        # Send to all contacts
        contacts = conn.execute("SELECT name, email, affiliation FROM contacts").fetchall()
        conn.close()
        
        recipients = [{"name": c["name"], "email": c["email"], "affiliation": c["affiliation"] or ""} for c in contacts]
        try:
            success, fail = send_bulk_email(admin_email, recipients, subject, body) # body is template
            message = f"Sent to {success} recipients. Failed: {fail}"
        except Exception as e:
            message = f"Bulk send error: {e}. Check SMTP settings."

    return templates.TemplateResponse("admin/mailing_announcement.html", {
        "request": request, 
        "message": message,
        "subject": subject,
        "body": body
    })


@router.get("/admin/mailing/json")
async def mailing_json_form(request: Request, user = Depends(require_admin)):
     return templates.TemplateResponse("admin/mailing_json.html", {"request": request})

@router.post("/admin/mailing/json")
async def send_json_email(request: Request, user = Depends(require_admin)):
    form = await request.form()
    json_str = form.get("json_data")
    test_only = form.get("test_only") == "on"
    
    from .mailing import send_email, send_bulk_email
    
    conn = get_db_connection()
    admin = conn.execute("SELECT email FROM admins WHERE username = ?", (user['username'],)).fetchone()
    conn.close()
    
    admin_email = admin['email'] if admin and admin['email'] else None
    if not admin_email:
         return templates.TemplateResponse("admin/mailing_json.html", {"request": request, "message": "Error: Admin email not found.", "json_data": json_str})
    
    try:
        data = json.loads(json_str) 
        # Format: [{"To": "...", "Cc": "...", "Subject": "...", "Body": "..."}]
        
        if not isinstance(data, list):
             raise ValueError("JSON must be a list of objects.")

        success_count = 0
        fail_count = 0
        
        for item in data:
            to_emails = item.get("To")
            cc_emails = item.get("Cc")
            subject = item.get("Subject")
            body = item.get("Body")
            
            if not to_emails or not subject or not body:
                fail_count += 1
                continue
            
            # Apply formatting
            try:
                formatted_subject_text = subject.format(**item)
                formatted_body_text = body.format(**item)
            except Exception as e:
                # Fallback if formatting fails (missing keys)
                print(f"Format error for {to_emails}: {e}")
                formatted_subject_text = subject
                formatted_body_text = body

            formatted_body = formatted_body_text.replace("\n", "<br>")
            
            # Test Mode Logic
            target_to = admin_email if test_only else to_emails
            target_cc = None if test_only else cc_emails
            target_subject = f"[TEST] {formatted_subject_text}" if test_only else formatted_subject_text
            
            try:
                if send_email(admin_email, target_to, target_subject, formatted_body, is_html=True, cc_email=target_cc):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"Send error: {e}")
                fail_count += 1

        message = f"Batch processed {'(TEST MODE)' if test_only else ''}. Success: {success_count}, Failed: {fail_count}"
        
    except json.JSONDecodeError:
        message = "Invalid JSON format."
    except Exception as e:
        message = f"Error processing JSON: {e}"

    return templates.TemplateResponse("admin/mailing_json.html", {"request": request, "message": message, "json_data": json_str})


