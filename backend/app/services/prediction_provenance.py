"""
Prediction provenance tracker.

For each prediction, traces the full chain of evidence: which graph entities
contributed, which agent posts supported it, which simulation rounds were
pivotal. Stored as a provenance DAG per report.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.provenance')


@dataclass
class ProvenanceNode:
    """A node in the provenance DAG."""
    node_id: str
    node_type: str  # "entity", "agent_post", "simulation_round", "consensus", "calibration"
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "metadata": self.metadata,
        }


@dataclass
class ProvenanceEdge:
    """A directed edge in the provenance DAG."""
    source_id: str
    target_id: str
    relationship: str  # "informed_by", "supported_by", "calibrated_by", "extracted_from"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
        }


@dataclass
class PredictionProvenance:
    """Full provenance DAG for a prediction."""
    prediction_idx: int
    event: str
    nodes: List[ProvenanceNode] = field(default_factory=list)
    edges: List[ProvenanceEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_idx": self.prediction_idx,
            "event": self.event,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


class ProvenanceTracker:
    """Build and store provenance DAGs for predictions."""

    def build_provenance(
        self,
        prediction: Dict[str, Any],
        prediction_idx: int,
        agent_posts: Dict[str, List[str]] = None,
        graph_entities: List[Dict[str, Any]] = None,
        consensus_data: Dict[str, Any] = None,
        calibration_data: Dict[str, Any] = None,
    ) -> PredictionProvenance:
        """Build a provenance DAG for a single prediction.

        Args:
            prediction: The prediction dict
            prediction_idx: Index of this prediction
            agent_posts: Agent -> posts mapping for finding supporting posts
            graph_entities: List of entity dicts from the knowledge graph
            consensus_data: Consensus analysis results
            calibration_data: Calibration metadata

        Returns:
            PredictionProvenance with nodes and edges
        """
        provenance = PredictionProvenance(
            prediction_idx=prediction_idx,
            event=prediction.get("event", ""),
        )

        # Root node: the prediction itself
        pred_node_id = f"pred_{prediction_idx}"
        provenance.nodes.append(ProvenanceNode(
            node_id=pred_node_id,
            node_type="prediction",
            label=prediction.get("event", "")[:100],
            metadata={"probability": prediction.get("probability", 0.5)},
        ))

        # Add evidence from prediction
        for i, evidence in enumerate(prediction.get("evidence", [])):
            ev_id = f"evidence_{prediction_idx}_{i}"
            provenance.nodes.append(ProvenanceNode(
                node_id=ev_id,
                node_type="evidence",
                label=evidence[:100],
            ))
            provenance.edges.append(ProvenanceEdge(
                source_id=pred_node_id,
                target_id=ev_id,
                relationship="supported_by",
            ))

        # Add supporting agent posts
        if agent_posts:
            event_words = set(prediction.get("event", "").lower().split())
            post_count = 0
            for agent, posts in agent_posts.items():
                for post in posts:
                    post_words = set(post.lower().split())
                    overlap = len(event_words & post_words)
                    if overlap >= 2 and post_count < 10:
                        post_id = f"post_{agent}_{post_count}"
                        provenance.nodes.append(ProvenanceNode(
                            node_id=post_id,
                            node_type="agent_post",
                            label=f"{agent}: {post[:80]}",
                            metadata={"agent": agent},
                        ))
                        provenance.edges.append(ProvenanceEdge(
                            source_id=pred_node_id,
                            target_id=post_id,
                            relationship="informed_by",
                        ))
                        post_count += 1

        # Add graph entities
        if graph_entities:
            event_lower = prediction.get("event", "").lower()
            for entity in graph_entities[:10]:
                name = entity.get("name", "")
                if name.lower() in event_lower:
                    ent_id = f"entity_{entity.get('uuid', name)}"
                    provenance.nodes.append(ProvenanceNode(
                        node_id=ent_id,
                        node_type="entity",
                        label=name,
                        metadata={"type": entity.get("type", ""), "summary": entity.get("summary", "")[:100]},
                    ))
                    provenance.edges.append(ProvenanceEdge(
                        source_id=pred_node_id,
                        target_id=ent_id,
                        relationship="extracted_from",
                    ))

        # Add consensus node
        if consensus_data:
            cons_id = f"consensus_{prediction_idx}"
            provenance.nodes.append(ProvenanceNode(
                node_id=cons_id,
                node_type="consensus",
                label=f"Agreement: {consensus_data.get('agreement_score', 'N/A')}",
                metadata={
                    "agreement_score": consensus_data.get("agreement_score", 0),
                    "total_agents": consensus_data.get("total_agents_analyzed", 0),
                },
            ))
            provenance.edges.append(ProvenanceEdge(
                source_id=pred_node_id,
                target_id=cons_id,
                relationship="calibrated_by",
            ))

        # Add calibration node
        if calibration_data:
            cal_id = f"calibration_{prediction_idx}"
            provenance.nodes.append(ProvenanceNode(
                node_id=cal_id,
                node_type="calibration",
                label=f"Adjustment: {calibration_data.get('adjustment', 1.0):.2f}x",
                metadata=calibration_data,
            ))
            provenance.edges.append(ProvenanceEdge(
                source_id=pred_node_id,
                target_id=cal_id,
                relationship="calibrated_by",
            ))

        return provenance

    def save_provenance(
        self,
        report_id: str,
        provenances: List[PredictionProvenance],
    ) -> None:
        """Save all provenance DAGs for a report."""
        from .report_agent import ReportManager
        folder = ReportManager._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "provenance.json")
        atomic_write_json(path, [p.to_dict() for p in provenances])

    def load_provenance(self, report_id: str) -> List[Dict[str, Any]]:
        """Load provenance DAGs for a report."""
        from .report_agent import ReportManager
        path = os.path.join(ReportManager._get_report_folder(report_id), "provenance.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
