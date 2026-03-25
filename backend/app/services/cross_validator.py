"""
Cross-validation prediction scorer.

Splits agents into train/test groups. The train group's consensus forms
the prediction, while the test group independently evaluates. Comparing
the two provides internal validation without waiting for real-world outcomes.
"""

import random
import math
from typing import Dict, List, Any, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.cross_validator')


class CrossValidator:
    """Split-sample validation for prediction robustness."""

    POSITIVE_KW = frozenset({"good", "great", "support", "agree", "happy", "love",
                             "excellent", "hope", "progress", "positive", "benefit"})
    NEGATIVE_KW = frozenset({"bad", "terrible", "oppose", "disagree", "angry", "hate",
                             "awful", "crisis", "fail", "problem", "danger", "risk"})

    def validate(
        self,
        agent_posts: Dict[str, List[str]],
        n_folds: int = 5,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Run k-fold cross-validation on agent sentiment predictions.

        Splits agents into k folds. For each fold, the held-out agents form
        the "test" group while the rest form "train". Compares train consensus
        direction with test consensus direction.

        Args:
            agent_posts: Mapping of agent_name -> list of post contents
            n_folds: Number of cross-validation folds
            seed: Random seed for reproducibility

        Returns:
            Dict with agreement_rate, per-fold results, and overall statistics
        """
        if not agent_posts or len(agent_posts) < 2:
            return {
                "agreement_rate": 0.0,
                "n_folds": 0,
                "n_agents": len(agent_posts),
                "folds": [],
                "is_valid": False,
                "reason": "Need at least 2 agents for cross-validation",
            }

        agents = list(agent_posts.keys())
        n_agents = len(agents)
        n_folds = min(n_folds, n_agents)  # Can't have more folds than agents

        rng = random.Random(seed)
        rng.shuffle(agents)

        # Create folds
        fold_size = max(1, n_agents // n_folds)
        folds = []
        for i in range(n_folds):
            start = i * fold_size
            end = start + fold_size if i < n_folds - 1 else n_agents
            folds.append(agents[start:end])

        # Run cross-validation
        fold_results = []
        agreements = 0

        for fold_idx in range(n_folds):
            test_agents = set(folds[fold_idx])
            train_agents = set(agents) - test_agents

            if not train_agents or not test_agents:
                continue

            train_sentiment = self._compute_group_sentiment(agent_posts, train_agents)
            test_sentiment = self._compute_group_sentiment(agent_posts, test_agents)

            # Check if train and test agree on direction
            train_direction = "positive" if train_sentiment > 0.05 else ("negative" if train_sentiment < -0.05 else "neutral")
            test_direction = "positive" if test_sentiment > 0.05 else ("negative" if test_sentiment < -0.05 else "neutral")

            agrees = train_direction == test_direction

            fold_results.append({
                "fold": fold_idx + 1,
                "train_agents": len(train_agents),
                "test_agents": len(test_agents),
                "train_sentiment": round(train_sentiment, 4),
                "test_sentiment": round(test_sentiment, 4),
                "train_direction": train_direction,
                "test_direction": test_direction,
                "agrees": agrees,
                "sentiment_delta": round(abs(train_sentiment - test_sentiment), 4),
            })

            if agrees:
                agreements += 1

        valid_folds = len(fold_results)
        agreement_rate = agreements / valid_folds if valid_folds > 0 else 0.0

        # Compute average sentiment delta across folds
        avg_delta = (
            sum(f["sentiment_delta"] for f in fold_results) / valid_folds
            if valid_folds > 0 else 0.0
        )

        return {
            "agreement_rate": round(agreement_rate, 4),
            "n_folds": valid_folds,
            "n_agents": n_agents,
            "folds": fold_results,
            "avg_sentiment_delta": round(avg_delta, 4),
            "is_valid": valid_folds >= 2,
            "interpretation": self._interpret(agreement_rate, avg_delta),
        }

    def _compute_group_sentiment(
        self,
        agent_posts: Dict[str, List[str]],
        agent_names: set,
    ) -> float:
        """Compute average sentiment for a group of agents."""
        scores = []
        for agent in agent_names:
            posts = agent_posts.get(agent, [])
            for post in posts:
                lower = post.lower()
                pos = sum(1 for w in self.POSITIVE_KW if w in lower)
                neg = sum(1 for w in self.NEGATIVE_KW if w in lower)
                total = pos + neg
                if total > 0:
                    scores.append((pos - neg) / total)
                else:
                    scores.append(0.0)
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _interpret(agreement_rate: float, avg_delta: float) -> str:
        """Interpret cross-validation results."""
        if agreement_rate >= 0.8 and avg_delta < 0.1:
            return "Strong consensus — prediction is robust across agent subgroups"
        elif agreement_rate >= 0.6:
            return "Moderate consensus — prediction direction is consistent but magnitude varies"
        elif agreement_rate >= 0.4:
            return "Weak consensus — significant disagreement between agent subgroups"
        else:
            return "No consensus — prediction is unreliable, agents fundamentally disagree"
