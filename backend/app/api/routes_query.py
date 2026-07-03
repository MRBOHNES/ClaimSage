"""Question-answering endpoint.

Given a session_id and a natural-language question, retrieves the most relevant
chunks from that claim's documents and returns a grounded answer with citations.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import OpenAIError, RateLimitError

from app.models import db
from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.services.query_engine import answer_question

router = APIRouter(tags=["query"])


@router.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    if not db.session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="Unknown session_id.")

    # Map upstream LLM/provider failures to clean, user-facing errors instead of
    # a bare 500 (e.g. OpenRouter's free-tier daily rate limit).
    try:
        result = answer_question(request.session_id, request.question)
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="The language model is rate-limited right now. Please try again shortly.",
        )
    except OpenAIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"The language model provider returned an error: {e}",
        )

    return QueryResponse(
        answer=result.answer,
        confidence=result.confidence,
        citations=[
            Citation(
                filename=c.filename,
                location=c.location,
                snippet=c.snippet,
                score=c.score,
            )
            for c in result.citations
        ],
    )
