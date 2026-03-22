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

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.graphiti')


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
    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            embedding_model=model,
            embedding_dim=dim,
            api_key="ollama",  # Ollama ignores this but the client requires it
            base_url=base_url,
        )
    )


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
    """Run an async coroutine from synchronous Flask/thread code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context — run in a separate thread to avoid deadlock
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)
