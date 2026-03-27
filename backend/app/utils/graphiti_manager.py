"""
Graphiti client manager and async bridge utilities.
Replaces Zep Cloud with self-hosted Graphiti + Neo4j.
"""

import asyncio
import threading
import concurrent.futures
from typing import Optional, Iterable

from graphiti_core import Graphiti
from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.client import CrossEncoderClient

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.graphiti')


class NoOpCrossEncoder(CrossEncoderClient):
    """Pass-through cross encoder that preserves original order.

    Avoids the default OpenAIRerankerClient which requires OPENAI_API_KEY.
    The cross encoder is only used for search reranking and is not critical
    for graph construction.
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(p, 1.0) for p in passages]


def _create_embedder() -> EmbedderClient:
    """Create the appropriate embedder based on configuration.

    Uses Voyage AI if VOYAGE_API_KEY is set, otherwise uses an
    OpenAI-compatible local server (e.g. Ollama) via EMBEDDER_BASE_URL.
    """
    if Config.VOYAGE_API_KEY:
        import voyageai
        return VoyageAIEmbedder(api_key=Config.VOYAGE_API_KEY)

    # Local embeddings via OpenAI-compatible server (Ollama, TEI, etc.)
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    base_url = Config.EMBEDDER_BASE_URL
    model = Config.EMBEDDER_MODEL
    dim = Config.EMBEDDER_DIM

    logger.info(f"Using local embedder: model={model}, dim={dim}, base_url={base_url}")
    return SafeOllamaEmbedder(
        config=OpenAIEmbedderConfig(
            embedding_model=model,
            embedding_dim=dim,
            api_key="ollama",  # Ollama ignores this but the client requires it
            base_url=base_url,
        )
    )


class SafeOllamaEmbedder(EmbedderClient):
    """OpenAI-compatible embedder that sanitizes empty strings.

    Ollama rejects empty strings with 400 'invalid input'. Graphiti can produce
    entity nodes with empty names during extraction, so we replace blanks with
    a placeholder before sending.
    """

    def __init__(self, config):
        from graphiti_core.embedder.openai import OpenAIEmbedder
        self._inner = OpenAIEmbedder(config=config)
        self.config = config

    @staticmethod
    def _sanitize(text: str) -> str:
        return text if text and text.strip() else "(empty)"

    async def create(self, input_data):
        if isinstance(input_data, str):
            input_data = self._sanitize(input_data)
        elif isinstance(input_data, list):
            if not input_data:
                return []
            if isinstance(input_data[0], str):
                input_data = [self._sanitize(s) for s in input_data]
        try:
            return await self._inner.create(input_data)
        except Exception as e:
            logger.warning(f"Embedding failed for {repr(str(input_data)[:80])}: {e}. Using zeros.")
            return [0.0] * self.config.embedding_dim

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        if not input_data_list:
            return []
        sanitized = [self._sanitize(s) for s in input_data_list]
        try:
            return await self._inner.create_batch(sanitized)
        except Exception as e:
            logger.warning(f"Batch embedding failed ({len(sanitized)} items): {e}. "
                           f"Items: {[repr(s[:50]) for s in sanitized]}. Falling back to one-by-one.")
            results = []
            for item in sanitized:
                try:
                    emb = await self._inner.create(item)
                    results.append(emb)
                except Exception as inner_e:
                    logger.error(f"Single embedding failed for {repr(item[:50])}: {inner_e}. Using zeros.")
                    results.append([0.0] * self.config.embedding_dim)
            return results


class VoyageAIEmbedder(EmbedderClient):
    """Voyage AI embedder implementing Graphiti's EmbedderClient interface."""

    def __init__(self, api_key: Optional[str] = None, model: str = 'voyage-3-lite'):
        import voyageai
        self.api_key = api_key or Config.VOYAGE_API_KEY
        self.model = model
        self._client = voyageai.AsyncClient(api_key=self.api_key)

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        if isinstance(input_data, str):
            texts = [input_data]
        elif isinstance(input_data, list) and len(input_data) > 0 and isinstance(input_data[0], str):
            texts = input_data
        else:
            texts = [str(input_data)]
        result = await self._client.embed(texts, model=self.model, input_type='document')
        return result.embeddings[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        result = await self._client.embed(input_data_list, model=self.model, input_type='document')
        return result.embeddings


class _AsyncBridge:
    """Persistent event loop running in a background thread.

    All Graphiti async operations go through this single loop so that
    Neo4j driver futures stay attached to the same loop.
    """

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _ensure_running(self):
        if self._loop is not None and self._loop.is_running():
            return
        with self._lock:
            if self._loop is not None and self._loop.is_running():
                return
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._loop.run_forever, daemon=True, name="graphiti-loop"
            )
            self._thread.start()
            logger.info("Started persistent async event loop for Graphiti")

    def run(self, coro):
        self._ensure_running()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self):
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._loop = None
            self._thread = None


_bridge = _AsyncBridge()


class GraphitiManager:
    """Thread-safe singleton for the Graphiti client."""

    _instance: Optional[Graphiti] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> Graphiti:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info(f"Initializing Graphiti connection to {Config.NEO4J_URI}")

                    llm_client = AnthropicClient(
                        config=LLMConfig(
                            api_key=Config.LLM_API_KEY,
                            model=Config.LLM_MODEL_NAME,
                            small_model=Config.LLM_MODEL_NAME,
                        )
                    )

                    embedder = _create_embedder()

                    cls._instance = Graphiti(
                        uri=Config.NEO4J_URI,
                        user=Config.NEO4J_USER,
                        password=Config.NEO4J_PASSWORD,
                        llm_client=llm_client,
                        embedder=embedder,
                        cross_encoder=NoOpCrossEncoder(),
                    )

                    run_async(cls._instance.build_indices_and_constraints())
                    logger.info("Graphiti initialized successfully")
        return cls._instance

    @classmethod
    def close(cls):
        if cls._instance is not None:
            try:
                run_async(cls._instance.close())
            except Exception:
                pass
            cls._instance = None

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None


def run_async(coro):
    """Run an async coroutine via the persistent event loop bridge."""
    return _bridge.run(coro)


def run_async_with_timeout(coro, timeout=120):
    """Run an async coroutine with a timeout (seconds)."""
    _bridge._ensure_running()
    future = asyncio.run_coroutine_threadsafe(coro, _bridge._loop)
    return future.result(timeout=timeout)
