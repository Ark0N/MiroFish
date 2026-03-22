"""
Ontology store for Graphiti integration.

Caches ontology definitions per group_id so they can be passed
to each add_episode() call. Graphiti v0.11.6 only supports
entity_types (not edge_types) in add_episode().
"""

import threading
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

from ..utils.logger import get_logger

logger = get_logger('mirofish.ontology_store')

# Reserved Neo4j/Graphiti property names
_RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}


def _safe_attr_name(attr_name: str) -> str:
    """Prefix reserved attribute names to avoid collisions."""
    if attr_name.lower() in _RESERVED_NAMES:
        return f"entity_{attr_name}"
    return attr_name


# group_id -> {"entity_types": dict[str, BaseModel]}
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


def store_ontology(group_id: str, mirofish_ontology: Dict[str, Any]):
    """
    Convert MiroFish ontology format into Graphiti entity_types and cache it.

    MiroFish format:
        {"entity_types": [{"name": "Person", "description": "...", "attributes": [{"name": "age", "description": "..."}]}],
         "edge_types": [...]}

    Graphiti format (v0.11.6):
        {"entity_types": {"Person": PersonModel}}

    Note: edge_types are not supported in Graphiti's add_episode() API,
    so we only convert entity_types.
    """
    entity_types = {}

    for entity_def in mirofish_ontology.get("entity_types", []):
        name = entity_def["name"]
        description = entity_def.get("description", f"A {name} entity.")

        # Build Pydantic model fields dynamically
        field_definitions: Dict[str, Any] = {}
        annotations: Dict[str, Any] = {}

        for attr_def in entity_def.get("attributes", []):
            attr_name = _safe_attr_name(attr_def["name"])
            attr_desc = attr_def.get("description", attr_name)
            field_definitions[attr_name] = Field(description=attr_desc, default=None)
            annotations[attr_name] = Optional[str]

        # Create dynamic Pydantic BaseModel subclass
        namespace = {"__annotations__": annotations, **field_definitions}
        model_cls = type(name, (BaseModel,), namespace)
        model_cls.__doc__ = description

        entity_types[name] = model_cls

    with _cache_lock:
        _cache[group_id] = {"entity_types": entity_types}
    logger.info(f"Stored ontology for group_id={group_id}: {len(entity_types)} entity types")


def get_ontology(group_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached ontology for a group_id."""
    return _cache.get(group_id)


def get_entity_types(group_id: str) -> Optional[Dict[str, type]]:
    """Get entity_types dict for passing to add_episode()."""
    cached = _cache.get(group_id)
    if cached:
        return cached.get("entity_types")
    return None


def clear(group_id: str):
    """Remove cached ontology for a group_id."""
    with _cache_lock:
        _cache.pop(group_id, None)
