"""
Counterfactual analysis service.

Asks "what if?" — given a prediction, computes how the probability would
change if key factors were different (remove influential agent, flip a
faction's stance, etc.). Reports sensitivity to each factor.
"""

import copy
from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.counterfactual')


class CounterfactualAnalyzer:
    """Compute counterfactual scenarios for prediction sensitivity analysis."""

    POSITIVE_KW = frozenset({"good", "great", "support", "agree", "happy", "love", "excellent", "hope", "progress"})
    NEGATIVE_KW = frozenset({"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail"})

    def analyze(
        self,
        agent_sentiments: Dict[str, float],
        prediction_probability: float,
        top_influencers: List[str] = None,
        faction_members: Dict[str, List[str]] = None,
    ) -> Dict[str, Any]:
        """Run counterfactual scenarios on a prediction.

        Args:
            agent_sentiments: Agent -> sentiment scores
            prediction_probability: Current prediction probability
            top_influencers: Most influential agents (to test removal)
            faction_members: {"supportive": [...], "opposing": [...], ...}

        Returns:
            Dict with scenarios and their impact on the prediction
        """
        if not agent_sentiments:
            return {"scenarios": [], "most_sensitive_factor": None}

        baseline_sentiment = sum(agent_sentiments.values()) / len(agent_sentiments)
        scenarios = []

        # Scenario 1: Remove top influencer
        if top_influencers:
            for influencer in top_influencers[:3]:
                if influencer in agent_sentiments:
                    modified = {a: s for a, s in agent_sentiments.items() if a != influencer}
                    if modified:
                        new_sentiment = sum(modified.values()) / len(modified)
                        delta = new_sentiment - baseline_sentiment
                        prob_impact = self._sentiment_to_prob_delta(delta, prediction_probability)
                        scenarios.append({
                            "scenario": f"Remove agent '{influencer}'",
                            "type": "remove_agent",
                            "target": influencer,
                            "sentiment_delta": round(delta, 4),
                            "probability_impact": round(prob_impact, 4),
                            "new_probability": round(max(0.05, min(0.99, prediction_probability + prob_impact)), 4),
                        })

        # Scenario 2: Flip faction stance
        if faction_members:
            for faction_name, members in faction_members.items():
                if not members or faction_name == "neutral":
                    continue
                modified = copy.copy(agent_sentiments)
                for member in members:
                    if member in modified:
                        modified[member] = -modified[member]  # Flip sentiment

                new_sentiment = sum(modified.values()) / len(modified)
                delta = new_sentiment - baseline_sentiment
                prob_impact = self._sentiment_to_prob_delta(delta, prediction_probability)
                scenarios.append({
                    "scenario": f"Flip '{faction_name}' faction stance ({len(members)} agents)",
                    "type": "flip_faction",
                    "target": faction_name,
                    "agents_affected": len(members),
                    "sentiment_delta": round(delta, 4),
                    "probability_impact": round(prob_impact, 4),
                    "new_probability": round(max(0.05, min(0.99, prediction_probability + prob_impact)), 4),
                })

        # Scenario 3: Unanimous agreement
        all_positive = {a: abs(s) for a, s in agent_sentiments.items()}
        pos_sentiment = sum(all_positive.values()) / len(all_positive)
        delta_pos = pos_sentiment - baseline_sentiment
        prob_impact_pos = self._sentiment_to_prob_delta(delta_pos, prediction_probability)
        scenarios.append({
            "scenario": "All agents agree positively",
            "type": "unanimous_positive",
            "sentiment_delta": round(delta_pos, 4),
            "probability_impact": round(prob_impact_pos, 4),
            "new_probability": round(max(0.05, min(0.99, prediction_probability + prob_impact_pos)), 4),
        })

        # Scenario 4: Unanimous disagreement
        all_negative = {a: -abs(s) for a, s in agent_sentiments.items()}
        neg_sentiment = sum(all_negative.values()) / len(all_negative)
        delta_neg = neg_sentiment - baseline_sentiment
        prob_impact_neg = self._sentiment_to_prob_delta(delta_neg, prediction_probability)
        scenarios.append({
            "scenario": "All agents disagree",
            "type": "unanimous_negative",
            "sentiment_delta": round(delta_neg, 4),
            "probability_impact": round(prob_impact_neg, 4),
            "new_probability": round(max(0.05, min(0.99, prediction_probability + prob_impact_neg)), 4),
        })

        # Sort by absolute impact
        scenarios.sort(key=lambda s: abs(s["probability_impact"]), reverse=True)

        most_sensitive = scenarios[0]["scenario"] if scenarios else None

        return {
            "baseline_probability": prediction_probability,
            "baseline_sentiment": round(baseline_sentiment, 4),
            "scenarios": scenarios,
            "most_sensitive_factor": most_sensitive,
            "total_scenarios": len(scenarios),
        }

    @staticmethod
    def _sentiment_to_prob_delta(sentiment_delta: float, current_prob: float) -> float:
        """Map a sentiment change to a probability change."""
        # Scale: 1.0 sentiment shift ≈ 0.3 probability shift
        return sentiment_delta * 0.3
