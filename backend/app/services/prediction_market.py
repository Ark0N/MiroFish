"""
Agent prediction market.

Virtual prediction market where agents "bet" on outcomes using karma points.
Agents more confident in their stance commit more karma. The bet distribution
provides a market-based probability estimate complementing sentiment analysis.
"""

import math
from typing import Dict, List, Any
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_market')


@dataclass
class AgentBet:
    """A single agent's bet on a prediction."""
    agent_name: str
    position: str  # "for" or "against"
    stake: float  # karma committed (0-1 of available)
    confidence: float  # 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "position": self.position,
            "stake": round(self.stake, 3),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class MarketState:
    """State of a prediction market."""
    prediction_event: str
    market_probability: float  # 0-1, derived from bet distribution
    total_for_stake: float
    total_against_stake: float
    num_bettors: int
    bets: List[AgentBet] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_event": self.prediction_event,
            "market_probability": round(self.market_probability, 4),
            "total_for_stake": round(self.total_for_stake, 3),
            "total_against_stake": round(self.total_against_stake, 3),
            "num_bettors": self.num_bettors,
            "bets": [b.to_dict() for b in self.bets],
        }


class PredictionMarket:
    """Virtual prediction market for probability estimation."""

    def create_market(
        self,
        prediction_event: str,
        agent_sentiments: Dict[str, float],
        agent_karma: Dict[str, float] = None,
    ) -> MarketState:
        """Create a prediction market from agent sentiments.

        Each agent's "bet" is derived from their sentiment:
        - Positive sentiment → bet FOR the prediction
        - Negative sentiment → bet AGAINST
        - Stake = abs(sentiment) * available karma (confidence = willingness to bet)

        Args:
            prediction_event: What the prediction is about
            agent_sentiments: Agent -> sentiment score (-1 to 1)
            agent_karma: Agent -> available karma (default 1.0 for all)

        Returns:
            MarketState with derived bets and market probability
        """
        if not agent_sentiments:
            return MarketState(
                prediction_event=prediction_event,
                market_probability=0.5,
                total_for_stake=0,
                total_against_stake=0,
                num_bettors=0,
            )

        bets = []
        total_for = 0.0
        total_against = 0.0

        for agent, sentiment in agent_sentiments.items():
            karma = (agent_karma or {}).get(agent, 1.0)
            confidence = abs(sentiment)
            stake = confidence * karma

            if sentiment > 0.05:
                position = "for"
                total_for += stake
            elif sentiment < -0.05:
                position = "against"
                total_against += stake
            else:
                continue  # Neutral agents don't bet

            bets.append(AgentBet(
                agent_name=agent,
                position=position,
                stake=stake,
                confidence=confidence,
            ))

        total_stake = total_for + total_against
        market_prob = total_for / total_stake if total_stake > 0 else 0.5

        return MarketState(
            prediction_event=prediction_event,
            market_probability=market_prob,
            total_for_stake=total_for,
            total_against_stake=total_against,
            num_bettors=len(bets),
            bets=bets,
        )

    def detect_arbitrage(
        self,
        market_probability: float,
        sentiment_probability: float,
        threshold: float = 0.15,
    ) -> Dict[str, Any]:
        """Detect divergence between market and sentiment probabilities.

        Large divergence suggests agents' actions don't match their words.

        Args:
            market_probability: From betting pool
            sentiment_probability: From consensus analysis
            threshold: Minimum divergence to flag

        Returns:
            Arbitrage signal analysis
        """
        divergence = market_probability - sentiment_probability
        abs_divergence = abs(divergence)
        has_arbitrage = abs_divergence > threshold

        if has_arbitrage:
            if divergence > 0:
                signal = ("Agents are betting MORE confidently than their posts suggest. "
                          "Their actions reveal higher conviction than their words.")
            else:
                signal = ("Agents are betting LESS confidently than their posts suggest. "
                          "Their public statements may be more extreme than their true beliefs.")
        else:
            signal = "Market and sentiment probabilities are consistent."

        return {
            "has_arbitrage": has_arbitrage,
            "divergence": round(divergence, 4),
            "abs_divergence": round(abs_divergence, 4),
            "market_probability": round(market_probability, 4),
            "sentiment_probability": round(sentiment_probability, 4),
            "signal": signal,
        }

    def aggregate_methods(
        self,
        probabilities: List[float],
    ) -> Dict[str, float]:
        """Compare multiple aggregation methods for a set of probabilities.

        Args:
            probabilities: List of probability estimates (0-1)

        Returns:
            Dict mapping method name -> aggregated probability
        """
        if not probabilities:
            return {"mean": 0.5, "median": 0.5, "geometric_mean": 0.5, "extremized_mean": 0.5}

        n = len(probabilities)
        sorted_p = sorted(probabilities)

        # Mean
        mean = sum(probabilities) / n

        # Median
        if n % 2 == 0:
            median = (sorted_p[n // 2 - 1] + sorted_p[n // 2]) / 2
        else:
            median = sorted_p[n // 2]

        # Geometric mean (only for positive values, clip to avoid log(0))
        clipped = [max(0.001, min(0.999, p)) for p in probabilities]
        log_sum = sum(math.log(p) for p in clipped)
        geometric_mean = math.exp(log_sum / n)

        # Extremized mean: push away from 0.5 to correct for averaging bias
        # extremized = mean^alpha / (mean^alpha + (1-mean)^alpha) where alpha > 1
        alpha = 1.5
        if mean > 0.001 and mean < 0.999:
            m_a = mean ** alpha
            extremized = m_a / (m_a + (1 - mean) ** alpha)
        else:
            extremized = mean

        return {
            "mean": round(mean, 4),
            "median": round(median, 4),
            "geometric_mean": round(geometric_mean, 4),
            "extremized_mean": round(extremized, 4),
        }
