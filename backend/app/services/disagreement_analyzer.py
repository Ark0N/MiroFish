"""
Disagreement analysis service.

When agents disagree, identifies the root cause: different information access,
different persona biases, or genuine ambiguity. Classifies disagreements to
help users understand prediction uncertainty.
"""

from typing import Dict, List, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.disagreement')


class DisagreementAnalyzer:
    """Analyze root causes of agent disagreements."""

    def analyze(
        self,
        agent_sentiments: Dict[str, float],
        agent_types: Dict[str, str],
        agent_posts: Dict[str, List[str]],
        follow_graph: Dict[str, List[str]] = None,
    ) -> Dict[str, Any]:
        """Analyze disagreement patterns among agents.

        Classifies disagreement causes:
        1. Persona bias: agents of different types systematically disagree
        2. Information asymmetry: agents with different network positions disagree
        3. Genuine ambiguity: disagreement cuts across types and network

        Args:
            agent_sentiments: Agent -> sentiment score
            agent_types: Agent -> persona type
            agent_posts: Agent -> list of posts
            follow_graph: Agent -> followed agents

        Returns:
            Analysis with root causes, type patterns, and recommendations
        """
        if not agent_sentiments or len(agent_sentiments) < 2:
            return {
                "has_disagreement": False,
                "cause": "insufficient_data",
                "description": "Not enough agents to analyze disagreement",
            }

        # Check if there IS meaningful disagreement
        values = list(agent_sentiments.values())
        spread = max(values) - min(values)
        if spread < 0.3:
            return {
                "has_disagreement": False,
                "cause": "consensus",
                "description": "Agents largely agree — no significant disagreement detected",
                "spread": round(spread, 3),
            }

        # Analyze type-based patterns
        type_analysis = self._analyze_by_type(agent_sentiments, agent_types)

        # Analyze network-based patterns
        network_analysis = self._analyze_by_network(agent_sentiments, follow_graph) if follow_graph else None

        # Determine root cause
        cause, description = self._classify_cause(type_analysis, network_analysis, spread)

        return {
            "has_disagreement": True,
            "cause": cause,
            "description": description,
            "spread": round(spread, 3),
            "type_patterns": type_analysis,
            "network_patterns": network_analysis,
            "recommendations": self._get_recommendations(cause),
        }

    def _analyze_by_type(
        self,
        sentiments: Dict[str, float],
        types: Dict[str, str],
    ) -> Dict[str, Any]:
        """Check if disagreement correlates with agent type."""
        type_sentiments: Dict[str, List[float]] = {}
        for agent, sentiment in sentiments.items():
            atype = types.get(agent, "Unknown")
            if atype not in type_sentiments:
                type_sentiments[atype] = []
            type_sentiments[atype].append(sentiment)

        type_averages = {}
        for atype, sents in type_sentiments.items():
            type_averages[atype] = round(sum(sents) / len(sents), 3) if sents else 0.0

        # Check if types have systematically different sentiments
        if len(type_averages) >= 2:
            avgs = list(type_averages.values())
            type_spread = max(avgs) - min(avgs)
            type_correlated = type_spread > 0.3
        else:
            type_spread = 0.0
            type_correlated = False

        return {
            "type_averages": type_averages,
            "type_spread": round(type_spread, 3),
            "type_correlated": type_correlated,
        }

    def _analyze_by_network(
        self,
        sentiments: Dict[str, float],
        follow_graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Check if disagreement correlates with network position."""
        if not follow_graph:
            return {"analyzed": False}

        # Compute connectivity (number of connections) per agent
        connectivity = {}
        for agent in sentiments:
            followed = set(follow_graph.get(agent, []))
            followers = sum(1 for a, f in follow_graph.items() if agent in f)
            connectivity[agent] = len(followed) + followers

        # Split into high/low connectivity groups
        if not connectivity:
            return {"analyzed": False}

        median_conn = sorted(connectivity.values())[len(connectivity) // 2]
        high_conn_sents = [sentiments[a] for a in sentiments if connectivity.get(a, 0) > median_conn]
        low_conn_sents = [sentiments[a] for a in sentiments if connectivity.get(a, 0) <= median_conn]

        high_avg = sum(high_conn_sents) / len(high_conn_sents) if high_conn_sents else 0
        low_avg = sum(low_conn_sents) / len(low_conn_sents) if low_conn_sents else 0

        return {
            "analyzed": True,
            "high_connectivity_sentiment": round(high_avg, 3),
            "low_connectivity_sentiment": round(low_avg, 3),
            "network_correlated": abs(high_avg - low_avg) > 0.3,
        }

    def _classify_cause(
        self,
        type_analysis: Dict[str, Any],
        network_analysis: Dict[str, Any],
        spread: float,
    ) -> tuple:
        """Classify the root cause of disagreement."""
        type_correlated = type_analysis.get("type_correlated", False)
        network_correlated = (network_analysis or {}).get("network_correlated", False)

        if type_correlated and not network_correlated:
            return (
                "persona_bias",
                "Disagreement is driven by agent persona types — different types "
                "have systematically different views. This suggests the prediction "
                "outcome depends on which stakeholder perspective you prioritize."
            )
        elif network_correlated and not type_correlated:
            return (
                "information_asymmetry",
                "Disagreement correlates with network position — well-connected "
                "agents have different views from isolated ones. This suggests "
                "some agents have access to different information or social influence."
            )
        elif type_correlated and network_correlated:
            return (
                "structural",
                "Disagreement is driven by both persona types and network position. "
                "This is a deep structural divide in the simulation — different "
                "communities with different perspectives."
            )
        else:
            return (
                "genuine_ambiguity",
                "Disagreement cuts across agent types and network positions — "
                "this is genuine ambiguity about the outcome. The prediction is "
                "inherently uncertain and more data may not resolve it."
            )

    @staticmethod
    def _get_recommendations(cause: str) -> List[str]:
        recs = {
            "persona_bias": [
                "Consider which stakeholder perspective is most relevant",
                "Weight predictions by domain-expert agent types",
                "Add more diverse agent types to balance perspectives",
            ],
            "information_asymmetry": [
                "Increase network connectivity to reduce information gaps",
                "Check if isolated agents have unique valid perspectives",
                "Consider running simulation with fully-connected graph",
            ],
            "structural": [
                "This division likely reflects real-world disagreements",
                "Report both perspectives as scenarios rather than one prediction",
                "Consider split predictions for different stakeholder groups",
            ],
            "genuine_ambiguity": [
                "More data or simulations unlikely to resolve this uncertainty",
                "Present prediction with wide confidence intervals",
                "Consider reporting multiple possible outcomes",
            ],
        }
        return recs.get(cause, ["Review prediction uncertainty carefully"])
