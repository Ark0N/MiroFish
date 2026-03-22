"""
Graph building service.
Uses Graphiti + Neo4j to construct knowledge graphs.
Replaces Zep Cloud API calls with self-hosted Graphiti.
"""

import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from graphiti_core.nodes import EpisodeType

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.graph_paging import fetch_all_nodes, fetch_all_edges
from ..utils.graphiti_manager import GraphitiManager, run_async
from ..utils.ontology_store import store_ontology, get_entity_types
from .text_processor import TextProcessor


@dataclass
class GraphInfo:
    """Graph information."""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    Graph building service.
    Uses Graphiti + Neo4j to construct knowledge graphs.
    """

    def __init__(self):
        self.task_manager = TaskManager()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        Build graph asynchronously.

        Args:
            text: Input text
            ontology: Ontology definition (from ontology generator)
            graph_name: Graph name
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap size
            batch_size: Chunks per batch

        Returns:
            Task ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int
    ):
        """Graph building worker thread."""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph construction..."
            )

            # 1. Generate group_id (no API call needed, Graphiti uses group_id for isolation)
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}"
            )

            # 2. Store ontology in cache (for use in add_episode calls)
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology configured"
            )

            # 3. Split text into chunks
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks"
            )

            # 4. Add episodes to graph (Graphiti processes inline, no separate wait needed)
            self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.65),  # 20-85%
                    message=msg
                )
            )

            # 5. Build communities
            self.task_manager.update_task(
                task_id,
                progress=85,
                message="Building communities..."
            )

            try:
                graphiti = GraphitiManager.get_instance()
                run_async(graphiti.build_communities(group_ids=[graph_id]))
            except Exception as e:
                # Community building is optional, don't fail the whole build
                from ..utils.logger import get_logger
                get_logger('mirofish.graph_builder').warning(
                    f"Community building failed (non-fatal): {e}"
                )

            # 6. Get graph info
            self.task_manager.update_task(
                task_id,
                progress=90,
                message="Fetching graph info..."
            )

            graph_info = self._get_graph_info(graph_id)

            # Complete
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """Create a new graph (generates a group_id, no API call needed)."""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        # Graphiti doesn't need an explicit "create graph" call.
        # The group_id is used to isolate data in add_episode().
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Store ontology for use in subsequent add_episode() calls."""
        store_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """Add text chunks to graph as episodes. Returns episode UUIDs."""
        episode_uuids = []
        total_chunks = len(chunks)
        entity_types = get_entity_types(graph_id)
        graphiti = GraphitiManager.get_instance()

        for i, chunk in enumerate(chunks):
            chunk_num = i + 1

            if progress_callback:
                progress = chunk_num / total_chunks
                progress_callback(
                    f"Processing chunk {chunk_num}/{total_chunks}...",
                    progress
                )

            try:
                result = run_async(graphiti.add_episode(
                    name=f"chunk_{chunk_num}",
                    episode_body=chunk,
                    source_description="MiroFish document upload",
                    reference_time=datetime.now(),
                    source=EpisodeType.text,
                    group_id=graph_id,
                    entity_types=entity_types,
                ))

                # Collect episode UUID from result
                if hasattr(result, 'episode') and result.episode:
                    ep_uuid = getattr(result.episode, 'uuid', None)
                    if ep_uuid:
                        episode_uuids.append(ep_uuid)

            except Exception as e:
                if progress_callback:
                    progress_callback(f"Chunk {chunk_num} failed: {str(e)}", 0)
                raise

        return episode_uuids

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """Get graph information."""
        nodes = fetch_all_nodes(graph_id)
        edges = fetch_all_edges(graph_id)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        Get complete graph data with detailed information.

        Args:
            graph_id: Graph ID (group_id)

        Returns:
            Dict with nodes and edges including temporal info
        """
        nodes = fetch_all_nodes(graph_id)
        edges = fetch_all_edges(graph_id)

        # Build node name map
        node_map = {}
        for node in nodes:
            node_map[node.uuid] = node.name or ""

        nodes_data = []
        for node in nodes:
            created_at = getattr(node, 'created_at', None)
            if created_at:
                created_at = str(created_at)

            nodes_data.append({
                "uuid": node.uuid,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": created_at,
            })

        edges_data = []
        for edge in edges:
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)

            episodes = getattr(edge, 'episodes', None)
            if episodes and not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(e) for e in episodes]

            fact_type = edge.name or ""

            edges_data.append({
                "uuid": edge.uuid,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": fact_type,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        """Delete a graph by removing all nodes with the given group_id."""
        graphiti = GraphitiManager.get_instance()
        driver = graphiti.driver

        async def _delete():
            async with driver.session() as session:
                await session.run(
                    "MATCH (n {group_id: $gid}) DETACH DELETE n",
                    {"gid": graph_id}
                )

        run_async(_delete())
