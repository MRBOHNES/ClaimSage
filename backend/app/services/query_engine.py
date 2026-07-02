"""Query pipeline: retrieve claim-scoped chunks, synthesize a grounded answer.

Citations are derived structurally from the retrieved source nodes (filename +
page/sheet/row + score), not by asking the LLM to self-report them — this is
both more accurate and directly demonstrates the RAG mechanism.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

from app.config import get_settings
from app.services.indexing import get_index

# Gemma (and some other OpenRouter models) occasionally leak special tokens
# into the completion text; strip them so answers render cleanly.
_SPECIAL_TOKEN_RE = re.compile(
    r"<(?:pad|eos|bos|unk|end_of_turn|start_of_turn|\|?endoftext\|?)>"
)


def _clean_answer(text: str) -> str:
    text = _SPECIAL_TOKEN_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()

_SYSTEM_PROMPT = (
    "You are ClaimSage, an insurance-claim assistant. Answer the question using "
    "ONLY the provided context from the claimant's documents. If the context is "
    "insufficient, say so plainly. Be concise and cite specific policy terms. "
    "This is advisory information, not a final claims-adjudication decision."
)


@dataclass
class Citation:
    filename: str
    location: str | None  # page / sheet+row / email field
    snippet: str
    score: float


@dataclass
class QueryResult:
    answer: str
    citations: list[Citation]
    confidence: float  # retrieval-confidence proxy (top node score), not certainty


def _location_label(metadata: dict) -> str | None:
    if metadata.get("page_label") is not None:
        return f"page {metadata['page_label']}"
    if metadata.get("sheet_name") is not None:
        row = metadata.get("row_number")
        return f"sheet '{metadata['sheet_name']}'" + (f", row {row}" if row else "")
    if metadata.get("email_field"):
        return f"email {metadata['email_field']}"
    return None


def answer_question(session_id: str, question: str) -> QueryResult:
    """Retrieve chunks scoped to this claim/session and synthesize an answer."""
    settings = get_settings()
    index = get_index()

    query_engine = index.as_query_engine(
        similarity_top_k=settings.similarity_top_k,
        filters=MetadataFilters(
            filters=[ExactMatchFilter(key="claim_id", value=session_id)]
        ),
        system_prompt=_SYSTEM_PROMPT,
        response_mode="compact",
    )

    response = query_engine.query(question)

    citations: list[Citation] = []
    for node in response.source_nodes:
        meta = node.node.metadata
        citations.append(
            Citation(
                filename=meta.get("source_filename", "unknown"),
                location=_location_label(meta),
                snippet=node.node.get_content()[:280],
                score=round(float(node.score), 4) if node.score is not None else 0.0,
            )
        )

    confidence = citations[0].score if citations else 0.0
    return QueryResult(
        answer=_clean_answer(str(response)),
        citations=citations,
        confidence=confidence,
    )
