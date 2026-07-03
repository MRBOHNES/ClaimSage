"""Application configuration.

All settings are read from environment variables (or a local ``.env`` file in
development). Secrets like ``OPENAI_API_KEY`` must never be committed — see
``.env.example`` for the template.
"""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # API key for managed Qdrant Cloud; empty for a local/self-hosted instance.
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "claimsage_documents"

    # --- Relational registry (sessions / documents / ingestion status) ---
    database_url: str = "sqlite:///./claimsage.db"

    # --- Chunking (centralised so the phase-2 eval harness can vary these) ---
    chunk_strategy: str = "sentence"  # maps to a node-parser factory
    chunk_size: int = 512
    chunk_overlap: int = 50

    # --- Retrieval ---
    similarity_top_k: int = 6

    # --- OCR (scanned PDFs + image/camera uploads) ---
    # OCR is a fallback for content with no extractable text layer. For PDFs it
    # runs per page only when needed; images always OCR (no text layer exists).
    ocr_enabled: bool = True
    # Default mode when an upload request omits ?ocr_mode=.
    #   "auto"   -> OCR a PDF page only if its text layer is below ocr_min_chars
    #   "always" -> OCR every PDF page regardless of any text layer
    #   "off"    -> never OCR (text layer only; images then yield nothing)
    ocr_default_mode: str = "auto"
    # Per-page native-text threshold (chars) below which "auto" mode OCRs a page.
    ocr_min_chars: int = 100
    # Rasterization DPI for OCR (higher = better accuracy, slower).
    ocr_dpi: int = 300
    # Tesseract language(s), e.g. "eng" or "eng+deu".
    ocr_lang: str = "eng"

    # --- Uploads ---
    max_upload_size_mb: int = 50
    upload_dir: str = "./storage/uploads"

    # --- CORS (allowed frontend origins) ---
    # Accepts a comma-separated string from the environment (e.g.
    # "https://claimsage.vercel.app,http://localhost:5173") or a list in code.
    # Defaults cover the Vite (5173) and CRA (3000) local dev servers.
    # NoDecode disables pydantic-settings' default JSON parsing of this env var
    # so the validator below can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
