"""
Prediction digest generator.

Produces a compact one-paragraph executive digest from prediction data:
top predictions by impact, overall confidence, contradictions, and health.
Designed for Slack/email integration — plain text, no markdown.
"""

from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.digest')


class PredictionDigestGenerator:
    """Generate compact prediction digests."""

    def generate(
        self,
        predictions: List[Dict[str, Any]],
        overall_confidence: str = "",
        health_data: Dict[str, Any] = None,
        contradictions: List[Dict[str, Any]] = None,
    ) -> str:
        """Generate a one-paragraph executive digest.

        Args:
            predictions: List of prediction dicts
            overall_confidence: Overall confidence statement
            health_data: Optional health dashboard data
            contradictions: Optional contradiction list

        Returns:
            Plain text digest string
        """
        if not predictions:
            return "No predictions available for this report."

        n = len(predictions)

        # Top 3 by probability
        ranked = sorted(predictions, key=lambda p: p.get("probability", 0), reverse=True)
        top3 = ranked[:3]

        parts = [f"This report contains {n} prediction{'s' if n != 1 else ''}."]

        # Top predictions
        top_strs = []
        for p in top3:
            prob = p.get("probability", 0.5)
            event = p.get("event", "Unknown")[:80]
            top_strs.append(f'"{event}" ({prob*100:.0f}%)')
        parts.append("Top predictions: " + "; ".join(top_strs) + ".")

        # Overall confidence
        if overall_confidence:
            parts.append(f"Overall confidence: {overall_confidence}.")

        # Health warnings
        if health_data:
            stale = sum(1 for h in health_data.get("prediction_health", [])
                        if h.get("health_status") == "stale")
            if stale > 0:
                parts.append(f"Warning: {stale} prediction{'s are' if stale > 1 else ' is'} stale and may need updating.")

        # Contradictions
        if contradictions:
            high = sum(1 for c in contradictions if c.get("severity") == "high")
            if high > 0:
                parts.append(f"Alert: {high} high-severity contradiction{'s' if high > 1 else ''} detected between predictions.")
            elif len(contradictions) > 0:
                parts.append(f"{len(contradictions)} contradiction{'s' if len(contradictions) > 1 else ''} detected.")

        return " ".join(parts)
