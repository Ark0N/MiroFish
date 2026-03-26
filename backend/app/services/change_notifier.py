"""
Prediction change notifier.

Detects when a prediction's probability changes significantly and emits
structured change events. Stored per report for retrieval via API.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.change_notifier')


@dataclass
class PredictionChange:
    """A significant prediction change event."""
    prediction_idx: int
    event: str
    old_probability: float
    new_probability: float
    delta: float
    source: str  # "bayesian", "calibration", "decay", "manual"
    severity: str  # "minor", "significant", "major"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_idx": self.prediction_idx,
            "event": self.event,
            "old_probability": round(self.old_probability, 4),
            "new_probability": round(self.new_probability, 4),
            "delta": round(self.delta, 4),
            "abs_delta_pct": round(abs(self.delta) * 100, 1),
            "direction": "up" if self.delta > 0 else "down",
            "source": self.source,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


class ChangeNotifier:
    """Detect and store significant prediction changes."""

    MINOR_THRESHOLD = 0.05    # 5%
    SIGNIFICANT_THRESHOLD = 0.10  # 10%
    MAJOR_THRESHOLD = 0.20    # 20%

    def check_and_record(
        self,
        report_id: str,
        prediction_idx: int,
        event: str,
        old_probability: float,
        new_probability: float,
        source: str = "unknown",
    ) -> Optional[PredictionChange]:
        """Check if a change is significant and record it if so.

        Args:
            report_id: Report containing the prediction
            prediction_idx: Index of the prediction
            event: Prediction event text
            old_probability: Previous probability
            new_probability: Updated probability
            source: What caused the change

        Returns:
            PredictionChange if significant, None otherwise
        """
        delta = new_probability - old_probability
        abs_delta = abs(delta)

        if abs_delta < self.MINOR_THRESHOLD:
            return None

        if abs_delta >= self.MAJOR_THRESHOLD:
            severity = "major"
        elif abs_delta >= self.SIGNIFICANT_THRESHOLD:
            severity = "significant"
        else:
            severity = "minor"

        change = PredictionChange(
            prediction_idx=prediction_idx,
            event=event,
            old_probability=old_probability,
            new_probability=new_probability,
            delta=delta,
            source=source,
            severity=severity,
        )

        self._store_change(report_id, change)
        logger.info(f"Prediction change ({severity}): '{event[:50]}' "
                     f"{old_probability:.2f} → {new_probability:.2f} [{source}]")
        return change

    def get_changes(
        self,
        report_id: str,
        min_severity: str = "minor",
    ) -> List[Dict[str, Any]]:
        """Get all recorded changes for a report.

        Args:
            report_id: Report to get changes for
            min_severity: Minimum severity to include ("minor", "significant", "major")

        Returns:
            List of change dicts, newest first
        """
        changes = self._load_changes(report_id)

        severity_order = {"minor": 0, "significant": 1, "major": 2}
        min_level = severity_order.get(min_severity, 0)

        filtered = [c for c in changes if severity_order.get(c.get("severity", "minor"), 0) >= min_level]
        filtered.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
        return filtered

    def _store_change(self, report_id: str, change: PredictionChange) -> None:
        changes = self._load_changes(report_id)
        changes.append(change.to_dict())
        # Keep last 200 changes
        if len(changes) > 200:
            changes = changes[-200:]
        path = self._get_path(report_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_json(path, changes)

    def _load_changes(self, report_id: str) -> List[Dict[str, Any]]:
        path = self._get_path(report_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _get_path(self, report_id: str) -> str:
        from .report_agent import ReportManager
        return os.path.join(ReportManager._get_report_folder(report_id), "prediction_changes.json")
