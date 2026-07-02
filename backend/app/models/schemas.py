"""API request/response models (the contract the frontend codes against).

Pydantic models here define exactly what each endpoint accepts and returns,
and FastAPI uses them to validate requests and auto-generate the /docs page.
"""
from __future__ import annotations

from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str


class DocumentStatus(BaseModel):
    doc_id: str
    filename: str
    status: str  # processing | ready | failed
    error: str = ""
    chunks_indexed: int = 0


class UploadResponse(BaseModel):
    documents: list[DocumentStatus]


class QueryRequest(BaseModel):
    session_id: str
    question: str


class Citation(BaseModel):
    filename: str
    location: str | None = None  # "page 4", "sheet 'Schedule', row 12", ...
    snippet: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float  # retrieval-confidence proxy (top score), not certainty
