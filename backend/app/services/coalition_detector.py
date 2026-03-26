"""
Agent coalition formation detector.

Detects when agents spontaneously form coalitions (coordinated posting,
mutual amplification). Tracks coalition stability and influence.
"""

from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.coalition')


@dataclass
class Coalition:
    """A detected agent coalition."""
    coalition_id: str
    members: List[str]
    avg_sentiment: float
    sentiment_coherence: float  # 0-1, how similar members' sentiments are
    mutual_interactions: int  # Number of within-coalition engagements
    stability_rounds: int  # How many rounds the coalition persisted
    influence_score: float  # 0-1, how much the coalition affects overall consensus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coalition_id": self.coalition_id,
            "members": self.members[:20],
            "size": len(self.members),
            "avg_sentiment": round(self.avg_sentiment, 3),
            "sentiment_coherence": round(self.sentiment_coherence, 3),
            "mutual_interactions": self.mutual_interactions,
            "stability_rounds": self.stability_rounds,
            "influence_score": round(self.influence_score, 3),
        }


class CoalitionDetector:
    """Detect spontaneous agent coalitions from interaction patterns."""

    def detect_coalitions(
        self,
        agent_sentiments: Dict[str, float],
        interactions: List[Dict[str, Any]],
        follow_graph: Dict[str, List[str]] = None,
        min_coalition_size: int = 3,
        coherence_threshold: float = 0.3,
    ) -> List[Coalition]:
        """Detect coalitions from agent interactions.

        Identifies groups of agents that:
        1. Have similar sentiments (low internal variance)
        2. Interact frequently with each other (mutual likes, reposts, comments)

        Args:
            agent_sentiments: Agent -> sentiment score
            interactions: List of interaction dicts {source, target, type}
            follow_graph: Follow relationships for connectivity bonus
            min_coalition_size: Minimum members to qualify as coalition
            coherence_threshold: Max sentiment std dev within coalition

        Returns:
            List of detected Coalitions
        """
        if not agent_sentiments or len(agent_sentiments) < min_coalition_size:
            return []

        # Build interaction graph: count mutual interactions
        interaction_counts: Dict[Tuple[str, str], int] = {}
        for inter in interactions:
            source = inter.get("source", "")
            target = inter.get("target", "")
            if source and target and source != target:
                pair = tuple(sorted([source, target]))
                interaction_counts[pair] = interaction_counts.get(pair, 0) + 1

        # Group agents by similar sentiment
        sorted_agents = sorted(agent_sentiments.items(), key=lambda x: x[1])

        # Sliding window to find coherent groups
        coalitions = []
        used = set()

        for i in range(len(sorted_agents)):
            if sorted_agents[i][0] in used:
                continue

            group = [sorted_agents[i]]
            for j in range(i + 1, len(sorted_agents)):
                if sorted_agents[j][0] in used:
                    continue
                # Check sentiment proximity
                if abs(sorted_agents[j][1] - group[-1][1]) < 0.3:
                    group.append(sorted_agents[j])
                else:
                    break

            if len(group) < min_coalition_size:
                continue

            members = [a for a, _ in group]
            sents = [s for _, s in group]
            avg_sent = sum(sents) / len(sents)
            variance = sum((s - avg_sent) ** 2 for s in sents) / len(sents)
            std = variance ** 0.5

            if std > coherence_threshold:
                continue

            # Count mutual interactions within this group
            member_set = set(members)
            mutual = sum(
                count for pair, count in interaction_counts.items()
                if pair[0] in member_set and pair[1] in member_set
            )

            # Influence: coalition size relative to total, weighted by interaction density
            total_agents = len(agent_sentiments)
            size_weight = len(members) / total_agents
            interaction_density = mutual / (len(members) * (len(members) - 1) / 2) if len(members) > 1 else 0
            influence = min(1.0, size_weight * 0.6 + interaction_density * 0.4)

            for m in members:
                used.add(m)

            coalitions.append(Coalition(
                coalition_id=f"coalition_{len(coalitions)}",
                members=members,
                avg_sentiment=avg_sent,
                sentiment_coherence=max(0, 1.0 - std / coherence_threshold),
                mutual_interactions=mutual,
                stability_rounds=0,  # Would be updated across rounds
                influence_score=influence,
            ))

        coalitions.sort(key=lambda c: c.influence_score, reverse=True)
        return coalitions
