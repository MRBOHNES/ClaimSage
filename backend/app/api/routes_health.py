"""Health check endpoint.

Reports service liveness and Qdrant reachability. Used both by humans during
local dev and by the docker-compose healthcheck.
"""
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    settings = get_settings()
    qdrant_status = "unknown"
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url, timeout=2.0)
        client.get_collections()
        qdrant_status = "ok"
    except Exception:
        qdrant_status = "unreachable"

    return {"status": "ok", "qdrant": qdrant_status}
