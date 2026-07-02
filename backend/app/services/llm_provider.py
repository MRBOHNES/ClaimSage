"""LLM / embedding provider abstraction.

All OpenAI usage in the app funnels through here so that:
  * provider swaps (Anthropic, local models) are a one-file change, and
  * the phase-2 LangChain agent layer has a single place to obtain its models.

Nothing else in the codebase should import ``openai`` or the LlamaIndex OpenAI
classes directly — call ``get_llm_provider()`` instead.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms.llm import LLM
from llama_index.llms.openai_like import OpenAILike

from app.config import Settings, get_settings
from app.services.openrouter_embedding import OpenRouterEmbedding


class LLMProvider(Protocol):
    """Minimal surface the rest of the app depends on."""

    def get_llm(self) -> LLM: ...

    def get_embedding_model(self) -> BaseEmbedding: ...


class OpenRouterProvider:
    """Concrete provider backed by OpenRouter (OpenAI-compatible API).

    A single API key + base URL serves both the chat model and the embedding
    model — only the model slug differs between the two calls.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_llm(self) -> LLM:
        return OpenAILike(
            model=self._settings.llm_model,
            api_base=self._settings.openrouter_base_url,
            api_key=self._settings.openrouter_api_key,
            temperature=self._settings.llm_temperature,
            is_chat_model=True,
            # OpenRouter reports context via its own API; set a safe default so
            # LlamaIndex doesn't assume a tiny window and truncate retrieved chunks.
            context_window=128000,
        )

    def get_embedding_model(self) -> BaseEmbedding:
        return OpenRouterEmbedding(
            model_name=self._settings.embedding_model,
            api_base=self._settings.openrouter_base_url,
            api_key=self._settings.openrouter_api_key,
        )


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Cached singleton provider for the configured backend."""
    return OpenRouterProvider(get_settings())
