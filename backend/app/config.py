"""Application configuration.

All settings are read from environment variables (or a local ``.env`` file in
development). Secrets like ``OPENAI_API_KEY`` must never be committed — see
``.env.example`` for the template.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenRouter (accessed only through services/llm_provider.py) ---
    # Single provider for both chat + embeddings; OpenAI-compatible API.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Chat model that writes grounded answers.
    llm_model: str = "google/gemma-4-26b-a4b-it:free"
    # Embedding model (turns chunks/questions into vectors for search).
    embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    # Embedding dimensionality: 0 = discover at runtime from a probe embedding
    # (see services/indexing.py). Avoids hardcoding a wrong value per model.
    embedding_dim: int = 0
    llm_temperature: float = 0.1

    # --- Qdrant (vector store) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "claimsage_documents"

    # --- Relational registry (sessions / documents / ingestion status) ---
    database_url: str = "sqlite:///./claimsage.db"

    # --- Chunking (centralised so the phase-2 eval harness can vary these) ---
    chunk_strategy: str = "sentence"  # maps to a node-parser factory
    chunk_size: int = 512
    chunk_overlap: int = 50

    # --- Retrieval ---
    similarity_top_k: int = 6

    # --- Uploads ---
    max_upload_size_mb: int = 50
    upload_dir: str = "./storage/uploads"

    # --- CORS (frontend dev origin) ---
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
