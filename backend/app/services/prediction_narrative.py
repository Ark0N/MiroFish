"""
Prediction narrative generator.

Auto-generates natural language narratives for each prediction explaining
the causal chain in plain English, without requiring an LLM call.
"""

from typing import Dict, List, Any, Optional

from ..utils.logger import get_logger

logger = get_logger('mirofish.narrative')


class PredictionNarrativeGenerator:
    """Generate human-readable narratives explaining predictions."""

    def generate_narrative(
        self,
        prediction: Dict[str, Any],
        consensus_data: Optional[Dict[str, Any]] = None,
        calibration_data: Optional[Dict[str, Any]] = None,
        provenance_data: Optional[Dict[str, Any]] = None,
        counterfactual_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a narrative explanation for a prediction.

        Args:
            prediction: Prediction dict with event, probability, evidence, etc.
            consensus_data: Consensus analysis results
            calibration_data: Calibration metadata
            provenance_data: Provenance DAG data
            counterfactual_data: Counterfactual scenario results

        Returns:
            Natural language narrative string
        """
        event = prediction.get("event", "Unknown event")
        probability = prediction.get("probability", 0.5)
        evidence = prediction.get("evidence", [])
        risk_factors = prediction.get("risk_factors", [])
        agreement = prediction.get("agent_agreement", 0.5)
        timeframe = prediction.get("timeframe", "")

        parts = []

        # Opening: confidence statement
        confidence_word = self._confidence_word(probability)
        parts.append(
            f"**{event}** — This prediction has a {confidence_word} likelihood "
            f"({probability*100:.0f}% probability)."
        )

        # Timeframe
        if timeframe:
            parts.append(f"Expected timeframe: {timeframe}.")

        # Evidence basis
        if evidence:
            parts.append(f"This is supported by {len(evidence)} pieces of evidence:")
            for e in evidence[:5]:
                parts.append(f"  - {e}")

        # Agent consensus
        agreement_desc = self._agreement_description(agreement)
        parts.append(
            f"Agent consensus: {agreement_desc} ({agreement*100:.0f}% agreement)."
        )

        # Consensus strength details
        if consensus_data:
            strength = consensus_data.get("consensus_strength", {})
            if strength:
                stability = strength.get("stability_score", 0.5)
                if stability > 0.7:
                    parts.append("The consensus has been stable across simulation rounds.")
                elif stability < 0.3:
                    parts.append("Warning: The consensus was unstable, with frequent direction changes.")

        # Calibration adjustments
        if calibration_data:
            adj = calibration_data.get("adjustment", 1.0)
            if adj > 1.05:
                parts.append(
                    f"Calibration boosted this prediction by {(adj-1)*100:.0f}% "
                    "due to strong consensus signals."
                )
            elif adj < 0.95:
                parts.append(
                    f"Calibration reduced this prediction by {(1-adj)*100:.0f}% "
                    "due to weak or contested consensus."
                )

        # Counterfactual sensitivity
        if counterfactual_data:
            most_sensitive = counterfactual_data.get("most_sensitive_factor")
            if most_sensitive:
                parts.append(f"Most sensitive factor: {most_sensitive}.")

        # Risk factors
        if risk_factors:
            parts.append(f"Key risks that could invalidate this prediction:")
            for r in risk_factors[:3]:
                parts.append(f"  - {r}")

        # Provenance summary
        if provenance_data:
            node_count = provenance_data.get("node_count", 0)
            if node_count > 3:
                parts.append(
                    f"This prediction draws from {node_count} evidence sources "
                    "including agent posts, graph entities, and consensus data."
                )

        return "\n".join(parts)

    def generate_batch_narratives(
        self,
        predictions: List[Dict[str, Any]],
        **kwargs,
    ) -> List[str]:
        """Generate narratives for multiple predictions."""
        return [
            self.generate_narrative(pred, **kwargs)
            for pred in predictions
        ]

    @staticmethod
    def _confidence_word(probability: float) -> str:
        if probability >= 0.85:
            return "very high"
        elif probability >= 0.7:
            return "high"
        elif probability >= 0.5:
            return "moderate"
        elif probability >= 0.3:
            return "low"
        else:
            return "very low"

    @staticmethod
    def _agreement_description(agreement: float) -> str:
        if agreement >= 0.8:
            return "strong consensus among simulation agents"
        elif agreement >= 0.6:
            return "moderate agreement among agents"
        elif agreement >= 0.4:
            return "divided opinions among agents"
        else:
            return "significant disagreement among agents"
