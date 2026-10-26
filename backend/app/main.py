"""ClaimSage backend — FastAPI application entrypoint.

Wires up CORS for the React frontend (allowed origins come from CORS_ORIGINS) and
mounts the health, upload and query routers.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import routes_health, routes_query, routes_upload
from app.models.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup: create SQLite tables (idempotent) before serving."""
    init_db()
    yield


app = FastAPI(
    title="ClaimSage API",
    description="Document-grounded Q&A over insurance claim documents (RAG).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(routes_health.router)
app.include_router(routes_upload.router)
app.include_router(routes_query.router)


@app.get("/")
def root() -> dict:
    return {"service": "ClaimSage API", "docs": "/docs", "health": "/api/health"}
