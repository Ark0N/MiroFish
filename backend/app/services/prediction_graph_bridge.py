"""
Prediction-aware graph enrichment.

When predictions are generated, creates new Graphiti episodes linking
prediction events back to the knowledge graph. Enables graph-based
prediction exploration and cross-project knowledge transfer.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_graph')


class PredictionGraphBridge:
    """Bridge predictions back into the knowledge graph as episodes."""

    def enrich_graph_with_predictions(
        self,
        graph_id: str,
        predictions: List[Dict[str, Any]],
        simulation_id: str = "",
        report_id: str = "",
    ) -> Dict[str, Any]:
        """Add prediction events as episodes to the knowledge graph.

        Each prediction becomes an episode containing:
        - The prediction event text
        - Probability and confidence information
        - Evidence and risk factors
        - Metadata linking to the source simulation/report

        Args:
            graph_id: Target graph to enrich
            predictions: List of prediction dicts
            simulation_id: Source simulation ID
            report_id: Source report ID

        Returns:
            Dict with added_count and any errors
        """
        if not predictions or not graph_id:
            return {"added_count": 0, "errors": []}

        added = 0
        errors = []

        for i, pred in enumerate(predictions):
            episode_text = self._format_prediction_episode(pred, i, simulation_id, report_id)

            try:
                self._add_episode(graph_id, episode_text, i)
                added += 1
            except Exception as e:
                errors.append({"prediction_idx": i, "error": str(e)})
                logger.warning(f"Failed to add prediction {i} to graph: {e}")

        logger.info(f"Graph enrichment: {added}/{len(predictions)} predictions added to {graph_id}")
        return {"added_count": added, "errors": errors, "total": len(predictions)}

    def _format_prediction_episode(
        self,
        prediction: Dict[str, Any],
        idx: int,
        simulation_id: str,
        report_id: str,
    ) -> str:
        """Format a prediction as a text episode for Graphiti ingestion."""
        event = prediction.get("event", "Unknown prediction")
        probability = prediction.get("probability", 0.5)
        timeframe = prediction.get("timeframe", "")
        evidence = prediction.get("evidence", [])
        risk_factors = prediction.get("risk_factors", [])
        agreement = prediction.get("agent_agreement", 0.5)
        impact = prediction.get("impact_level", "medium")

        parts = [
            f"PREDICTION: {event}",
            f"Probability: {probability*100:.0f}% (agent agreement: {agreement*100:.0f}%)",
            f"Impact level: {impact}",
        ]

        if timeframe:
            parts.append(f"Timeframe: {timeframe}")

        if evidence:
            parts.append("Evidence: " + "; ".join(evidence[:5]))

        if risk_factors:
            parts.append("Risk factors: " + "; ".join(risk_factors[:3]))

        parts.append(f"Source: simulation={simulation_id}, report={report_id}, prediction_idx={idx}")

        return "\n".join(parts)

    def _add_episode(self, graph_id: str, episode_text: str, idx: int) -> None:
        """Add a single episode to the graph via Graphiti.

        This is separated for easy mocking in tests.
        """
        from ..utils.graphiti_manager import GraphitiManager, run_async
        from graphiti_core.utils.maintenance.graph_data_operations import EpisodeType

        graphiti = GraphitiManager.get_instance()
        run_async(graphiti.add_episode(
            name=f"prediction_{idx}",
            episode_body=episode_text,
            source_description="MiroFish prediction engine",
            reference_time=datetime.now(),
            source=EpisodeType.text,
            group_id=graph_id,
        ))

    def format_predictions_as_text(
        self,
        predictions: List[Dict[str, Any]],
    ) -> str:
        """Format all predictions as a single text block.

        Useful for adding as one episode rather than multiple.
        """
        if not predictions:
            return ""

        parts = ["=== SIMULATION PREDICTIONS ===\n"]
        for i, pred in enumerate(predictions):
            event = pred.get("event", "Unknown")
            prob = pred.get("probability", 0.5)
            parts.append(f"{i+1}. {event} ({prob*100:.0f}%)")

        return "\n".join(parts)
