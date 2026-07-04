"""Chunking + Qdrant vector store wiring.

Central place that:
  * configures LlamaIndex global Settings (LLM, embed model, node parser),
  * discovers the embedding dimension at runtime,
  * ensures the Qdrant collection exists with that dimension, and
  * exposes the shared VectorStoreIndex used by ingestion and querying.
"""
from __future__ import annotations

from functools import lru_cache

import qdrant_client
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from app.config import get_settings
from app.services.llm_provider import get_llm_provider


def build_node_parser() -> SentenceSplitter:
    """Baseline chunker. Excel rows arrive as 1 Document each and are short
    enough that they won't be split, preserving per-row citation granularity.
    Centralised here so the phase-2 eval harness can swap strategies."""
    s = get_settings()
    return SentenceSplitter(chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap)


@lru_cache
def discover_embedding_dim() -> int:
    """Use the configured dim if set, else probe the model once and cache it."""
    s = get_settings()
    if s.embedding_dim and s.embedding_dim > 0:
        return s.embedding_dim
    emb = get_llm_provider().get_embedding_model()
    return len(emb.get_text_embedding("dimension probe"))


@lru_cache
def get_qdrant_client() -> qdrant_client.QdrantClient:
    s = get_settings()
    # api_key is required by managed Qdrant Cloud; None for local/self-hosted.
    return qdrant_client.QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)


def ensure_collection() -> None:
    """Create the Qdrant collection (cosine distance) if it doesn't exist, and
    ensure the ``claim_id`` payload index that scoped retrieval filters on.

    Managed Qdrant Cloud rejects a filter on an unindexed field (400), so this
    index is required, not just an optimisation. Creating it is idempotent.
    """
    s = get_settings()
    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if s.qdrant_collection_name not in existing:
        client.create_collection(
            collection_name=s.qdrant_collection_name,
            vectors_config=VectorParams(
                size=discover_embedding_dim(),
                distance=Distance.COSINE,
            ),
        )
    try:
        client.create_payload_index(
            collection_name=s.qdrant_collection_name,
            field_name="claim_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        # Index already exists (or a benign race) — safe to ignore.
        pass


@lru_cache
def _configure_settings() -> None:
    """Set LlamaIndex globals once so index/query use our OpenRouter models."""
    provider = get_llm_provider()
    Settings.llm = provider.get_llm()
    Settings.embed_model = provider.get_embedding_model()
    Settings.node_parser = build_node_parser()


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    s = get_settings()
    ensure_collection()
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=s.qdrant_collection_name,
    )


def get_index() -> VectorStoreIndex:
    """Shared index over the Qdrant collection (embeds on insert/query)."""
    _configure_settings()
    return VectorStoreIndex.from_vector_store(get_vector_store())
