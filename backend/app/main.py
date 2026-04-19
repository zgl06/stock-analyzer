from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from backend.app.api.routes import router

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="Stock Analyzer Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
