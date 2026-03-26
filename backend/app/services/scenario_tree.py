"""
Scenario tree builder.

Builds a tree of mutually exclusive future scenarios from predictions.
Each branch is a combination of prediction outcomes weighted by joint
probability. Enables "best case / worst case / most likely" framing.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from itertools import product

from ..utils.logger import get_logger

logger = get_logger('mirofish.scenario_tree')


@dataclass
class ScenarioNode:
    """A node in the scenario tree (one prediction outcome)."""
    prediction_idx: int
    event: str
    outcome: bool  # True = event happens, False = doesn't
    probability: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_idx": self.prediction_idx,
            "event": self.event,
            "outcome": self.outcome,
            "probability": round(self.probability, 4),
        }


@dataclass
class Scenario:
    """A complete scenario (path through the tree)."""
    scenario_id: str
    nodes: List[ScenarioNode]
    joint_probability: float
    label: str  # "best_case", "worst_case", "most_likely", or "scenario_N"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "joint_probability": round(self.joint_probability, 6),
            "label": self.label,
            "description": self._describe(),
        }

    def _describe(self) -> str:
        happens = [n.event for n in self.nodes if n.outcome]
        doesnt = [n.event for n in self.nodes if not n.outcome]
        parts = []
        if happens:
            parts.append("Happens: " + "; ".join(happens))
        if doesnt:
            parts.append("Doesn't happen: " + "; ".join(doesnt))
        return " | ".join(parts) if parts else "No events"


class ScenarioTreeBuilder:
    """Build scenario trees from predictions."""

    def build_tree(
        self,
        predictions: List[Dict[str, Any]],
        max_predictions: int = 6,
    ) -> Dict[str, Any]:
        """Build a complete scenario tree from predictions.

        For N predictions, generates 2^N scenarios (capped at max_predictions).
        Labels the best, worst, and most likely scenarios.

        Args:
            predictions: List of prediction dicts with 'event' and 'probability'
            max_predictions: Max predictions to include (to prevent combinatorial explosion)

        Returns:
            Dict with scenarios, labeled special cases, and summary stats
        """
        # Limit to top predictions by probability spread
        preds = predictions[:max_predictions]

        if not preds:
            return {"scenarios": [], "best_case": None, "worst_case": None, "most_likely": None}

        # Generate all outcome combinations
        scenarios = []
        for i, outcomes in enumerate(product([True, False], repeat=len(preds))):
            nodes = []
            joint_prob = 1.0

            for j, (pred, outcome) in enumerate(zip(preds, outcomes)):
                prob = pred.get("probability", 0.5)
                outcome_prob = prob if outcome else (1 - prob)
                joint_prob *= outcome_prob

                nodes.append(ScenarioNode(
                    prediction_idx=j,
                    event=pred.get("event", f"Event {j}"),
                    outcome=outcome,
                    probability=outcome_prob,
                ))

            scenarios.append(Scenario(
                scenario_id=f"scenario_{i}",
                nodes=nodes,
                joint_probability=joint_prob,
                label=f"scenario_{i}",
            ))

        # Sort by joint probability
        scenarios.sort(key=lambda s: s.joint_probability, reverse=True)

        # Label special scenarios
        most_likely = scenarios[0] if scenarios else None
        if most_likely:
            most_likely.label = "most_likely"

        # Best case: all events happen
        best = next((s for s in scenarios if all(n.outcome for n in s.nodes)), None)
        if best:
            best.label = "best_case"

        # Worst case: no events happen
        worst = next((s for s in scenarios if not any(n.outcome for n in s.nodes)), None)
        if worst:
            worst.label = "worst_case"

        return {
            "scenarios": [s.to_dict() for s in scenarios[:20]],  # Cap output
            "total_scenarios": len(scenarios),
            "best_case": best.to_dict() if best else None,
            "worst_case": worst.to_dict() if worst else None,
            "most_likely": most_likely.to_dict() if most_likely else None,
            "num_predictions": len(preds),
        }
