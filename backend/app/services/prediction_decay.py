"""
Prediction decay tracker.

Tracks how predictions age over time. Predictions with no supporting
evidence after N days get automatically downgraded. Predictions with
new supporting evidence get boosted.

Stores health status in prediction_health.json per report.
"""

import json
import os
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.prediction_decay')


@dataclass
class PredictionHealth:
    """Health status of a single prediction."""
    prediction_idx: int
    event: str
    original_probability: float
    current_probability: float
    health_status: str  # "fresh", "aging", "stale", "boosted"
    days_since_creation: float = 0.0
    days_since_last_evidence: float = 0.0
    evidence_count: int = 0
    decay_factor: float = 1.0  # 0-1, applied to probability
    last_evidence_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_idx": self.prediction_idx,
            "event": self.event,
            "original_probability": round(self.original_probability, 4),
            "current_probability": round(self.current_probability, 4),
            "health_status": self.health_status,
            "days_since_creation": round(self.days_since_creation, 1),
            "days_since_last_evidence": round(self.days_since_last_evidence, 1),
            "evidence_count": self.evidence_count,
            "decay_factor": round(self.decay_factor, 4),
            "last_evidence_at": self.last_evidence_at,
        }


class PredictionDecayTracker:
    """Track prediction freshness and apply time-based decay."""

    # Decay thresholds (days)
    FRESH_THRESHOLD = 7       # < 7 days = fresh
    AGING_THRESHOLD = 14      # 7-14 days = aging
    STALE_THRESHOLD = 30      # > 30 days without evidence = stale

    # Decay rate: probability reduced by this fraction per day after AGING_THRESHOLD
    DAILY_DECAY_RATE = 0.02   # 2% per day
    EVIDENCE_BOOST = 0.05     # 5% boost per new evidence

    def compute_health(
        self,
        predictions: List[Dict[str, Any]],
        created_at: str,
        evidence_log: Optional[List[Dict[str, Any]]] = None,
    ) -> List[PredictionHealth]:
        """Compute health status for all predictions in a report.

        Args:
            predictions: List of prediction dicts (from PredictionSet)
            created_at: When the predictions were created (ISO format)
            evidence_log: Optional list of evidence events with timestamps

        Returns:
            List of PredictionHealth objects
        """
        now = datetime.now()
        try:
            creation_time = datetime.fromisoformat(created_at.replace("Z", "+00:00").split("+")[0])
        except (ValueError, AttributeError):
            creation_time = now

        days_since_creation = max(0, (now - creation_time).total_seconds() / 86400)

        # Build evidence map: prediction_idx -> list of evidence timestamps
        evidence_map: Dict[int, List[datetime]] = {}
        if evidence_log:
            for ev in evidence_log:
                idx = ev.get("prediction_idx", -1)
                ts_str = ev.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").split("+")[0])
                    if idx not in evidence_map:
                        evidence_map[idx] = []
                    evidence_map[idx].append(ts)
                except (ValueError, AttributeError):
                    continue

        results = []
        for i, pred in enumerate(predictions):
            original_prob = pred.get("probability", 0.5)
            evidence_times = evidence_map.get(i, [])
            evidence_count = len(evidence_times)

            # Days since last evidence
            if evidence_times:
                last_evidence = max(evidence_times)
                days_since_evidence = max(0, (now - last_evidence).total_seconds() / 86400)
                last_evidence_str = last_evidence.isoformat()
            else:
                days_since_evidence = days_since_creation
                last_evidence_str = ""

            # Compute decay factor
            decay_factor, health_status = self._compute_decay(
                days_since_creation, days_since_evidence, evidence_count
            )

            current_prob = max(0.05, min(0.99, original_prob * decay_factor))

            results.append(PredictionHealth(
                prediction_idx=i,
                event=pred.get("event", ""),
                original_probability=original_prob,
                current_probability=current_prob,
                health_status=health_status,
                days_since_creation=days_since_creation,
                days_since_last_evidence=days_since_evidence,
                evidence_count=evidence_count,
                decay_factor=decay_factor,
                last_evidence_at=last_evidence_str,
            ))

        return results

    def _compute_decay(
        self,
        days_since_creation: float,
        days_since_evidence: float,
        evidence_count: int,
    ) -> tuple:
        """Compute decay factor and health status.

        Returns (decay_factor, health_status)
        """
        # Base: start at 1.0
        decay = 1.0

        # Evidence boost
        decay += evidence_count * self.EVIDENCE_BOOST

        # Time-based decay
        if days_since_evidence > self.STALE_THRESHOLD:
            # Stale: significant decay
            excess_days = days_since_evidence - self.STALE_THRESHOLD
            decay -= excess_days * self.DAILY_DECAY_RATE * 2
            status = "stale"
        elif days_since_evidence > self.AGING_THRESHOLD:
            # Aging: moderate decay
            excess_days = days_since_evidence - self.AGING_THRESHOLD
            decay -= excess_days * self.DAILY_DECAY_RATE
            status = "aging"
        elif evidence_count > 0 and days_since_evidence < self.FRESH_THRESHOLD:
            status = "boosted"
        else:
            status = "fresh"

        # Clamp decay factor
        decay = max(0.3, min(2.0, decay))

        return decay, status

    def save_health(self, report_id: str, health: List[PredictionHealth]) -> None:
        """Save prediction health to report directory."""
        from .report_agent import ReportManager
        folder = ReportManager._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "prediction_health.json")
        atomic_write_json(path, [h.to_dict() for h in health])

    def record_evidence(self, report_id: str, prediction_idx: int, description: str = "") -> None:
        """Record new supporting evidence for a prediction."""
        from .report_agent import ReportManager
        folder = ReportManager._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        evidence_file = os.path.join(folder, "evidence_log.jsonl")

        entry = {
            "prediction_idx": prediction_idx,
            "description": description[:500],
            "timestamp": datetime.now().isoformat(),
        }

        with open(evidence_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
