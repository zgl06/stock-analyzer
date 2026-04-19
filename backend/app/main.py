from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from backend.app.api.routes import router

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="Stock Analyzer Backend", version="0.1.0")
app.include_router(router)
