"""
Prediction chaining engine.

Computes joint probabilities for compound events using the dependency
graph. Supports AND, OR, and conditional (THEN) operations.
"""

import math
from typing import Dict, List, Any, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.chaining')


class PredictionChainingEngine:
    """Compute joint probabilities for compound prediction events."""

    def joint_and(self, prob_a: float, prob_b: float, dependency_strength: float = 0.0) -> float:
        """P(A AND B) with optional positive dependency.

        For independent events: P(A AND B) = P(A) * P(B)
        With dependency: interpolates toward min(P(A), P(B))

        Args:
            prob_a, prob_b: Individual probabilities
            dependency_strength: 0 = independent, 1 = fully dependent
        """
        independent = prob_a * prob_b
        dependent = min(prob_a, prob_b)
        return independent + dependency_strength * (dependent - independent)

    def joint_or(self, prob_a: float, prob_b: float, dependency_strength: float = 0.0) -> float:
        """P(A OR B) with optional positive dependency.

        For independent: P(A OR B) = P(A) + P(B) - P(A)*P(B)
        With dependency: interpolates toward max(P(A), P(B))
        """
        independent = prob_a + prob_b - prob_a * prob_b
        dependent = max(prob_a, prob_b)
        return independent + dependency_strength * (dependent - independent)

    def conditional(self, prob_a: float, prob_b_given_a: float) -> float:
        """P(A THEN B) = P(A) * P(B|A).

        Args:
            prob_a: Probability of first event
            prob_b_given_a: Probability of second event given first happened
        """
        return prob_a * prob_b_given_a

    def chain_predictions(
        self,
        predictions: List[Dict[str, Any]],
        dependency_edges: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compute compound probabilities from predictions and their dependencies.

        Args:
            predictions: List of prediction dicts with 'probability'
            dependency_edges: List of edge dicts with 'source_idx', 'target_idx', 'strength', 'relationship'

        Returns:
            List of compound prediction results
        """
        if not predictions or not dependency_edges:
            return []

        compounds = []

        for edge in dependency_edges:
            src = edge.get("source_idx", -1)
            tgt = edge.get("target_idx", -1)
            strength = edge.get("strength", 0.5)
            relationship = edge.get("relationship", "causes")

            if src < 0 or tgt < 0 or src >= len(predictions) or tgt >= len(predictions):
                continue

            prob_a = predictions[src].get("probability", 0.5)
            prob_b = predictions[tgt].get("probability", 0.5)
            event_a = predictions[src].get("event", f"Prediction {src}")
            event_b = predictions[tgt].get("event", f"Prediction {tgt}")

            # AND: both happen
            p_and = self.joint_and(prob_a, prob_b, strength)

            # OR: either happens
            p_or = self.joint_or(prob_a, prob_b, strength)

            # THEN: A causes B (conditional)
            # Estimate P(B|A) from dependency strength
            p_b_given_a = min(0.99, prob_b + strength * (1 - prob_b) * 0.5)
            p_then = self.conditional(prob_a, p_b_given_a)

            compounds.append({
                "source_event": event_a,
                "target_event": event_b,
                "source_probability": round(prob_a, 4),
                "target_probability": round(prob_b, 4),
                "relationship": relationship,
                "dependency_strength": round(strength, 3),
                "joint_and": round(p_and, 4),
                "joint_or": round(p_or, 4),
                "conditional_then": round(p_then, 4),
            })

        return compounds

    def best_worst_most_likely(
        self,
        predictions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute best/worst/most-likely scenarios from a set of predictions.

        Best case: all positive predictions happen, negative ones don't
        Worst case: all negative predictions happen, positive ones don't
        Most likely: each prediction independently at its stated probability
        """
        if not predictions:
            return {"best_case": 0.0, "worst_case": 0.0, "most_likely": 0.0}

        probs = [p.get("probability", 0.5) for p in predictions]

        # Most likely: product of each prediction's most probable outcome
        most_likely = 1.0
        for p in probs:
            most_likely *= max(p, 1 - p)

        # Best case: all high-probability events happen
        best = 1.0
        for p in probs:
            best *= p

        # Worst case: all events go the less likely way
        worst = 1.0
        for p in probs:
            worst *= (1 - p)

        return {
            "best_case": round(best, 6),
            "worst_case": round(worst, 6),
            "most_likely": round(most_likely, 6),
            "num_predictions": len(predictions),
        }
