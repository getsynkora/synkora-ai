"""
ML Microservice — sentence-transformers + FAISS


Endpoints:
  POST /v1/embed              - generate text embeddings
  POST /v1/rerank             - cross-encoder reranking
  POST /v1/tools/initialize   - build per-agent FAISS index
  POST /v1/tools/search       - query per-agent FAISS index
  GET  /health
"""

import logging
import os
import hmac
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory caches
# ---------------------------------------------------------------------------

_embed_models: dict[str, Any] = {}  # model_name → SentenceTransformer
_rerank_models: dict[str, Any] = {}  # model_name → CrossEncoder
_tool_indexes: dict[str, dict] = {}  # agent_id → {index, tool_names, ts}

TOOL_INDEX_TTL = 3600  # 1 hour

DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
EMBED_MODEL_REVISION = os.environ.get("EMBEDDING_MODEL_REVISION", "")
RERANK_MODEL_REVISION = os.environ.get("RERANK_MODEL_REVISION", "")


def _get_embed_model(model_name: str):
    if model_name != DEFAULT_EMBED_MODEL:
        raise HTTPException(400, "Embedding model is not approved")
    if model_name not in _embed_models:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading embedding model: {model_name}")
        if not EMBED_MODEL_REVISION:
            raise HTTPException(503, "Embedding model revision is not configured")
        _embed_models[model_name] = SentenceTransformer(
            model_name, revision=EMBED_MODEL_REVISION, local_files_only=True
        )
    return _embed_models[model_name]


def _get_rerank_model(model_name: str):
    if model_name != DEFAULT_RERANK_MODEL:
        raise HTTPException(400, "Reranking model is not approved")
    if model_name not in _rerank_models:
        from sentence_transformers import CrossEncoder

        logger.info(f"Loading cross-encoder model: {model_name}")
        if not RERANK_MODEL_REVISION:
            raise HTTPException(503, "Reranking model revision is not configured")
        _rerank_models[model_name] = CrossEncoder(
            model_name, revision=RERANK_MODEL_REVISION, local_files_only=True
        )
    return _rerank_models[model_name]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("ML_API_KEY", "")
    if len(key) < 32 or key.startswith("dev-"):
        raise RuntimeError(
            "ML_API_KEY must be a nondefault secret of at least 32 characters"
        )
    # Eagerly load default models
    try:
        _get_embed_model(DEFAULT_EMBED_MODEL)
        logger.info("Default embedding model loaded")
    except Exception as e:
        logger.warning(f"Could not pre-load embedding model: {e}")
    yield


app = FastAPI(title="Synkora ML Service", lifespan=lifespan)


@app.middleware("http")
async def authenticate_service(request: Request, call_next):
    if request.url.path != "/health":
        key = os.environ.get("ML_API_KEY", "")
        supplied = request.headers.get("X-ML-Key", "")
        if len(key) < 32 or not hmac.compare_digest(key, supplied):
            return JSONResponse(
                {"detail": "Service authentication required"}, status_code=401
            )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=256)
    model: str = DEFAULT_EMBED_MODEL


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimension: int


class RerankResultItem(BaseModel):
    id: str
    original_score: float
    rerank_score: float
    combined_score: float
    payload: dict[str, Any]
    rank: int


class RerankRequest(BaseModel):
    query: str
    results: list[dict[str, Any]] = Field(max_length=256)
    top_k: int = 5
    score_weight: float = 0.3
    model: str = DEFAULT_RERANK_MODEL


class RerankResponse(BaseModel):
    results: list[RerankResultItem]


class ToolDef(BaseModel):
    name: str
    description: str = ""
    example_queries: list[str] = []


class ToolInitRequest(BaseModel):
    agent_id: str
    tools: list[ToolDef] = Field(max_length=2000)


class ToolInitResponse(BaseModel):
    success: bool
    count: int


class ToolSearchRequest(BaseModel):
    agent_id: str
    query: str
    limit: int = Field(default=15, ge=1, le=100)
    threshold: float = 0.3


class ToolSearchResponse(BaseModel):
    tools: list[dict[str, Any]]  # [{name, score}]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    if not req.texts:
        raise HTTPException(400, "texts must not be empty")
    try:
        model = _get_embed_model(req.model)
        embeddings = model.encode(req.texts, convert_to_numpy=True)
        return EmbedResponse(
            embeddings=[emb.tolist() for emb in embeddings],
            dimension=int(embeddings.shape[1]),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(500, "ML operation failed") from e


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest):
    if not req.results:
        return RerankResponse(results=[])
    try:
        model = _get_rerank_model(req.model)
        pairs = []
        for r in req.results:
            text = r.get("payload", {}).get("text", "") or str(r.get("payload", {}))
            pairs.append([req.query, text])

        raw_scores = model.predict(pairs)
        min_s, max_s = float(min(raw_scores)), float(max(raw_scores))
        score_range = max_s - min_s if max_s != min_s else 1.0
        norm_scores = [(s - min_s) / score_range for s in raw_scores]

        items = []
        for i, (result, rerank_score) in enumerate(
            zip(req.results, norm_scores, strict=False)
        ):
            original_score = float(result.get("score", 0))
            combined = (
                1 - req.score_weight
            ) * rerank_score + req.score_weight * original_score
            items.append(
                RerankResultItem(
                    id=result.get("id", f"result_{i}"),
                    original_score=original_score,
                    rerank_score=float(rerank_score),
                    combined_score=combined,
                    payload=result.get("payload", {}),
                    rank=0,
                )
            )

        items.sort(key=lambda x: x.combined_score, reverse=True)
        top_items = items[: req.top_k]
        for rank, item in enumerate(top_items, 1):
            item.rank = rank

        return RerankResponse(results=top_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rerank error: {e}")
        raise HTTPException(500, "ML operation failed") from e


@app.post("/v1/tools/initialize", response_model=ToolInitResponse)
async def tools_initialize(req: ToolInitRequest):
    if not req.tools:
        return ToolInitResponse(success=True, count=0)
    try:
        import faiss

        model = _get_embed_model(DEFAULT_EMBED_MODEL)

        texts: list[str] = []
        tool_names: list[str] = []
        for tool in req.tools:
            if not tool.name:
                continue
            name_words = tool.name.replace("internal_", "").replace("_", " ")
            parts = [name_words, tool.description] + list(tool.example_queries)
            texts.append(" ".join(parts))
            tool_names.append(tool.name)

        if not texts:
            return ToolInitResponse(success=True, count=0)

        embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        now = time.time()
        for key in list(_tool_indexes):
            if now - _tool_indexes[key]["ts"] > TOOL_INDEX_TTL:
                del _tool_indexes[key]
        if req.agent_id not in _tool_indexes and len(_tool_indexes) >= 1000:
            raise HTTPException(503, "Tool index capacity reached")
        _tool_indexes[req.agent_id] = {
            "index": index,
            "tool_names": tool_names,
            "ts": time.time(),
        }
        logger.info(
            f"Tool index built for agent {req.agent_id}: {len(tool_names)} tools"
        )
        return ToolInitResponse(success=True, count=len(tool_names))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tool init error: {e}")
        raise HTTPException(500, "ML operation failed") from e


@app.post("/v1/tools/search", response_model=ToolSearchResponse)
async def tools_search(req: ToolSearchRequest):
    # Evict expired indexes
    now = time.time()
    expired = [
        aid for aid, v in _tool_indexes.items() if now - v["ts"] > TOOL_INDEX_TTL
    ]
    for aid in expired:
        del _tool_indexes[aid]

    entry = _tool_indexes.get(req.agent_id)
    if not entry:
        return ToolSearchResponse(tools=[])

    try:
        import faiss

        model = _get_embed_model(DEFAULT_EMBED_MODEL)
        query_emb = model.encode([req.query], convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(query_emb)

        k = min(req.limit, len(entry["tool_names"]))
        scores, indices = entry["index"].search(query_emb, k)

        tools = []
        for score, idx in zip(scores[0], indices[0], strict=True):
            if idx >= 0 and float(score) >= req.threshold:
                tools.append({"name": entry["tool_names"][idx], "score": float(score)})

        return ToolSearchResponse(tools=tools)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tool search error: {e}")
        raise HTTPException(500, "ML operation failed") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5002)
