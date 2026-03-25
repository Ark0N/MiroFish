"""
Ensemble prediction aggregator.

Aggregates predictions from multiple simulations for the same project,
producing weighted-average ensemble predictions that are more robust
than any single simulation's predictions.

Weights are based on:
- Simulation recency (newer simulations weighted higher)
- Agent count (more agents = larger sample = higher weight)
- Consensus strength (stronger consensus = more reliable signal)
"""

import math
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.ensemble')


@dataclass
class EnsemblePrediction:
    """A single prediction aggregated across multiple simulations."""
    event: str
    probability: float  # Weighted average probability
    confidence_interval: List[float] = field(default_factory=lambda: [0.0, 1.0])
    agreement_spread: float = 0.0  # Std dev of probabilities across simulations
    num_simulations: int = 0
    source_predictions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "probability": round(self.probability, 4),
            "confidence_interval": [round(ci, 4) for ci in self.confidence_interval],
            "agreement_spread": round(self.agreement_spread, 4),
            "num_simulations": self.num_simulations,
            "source_predictions": self.source_predictions,
        }


@dataclass
class EnsembleResult:
    """Complete ensemble prediction set."""
    project_id: str
    predictions: List[EnsemblePrediction] = field(default_factory=list)
    num_simulations: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "predictions": [p.to_dict() for p in self.predictions],
            "num_simulations": self.num_simulations,
            "generated_at": self.generated_at,
        }


class EnsemblePredictor:
    """Aggregate predictions from multiple simulations using weighted averaging."""

    def aggregate(
        self,
        project_id: str,
        prediction_sets: List[Dict[str, Any]],
        weights: Optional[List[float]] = None,
    ) -> EnsembleResult:
        """Aggregate multiple prediction sets into ensemble predictions.

        Args:
            project_id: The project these predictions belong to
            prediction_sets: List of PredictionSet.to_dict() outputs
            weights: Optional pre-computed weights (one per prediction_set).
                     If None, defaults to equal weighting.

        Returns:
            EnsembleResult with aggregated predictions
        """
        if not prediction_sets:
            return EnsembleResult(project_id=project_id)

        num_sets = len(prediction_sets)

        if weights is None:
            weights = [1.0 / num_sets] * num_sets
        else:
            # Normalize weights
            total = sum(weights)
            weights = [w / total for w in weights] if total > 0 else [1.0 / num_sets] * num_sets

        # Collect all unique predictions, matched by event text similarity
        all_events = []
        event_probs = {}  # event -> list of (prob, weight, source_info)

        for idx, ps in enumerate(prediction_sets):
            for pred in ps.get("predictions", []):
                event = pred.get("event", "")
                prob = pred.get("probability", 0.5)
                agreement = pred.get("agent_agreement", 0.5)

                # Find matching event or create new
                matched_key = self._find_matching_event(event, list(event_probs.keys()))
                if matched_key:
                    event_probs[matched_key].append({
                        "probability": prob,
                        "weight": weights[idx],
                        "agreement": agreement,
                        "source_idx": idx,
                    })
                else:
                    event_probs[event] = [{
                        "probability": prob,
                        "weight": weights[idx],
                        "agreement": agreement,
                        "source_idx": idx,
                    }]

        # Compute weighted averages for each prediction
        ensemble_predictions = []
        for event, entries in event_probs.items():
            total_weight = sum(e["weight"] for e in entries)
            if total_weight == 0:
                continue

            # Weighted average probability
            avg_prob = sum(e["probability"] * e["weight"] for e in entries) / total_weight

            # Standard deviation of probabilities (spread)
            if len(entries) > 1:
                variance = sum(
                    e["weight"] * (e["probability"] - avg_prob) ** 2
                    for e in entries
                ) / total_weight
                spread = math.sqrt(variance)
            else:
                spread = 0.0

            # Confidence interval from spread
            ci_low = max(0.0, avg_prob - 2 * spread)
            ci_high = min(1.0, avg_prob + 2 * spread)

            ensemble_predictions.append(EnsemblePrediction(
                event=event,
                probability=avg_prob,
                confidence_interval=[ci_low, ci_high],
                agreement_spread=spread,
                num_simulations=len(entries),
                source_predictions=[
                    {"source_idx": e["source_idx"], "probability": e["probability"]}
                    for e in entries
                ],
            ))

        # Sort by probability descending
        ensemble_predictions.sort(key=lambda p: p.probability, reverse=True)

        return EnsembleResult(
            project_id=project_id,
            predictions=ensemble_predictions,
            num_simulations=num_sets,
        )

    def compute_weights(
        self,
        simulation_metadata: List[Dict[str, Any]],
    ) -> List[float]:
        """Compute weights for each simulation based on metadata.

        Factors:
        - Recency: newer simulations weighted higher (exponential decay, 30-day half-life)
        - Agent count: more agents → higher weight (sqrt scaling)
        - Consensus strength: higher weighted_score → higher weight

        Args:
            simulation_metadata: List of dicts with 'created_at', 'agent_count',
                                 'consensus_strength' fields

        Returns:
            List of weights (not normalized)
        """
        weights = []
        now = datetime.now()

        for meta in simulation_metadata:
            # Recency weight
            created_str = meta.get("created_at", "")
            recency = 1.0
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00").split("+")[0])
                    age_days = max(0, (now - created).total_seconds() / 86400)
                    recency = math.pow(2, -age_days / 30.0)  # 30-day half-life
                except (ValueError, TypeError):
                    pass

            # Agent count weight (sqrt scaling, normalized around 50 agents)
            agent_count = meta.get("agent_count", 50)
            agent_weight = math.sqrt(agent_count / 50.0)

            # Consensus strength weight
            strength = meta.get("consensus_strength", 0.5)
            strength_weight = 0.5 + strength * 0.5

            weights.append(recency * agent_weight * strength_weight)

        return weights

    @staticmethod
    def _find_matching_event(event: str, existing_events: List[str], threshold: float = 0.3) -> Optional[str]:
        """Find the best matching event by word overlap (Jaccard similarity)."""
        if not existing_events:
            return None

        event_words = set(event.lower().split())
        best_match = None
        best_score = 0

        for existing in existing_events:
            existing_words = set(existing.lower().split())
            intersection = len(event_words & existing_words)
            union = len(event_words | existing_words)
            score = intersection / union if union > 0 else 0

            if score > best_score and score > threshold:
                best_score = score
                best_match = existing

        return best_match
