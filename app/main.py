from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from starlette.middleware.sessions import SessionMiddleware
import os

from .routes import router

app = FastAPI(title="Glimprint")

# Get Root Dir (now the current directory)
BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Session Middleware
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev_secret_key"))

app.include_router(router)
