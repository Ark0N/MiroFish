"""
Prediction uncertainty decomposition.

Decomposes total prediction uncertainty into:
- Epistemic uncertainty: model/data uncertainty that decreases with more data
- Aleatoric uncertainty: inherent randomness that cannot be reduced

Reports both to users so they understand what kind of uncertainty remains.
"""

import math
from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.uncertainty')


class UncertaintyDecomposer:
    """Decompose prediction uncertainty into epistemic and aleatoric components."""

    def decompose(
        self,
        prediction_probability: float,
        agent_sentiments: List[float],
        n_simulations: int = 1,
        n_agents: int = 0,
        bootstrap_ci_width: float = 0.0,
    ) -> Dict[str, Any]:
        """Decompose uncertainty for a single prediction.

        Epistemic uncertainty (reducible):
        - Decreases with more agents (larger sample)
        - Decreases with more simulations (ensemble averaging)
        - Estimated from bootstrap CI width and sample size

        Aleatoric uncertainty (irreducible):
        - Inherent in the prediction task
        - Estimated from agent disagreement variance
        - Highest when probability is near 0.5 (max entropy)

        Args:
            prediction_probability: The point prediction (0-1)
            agent_sentiments: Per-agent sentiment scores
            n_simulations: Number of simulations contributing to prediction
            n_agents: Number of agents (if different from len(agent_sentiments))
            bootstrap_ci_width: Width of bootstrap confidence interval

        Returns:
            Dict with total_uncertainty, epistemic, aleatoric, and metadata
        """
        n = n_agents or len(agent_sentiments)

        # --- Aleatoric uncertainty ---
        # Binary entropy of the prediction: H(p) = -p*log(p) - (1-p)*log(1-p)
        p = max(0.01, min(0.99, prediction_probability))
        entropy = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        # Normalize to 0-1 (max entropy is 1.0 at p=0.5)
        aleatoric = entropy

        # Also factor in agent variance (high disagreement = high aleatoric)
        if agent_sentiments and len(agent_sentiments) >= 2:
            mean = sum(agent_sentiments) / len(agent_sentiments)
            variance = sum((s - mean) ** 2 for s in agent_sentiments) / len(agent_sentiments)
            # Normalize: variance of uniform[-1,1] is 1/3
            normalized_variance = min(1.0, variance / 0.33)
            aleatoric = aleatoric * 0.6 + normalized_variance * 0.4

        # --- Epistemic uncertainty ---
        # Decreases with sqrt(n_agents) and sqrt(n_simulations)
        agent_factor = 1.0 / math.sqrt(max(1, n)) if n > 0 else 1.0
        sim_factor = 1.0 / math.sqrt(max(1, n_simulations))

        # Bootstrap CI width directly measures epistemic uncertainty
        if bootstrap_ci_width > 0:
            epistemic = bootstrap_ci_width * 0.5 + agent_factor * 0.3 + sim_factor * 0.2
        else:
            epistemic = agent_factor * 0.6 + sim_factor * 0.4

        # Bound epistemic to 0-1
        epistemic = min(1.0, max(0.0, epistemic))

        # Total uncertainty
        total = math.sqrt(epistemic ** 2 + aleatoric ** 2)
        total = min(1.0, total)

        return {
            "total_uncertainty": round(total, 4),
            "epistemic": round(epistemic, 4),
            "aleatoric": round(aleatoric, 4),
            "entropy": round(entropy, 4),
            "n_agents": n,
            "n_simulations": n_simulations,
            "can_reduce_epistemic": epistemic > 0.1,
            "recommendation": self._recommend(epistemic, aleatoric),
        }

    @staticmethod
    def _recommend(epistemic: float, aleatoric: float) -> str:
        """Generate a recommendation based on uncertainty decomposition."""
        if epistemic > 0.3 and aleatoric < 0.5:
            return "High epistemic uncertainty — run more simulations or add more agents to reduce"
        elif epistemic < 0.2 and aleatoric > 0.7:
            return "High aleatoric uncertainty — prediction is inherently uncertain, more data won't help much"
        elif epistemic > 0.3 and aleatoric > 0.5:
            return "Both uncertainty types are high — more data may help but outcome is inherently hard to predict"
        else:
            return "Uncertainty is well-controlled — prediction is as reliable as the data allows"
