"""Session + document upload/status endpoints.

Flow the frontend follows:
  1. POST /api/sessions                      -> get a session_id (once per claim)
  2. POST /api/documents?session_id=...       -> upload files; ingestion starts in
                                                 the background, returns "processing"
  3. GET  /api/documents/{doc_id}/status      -> poll until "ready" / "failed"
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.models import db
from app.models.schemas import DocumentStatus, SessionResponse, UploadResponse
from app.services.ingestion import ingest_document
from app.services.parsers import REJECTED_EXTENSIONS, SUPPORTED_EXTENSIONS

router = APIRouter(tags=["documents"])


@router.post("/api/sessions", response_model=SessionResponse)
def create_session() -> SessionResponse:
    """Start a new claim workflow. The id scopes all its documents + queries."""
    return SessionResponse(session_id=db.create_session())


@router.post("/api/documents", response_model=UploadResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    session_id: str = Query(...),
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    settings = get_settings()

    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Unknown session_id.")

    upload_dir = Path(settings.upload_dir) / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    results: list[DocumentStatus] = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        contents = await upload.read()
        size = len(contents)

        # Reject early with a clear status rather than failing deep in ingestion.
        early_error = _validate(ext, size, max_bytes, settings.max_upload_size_mb)

        doc_id = db.create_document(
            session_id=session_id,
            filename=upload.filename or "unnamed",
            file_type=ext.lstrip("."),
            size_bytes=size,
        )

        if early_error:
            db.update_document(doc_id, status="failed", error=early_error)
            results.append(
                DocumentStatus(
                    doc_id=doc_id,
                    filename=upload.filename or "unnamed",
                    status="failed",
                    error=early_error,
                )
            )
            continue

        # Persist the file, then kick off background ingestion.
        dest = upload_dir / f"{doc_id}{ext}"
        dest.write_bytes(contents)
        background_tasks.add_task(
            ingest_document,
            document_id=doc_id,
            session_id=session_id,
            file_path=str(dest),
            filename=upload.filename or "unnamed",
        )
        results.append(
            DocumentStatus(
                doc_id=doc_id,
                filename=upload.filename or "unnamed",
                status="processing",
            )
        )

    return UploadResponse(documents=results)


@router.get("/api/documents/{doc_id}/status", response_model=DocumentStatus)
def document_status(doc_id: str) -> DocumentStatus:
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown doc_id.")
    return DocumentStatus(
        doc_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        error=doc.error,
        chunks_indexed=doc.chunks_indexed,
    )


@router.get("/api/sessions/{session_id}/documents", response_model=UploadResponse)
def list_session_documents(session_id: str) -> UploadResponse:
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    docs = db.list_documents(session_id)
    return UploadResponse(
        documents=[
            DocumentStatus(
                doc_id=d.id,
                filename=d.filename,
                status=d.status,
                error=d.error,
                chunks_indexed=d.chunks_indexed,
            )
            for d in docs
        ]
    )


def _validate(ext: str, size: int, max_bytes: int, max_mb: int) -> str | None:
    """Return an error string if the file should be rejected, else None."""
    if ext in REJECTED_EXTENSIONS:
        return f"'{ext}' is a legacy binary format not supported. Convert to PDF/DOCX/XLSX/TXT/EML."
    if ext not in SUPPORTED_EXTENSIONS:
        return f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
    if size == 0:
        return "File is empty."
    if size > max_bytes:
        return f"File exceeds the {max_mb} MB limit."
    return None
