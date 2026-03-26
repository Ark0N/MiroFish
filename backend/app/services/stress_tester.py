"""
Prediction stress tester.

Systematically tests how predictions respond to extreme inputs:
all agents flipping, removing agents, injecting contradictions.
Reports a robustness score and stability index for each prediction.
"""

import copy
import math
from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.stress_test')


class PredictionStressTester:
    """Stress test predictions with extreme scenarios."""

    POSITIVE_KW = frozenset({"good", "great", "support", "agree", "happy", "love", "excellent", "hope", "progress"})
    NEGATIVE_KW = frozenset({"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail"})

    def stress_test(
        self,
        agent_sentiments: Dict[str, float],
        prediction_probability: float,
    ) -> Dict[str, Any]:
        """Run comprehensive stress tests on a prediction.

        Tests:
        1. Flip all agents: what if everyone changed their mind?
        2. Remove 50% of agents: is the prediction sample-dependent?
        3. Unanimous agreement: what's the theoretical maximum?
        4. Unanimous opposition: what's the theoretical minimum?
        5. Remove strongest voices: sensitivity to loudest agents

        Returns:
            Dict with stress scenarios, robustness score, and stability index
        """
        if not agent_sentiments:
            return {
                "robustness_score": 0.0,
                "stability_index": "unknown",
                "scenarios": [],
            }

        baseline = self._compute_consensus(agent_sentiments)
        scenarios = []

        # 1. Flip all agents
        flipped = {a: -s for a, s in agent_sentiments.items()}
        flip_consensus = self._compute_consensus(flipped)
        flip_delta = abs(flip_consensus - baseline)
        scenarios.append({
            "name": "Flip all agents",
            "description": "All agents reverse their stance",
            "baseline_consensus": round(baseline, 4),
            "stressed_consensus": round(flip_consensus, 4),
            "delta": round(flip_delta, 4),
            "impact": "high" if flip_delta > 0.5 else "medium" if flip_delta > 0.2 else "low",
        })

        # 2. Remove 50% of agents (keep every other)
        agents = sorted(agent_sentiments.keys())
        half = {a: agent_sentiments[a] for i, a in enumerate(agents) if i % 2 == 0}
        if half:
            half_consensus = self._compute_consensus(half)
            half_delta = abs(half_consensus - baseline)
            scenarios.append({
                "name": "Remove 50% agents",
                "description": f"Keep {len(half)} of {len(agents)} agents",
                "baseline_consensus": round(baseline, 4),
                "stressed_consensus": round(half_consensus, 4),
                "delta": round(half_delta, 4),
                "impact": "high" if half_delta > 0.3 else "medium" if half_delta > 0.1 else "low",
            })

        # 3. Remove top 3 most extreme agents
        sorted_by_abs = sorted(agent_sentiments.items(), key=lambda x: abs(x[1]), reverse=True)
        if len(sorted_by_abs) > 3:
            without_extreme = {a: s for a, s in sorted_by_abs[3:]}
            extreme_consensus = self._compute_consensus(without_extreme)
            extreme_delta = abs(extreme_consensus - baseline)
            scenarios.append({
                "name": "Remove strongest voices",
                "description": f"Remove top 3 most extreme agents",
                "baseline_consensus": round(baseline, 4),
                "stressed_consensus": round(extreme_consensus, 4),
                "delta": round(extreme_delta, 4),
                "impact": "high" if extreme_delta > 0.2 else "medium" if extreme_delta > 0.1 else "low",
            })

        # 4. Add noise: randomize 30% of agents
        import random
        rng = random.Random(42)
        noisy = dict(agent_sentiments)
        noise_agents = rng.sample(list(noisy.keys()), min(len(noisy), max(1, len(noisy) * 3 // 10)))
        for a in noise_agents:
            noisy[a] = rng.uniform(-1, 1)
        noise_consensus = self._compute_consensus(noisy)
        noise_delta = abs(noise_consensus - baseline)
        scenarios.append({
            "name": "Inject 30% noise",
            "description": f"Randomize {len(noise_agents)} agents' sentiments",
            "baseline_consensus": round(baseline, 4),
            "stressed_consensus": round(noise_consensus, 4),
            "delta": round(noise_delta, 4),
            "impact": "high" if noise_delta > 0.2 else "medium" if noise_delta > 0.1 else "low",
        })

        # Compute robustness score: average of (1 - normalized delta) across scenarios
        deltas = [s["delta"] for s in scenarios]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        robustness = max(0, min(1, 1.0 - avg_delta))

        # Stability index
        if robustness >= 0.8:
            stability = "rock-solid"
        elif robustness >= 0.6:
            stability = "stable"
        elif robustness >= 0.4:
            stability = "moderate"
        elif robustness >= 0.2:
            stability = "fragile"
        else:
            stability = "volatile"

        return {
            "robustness_score": round(robustness, 3),
            "stability_index": stability,
            "baseline_consensus": round(baseline, 4),
            "scenarios": scenarios,
            "recommendation": self._recommend(stability),
        }

    def compute_stability_index(
        self,
        version_probabilities: List[float],
    ) -> Dict[str, Any]:
        """Compute stability index from prediction version history.

        Args:
            version_probabilities: List of probability values across versions

        Returns:
            Stability analysis
        """
        if len(version_probabilities) < 2:
            return {"stability_index": "insufficient_data", "variance": 0.0}

        mean = sum(version_probabilities) / len(version_probabilities)
        variance = sum((p - mean) ** 2 for p in version_probabilities) / len(version_probabilities)
        std = math.sqrt(variance)

        # Count direction changes
        changes = sum(
            1 for i in range(2, len(version_probabilities))
            if (version_probabilities[i] - version_probabilities[i-1]) *
               (version_probabilities[i-1] - version_probabilities[i-2]) < 0
        )

        max_change = max(
            abs(version_probabilities[i] - version_probabilities[i-1])
            for i in range(1, len(version_probabilities))
        )

        if std < 0.05 and changes <= 1:
            index = "rock-solid"
        elif std < 0.1:
            index = "stable"
        elif std < 0.2:
            index = "moderate"
        else:
            index = "volatile"

        return {
            "stability_index": index,
            "variance": round(variance, 4),
            "std_dev": round(std, 4),
            "direction_changes": changes,
            "max_single_change": round(max_change, 4),
            "num_versions": len(version_probabilities),
        }

    def _compute_consensus(self, sentiments: Dict[str, float]) -> float:
        if not sentiments:
            return 0.0
        return sum(sentiments.values()) / len(sentiments)

    @staticmethod
    def _recommend(stability: str) -> str:
        recs = {
            "rock-solid": "Prediction is highly robust — confident enough for high-stakes decisions",
            "stable": "Prediction is reliable — minor perturbations don't change the outcome",
            "moderate": "Prediction is reasonably stable but sensitive to some factors",
            "fragile": "Prediction is fragile — results depend heavily on specific agents",
            "volatile": "Prediction is unreliable — treat as directional signal only",
        }
        return recs.get(stability, "Review prediction carefully")
