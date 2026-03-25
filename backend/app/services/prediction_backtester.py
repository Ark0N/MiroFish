"""
Prediction backtesting framework.

Allows marking predictions as resolved (correct/incorrect) with actual outcomes.
Computes calibration curves and accuracy metrics across resolved predictions
per project. Stores outcomes in prediction_outcomes.json.
"""

import json
import os
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.backtester')


@dataclass
class PredictionOutcome:
    """Resolved prediction outcome."""
    report_id: str
    prediction_idx: int
    event: str
    predicted_probability: float
    actual_outcome: bool  # True = prediction was correct
    resolution_notes: str = ""
    resolved_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "prediction_idx": self.prediction_idx,
            "event": self.event,
            "predicted_probability": self.predicted_probability,
            "actual_outcome": self.actual_outcome,
            "resolution_notes": self.resolution_notes,
            "resolved_at": self.resolved_at,
        }


@dataclass
class CalibrationBin:
    """A single bin in the calibration curve."""
    bin_center: float  # e.g., 0.1, 0.2, ..., 0.9
    bin_range: tuple  # e.g., (0.05, 0.15)
    predicted_avg: float  # average predicted probability in this bin
    actual_rate: float  # fraction that actually occurred
    count: int  # number of predictions in this bin

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bin_center": self.bin_center,
            "bin_range": list(self.bin_range),
            "predicted_avg": round(self.predicted_avg, 4),
            "actual_rate": round(self.actual_rate, 4),
            "count": self.count,
        }


@dataclass
class CalibrationReport:
    """Calibration analysis results."""
    bins: List[CalibrationBin] = field(default_factory=list)
    total_predictions: int = 0
    accuracy: float = 0.0  # fraction correct (using 0.5 threshold)
    brier_score: float = 0.0  # lower = better calibrated (0 = perfect)
    overconfidence_bias: float = 0.0  # positive = overconfident, negative = underconfident

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bins": [b.to_dict() for b in self.bins],
            "total_predictions": self.total_predictions,
            "accuracy": round(self.accuracy, 4),
            "brier_score": round(self.brier_score, 4),
            "overconfidence_bias": round(self.overconfidence_bias, 4),
        }


class PredictionBacktester:
    """Manage prediction outcomes and compute calibration metrics."""

    OUTCOMES_DIR = os.path.join(Config.UPLOAD_FOLDER, 'prediction_outcomes')

    def resolve_prediction(
        self,
        project_id: str,
        report_id: str,
        prediction_idx: int,
        event: str,
        predicted_probability: float,
        actual_outcome: bool,
        resolution_notes: str = "",
    ) -> PredictionOutcome:
        """Mark a prediction as resolved.

        Args:
            project_id: Project this prediction belongs to
            report_id: Report containing the prediction
            prediction_idx: Index of prediction in the report's prediction set
            event: The prediction event text
            predicted_probability: What we predicted (0-1)
            actual_outcome: Whether the event actually happened
            resolution_notes: Optional notes about the resolution

        Returns:
            PredictionOutcome record
        """
        outcome = PredictionOutcome(
            report_id=report_id,
            prediction_idx=prediction_idx,
            event=event,
            predicted_probability=predicted_probability,
            actual_outcome=actual_outcome,
            resolution_notes=resolution_notes,
        )

        # Load existing outcomes and append
        outcomes = self._load_outcomes(project_id)
        outcomes.append(outcome.to_dict())
        self._save_outcomes(project_id, outcomes)

        logger.info(f"Resolved prediction for project {project_id}: "
                     f"'{event[:50]}' → {'correct' if actual_outcome else 'incorrect'}")
        return outcome

    def compute_calibration(self, project_id: str, num_bins: int = 10) -> CalibrationReport:
        """Compute calibration curve from all resolved predictions.

        Args:
            project_id: Project to analyze
            num_bins: Number of probability bins (default 10: 0-10%, 10-20%, etc.)

        Returns:
            CalibrationReport with bins, accuracy, Brier score
        """
        outcomes = self._load_outcomes(project_id)
        if not outcomes:
            return CalibrationReport()

        # Initialize bins
        bin_width = 1.0 / num_bins
        bins = {}
        for i in range(num_bins):
            center = (i + 0.5) * bin_width
            bin_range = (i * bin_width, (i + 1) * bin_width)
            bins[i] = {"predictions": [], "outcomes": [], "center": center, "range": bin_range}

        # Assign predictions to bins
        for outcome in outcomes:
            prob = outcome.get("predicted_probability", 0.5)
            actual = 1.0 if outcome.get("actual_outcome", False) else 0.0
            bin_idx = min(int(prob * num_bins), num_bins - 1)
            bins[bin_idx]["predictions"].append(prob)
            bins[bin_idx]["outcomes"].append(actual)

        # Compute per-bin statistics
        calibration_bins = []
        for i in range(num_bins):
            b = bins[i]
            if b["predictions"]:
                predicted_avg = sum(b["predictions"]) / len(b["predictions"])
                actual_rate = sum(b["outcomes"]) / len(b["outcomes"])
            else:
                predicted_avg = b["center"]
                actual_rate = 0.0

            calibration_bins.append(CalibrationBin(
                bin_center=b["center"],
                bin_range=b["range"],
                predicted_avg=predicted_avg,
                actual_rate=actual_rate,
                count=len(b["predictions"]),
            ))

        # Overall metrics
        total = len(outcomes)
        all_probs = [o.get("predicted_probability", 0.5) for o in outcomes]
        all_actuals = [1.0 if o.get("actual_outcome", False) else 0.0 for o in outcomes]

        # Accuracy (using 0.5 threshold)
        correct = sum(
            1 for p, a in zip(all_probs, all_actuals)
            if (p >= 0.5 and a == 1.0) or (p < 0.5 and a == 0.0)
        )
        accuracy = correct / total if total > 0 else 0.0

        # Brier score: mean squared difference between predicted probability and actual outcome
        brier = sum((p - a) ** 2 for p, a in zip(all_probs, all_actuals)) / total if total > 0 else 0.0

        # Overconfidence bias: avg(predicted - actual) for predictions > 0.5
        high_conf = [(p, a) for p, a in zip(all_probs, all_actuals) if p >= 0.5]
        if high_conf:
            overconfidence = sum(p - a for p, a in high_conf) / len(high_conf)
        else:
            overconfidence = 0.0

        return CalibrationReport(
            bins=calibration_bins,
            total_predictions=total,
            accuracy=accuracy,
            brier_score=brier,
            overconfidence_bias=overconfidence,
        )

    def get_outcomes(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all resolved predictions for a project."""
        return self._load_outcomes(project_id)

    def _load_outcomes(self, project_id: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.OUTCOMES_DIR, f"{project_id}.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_outcomes(self, project_id: str, outcomes: List[Dict[str, Any]]) -> None:
        os.makedirs(self.OUTCOMES_DIR, exist_ok=True)
        path = os.path.join(self.OUTCOMES_DIR, f"{project_id}.json")
        atomic_write_json(path, outcomes)
