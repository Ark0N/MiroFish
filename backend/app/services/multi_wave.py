"""
Multi-wave simulation manager.

Enables running sequential simulation waves where each wave inherits
the final state (agent opinions, relationships) from the previous wave
but can inject new events to model evolving situations.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.multi_wave')


@dataclass
class WaveState:
    """State of a single simulation wave."""
    wave_number: int
    simulation_id: str
    status: str = "pending"  # pending, running, completed, failed
    injected_events: List[Dict[str, Any]] = field(default_factory=list)
    sentiment_snapshot: Dict[str, float] = field(default_factory=dict)  # agent -> avg sentiment
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_number": self.wave_number,
            "simulation_id": self.simulation_id,
            "status": self.status,
            "injected_events": self.injected_events,
            "sentiment_snapshot": self.sentiment_snapshot,
            "created_at": self.created_at,
        }


@dataclass
class MultiWaveConfig:
    """Configuration for a multi-wave simulation series."""
    series_id: str
    project_id: str
    graph_id: str
    waves: List[WaveState] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_id": self.series_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "waves": [w.to_dict() for w in self.waves],
            "created_at": self.created_at,
        }


class MultiWaveManager:
    """Orchestrates sequential simulation waves.

    Each wave can:
    1. Inherit agent sentiment/opinion state from the previous wave
    2. Inject new events to model evolving situations
    3. Track predictions across waves to see how they shift
    """

    SERIES_DIR = os.path.join(Config.UPLOAD_FOLDER, 'wave_series')

    def create_series(
        self,
        project_id: str,
        graph_id: str,
    ) -> MultiWaveConfig:
        """Create a new multi-wave series."""
        import uuid
        series_id = f"series_{uuid.uuid4().hex[:12]}"

        config = MultiWaveConfig(
            series_id=series_id,
            project_id=project_id,
            graph_id=graph_id,
        )

        self._save_series(config)
        logger.info(f"Created multi-wave series: {series_id}")
        return config

    def add_wave(
        self,
        series_id: str,
        simulation_id: str,
        injected_events: Optional[List[Dict[str, Any]]] = None,
    ) -> WaveState:
        """Add a new wave to the series.

        Args:
            series_id: The series to add to
            simulation_id: The simulation ID for this wave
            injected_events: New events to inject for this wave
        """
        config = self.get_series(series_id)
        if not config:
            raise ValueError(f"Series not found: {series_id}")

        wave_number = len(config.waves) + 1
        wave = WaveState(
            wave_number=wave_number,
            simulation_id=simulation_id,
            injected_events=injected_events or [],
        )

        config.waves.append(wave)
        self._save_series(config)
        logger.info(f"Added wave {wave_number} to series {series_id}")
        return wave

    def extract_sentiment_snapshot(self, simulation_dir: str) -> Dict[str, float]:
        """Extract final agent sentiment state from a completed simulation.

        Reads action logs and computes each agent's final average sentiment.
        This snapshot is used to initialize the next wave's agent attitudes.

        Args:
            simulation_dir: Path to completed simulation output directory

        Returns:
            Dict mapping agent_name -> average sentiment score (-1.0 to 1.0)
        """
        positive_kw = {"good", "great", "support", "agree", "happy", "love",
                       "excellent", "hope", "progress", "positive", "benefit"}
        negative_kw = {"bad", "terrible", "oppose", "disagree", "angry", "hate",
                       "awful", "crisis", "fail", "problem", "danger"}

        agent_scores = {}  # agent -> list of sentiment scores

        for platform in ["twitter", "reddit"]:
            actions_file = os.path.join(simulation_dir, platform, "actions.jsonl")
            if not os.path.exists(actions_file):
                continue

            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            action = json.loads(line)
                            atype = action.get("action_type", "")
                            if atype not in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"):
                                continue
                            agent = action.get("agent_name", action.get("user_name", ""))
                            content = action.get("content", "")
                            if not content:
                                continue

                            lower = content.lower()
                            pos = sum(1 for w in positive_kw if w in lower)
                            neg = sum(1 for w in negative_kw if w in lower)
                            total = pos + neg
                            score = (pos - neg) / total if total > 0 else 0.0

                            if agent not in agent_scores:
                                agent_scores[agent] = []
                            agent_scores[agent].append(score)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        # Compute averages
        snapshot = {}
        for agent, scores in agent_scores.items():
            snapshot[agent] = round(sum(scores) / len(scores), 3) if scores else 0.0

        return snapshot

    def generate_wave_events(
        self,
        previous_snapshot: Dict[str, float],
        new_events_description: str,
    ) -> List[Dict[str, Any]]:
        """Generate events for a new wave based on previous state.

        Creates initial posts that reflect the evolved state from the
        previous wave, plus any new injected events.

        Args:
            previous_snapshot: Sentiment snapshot from previous wave
            new_events_description: Description of new events to inject

        Returns:
            List of event dicts for the new wave's scheduled_events
        """
        events = []

        # Generate a summary event at round 1 reflecting previous state
        if previous_snapshot:
            avg_sentiment = sum(previous_snapshot.values()) / len(previous_snapshot)
            if avg_sentiment > 0.2:
                tone = "generally positive sentiment and support"
            elif avg_sentiment < -0.2:
                tone = "growing concern and opposition"
            else:
                tone = "mixed and divided opinions"

            events.append({
                "round": 1,
                "content": (
                    f"Continuing from previous developments, the community mood reflects "
                    f"{tone}. New information emerges that may shift the discussion."
                ),
                "poster_type": "MediaOutlet",
                "is_wave_transition": True,
            })

        # Inject new events at staggered rounds
        if new_events_description:
            events.append({
                "round": 3,
                "content": new_events_description,
                "poster_type": "MediaOutlet",
                "is_wave_injection": True,
            })

        return events

    def update_wave_status(
        self,
        series_id: str,
        wave_number: int,
        status: str,
        sentiment_snapshot: Optional[Dict[str, float]] = None,
    ) -> None:
        """Update the status of a wave."""
        config = self.get_series(series_id)
        if not config:
            return

        for wave in config.waves:
            if wave.wave_number == wave_number:
                wave.status = status
                if sentiment_snapshot is not None:
                    wave.sentiment_snapshot = sentiment_snapshot
                break

        self._save_series(config)

    def get_series(self, series_id: str) -> Optional[MultiWaveConfig]:
        """Load a series configuration."""
        path = os.path.join(self.SERIES_DIR, f"{series_id}.json")
        if not os.path.exists(path):
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            waves = []
            for w in data.get("waves", []):
                waves.append(WaveState(
                    wave_number=w["wave_number"],
                    simulation_id=w["simulation_id"],
                    status=w.get("status", "pending"),
                    injected_events=w.get("injected_events", []),
                    sentiment_snapshot=w.get("sentiment_snapshot", {}),
                    created_at=w.get("created_at", ""),
                ))

            return MultiWaveConfig(
                series_id=data["series_id"],
                project_id=data["project_id"],
                graph_id=data["graph_id"],
                waves=waves,
                created_at=data.get("created_at", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load series {series_id}: {e}")
            return None

    def _save_series(self, config: MultiWaveConfig) -> None:
        """Save series configuration to disk."""
        os.makedirs(self.SERIES_DIR, exist_ok=True)
        path = os.path.join(self.SERIES_DIR, f"{config.series_id}.json")
        atomic_write_json(path, config.to_dict())
