"""Embedding service — delegates sentence_transformers to the ML microservice."""

import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

_background_loop: asyncio.AbstractEventLoop | None = None
_background_loop_lock = threading.Lock()


def _get_background_loop() -> asyncio.AbstractEventLoop:
    """Lazily start one dedicated background event loop, reused for the life of
    the process.

    ``get_ml_client()`` (``src.core.ml_client``) caches a single
    ``httpx.AsyncClient`` at module scope, bound to whichever event loop is
    running the first time it's used. A previous implementation ran each call
    via ``asyncio.run()`` in a fresh thread, tearing the loop down afterwards —
    every call after the first then failed with "RuntimeError: Event loop is
    closed" when it tried to reuse that cached client. Running everything on
    one persistent loop keeps the client's connections valid across calls.
    """
    global _background_loop
    with _background_loop_lock:
        if _background_loop is None or _background_loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True).start()
            _background_loop = loop
    return _background_loop


def _run_async(coro) -> object:
    """Run an async coroutine safely from synchronous code.

    Schedules the coroutine on the shared background event loop so this works
    whether or not there is already a running event loop in the calling
    context (FastAPI, Celery, tests, etc.), without tearing the loop down
    between calls.
    """
    loop = _get_background_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


class EmbeddingService:
    """Service for generating text embeddings using multiple providers.

    The ``sentence_transformers`` and ``huggingface`` providers are served by the
    ML microservice (``synkora-ml``) so that the API image does not need to bundle
    those heavy packages.  All other providers (OPENAI, cohere, LITELLM) are still
    executed in-process.
    """

    def __init__(
        self, provider: str = "SENTENCE_TRANSFORMERS", model_name: str = "all-MiniLM-L6-v2", config: dict | None = None
    ):
        # KnowledgeBase.embedding_provider (models/knowledge_base.py) is an UPPERCASE
        # StrEnum, and every caller passes its `.value` straight through. Normalize
        # here so provider dispatch is case-insensitive regardless of caller.
        self.provider = provider.upper() if provider else provider
        self.model_name = model_name
        self.config = config or {}
        self.model = None
        self.client = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the embedding model based on provider."""
        try:
            logger.info(f"Loading embedding model: {self.provider}/{self.model_name}")

            if self.provider in ("SENTENCE_TRANSFORMERS", "HUGGINGFACE"):
                # Handled by ML microservice — no local model to load
                logger.info(f"Using ML microservice for provider={self.provider}")

            elif self.provider == "OPENAI":
                import openai

                api_key = self.config.get("api_key")
                if not api_key:
                    raise ValueError("OpenAI API key not provided in embedding_config")
                self.client = openai.OpenAI(api_key=api_key)

            elif self.provider == "COHERE":
                import cohere

                api_key = self.config.get("api_key")
                if not api_key:
                    raise ValueError("Cohere API key not provided in embedding_config")
                self.client = cohere.Client(api_key)

            elif self.provider == "LITELLM":
                import litellm

                self.client = litellm
                if self.config.get("api_base"):
                    litellm.api_base = self.config["api_base"]
                logger.info(f"Initialized LiteLLM for embeddings with model: {self.model_name}")

            else:
                raise ValueError(f"Unsupported embedding provider: {self.provider}")

            logger.info(f"Successfully loaded model: {self.provider}/{self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        try:
            if self.provider in ("SENTENCE_TRANSFORMERS", "HUGGINGFACE"):
                from src.core.ml_client import get_ml_client

                client = get_ml_client()
                return _run_async(client.embed_text(text, model=self.model_name))

            elif self.provider == "OPENAI":
                response = self.client.embeddings.create(model=self.model_name, input=text)
                return response.data[0].embedding

            elif self.provider == "COHERE":
                response = self.client.embed(texts=[text], model=self.model_name)
                return response.embeddings[0]

            elif self.provider == "LITELLM":
                import litellm

                response = litellm.embedding(
                    model=self.model_name,
                    input=[text],
                    api_key=self.config.get("api_key"),
                    api_base=self.config.get("api_base"),
                )
                return response.data[0]["embedding"]

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches."""
        try:
            if self.provider in ("SENTENCE_TRANSFORMERS", "HUGGINGFACE"):
                from src.core.ml_client import get_ml_client

                client = get_ml_client()
                # ML service handles batching internally
                return _run_async(client.embed(texts, model=self.model_name))

            elif self.provider == "OPENAI":
                response = self.client.embeddings.create(model=self.model_name, input=texts)
                return [item.embedding for item in response.data]

            elif self.provider == "COHERE":
                response = self.client.embed(texts=texts, model=self.model_name)
                return response.embeddings

            elif self.provider == "LITELLM":
                import litellm

                response = litellm.embedding(
                    model=self.model_name,
                    input=texts,
                    api_key=self.config.get("api_key"),
                    api_base=self.config.get("api_base"),
                )
                return [item["embedding"] for item in response.data]

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        if "dimension" in self.config:
            return self.config["dimension"]

        if self.provider in ("SENTENCE_TRANSFORMERS", "HUGGINGFACE"):
            from src.core.ml_client import get_ml_client

            client = get_ml_client()
            return _run_async(client.get_embedding_dimension(model=self.model_name))

        raise ValueError(
            f"Embedding dimension not configured for provider '{self.provider}'. "
            "Please specify 'dimension' in embedding_config."
        )
