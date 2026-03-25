"""
Historical pattern matcher.

Compares current simulation dynamics (sentiment trajectory, faction evolution,
momentum patterns) against previously completed simulations to identify
similar historical patterns and use their outcomes to adjust predictions.
"""

import json
import os
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.pattern_matcher')


@dataclass
class SimulationFingerprint:
    """Compact representation of a simulation's dynamics for comparison."""
    simulation_id: str
    sentiment_trajectory: List[float]  # avg sentiment per round
    momentum_trajectory: List[float]  # velocity per round
    faction_sizes: Dict[str, List[int]]  # {"supportive": [n1, n2...], ...}
    final_agreement: float = 0.0
    total_rounds: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "sentiment_trajectory": [round(s, 3) for s in self.sentiment_trajectory],
            "momentum_trajectory": [round(m, 3) for m in self.momentum_trajectory],
            "faction_sizes": self.faction_sizes,
            "final_agreement": round(self.final_agreement, 3),
            "total_rounds": self.total_rounds,
        }


@dataclass
class PatternMatch:
    """Result of a pattern match between two simulations."""
    matched_simulation_id: str
    similarity_score: float  # 0-1, higher = more similar
    sentiment_similarity: float
    momentum_similarity: float
    faction_similarity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched_simulation_id": self.matched_simulation_id,
            "similarity_score": round(self.similarity_score, 4),
            "sentiment_similarity": round(self.sentiment_similarity, 4),
            "momentum_similarity": round(self.momentum_similarity, 4),
            "faction_similarity": round(self.faction_similarity, 4),
        }


class PatternMatcher:
    """Compare simulation dynamics to find similar historical patterns."""

    def extract_fingerprint(self, simulation_dir: str, simulation_id: str) -> SimulationFingerprint:
        """Extract a dynamics fingerprint from a simulation's round metrics.

        Args:
            simulation_dir: Path to simulation output directory
            simulation_id: ID of the simulation

        Returns:
            SimulationFingerprint summarizing the simulation dynamics
        """
        sentiments = []
        momenta = []
        factions = {"supportive": [], "opposing": [], "neutral": []}

        for platform in ["twitter", "reddit"]:
            metrics_file = os.path.join(simulation_dir, platform, "round_metrics.jsonl")
            if not os.path.exists(metrics_file):
                continue

            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            m = json.loads(line)
                            avg_sent = m.get("sentiment", {}).get("average", 0)
                            sentiments.append(avg_sent)

                            momentum = m.get("momentum", {})
                            momenta.append(momentum.get("velocity", 0))

                            faction_data = m.get("factions", {})
                            for stance in ["supportive", "opposing", "neutral"]:
                                count = faction_data.get(stance, {}).get("count", 0)
                                factions[stance].append(count)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        final_agreement = 0.0
        if sentiments:
            # Estimate agreement from final sentiment distribution
            final_abs = abs(sentiments[-1]) if sentiments else 0
            final_agreement = min(1.0, final_abs * 2)  # Strong sentiment = high agreement

        return SimulationFingerprint(
            simulation_id=simulation_id,
            sentiment_trajectory=sentiments,
            momentum_trajectory=momenta,
            faction_sizes=factions,
            final_agreement=final_agreement,
            total_rounds=len(sentiments),
        )

    def compare(
        self,
        current: SimulationFingerprint,
        historical: SimulationFingerprint,
    ) -> PatternMatch:
        """Compare two simulation fingerprints for similarity.

        Uses cosine similarity on trajectories and faction distribution
        correlation.

        Args:
            current: The current simulation's fingerprint
            historical: A historical simulation's fingerprint

        Returns:
            PatternMatch with similarity scores
        """
        sent_sim = self._trajectory_similarity(
            current.sentiment_trajectory,
            historical.sentiment_trajectory
        )
        mom_sim = self._trajectory_similarity(
            current.momentum_trajectory,
            historical.momentum_trajectory
        )
        faction_sim = self._faction_similarity(
            current.faction_sizes,
            historical.faction_sizes
        )

        # Weighted composite: sentiment matters most
        overall = sent_sim * 0.4 + mom_sim * 0.3 + faction_sim * 0.3

        return PatternMatch(
            matched_simulation_id=historical.simulation_id,
            similarity_score=overall,
            sentiment_similarity=sent_sim,
            momentum_similarity=mom_sim,
            faction_similarity=faction_sim,
        )

    def find_similar(
        self,
        current: SimulationFingerprint,
        historical_fingerprints: List[SimulationFingerprint],
        top_k: int = 3,
        min_similarity: float = 0.3,
    ) -> List[PatternMatch]:
        """Find the most similar historical simulations.

        Args:
            current: Current simulation fingerprint
            historical_fingerprints: List of historical fingerprints to compare
            top_k: Maximum number of matches to return
            min_similarity: Minimum similarity score to include

        Returns:
            Top-k matches sorted by similarity (highest first)
        """
        matches = []
        for hist in historical_fingerprints:
            if hist.simulation_id == current.simulation_id:
                continue
            match = self.compare(current, hist)
            if match.similarity_score >= min_similarity:
                matches.append(match)

        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:top_k]

    @staticmethod
    def _trajectory_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two trajectories.

        Handles different lengths by truncating to the shorter one.
        """
        if not a or not b:
            return 0.5  # No data, assume moderate similarity

        # Truncate to same length
        min_len = min(len(a), len(b))
        a = a[:min_len]
        b = b[:min_len]

        # Cosine similarity
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1e-10
        norm_b = math.sqrt(sum(x * x for x in b)) or 1e-10

        cos_sim = dot / (norm_a * norm_b)

        # Map from [-1, 1] to [0, 1]
        return (cos_sim + 1) / 2

    @staticmethod
    def _faction_similarity(a: Dict[str, List[int]], b: Dict[str, List[int]]) -> float:
        """Compare faction size distributions across two simulations."""
        if not a or not b:
            return 0.5

        similarities = []
        for stance in ["supportive", "opposing", "neutral"]:
            a_vals = a.get(stance, [])
            b_vals = b.get(stance, [])

            if not a_vals and not b_vals:
                similarities.append(1.0)
                continue
            if not a_vals or not b_vals:
                similarities.append(0.0)
                continue

            # Compare average faction sizes
            a_avg = sum(a_vals) / len(a_vals)
            b_avg = sum(b_vals) / len(b_vals)
            max_val = max(a_avg, b_avg, 1)
            sim = 1.0 - abs(a_avg - b_avg) / max_val
            similarities.append(max(0.0, sim))

        return sum(similarities) / len(similarities) if similarities else 0.5
