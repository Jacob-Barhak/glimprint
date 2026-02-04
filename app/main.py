from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .routes import router

app = FastAPI(title="Glimprint")

# Get Root Dir (now the current directory)
BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(router)
