"""
Prediction dependency graph.

Models causal dependencies between predictions. If Prediction A causes
Prediction B, a change in A's probability should propagate to B.
Stored as a directed graph in the prediction set.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_deps')


@dataclass
class DependencyEdge:
    """A causal dependency between two predictions."""
    source_idx: int  # Prediction that causes
    target_idx: int  # Prediction that is affected
    strength: float  # 0-1, how strongly source influences target
    relationship: str  # "causes", "enables", "prevents", "amplifies"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_idx": self.source_idx,
            "target_idx": self.target_idx,
            "strength": round(self.strength, 3),
            "relationship": self.relationship,
        }


@dataclass
class DependencyGraph:
    """Directed graph of prediction dependencies."""
    edges: List[DependencyEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edges": [e.to_dict() for e in self.edges],
            "num_edges": len(self.edges),
        }

    def get_dependents(self, source_idx: int) -> List[DependencyEdge]:
        """Get all predictions that depend on the given prediction."""
        return [e for e in self.edges if e.source_idx == source_idx]

    def get_dependencies(self, target_idx: int) -> List[DependencyEdge]:
        """Get all predictions that the given prediction depends on."""
        return [e for e in self.edges if e.target_idx == target_idx]


class PredictionDependencyManager:
    """Manage causal dependencies and propagate probability changes."""

    # Keywords that suggest causal relationships
    CAUSAL_KEYWORDS = {
        "causes": {"cause", "lead", "trigger", "result", "create", "produce"},
        "enables": {"enable", "allow", "facilitate", "support", "open"},
        "prevents": {"prevent", "block", "stop", "hinder", "reduce"},
        "amplifies": {"amplify", "increase", "accelerate", "worsen", "intensify"},
    }

    def detect_dependencies(
        self,
        predictions: List[Dict[str, Any]],
    ) -> DependencyGraph:
        """Auto-detect causal dependencies between predictions.

        Uses keyword overlap and semantic heuristics to identify
        cause-effect relationships.

        Args:
            predictions: List of prediction dicts with 'event', 'evidence', etc.

        Returns:
            DependencyGraph with detected edges
        """
        edges = []

        for i, pred_a in enumerate(predictions):
            event_a = pred_a.get("event", "").lower()
            evidence_a = " ".join(pred_a.get("evidence", [])).lower()
            risks_a = " ".join(pred_a.get("risk_factors", [])).lower()
            text_a = f"{event_a} {evidence_a} {risks_a}"

            for j, pred_b in enumerate(predictions):
                if i == j:
                    continue

                event_b = pred_b.get("event", "").lower()
                evidence_b = " ".join(pred_b.get("evidence", [])).lower()
                text_b = f"{event_b} {evidence_b}"

                # Check if A is mentioned in B's evidence or text
                words_a = set(event_a.split()) - {"the", "a", "an", "is", "of", "in", "to", "and", "or"}
                words_b_all = set(text_b.split())

                overlap = len(words_a & words_b_all)
                overlap_ratio = overlap / len(words_a) if words_a else 0

                if overlap_ratio >= 0.3:
                    # Determine relationship type
                    rel_type, strength = self._classify_relationship(text_a, text_b)
                    if strength > 0.2:
                        edges.append(DependencyEdge(
                            source_idx=i,
                            target_idx=j,
                            strength=strength,
                            relationship=rel_type,
                        ))

        return DependencyGraph(edges=edges)

    def propagate_change(
        self,
        predictions: List[Dict[str, Any]],
        graph: DependencyGraph,
        changed_idx: int,
        probability_delta: float,
    ) -> List[Dict[str, Any]]:
        """Propagate a probability change through the dependency graph.

        When prediction at changed_idx changes by probability_delta,
        propagate the effect to all dependent predictions.

        Args:
            predictions: List of prediction dicts (modified in-place)
            graph: The dependency graph
            changed_idx: Index of the prediction that changed
            probability_delta: Change in probability (-1 to 1)

        Returns:
            List of predictions with propagated changes
        """
        result = [dict(p) for p in predictions]
        visited = set()

        self._propagate_recursive(result, graph, changed_idx, probability_delta, visited)

        return result

    def _propagate_recursive(
        self,
        predictions: List[Dict[str, Any]],
        graph: DependencyGraph,
        source_idx: int,
        delta: float,
        visited: set,
        depth: int = 0,
    ) -> None:
        """Recursively propagate changes through the graph."""
        if depth > 5 or source_idx in visited:
            return  # Prevent infinite loops and deep recursion

        visited.add(source_idx)

        for edge in graph.get_dependents(source_idx):
            target = edge.target_idx
            if target in visited or target >= len(predictions):
                continue

            # Compute propagated delta
            if edge.relationship == "prevents":
                propagated = -delta * edge.strength
            elif edge.relationship == "amplifies":
                propagated = delta * edge.strength * 1.5
            else:
                propagated = delta * edge.strength

            # Apply to target
            current_prob = predictions[target].get("probability", 0.5)
            new_prob = max(0.05, min(0.99, current_prob + propagated))
            predictions[target]["probability"] = round(new_prob, 4)

            # Continue propagation (attenuated)
            if abs(propagated) > 0.01:
                self._propagate_recursive(
                    predictions, graph, target, propagated * 0.5, visited, depth + 1
                )

    def _classify_relationship(self, text_a: str, text_b: str) -> Tuple[str, float]:
        """Classify the relationship type and strength between two texts."""
        combined = f"{text_a} {text_b}"

        best_type = "causes"
        best_score = 0.0

        for rel_type, keywords in self.CAUSAL_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_type = rel_type

        # Normalize strength
        strength = min(1.0, best_score / 3.0) if best_score > 0 else 0.3

        return best_type, strength
