"""Async HTTP client for the synkora-ml microservice."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from src.config.settings import settings


class MLServiceClient:
    """Thin async client wrapping the ML microservice HTTP API."""

    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or settings.ml_service_url
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            key = settings.ml_api_key or ""
            if len(key) < 32:
                raise RuntimeError("ML_API_KEY must contain at least 32 characters")
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0,
                headers={"X-ML-Key": key},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        payload: dict[str, Any] = {"texts": texts}
        if model:
            payload["model"] = model
        resp = self._get_client().post("/v1/embed", json=payload)
        r = await resp
        r.raise_for_status()
        return r.json()["embeddings"]

    async def embed_text(self, text: str, model: str | None = None) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text], model=model)
        return embeddings[0]

    async def get_embedding_dimension(self, model: str | None = None) -> int:
        """Get embedding dimension by embedding a dummy string."""
        payload: dict[str, Any] = {"texts": [" "]}
        if model:
            payload["model"] = model
        r = await self._get_client().post("/v1/embed", json=payload)
        r.raise_for_status()
        return r.json()["dimension"]

    async def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = 5,
        score_weight: float = 0.3,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank search results using cross-encoder."""
        payload: dict[str, Any] = {
            "query": query,
            "results": results,
            "top_k": top_k,
            "score_weight": score_weight,
        }
        if model:
            payload["model"] = model
        r = await self._get_client().post("/v1/rerank", json=payload)
        r.raise_for_status()
        return r.json()["results"]

    async def initialize_tools(self, agent_id: str, tools: list[dict[str, Any]]) -> None:
        """Build FAISS index for agent tools."""
        payload = {"agent_id": agent_id, "tools": tools}
        r = await self._get_client().post("/v1/tools/initialize", json=payload)
        r.raise_for_status()

    async def search_tools(
        self,
        agent_id: str,
        query: str,
        limit: int = 15,
        threshold: float = 0.3,
    ) -> list[tuple[str, float]]:
        """Search agent tools by semantic similarity."""
        payload = {
            "agent_id": agent_id,
            "query": query,
            "limit": limit,
            "threshold": threshold,
        }
        r = await self._get_client().post("/v1/tools/search", json=payload)
        r.raise_for_status()
        return [(t["name"], t["score"]) for t in r.json()["tools"]]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ml_client: MLServiceClient | None = None


def get_ml_client() -> MLServiceClient:
    global _ml_client
    if _ml_client is None:
        _ml_client = MLServiceClient()
    return _ml_client
