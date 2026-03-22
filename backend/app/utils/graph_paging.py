"""Graph node/edge retrieval using Graphiti + Neo4j.

Replaces zep_paging.py. Graphiti returns all results via
EntityNode.get_by_group_ids / EntityEdge.get_by_group_ids,
so cursor-based pagination is handled internally.
"""

from __future__ import annotations

import time
from typing import Any

from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge

from .graphiti_manager import GraphitiManager, run_async
from .logger import get_logger

logger = get_logger('mirofish.graph_paging')

_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0  # seconds, doubles each retry


def _with_retry(func, max_retries: int = _DEFAULT_MAX_RETRIES,
                retry_delay: float = _DEFAULT_RETRY_DELAY,
                description: str = "operation"):
    """Execute a function with exponential backoff retry."""
    last_exception = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Graph {description} attempt {attempt + 1} failed: {str(e)[:100]}, "
                    f"retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Graph {description} failed after {max_retries} attempts: {str(e)}")

    raise last_exception


def fetch_all_nodes(
    group_id: str,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """Fetch all entity nodes for a group_id, up to max_items."""
    graphiti = GraphitiManager.get_instance()
    driver = graphiti.driver

    nodes = _with_retry(
        lambda: run_async(
            EntityNode.get_by_group_ids(driver, [group_id], limit=max_items)
        ),
        max_retries=max_retries,
        retry_delay=retry_delay,
        description=f"fetch nodes (group={group_id})",
    )

    if len(nodes) >= max_items:
        logger.warning(f"Node count reached limit ({max_items}) for group {group_id}")

    return nodes


def fetch_all_edges(
    group_id: str,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """Fetch all entity edges for a group_id."""
    graphiti = GraphitiManager.get_instance()
    driver = graphiti.driver

    edges = _with_retry(
        lambda: run_async(
            EntityEdge.get_by_group_ids(driver, [group_id])
        ),
        max_retries=max_retries,
        retry_delay=retry_delay,
        description=f"fetch edges (group={group_id})",
    )

    return edges
