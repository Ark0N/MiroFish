"""
Graph entity reader and filter service.
Reads nodes from the Graphiti/Neo4j knowledge graph and filters entities
matching predefined entity types.

Replaces zep_entity_reader.py.
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from graphiti_core.nodes import EntityNode as GraphitiNode
from graphiti_core.edges import EntityEdge as GraphitiEdge

from ..config import Config
from ..utils.logger import get_logger
from ..utils.graph_paging import fetch_all_nodes, fetch_all_edges
from ..utils.graphiti_manager import GraphitiManager, run_async

logger = get_logger('mirofish.graph_entity_reader')

T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure (unchanged from Zep version)."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """Get entity type (excluding default Entity/Node labels)."""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection."""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


def _graphiti_node_to_dict(node) -> Dict[str, Any]:
    """Convert a Graphiti EntityNode to a dict matching our format."""
    return {
        "uuid": node.uuid,
        "name": node.name or "",
        "labels": node.labels or [],
        "summary": node.summary or "",
        "attributes": node.attributes or {},
    }


def _graphiti_edge_to_dict(edge) -> Dict[str, Any]:
    """Convert a Graphiti EntityEdge to a dict matching our format."""
    return {
        "uuid": edge.uuid,
        "name": edge.name or "",
        "fact": edge.fact or "",
        "source_node_uuid": edge.source_node_uuid,
        "target_node_uuid": edge.target_node_uuid,
        "attributes": {},
    }


class GraphEntityReader:
    """
    Graph entity reader and filter service.

    Main functions:
    1. Read all nodes from the knowledge graph
    2. Filter nodes matching predefined entity types
    3. Get related edges and connected nodes for each entity
    """

    def __init__(self):
        # No API key needed - uses GraphitiManager singleton
        pass

    def _call_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """API call with exponential backoff retry."""
        last_exception = None
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Graph {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Graph {operation_name} failed after {max_retries} attempts: {str(e)}")

        raise last_exception

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all nodes for a graph (by group_id)."""
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        nodes = fetch_all_nodes(graph_id)

        nodes_data = [_graphiti_node_to_dict(node) for node in nodes]

        logger.info(f"Fetched {len(nodes_data)} nodes")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all edges for a graph (by group_id)."""
        logger.info(f"Fetching all edges for graph {graph_id}...")

        edges = fetch_all_edges(graph_id)

        edges_data = [_graphiti_edge_to_dict(edge) for edge in edges]

        logger.info(f"Fetched {len(edges_data)} edges")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """Get all edges related to a node (with retry)."""
        try:
            graphiti = GraphitiManager.get_instance()
            driver = graphiti.driver

            edges = self._call_with_retry(
                func=lambda: run_async(
                    GraphitiEdge.get_by_node_uuid(driver, node_uuid)
                ),
                operation_name=f"get node edges (node={node_uuid[:8]}...)"
            )

            return [_graphiti_edge_to_dict(edge) for edge in edges]
        except Exception as e:
            logger.warning(f"Failed to get edges for node {node_uuid}: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        Filter nodes matching predefined entity types.

        Filtering logic:
        - Skip nodes whose labels only contain "Entity" or "Node"
        - Keep nodes with custom labels beyond "Entity"/"Node"
        """
        logger.info(f"Filtering entities for graph {graph_id}...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []

        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            labels = node.get("labels", [])

            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"Filtering complete: total {total_count}, matched {len(filtered_entities)}, "
                   f"entity types: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """Get a single entity with full context (edges and related nodes)."""
        try:
            graphiti = GraphitiManager.get_instance()
            driver = graphiti.driver

            node = self._call_with_retry(
                func=lambda: run_async(
                    GraphitiNode.get_by_group_ids(driver, [graph_id], limit=None)
                ),
                operation_name=f"get node detail (uuid={entity_uuid[:8]}...)"
            )

            # Find the specific node
            target_node = None
            for n in node:
                if n.uuid == entity_uuid:
                    target_node = n
                    break

            if not target_node:
                return None

            edges = self.get_node_edges(entity_uuid)

            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=target_node.uuid,
                name=target_node.name or "",
                labels=target_node.labels or [],
                summary=target_node.summary or "",
                attributes=target_node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"Failed to get entity {entity_uuid}: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """Get all entities of a specific type."""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
