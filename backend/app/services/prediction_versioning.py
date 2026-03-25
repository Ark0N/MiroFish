"""
Prediction versioning service.

Tracks prediction versions when updated (Bayesian updates, decay,
calibration). Stores full version history for audit trail and
regression detection.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.prediction_versioning')


@dataclass
class PredictionVersion:
    """A single version of a prediction."""
    version: int
    probability: float
    confidence_interval: List[float]
    update_source: str  # "initial", "bayesian", "calibration", "decay", "manual"
    update_reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "probability": round(self.probability, 4),
            "confidence_interval": [round(ci, 4) for ci in self.confidence_interval],
            "update_source": self.update_source,
            "update_reason": self.update_reason,
            "timestamp": self.timestamp,
        }


class PredictionVersionManager:
    """Manage prediction version histories."""

    VERSIONS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'prediction_versions')

    def create_initial_version(
        self,
        report_id: str,
        prediction_idx: int,
        probability: float,
        confidence_interval: List[float],
    ) -> PredictionVersion:
        """Create the initial version of a prediction."""
        version = PredictionVersion(
            version=1,
            probability=probability,
            confidence_interval=confidence_interval,
            update_source="initial",
            update_reason="Initial prediction from report generation",
        )
        self._save_version(report_id, prediction_idx, version)
        return version

    def record_update(
        self,
        report_id: str,
        prediction_idx: int,
        new_probability: float,
        new_confidence_interval: List[float],
        update_source: str,
        update_reason: str,
    ) -> PredictionVersion:
        """Record a new version after an update."""
        history = self.get_history(report_id, prediction_idx)
        next_version = len(history) + 1

        version = PredictionVersion(
            version=next_version,
            probability=new_probability,
            confidence_interval=new_confidence_interval,
            update_source=update_source,
            update_reason=update_reason,
        )
        self._save_version(report_id, prediction_idx, version)
        return version

    def get_history(self, report_id: str, prediction_idx: int) -> List[PredictionVersion]:
        """Get full version history for a prediction."""
        data = self._load_versions(report_id, prediction_idx)
        return [
            PredictionVersion(**{k: v for k, v in d.items() if k in PredictionVersion.__dataclass_fields__})
            for d in data
        ]

    def get_latest(self, report_id: str, prediction_idx: int) -> Optional[PredictionVersion]:
        """Get the latest version of a prediction."""
        history = self.get_history(report_id, prediction_idx)
        return history[-1] if history else None

    def detect_regression(self, report_id: str, prediction_idx: int) -> Optional[Dict[str, Any]]:
        """Detect if a prediction has regressed (probability oscillating).

        Returns regression info if detected, None otherwise.
        """
        history = self.get_history(report_id, prediction_idx)
        if len(history) < 3:
            return None

        # Check for oscillation: direction changes more than 2 times in last 5 versions
        recent = history[-5:]
        direction_changes = 0
        for i in range(1, len(recent)):
            prev_delta = recent[i].probability - recent[i-1].probability if i >= 1 else 0
            if i >= 2:
                prev_prev_delta = recent[i-1].probability - recent[i-2].probability
                if prev_delta * prev_prev_delta < 0:  # Sign change
                    direction_changes += 1

        if direction_changes >= 2:
            return {
                "regression_detected": True,
                "direction_changes": direction_changes,
                "recent_versions": len(recent),
                "probability_range": [
                    round(min(v.probability for v in recent), 4),
                    round(max(v.probability for v in recent), 4),
                ],
            }
        return None

    def _save_version(self, report_id: str, prediction_idx: int, version: PredictionVersion) -> None:
        data = self._load_versions(report_id, prediction_idx)
        data.append(version.to_dict())
        path = self._get_path(report_id, prediction_idx)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_json(path, data)

    def _load_versions(self, report_id: str, prediction_idx: int) -> List[Dict[str, Any]]:
        path = self._get_path(report_id, prediction_idx)
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _get_path(self, report_id: str, prediction_idx: int) -> str:
        return os.path.join(self.VERSIONS_DIR, report_id, f"prediction_{prediction_idx}_versions.json")
