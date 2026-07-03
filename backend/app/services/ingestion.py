"""Ingestion orchestration: file on disk -> searchable vectors in Qdrant.

The full pipeline for one uploaded file:

    parse (parsers.py)            raw file  -> LlamaIndex Documents (+metadata)
    chunk (indexing.py)           Documents -> Nodes (bounded-size pieces)
    embed (llm_provider.py)       Nodes     -> 2048-dim vectors  [OpenRouter]
    store (Qdrant)                vectors   -> collection, tagged with claim_id
    record (db.py)                status    -> processing/ready/failed

This runs as a FastAPI BackgroundTask so a large PDF (which can take seconds to
parse + embed) never blocks the HTTP upload response — the frontend polls the
document status endpoint instead.
"""
from __future__ import annotations

from app.models import db
from app.services.indexing import build_node_parser, get_index
from app.services.parsers import UnsupportedFileTypeError, parse_file


def ingest_document(
    document_id: str,
    session_id: str,
    file_path: str,
    filename: str,
    ocr_mode: str = "auto",
) -> None:
    """Parse, chunk, embed and store one file; update its DB status throughout.

    Never raises — failures are recorded on the document row so the API can
    report them, because this runs detached in a background thread.
    """
    try:
        # 1) Parse: raw bytes -> Documents carrying page/sheet/row metadata.
        documents = parse_file(
            file_path=file_path,
            filename=filename,
            claim_id=session_id,   # claim_id == session_id scopes retrieval
            document_id=document_id,
            ocr_mode=ocr_mode,
        )
        if not documents:
            db.update_document(
                document_id,
                status="failed",
                error="No extractable text found in the file.",
            )
            return

        # 2) Chunk: Documents -> Nodes. Counting nodes ourselves gives an exact
        #    chunks_indexed figure and lets us embed+store in one insert call.
        nodes = build_node_parser().get_nodes_from_documents(documents)

        # 3+4) Embed + store: insert_nodes embeds each node (OpenRouter) and
        #      upserts it into the Qdrant collection.
        get_index().insert_nodes(nodes)

        # 5) Record success.
        db.update_document(document_id, status="ready", chunks_indexed=len(nodes))

    except UnsupportedFileTypeError as e:
        db.update_document(document_id, status="failed", error=str(e))
    except Exception as e:  # noqa: BLE001 - background task must not crash silently
        db.update_document(
            document_id,
            status="failed",
            error=f"{type(e).__name__}: {e}",
        )
