from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown
import json
import frontmatter

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
CONTENT_DIR = BASE_DIR / "content"

def get_news_items():
    news_dir = CONTENT_DIR / "news"
    items = []
    if not news_dir.exists():
        return items
    
    for file in news_dir.glob("*.md"):
        post = frontmatter.load(file)
        html_content = markdown.markdown(post.content)
        items.append({
            "slug": file.stem,
            "title": post.get("title", "No Title"),
            "date": post.get("date", ""),
            "summary": post.get("summary", ""),
            "image": post.get("image", ""),
            "content": html_content
        })
    # Sort by date descending
    return sorted(items, key=lambda x: str(x["date"]), reverse=True)

@router.get("/")
async def home(request: Request):
    news = get_news_items()[:3] # Latest 3
    return templates.TemplateResponse("home.html", {
        "request": request,
        "news_items": news
    })

@router.get("/news")
async def news_list(request: Request):
    news = get_news_items()
    return templates.TemplateResponse("news_list.html", {
        "request": request,
        "news_items": news
    })

@router.get("/news/{slug}")
async def news_detail(request: Request, slug: str):
    file_path = CONTENT_DIR / "news" / f"{slug}.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="News item not found")
    
    post = frontmatter.load(file_path)
    html_content = markdown.markdown(post.content)
    item = {
        "title": post.get("title", "No Title"),
        "date": post.get("date", ""),
        "image": post.get("image", ""),
        "content": html_content
    }
    return templates.TemplateResponse("news_detail.html", {
        "request": request,
        "item": item
    })

@router.get("/resources")
async def resources(request: Request):
    # Load from json if exists
    models_file = CONTENT_DIR / "models.json"
    models = []
    if models_file.exists():
        with open(models_file) as f:
            models = json.load(f)
            
    return templates.TemplateResponse("resources.html", {
        "request": request,
        "models": models
    })

@router.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("generic.html", {"request": request, "title": "About Us"})

@router.get("/basic-viral-sir-model-lorenzo-felletti")
async def sir_model(request: Request):
    return templates.TemplateResponse("sir_model.html", {"request": request})

@router.get("/members")
async def members_list(request: Request):
    members_file = CONTENT_DIR / "members.json"
    members = []
    if members_file.exists():
        with open(members_file) as f:
            members = json.load(f)
    return templates.TemplateResponse("members.html", {"request": request, "members": members})
