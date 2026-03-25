"""
Simulation parameter learning service.

Tracks which simulation configurations (agent count, round count, temperature
settings, persona types) produce the most accurate predictions. Uses historical
accuracy data to recommend optimal parameters for new projects.
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

logger = get_logger('mirofish.parameter_learner')


@dataclass
class SimulationRecord:
    """Record of a simulation's parameters and outcome accuracy."""
    simulation_id: str
    project_id: str
    agent_count: int
    round_count: int
    avg_temperature: float
    contrarian_pct: float
    accuracy: float  # 0-1, from backtesting outcomes
    brier_score: float  # calibration quality
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "agent_count": self.agent_count,
            "round_count": self.round_count,
            "avg_temperature": round(self.avg_temperature, 3),
            "contrarian_pct": round(self.contrarian_pct, 3),
            "accuracy": round(self.accuracy, 4),
            "brier_score": round(self.brier_score, 4),
            "created_at": self.created_at,
        }


@dataclass
class ParameterRecommendation:
    """Recommended simulation parameters based on historical performance."""
    recommended_agent_count: int
    recommended_round_count: int
    recommended_temperature: float
    recommended_contrarian_pct: float
    confidence: float  # 0-1, how confident we are in this recommendation
    based_on_n_simulations: int
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_agent_count": self.recommended_agent_count,
            "recommended_round_count": self.recommended_round_count,
            "recommended_temperature": round(self.recommended_temperature, 2),
            "recommended_contrarian_pct": round(self.recommended_contrarian_pct, 3),
            "confidence": round(self.confidence, 3),
            "based_on_n_simulations": self.based_on_n_simulations,
            "reasoning": self.reasoning,
        }


class ParameterLearner:
    """Learn optimal simulation parameters from historical outcomes."""

    RECORDS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'parameter_records')

    def record_simulation(self, record: SimulationRecord) -> None:
        """Record a simulation's parameters and accuracy for learning."""
        records = self._load_records()
        records.append(record.to_dict())
        self._save_records(records)
        logger.info(f"Recorded simulation {record.simulation_id}: "
                     f"accuracy={record.accuracy:.2f}, agents={record.agent_count}")

    def recommend_parameters(self, min_records: int = 3) -> ParameterRecommendation:
        """Recommend optimal simulation parameters based on historical data.

        Uses accuracy-weighted averaging of the top-performing simulations.

        Args:
            min_records: Minimum records needed for a confident recommendation

        Returns:
            ParameterRecommendation with optimal parameters
        """
        records = self._load_records()

        if len(records) < min_records:
            return ParameterRecommendation(
                recommended_agent_count=45,
                recommended_round_count=20,
                recommended_temperature=0.6,
                recommended_contrarian_pct=0.07,
                confidence=0.0,
                based_on_n_simulations=len(records),
                reasoning=f"Insufficient data ({len(records)}/{min_records} records). "
                          "Using default parameters.",
            )

        # Weight records by accuracy (higher accuracy = more weight)
        weighted_agents = 0.0
        weighted_rounds = 0.0
        weighted_temp = 0.0
        weighted_contrarian = 0.0
        total_weight = 0.0

        for r in records:
            accuracy = r.get("accuracy", 0.5)
            weight = accuracy ** 2  # Square to emphasize high-accuracy records
            weighted_agents += r.get("agent_count", 45) * weight
            weighted_rounds += r.get("round_count", 20) * weight
            weighted_temp += r.get("avg_temperature", 0.6) * weight
            weighted_contrarian += r.get("contrarian_pct", 0.07) * weight
            total_weight += weight

        if total_weight == 0:
            total_weight = 1.0

        avg_accuracy = sum(r.get("accuracy", 0.5) for r in records) / len(records)
        confidence = min(1.0, (len(records) / 10.0) * avg_accuracy)

        return ParameterRecommendation(
            recommended_agent_count=round(weighted_agents / total_weight),
            recommended_round_count=round(weighted_rounds / total_weight),
            recommended_temperature=weighted_temp / total_weight,
            recommended_contrarian_pct=weighted_contrarian / total_weight,
            confidence=confidence,
            based_on_n_simulations=len(records),
            reasoning=f"Based on {len(records)} simulations with "
                      f"avg accuracy {avg_accuracy:.1%}. "
                      f"Parameters weighted by accuracy.",
        )

    def get_records(self) -> List[Dict[str, Any]]:
        """Get all simulation parameter records."""
        return self._load_records()

    def _load_records(self) -> List[Dict[str, Any]]:
        path = os.path.join(self.RECORDS_DIR, "records.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_records(self, records: List[Dict[str, Any]]) -> None:
        os.makedirs(self.RECORDS_DIR, exist_ok=True)
        path = os.path.join(self.RECORDS_DIR, "records.json")
        atomic_write_json(path, records)
