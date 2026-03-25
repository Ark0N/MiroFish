"""
Bootstrap confidence band calculator.

Uses bootstrap resampling of agent sentiment/opinions to compute
statistically rigorous confidence intervals for predictions, rather
than relying on LLM-estimated intervals.
"""

import random
import math
from typing import Dict, List, Any, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.bootstrap')


class BootstrapConfidence:
    """Compute confidence bands via bootstrap resampling of agent opinions."""

    def compute_confidence_interval(
        self,
        agent_sentiments: List[float],
        confidence_level: float = 0.95,
        n_bootstrap: int = 100,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Compute bootstrap confidence interval for mean sentiment.

        Resamples agent sentiments with replacement to estimate the
        distribution of the mean, then extracts percentile-based
        confidence intervals.

        Args:
            agent_sentiments: List of per-agent sentiment scores (-1 to 1)
            confidence_level: Confidence level (default 0.95 for 95% CI)
            n_bootstrap: Number of bootstrap samples
            seed: Random seed for reproducibility

        Returns:
            Dict with mean, ci_low, ci_high, std_error, n_agents, n_bootstrap
        """
        if not agent_sentiments:
            return {
                "mean": 0.0,
                "ci_low": 0.0,
                "ci_high": 0.0,
                "std_error": 0.0,
                "n_agents": 0,
                "n_bootstrap": 0,
            }

        rng = random.Random(seed)
        n = len(agent_sentiments)
        observed_mean = sum(agent_sentiments) / n

        # Bootstrap resampling
        bootstrap_means = []
        for _ in range(n_bootstrap):
            sample = [rng.choice(agent_sentiments) for _ in range(n)]
            bootstrap_means.append(sum(sample) / len(sample))

        bootstrap_means.sort()

        # Percentile method for confidence interval
        alpha = 1 - confidence_level
        lower_idx = max(0, int(math.floor(alpha / 2 * n_bootstrap)))
        upper_idx = min(n_bootstrap - 1, int(math.ceil((1 - alpha / 2) * n_bootstrap)) - 1)

        ci_low = bootstrap_means[lower_idx]
        ci_high = bootstrap_means[upper_idx]

        # Standard error of the mean
        std_error = (
            math.sqrt(sum((m - observed_mean) ** 2 for m in bootstrap_means) / n_bootstrap)
            if n_bootstrap > 0 else 0.0
        )

        return {
            "mean": round(observed_mean, 4),
            "ci_low": round(ci_low, 4),
            "ci_high": round(ci_high, 4),
            "std_error": round(std_error, 4),
            "n_agents": n,
            "n_bootstrap": n_bootstrap,
        }

    def compute_prediction_bands(
        self,
        agent_sentiments: Dict[str, float],
        prediction_probability: float,
        confidence_level: float = 0.95,
        n_bootstrap: int = 100,
    ) -> Dict[str, Any]:
        """Compute prediction-level confidence bands.

        Maps bootstrapped sentiment distributions to probability confidence bands.

        Args:
            agent_sentiments: Agent name -> sentiment score mapping
            prediction_probability: The point prediction probability
            confidence_level: Confidence level
            n_bootstrap: Number of bootstrap samples

        Returns:
            Dict with probability, ci_low, ci_high, band_width, sentiment_stats
        """
        sentiments = list(agent_sentiments.values())
        sentiment_ci = self.compute_confidence_interval(
            sentiments, confidence_level, n_bootstrap
        )

        # Map sentiment CI to probability CI
        # Sentiment range [-1, 1] maps to probability range [0, 1]
        # Using a sigmoid-like mapping centered on the prediction probability
        mean_sent = sentiment_ci["mean"]
        ci_low_sent = sentiment_ci["ci_low"]
        ci_high_sent = sentiment_ci["ci_high"]

        # Scale sentiment uncertainty to probability uncertainty
        # Wider sentiment CI = wider probability CI
        sent_range = ci_high_sent - ci_low_sent
        prob_uncertainty = sent_range / 2  # Scale factor

        prob_ci_low = max(0.0, prediction_probability - prob_uncertainty)
        prob_ci_high = min(1.0, prediction_probability + prob_uncertainty)

        return {
            "probability": prediction_probability,
            "ci_low": round(prob_ci_low, 4),
            "ci_high": round(prob_ci_high, 4),
            "band_width": round(prob_ci_high - prob_ci_low, 4),
            "confidence_level": confidence_level,
            "sentiment_stats": sentiment_ci,
        }
