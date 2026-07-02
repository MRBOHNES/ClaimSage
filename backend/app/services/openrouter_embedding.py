"""Custom LlamaIndex embedding backed by OpenRouter.

Why not the stock ``OpenAIEmbedding``? The ``openai`` SDK defaults to
``encoding_format="base64"``, which OpenRouter's embedding router returns as a
null payload — LlamaIndex then fails with "NoneType is not iterable". Forcing
``encoding_format="float"`` fixes it, so we wrap the client directly.

Sends plain-text input (the model is multimodal, but we only embed text).
"""
from __future__ import annotations

from typing import List

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import PrivateAttr
from openai import AsyncOpenAI, OpenAI


class OpenRouterEmbedding(BaseEmbedding):
    _client: OpenAI = PrivateAttr()
    _aclient: AsyncOpenAI = PrivateAttr()

    def __init__(
        self,
        model_name: str,
        api_key: str,
        api_base: str,
        embed_batch_size: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(
            model_name=model_name,
            embed_batch_size=embed_batch_size,
            **kwargs,
        )
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._aclient = AsyncOpenAI(api_key=api_key, base_url=api_base)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(
            model=self.model_name,
            input=texts,
            encoding_format="float",
        )
        return [item.embedding for item in resp.data]

    async def _aembed(self, texts: List[str]) -> List[List[float]]:
        resp = await self._aclient.embeddings.create(
            model=self.model_name,
            input=texts,
            encoding_format="float",
        )
        return [item.embedding for item in resp.data]

    # --- sync ---
    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed([text])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    # --- async ---
    async def _aget_query_embedding(self, query: str) -> List[float]:
        return (await self._aembed([query]))[0]

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return (await self._aembed([text]))[0]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._aembed(texts)
