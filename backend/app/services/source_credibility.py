"""
Source credibility scoring.

Tracks source reliability based on prediction accuracy. Sources that
consistently provide information leading to accurate predictions get
higher credibility weights. Applied to graph entity episode weighting.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.credibility')


@dataclass
class SourceScore:
    """Credibility score for a single source."""
    source_name: str
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.5  # Start at neutral
    credibility_weight: float = 1.0  # 0.5 (unreliable) to 2.0 (highly reliable)
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy": round(self.accuracy, 4),
            "credibility_weight": round(self.credibility_weight, 4),
            "last_updated": self.last_updated,
        }


class SourceCredibilityTracker:
    """Track and compute source credibility from prediction outcomes."""

    CREDIBILITY_DIR = os.path.join(Config.UPLOAD_FOLDER, 'source_credibility')

    # Weight mapping: accuracy -> credibility multiplier
    # 0% accuracy -> 0.5x, 50% -> 1.0x, 100% -> 2.0x
    MIN_WEIGHT = 0.5
    MAX_WEIGHT = 2.0

    def record_outcome(
        self,
        project_id: str,
        source_name: str,
        prediction_correct: bool,
    ) -> SourceScore:
        """Record whether a prediction from this source was correct.

        Args:
            project_id: Project context
            source_name: Name/identifier of the information source
            prediction_correct: Whether the prediction based on this source was correct

        Returns:
            Updated SourceScore
        """
        scores = self._load_scores(project_id)

        if source_name not in scores:
            scores[source_name] = {
                "source_name": source_name,
                "total_predictions": 0,
                "correct_predictions": 0,
            }

        entry = scores[source_name]
        entry["total_predictions"] += 1
        if prediction_correct:
            entry["correct_predictions"] += 1

        # Compute accuracy and weight
        accuracy = entry["correct_predictions"] / entry["total_predictions"]
        weight = self.MIN_WEIGHT + accuracy * (self.MAX_WEIGHT - self.MIN_WEIGHT)
        entry["accuracy"] = accuracy
        entry["credibility_weight"] = weight
        entry["last_updated"] = datetime.now().isoformat()

        self._save_scores(project_id, scores)

        return SourceScore(**{k: v for k, v in entry.items() if k in SourceScore.__dataclass_fields__})

    def get_weight(self, project_id: str, source_name: str) -> float:
        """Get the credibility weight for a source.

        Returns 1.0 (neutral) if source has no history.
        """
        scores = self._load_scores(project_id)
        entry = scores.get(source_name, {})
        return entry.get("credibility_weight", 1.0)

    def get_all_scores(self, project_id: str) -> List[SourceScore]:
        """Get all source credibility scores for a project."""
        scores = self._load_scores(project_id)
        result = []
        for entry in scores.values():
            result.append(SourceScore(
                **{k: v for k, v in entry.items() if k in SourceScore.__dataclass_fields__}
            ))
        return sorted(result, key=lambda s: s.credibility_weight, reverse=True)

    def _load_scores(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        path = os.path.join(self.CREDIBILITY_DIR, f"{project_id}.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_scores(self, project_id: str, scores: Dict[str, Dict[str, Any]]) -> None:
        os.makedirs(self.CREDIBILITY_DIR, exist_ok=True)
        path = os.path.join(self.CREDIBILITY_DIR, f"{project_id}.json")
        atomic_write_json(path, scores)
