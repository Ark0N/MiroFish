"""
Simulation quality scorer.

Computes an overall quality metric for each simulation based on:
- Agent diversity (variety of persona types and behavior patterns)
- Network connectivity (how well-connected the follow graph is)
- Opinion spread (range and distribution of sentiments)
- Participation rate (fraction of agents actively posting)
- Absence of degenerate behaviors (instant convergence, all-neutral)
"""

import math
from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.sim_quality')


class SimulationQualityScorer:
    """Compute quality metrics for a simulation."""

    def score(
        self,
        agent_sentiments: Dict[str, float],
        follow_graph: Dict[str, List[str]],
        agent_types: Dict[str, str],
        participation_rate: float,
        rounds_data: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute comprehensive simulation quality score.

        Args:
            agent_sentiments: Agent -> sentiment score
            follow_graph: Agent -> followed agents
            agent_types: Agent -> persona type (e.g., "Person", "Official")
            participation_rate: Fraction of agents that posted (0-1)
            rounds_data: Optional list of per-round metrics

        Returns:
            Dict with component scores and overall quality
        """
        diversity = self._diversity_score(agent_types)
        connectivity = self._connectivity_score(follow_graph)
        opinion_spread = self._opinion_spread_score(agent_sentiments)
        participation = min(1.0, participation_rate)
        degenerate = self._degenerate_check(agent_sentiments, rounds_data)

        # Weighted composite
        overall = (
            diversity * 0.2 +
            connectivity * 0.15 +
            opinion_spread * 0.25 +
            participation * 0.2 +
            degenerate * 0.2
        )

        grade = self._grade(overall)

        return {
            "overall_quality": round(overall, 3),
            "grade": grade,
            "components": {
                "diversity": round(diversity, 3),
                "connectivity": round(connectivity, 3),
                "opinion_spread": round(opinion_spread, 3),
                "participation": round(participation, 3),
                "non_degenerate": round(degenerate, 3),
            },
            "n_agents": len(agent_sentiments),
            "n_types": len(set(agent_types.values())),
            "recommendations": self._recommendations(
                diversity, connectivity, opinion_spread, participation, degenerate
            ),
        }

    def _diversity_score(self, agent_types: Dict[str, str]) -> float:
        """Score based on variety of agent persona types."""
        if not agent_types:
            return 0.0

        types = list(agent_types.values())
        unique_types = set(types)
        n_types = len(unique_types)
        n_agents = len(types)

        # Shannon entropy of type distribution, normalized
        from collections import Counter
        counts = Counter(types)
        probs = [c / n_agents for c in counts.values()]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(n_types) if n_types > 1 else 1.0

        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _connectivity_score(self, follow_graph: Dict[str, List[str]]) -> float:
        """Score based on how well-connected the network is."""
        if not follow_graph:
            return 0.0

        all_agents = set(follow_graph.keys())
        for follows in follow_graph.values():
            all_agents.update(follows)

        n = len(all_agents)
        if n <= 1:
            return 0.0

        # Average connections per agent vs maximum possible
        total_connections = sum(len(f) for f in follow_graph.values())
        max_connections = n * (n - 1)
        density = total_connections / max_connections if max_connections > 0 else 0

        # Ideal density is moderate (0.1-0.3), too high means no structure
        if density < 0.05:
            return density * 10  # Too sparse
        elif density > 0.5:
            return max(0.5, 1.0 - (density - 0.5))  # Too dense
        else:
            return min(1.0, density * 3)

    def _opinion_spread_score(self, sentiments: Dict[str, float]) -> float:
        """Score based on opinion diversity."""
        if not sentiments:
            return 0.0

        values = list(sentiments.values())
        spread = max(values) - min(values)
        # Ideal spread is > 0.5 (agents have diverse opinions)
        return min(1.0, spread / 1.0)

    def _degenerate_check(
        self,
        sentiments: Dict[str, float],
        rounds_data: List[Dict[str, Any]] = None,
    ) -> float:
        """Score checking for degenerate behaviors.

        Returns 1.0 for non-degenerate, lower for problematic simulations.
        """
        if not sentiments:
            return 0.0

        values = list(sentiments.values())

        # Check 1: All agents identical (no diversity)
        if len(set(round(v, 2) for v in values)) == 1:
            return 0.2  # Bad: all identical

        # Check 2: All neutral (no opinions formed)
        if all(abs(v) < 0.05 for v in values):
            return 0.3  # Bad: nobody has an opinion

        # Check 3: Instant convergence (check rounds data)
        if rounds_data and len(rounds_data) >= 3:
            sentiments_by_round = [r.get("sentiment", {}).get("average", 0) for r in rounds_data]
            if len(sentiments_by_round) >= 3:
                # Check if sentiment was identical from round 2 onwards
                if all(abs(s - sentiments_by_round[1]) < 0.02 for s in sentiments_by_round[2:]):
                    return 0.5  # Suspicious: converged too fast

        return 1.0  # Good: non-degenerate

    def _grade(self, score: float) -> str:
        if score >= 0.8:
            return "A"
        elif score >= 0.65:
            return "B"
        elif score >= 0.5:
            return "C"
        elif score >= 0.35:
            return "D"
        else:
            return "F"

    def _recommendations(self, div, conn, spread, part, degen) -> List[str]:
        recs = []
        if div < 0.5:
            recs.append("Add more diverse agent types for better perspective coverage")
        if conn < 0.3:
            recs.append("Increase network connectivity — agents are too isolated")
        if spread < 0.3:
            recs.append("Opinion spread is low — consider adding contrarian agents")
        if part < 0.5:
            recs.append("Participation rate is low — increase agent activity or reduce agent count")
        if degen < 0.7:
            recs.append("Simulation shows degenerate patterns — check agent prompts and parameters")
        if not recs:
            recs.append("Simulation quality is good — no major issues detected")
        return recs
