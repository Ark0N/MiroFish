"""
Minority opinion amplifier.

Weights contrarian/minority agent opinions more heavily when they provide
unique information not captured by the majority. Uses information-theoretic
measures (surprise/entropy) to identify high-value dissenting signals.
"""

import math
from typing import Dict, List, Any
from collections import Counter

from ..utils.logger import get_logger

logger = get_logger('mirofish.minority')


class MinorityAmplifier:
    """Identify and amplify high-value minority opinions."""

    def compute_information_value(
        self,
        agent_sentiments: Dict[str, float],
        agent_posts: Dict[str, List[str]],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute information value for each agent based on surprise/uniqueness.

        Agents whose opinions are rare (minority) but substantive get higher
        information value. This is based on Shannon surprise: -log2(p(opinion)).

        Args:
            agent_sentiments: Agent name -> average sentiment score
            agent_posts: Agent name -> list of post contents

        Returns:
            Dict mapping agent_name -> {"info_value": float, "is_minority": bool, ...}
        """
        if not agent_sentiments:
            return {}

        # Classify agents into stance bins
        stance_counts = Counter()
        agent_stances = {}
        for agent, sentiment in agent_sentiments.items():
            if sentiment > 0.15:
                stance = "positive"
            elif sentiment < -0.15:
                stance = "negative"
            else:
                stance = "neutral"
            stance_counts[stance] += 1
            agent_stances[agent] = stance

        total = sum(stance_counts.values())
        if total == 0:
            return {}

        # Compute per-stance probability and surprise
        stance_probs = {s: c / total for s, c in stance_counts.items()}

        # Shannon surprise: -log2(p). Rarer stances have higher surprise.
        stance_surprise = {}
        for stance, prob in stance_probs.items():
            if prob > 0:
                stance_surprise[stance] = -math.log2(prob)
            else:
                stance_surprise[stance] = 0.0

        # Max surprise for normalization
        max_surprise = max(stance_surprise.values()) if stance_surprise else 1.0

        # Compute per-agent information value
        results = {}
        for agent, sentiment in agent_sentiments.items():
            stance = agent_stances[agent]
            surprise = stance_surprise.get(stance, 0)
            normalized_surprise = surprise / max_surprise if max_surprise > 0 else 0

            # Content uniqueness: how many unique words does this agent use?
            posts = agent_posts.get(agent, [])
            unique_words = set()
            for post in posts:
                unique_words.update(post.lower().split())
            content_richness = min(1.0, len(unique_words) / 50.0) if unique_words else 0

            # Information value = surprise * content_richness
            info_value = normalized_surprise * 0.7 + content_richness * 0.3

            is_minority = stance_counts[stance] < total * 0.3

            results[agent] = {
                "agent_name": agent,
                "stance": stance,
                "sentiment": round(sentiment, 3),
                "surprise": round(surprise, 3),
                "info_value": round(info_value, 3),
                "is_minority": is_minority,
                "content_richness": round(content_richness, 3),
                "amplification_weight": round(1.0 + info_value, 3) if is_minority else 1.0,
            }

        return results

    def get_amplified_consensus(
        self,
        agent_sentiments: Dict[str, float],
        agent_posts: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Compute consensus with minority opinions amplified.

        Returns both standard and amplified consensus for comparison.
        """
        info_values = self.compute_information_value(agent_sentiments, agent_posts)

        if not info_values:
            return {"standard_consensus": 0.0, "amplified_consensus": 0.0, "delta": 0.0}

        # Standard consensus (unweighted)
        sentiments = list(agent_sentiments.values())
        standard = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Amplified consensus (weighted by amplification_weight)
        weighted_sum = 0.0
        weight_total = 0.0
        for agent, sentiment in agent_sentiments.items():
            weight = info_values.get(agent, {}).get("amplification_weight", 1.0)
            weighted_sum += sentiment * weight
            weight_total += weight

        amplified = weighted_sum / weight_total if weight_total > 0 else 0.0

        minority_agents = [a for a, v in info_values.items() if v["is_minority"]]

        return {
            "standard_consensus": round(standard, 4),
            "amplified_consensus": round(amplified, 4),
            "delta": round(amplified - standard, 4),
            "minority_count": len(minority_agents),
            "total_agents": len(agent_sentiments),
            "minority_agents": minority_agents[:10],
        }
