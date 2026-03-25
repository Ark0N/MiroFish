"""
Echo chamber detector.

Detects when agent subgroups form echo chambers — clusters that only
interact with like-minded agents. Flags these in analytics as they
reduce prediction diversity and reliability.
"""

from typing import Dict, List, Any, Set
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.echo_chamber')


@dataclass
class EchoChamber:
    """Detected echo chamber cluster."""
    agents: List[str]
    avg_sentiment: float
    sentiment_std: float  # Low std = strong echo chamber
    internal_connections: int  # Connections within the chamber
    external_connections: int  # Connections to outside
    insularity_score: float  # 0-1, how isolated the group is

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": self.agents[:20],
            "size": len(self.agents),
            "avg_sentiment": round(self.avg_sentiment, 3),
            "sentiment_std": round(self.sentiment_std, 3),
            "internal_connections": self.internal_connections,
            "external_connections": self.external_connections,
            "insularity_score": round(self.insularity_score, 3),
        }


class EchoChamberDetector:
    """Detect echo chambers in agent networks."""

    def detect(
        self,
        agent_sentiments: Dict[str, float],
        follow_graph: Dict[str, List[str]],
        sentiment_threshold: float = 0.15,
        insularity_threshold: float = 0.7,
    ) -> List[EchoChamber]:
        """Detect echo chambers in the agent network.

        Groups agents by sentiment polarity, then checks if like-minded
        agents predominantly follow each other (high insularity).

        Args:
            agent_sentiments: Agent -> sentiment score
            follow_graph: Agent -> followed agents
            sentiment_threshold: Threshold for positive/negative classification
            insularity_threshold: Minimum insularity to flag as echo chamber

        Returns:
            List of detected EchoChamber objects
        """
        if not agent_sentiments or not follow_graph:
            return []

        # Group agents by stance
        groups: Dict[str, Set[str]] = {
            "positive": set(),
            "negative": set(),
            "neutral": set(),
        }

        for agent, sentiment in agent_sentiments.items():
            if sentiment > sentiment_threshold:
                groups["positive"].add(agent)
            elif sentiment < -sentiment_threshold:
                groups["negative"].add(agent)
            else:
                groups["neutral"].add(agent)

        chambers = []

        for stance, members in groups.items():
            if len(members) < 2:
                continue

            internal = 0
            external = 0

            for agent in members:
                followed = set(follow_graph.get(agent, []))
                internal += len(followed & members)
                external += len(followed - members)

            total_connections = internal + external
            if total_connections == 0:
                continue

            insularity = internal / total_connections

            # Compute sentiment statistics
            sents = [agent_sentiments[a] for a in members]
            avg = sum(sents) / len(sents)
            variance = sum((s - avg) ** 2 for s in sents) / len(sents)
            std = variance ** 0.5

            if insularity >= insularity_threshold:
                chambers.append(EchoChamber(
                    agents=sorted(members),
                    avg_sentiment=avg,
                    sentiment_std=std,
                    internal_connections=internal,
                    external_connections=external,
                    insularity_score=insularity,
                ))

        # Sort by insularity
        chambers.sort(key=lambda c: c.insularity_score, reverse=True)
        return chambers

    def compute_network_health(
        self,
        agent_sentiments: Dict[str, float],
        follow_graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Compute overall network health metrics.

        Returns:
            Dict with echo_chambers, diversity_score, and health assessment
        """
        chambers = self.detect(agent_sentiments, follow_graph)
        total_agents = len(agent_sentiments)

        agents_in_chambers = sum(len(c.agents) for c in chambers)
        chamber_ratio = agents_in_chambers / total_agents if total_agents > 0 else 0.0

        # Diversity: based on sentiment spread and low echo chamber presence
        if agent_sentiments:
            sents = list(agent_sentiments.values())
            spread = max(sents) - min(sents) if sents else 0
        else:
            spread = 0

        diversity_score = min(1.0, spread) * (1.0 - chamber_ratio)

        if chamber_ratio > 0.5:
            health = "unhealthy"
            assessment = "Majority of agents are in echo chambers — predictions may lack diversity"
        elif chamber_ratio > 0.2:
            health = "moderate"
            assessment = "Some echo chambers detected — consider adding more diverse connections"
        elif len(chambers) > 0:
            health = "mild"
            assessment = "Minor echo chambers present but network is generally diverse"
        else:
            health = "healthy"
            assessment = "No significant echo chambers — good opinion diversity"

        return {
            "echo_chambers": [c.to_dict() for c in chambers],
            "num_chambers": len(chambers),
            "agents_in_chambers": agents_in_chambers,
            "total_agents": total_agents,
            "chamber_ratio": round(chamber_ratio, 3),
            "diversity_score": round(diversity_score, 3),
            "health": health,
            "assessment": assessment,
        }
