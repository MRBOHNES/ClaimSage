"""SQLite registry for sessions and documents.

This is the *relational* half of the storage story (the vector half lives in
Qdrant). It answers bookkeeping questions the vector store shouldn't:
  * which documents belong to which claim/session, and
  * what's the ingestion status of each upload (processing / ready / failed).

Why SQLite: zero infra (a single file), survives backend restarts (unlike an
in-memory dict), and is a one-line swap to Postgres later via the ORM.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from app.config import get_settings

_settings = get_settings()

# check_same_thread=False: FastAPI BackgroundTasks run in a threadpool, so the
# connection may be touched from a different thread than it was created on.
engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ClaimSession(Base):
    """One claim workflow. The `id` doubles as the Qdrant `claim_id` filter."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Document(Base):
    """One uploaded file and its ingestion status."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String, default="")
    size_bytes: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String, default="processing")  # processing|ready|failed
    error: Mapped[str] = mapped_column(String, default="")
    chunks_indexed: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_now)


def init_db() -> None:
    """Create tables if they don't exist. Called once at app startup."""
    Base.metadata.create_all(engine)


# --- CRUD helpers (each opens a short-lived session) -----------------------

def create_session() -> str:
    with SessionLocal() as db:
        s = ClaimSession()
        db.add(s)
        db.commit()
        return s.id


def session_exists(session_id: str) -> bool:
    with SessionLocal() as db:
        return db.get(ClaimSession, session_id) is not None


def create_document(session_id: str, filename: str, file_type: str, size_bytes: int) -> str:
    with SessionLocal() as db:
        doc = Document(
            session_id=session_id,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
        )
        db.add(doc)
        db.commit()
        return doc.id


def update_document(
    document_id: str,
    *,
    status: str | None = None,
    error: str | None = None,
    chunks_indexed: int | None = None,
) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        if status is not None:
            doc.status = status
        if error is not None:
            doc.error = error
        if chunks_indexed is not None:
            doc.chunks_indexed = chunks_indexed
        db.commit()


def get_document(document_id: str) -> Document | None:
    with SessionLocal() as db:
        return db.get(Document, document_id)


def list_documents(session_id: str) -> list[Document]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Document)
                .where(Document.session_id == session_id)
                .order_by(Document.created_at)
            )
        )
