"""
Network influence weighting.

Computes PageRank-like influence scores for agents based on their
position in the follow graph. Agents with more followers have more
influence on overall sentiment and prediction outcomes.
"""

from typing import Dict, List, Any, Set

from ..utils.logger import get_logger

logger = get_logger('mirofish.network_influence')


class NetworkInfluenceScorer:
    """Compute network-based influence scores using simplified PageRank."""

    def compute_pagerank(
        self,
        follow_graph: Dict[str, List[str]],
        damping: float = 0.85,
        max_iterations: int = 50,
        tolerance: float = 1e-6,
    ) -> Dict[str, float]:
        """Compute PageRank scores for all agents in the follow graph.

        Args:
            follow_graph: agent_name -> list of agents they follow
            damping: PageRank damping factor (0.85 standard)
            max_iterations: Maximum iterations before convergence
            tolerance: Convergence threshold

        Returns:
            Dict mapping agent_name -> PageRank score (0-1, sums to 1)
        """
        # Build reverse graph: who follows whom
        all_agents = set(follow_graph.keys())
        for followers in follow_graph.values():
            all_agents.update(followers)

        if not all_agents:
            return {}

        n = len(all_agents)
        agents = sorted(all_agents)
        agent_idx = {a: i for i, a in enumerate(agents)}

        # Reverse graph: agent -> set of followers
        followers_of: Dict[str, Set[str]] = {a: set() for a in agents}
        out_degree: Dict[str, int] = {a: 0 for a in agents}

        for follower, followed_list in follow_graph.items():
            out_degree[follower] = len(followed_list)
            for followed in followed_list:
                if followed in followers_of:
                    followers_of[followed].add(follower)

        # Initialize scores uniformly
        scores = {a: 1.0 / n for a in agents}

        # Iterative PageRank
        for iteration in range(max_iterations):
            new_scores = {}
            for agent in agents:
                rank_sum = sum(
                    scores[follower] / out_degree[follower]
                    for follower in followers_of[agent]
                    if out_degree[follower] > 0
                )
                new_scores[agent] = (1 - damping) / n + damping * rank_sum

            # Check convergence
            diff = sum(abs(new_scores[a] - scores[a]) for a in agents)
            scores = new_scores

            if diff < tolerance:
                break

        return {a: round(s, 6) for a, s in scores.items()}

    def compute_influence_weighted_sentiment(
        self,
        agent_sentiments: Dict[str, float],
        follow_graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Compute sentiment weighted by network influence.

        Args:
            agent_sentiments: Agent -> sentiment score mapping
            follow_graph: Agent -> followed agents mapping

        Returns:
            Dict with standard_sentiment, influence_weighted_sentiment, and top influencers
        """
        pagerank = self.compute_pagerank(follow_graph)

        if not agent_sentiments:
            return {
                "standard_sentiment": 0.0,
                "influence_weighted_sentiment": 0.0,
                "top_influencers": [],
            }

        # Standard (unweighted) sentiment
        sentiments = list(agent_sentiments.values())
        standard = sum(sentiments) / len(sentiments)

        # Influence-weighted sentiment
        weighted_sum = 0.0
        weight_total = 0.0
        for agent, sentiment in agent_sentiments.items():
            weight = pagerank.get(agent, 1.0 / len(agent_sentiments))
            weighted_sum += sentiment * weight
            weight_total += weight

        influence_weighted = weighted_sum / weight_total if weight_total > 0 else 0.0

        # Top influencers
        ranked = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        top = [
            {"agent": a, "pagerank": s, "sentiment": agent_sentiments.get(a, 0.0)}
            for a, s in ranked[:10]
        ]

        return {
            "standard_sentiment": round(standard, 4),
            "influence_weighted_sentiment": round(influence_weighted, 4),
            "delta": round(influence_weighted - standard, 4),
            "top_influencers": top,
        }
