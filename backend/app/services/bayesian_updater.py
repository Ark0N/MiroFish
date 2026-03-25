"""
Bayesian prediction updater.

Adjusts prediction probabilities using Bayes' theorem when new evidence
arrives (new simulation waves, new data ingestion, consensus updates).

Prior probability: current prediction probability
Likelihood: how well new evidence supports the prediction
Posterior: updated probability after incorporating new evidence

Maintains an update history for transparency and auditability.
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

logger = get_logger('mirofish.bayesian_updater')


@dataclass
class UpdateRecord:
    """Record of a single Bayesian update."""
    timestamp: str
    prior: float
    likelihood: float
    posterior: float
    evidence_source: str  # "consensus", "wave", "ingestion", "manual"
    evidence_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "prior": round(self.prior, 4),
            "likelihood": round(self.likelihood, 4),
            "posterior": round(self.posterior, 4),
            "evidence_source": self.evidence_source,
            "evidence_summary": self.evidence_summary,
        }


@dataclass
class PredictionHistory:
    """Full history of Bayesian updates for a prediction."""
    event: str
    initial_probability: float
    current_probability: float
    updates: List[UpdateRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "initial_probability": round(self.initial_probability, 4),
            "current_probability": round(self.current_probability, 4),
            "num_updates": len(self.updates),
            "updates": [u.to_dict() for u in self.updates],
        }


class BayesianUpdater:
    """Update prediction probabilities using Bayes' theorem.

    For a prediction with prior probability P(H):
        P(H|E) = P(E|H) * P(H) / P(E)

    Where:
        P(H) = prior (current prediction probability)
        P(E|H) = likelihood (how likely is the evidence if the prediction is true)
        P(E) = marginal likelihood (normalizing constant)
        P(H|E) = posterior (updated probability)

    Likelihood estimation from consensus data:
        - High agreement supporting prediction → high likelihood
        - Low agreement → moderate likelihood
        - Consensus opposing prediction → low likelihood
    """

    # Bounds to prevent probabilities from collapsing to 0 or 1
    MIN_PROB = 0.01
    MAX_PROB = 0.99

    def update_from_consensus(
        self,
        prior: float,
        agreement_score: float,
        stance_distribution: Dict[str, int],
        total_agents: int,
    ) -> tuple:
        """Update probability using consensus analysis data.

        Args:
            prior: Current prediction probability (0-1)
            agreement_score: Consensus agreement score (0-1)
            stance_distribution: {"supportive": N, "opposing": N, "neutral": N}
            total_agents: Total agents analyzed

        Returns:
            (posterior, likelihood) tuple
        """
        if total_agents == 0:
            return prior, 0.5

        supportive = stance_distribution.get("supportive", 0)
        opposing = stance_distribution.get("opposing", 0)

        # Likelihood: proportion of agents supporting the prediction direction
        # adjusted by agreement strength
        support_ratio = supportive / total_agents if total_agents > 0 else 0.5

        # Scale likelihood: support_ratio maps to [0.2, 0.9] range
        # Strong support → high likelihood, opposition → low likelihood
        likelihood = 0.2 + support_ratio * 0.7

        # Adjust by agreement strength — strong consensus amplifies the signal
        likelihood = likelihood * (0.5 + 0.5 * agreement_score)

        return self._bayes_update(prior, likelihood), likelihood

    def update_from_sentiment_shift(
        self,
        prior: float,
        sentiment_delta: float,
        prediction_direction: str = "positive",
    ) -> tuple:
        """Update probability based on sentiment momentum shift.

        Args:
            prior: Current probability
            sentiment_delta: Change in sentiment (-1 to 1)
            prediction_direction: "positive" if prediction aligns with positive sentiment

        Returns:
            (posterior, likelihood) tuple
        """
        # If prediction expects positive outcome and sentiment shifts positive → boost
        if prediction_direction == "positive":
            # Map sentiment_delta [-1,1] to likelihood [0.2, 0.9]
            likelihood = 0.55 + sentiment_delta * 0.35
        else:
            # Inverse: negative prediction boosted by negative sentiment
            likelihood = 0.55 - sentiment_delta * 0.35

        likelihood = max(0.1, min(0.95, likelihood))
        return self._bayes_update(prior, likelihood), likelihood

    def update_from_new_data(
        self,
        prior: float,
        relevance_score: float,
        alignment_score: float,
    ) -> tuple:
        """Update probability when new data is ingested.

        Args:
            prior: Current probability
            relevance_score: How relevant the new data is (0-1)
            alignment_score: How much new data supports the prediction (0-1)

        Returns:
            (posterior, likelihood) tuple
        """
        # Irrelevant data barely moves the probability
        # Relevant aligned data boosts, relevant contradicting data reduces
        if relevance_score < 0.1:
            return prior, 0.5  # neutral update

        # Likelihood = base 0.5 + (alignment - 0.5) * relevance
        likelihood = 0.5 + (alignment_score - 0.5) * relevance_score
        likelihood = max(0.1, min(0.95, likelihood))

        return self._bayes_update(prior, likelihood), likelihood

    def _bayes_update(self, prior: float, likelihood: float) -> float:
        """Apply Bayes' theorem update.

        Uses the odds form for numerical stability:
            posterior_odds = likelihood_ratio * prior_odds
        """
        prior = max(self.MIN_PROB, min(self.MAX_PROB, prior))
        likelihood = max(0.01, min(0.99, likelihood))

        # Complement likelihood: P(E|~H) = 1 - likelihood
        complement = 1.0 - likelihood

        # Odds form: avoids division by P(E)
        prior_odds = prior / (1.0 - prior)
        likelihood_ratio = likelihood / complement if complement > 0 else likelihood / 0.01
        posterior_odds = likelihood_ratio * prior_odds

        # Convert back to probability
        posterior = posterior_odds / (1.0 + posterior_odds)

        return max(self.MIN_PROB, min(self.MAX_PROB, round(posterior, 4)))

    def create_update_record(
        self,
        prior: float,
        posterior: float,
        likelihood: float,
        evidence_source: str,
        evidence_summary: str,
    ) -> UpdateRecord:
        """Create an update record for history tracking."""
        return UpdateRecord(
            timestamp=datetime.now().isoformat(),
            prior=prior,
            likelihood=likelihood,
            posterior=posterior,
            evidence_source=evidence_source,
            evidence_summary=evidence_summary,
        )
