"""
Analytics service for simulation and prediction data.

Aggregates metrics from round_metrics.jsonl, faction_metrics.jsonl,
influence_metrics.jsonl, and predictions into comprehensive analytics
for dashboard rendering.
"""

import json
import os
from typing import Dict, List, Any, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.analytics')


class AnalyticsService:
    """Compute comprehensive analytics from simulation data."""

    def simulation_analytics(self, simulation_dir: str) -> Dict[str, Any]:
        """Get comprehensive analytics for a single simulation.

        Returns round-by-round sentiment curves, faction evolution,
        influence rankings, and momentum indicators.
        """
        sentiment_curve = []
        faction_evolution = []
        influence_data = []
        momentum_data = []

        for platform in ["twitter", "reddit"]:
            # Round metrics
            metrics_file = os.path.join(simulation_dir, platform, "round_metrics.jsonl")
            if os.path.exists(metrics_file):
                try:
                    with open(metrics_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                m = json.loads(line)
                                sentiment_curve.append({
                                    "round": m.get("round"),
                                    "platform": platform,
                                    "avg_sentiment": m.get("sentiment", {}).get("average", 0),
                                    "positive": m.get("sentiment", {}).get("positive", 0),
                                    "negative": m.get("sentiment", {}).get("negative", 0),
                                    "neutral": m.get("sentiment", {}).get("neutral", 0),
                                    "participation_rate": m.get("participation_rate", 0),
                                })

                                # Momentum
                                mom = m.get("momentum", {})
                                if mom:
                                    momentum_data.append({
                                        "round": m.get("round"),
                                        "platform": platform,
                                        "velocity": mom.get("velocity", 0),
                                        "acceleration": mom.get("acceleration", 0),
                                        "direction": mom.get("direction", "stable"),
                                        "signal": mom.get("signal", "neutral"),
                                    })
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    pass

            # Faction metrics
            faction_file = os.path.join(simulation_dir, platform, "faction_metrics.jsonl")
            if os.path.exists(faction_file):
                try:
                    with open(faction_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                m = json.loads(line)
                                factions = m.get("factions", {})
                                faction_evolution.append({
                                    "round": m.get("round"),
                                    "platform": platform,
                                    "supportive": factions.get("supportive", {}).get("count", 0),
                                    "opposing": factions.get("opposing", {}).get("count", 0),
                                    "neutral": factions.get("neutral", {}).get("count", 0),
                                })
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    pass

            # Influence metrics
            influence_file = os.path.join(simulation_dir, platform, "influence_metrics.jsonl")
            if os.path.exists(influence_file):
                try:
                    with open(influence_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                m = json.loads(line)
                                influence_data.append({
                                    "round": m.get("round"),
                                    "platform": platform,
                                    "top_influencers": m.get("top_influencers", [])[:5],
                                    "total_engagements": m.get("total_engagements_this_round", 0),
                                })
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    pass

        return {
            "sentiment_curve": sentiment_curve,
            "faction_evolution": faction_evolution,
            "momentum_indicators": momentum_data,
            "influence_rankings": influence_data,
            "total_rounds": len(sentiment_curve),
        }

    def agent_profiles(self, simulation_dir: str) -> List[Dict[str, Any]]:
        """Get per-agent analytics from simulation action logs.

        Returns posting frequency, sentiment consistency, and activity
        classification for each agent.
        """
        agent_data: Dict[str, Dict[str, Any]] = {}

        positive_kw = {"good", "great", "support", "agree", "happy", "love", "excellent"}
        negative_kw = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful"}

        for platform in ["twitter", "reddit"]:
            actions_file = os.path.join(simulation_dir, platform, "actions.jsonl")
            if not os.path.exists(actions_file):
                continue

            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            action = json.loads(line)
                            agent = action.get("agent_name", action.get("user_name", ""))
                            atype = action.get("action_type", "")
                            content = action.get("content", "")

                            if agent not in agent_data:
                                agent_data[agent] = {
                                    "agent_name": agent,
                                    "total_actions": 0,
                                    "posts": 0,
                                    "likes": 0,
                                    "reposts": 0,
                                    "comments": 0,
                                    "sentiments": [],
                                }

                            agent_data[agent]["total_actions"] += 1

                            if atype == "CREATE_POST":
                                agent_data[agent]["posts"] += 1
                            elif atype in ("LIKE_POST", "LIKE_COMMENT"):
                                agent_data[agent]["likes"] += 1
                            elif atype == "REPOST":
                                agent_data[agent]["reposts"] += 1
                            elif atype in ("CREATE_COMMENT", "QUOTE_POST"):
                                agent_data[agent]["comments"] += 1

                            if atype in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST") and content:
                                lower = content.lower()
                                pos = sum(1 for w in positive_kw if w in lower)
                                neg = sum(1 for w in negative_kw if w in lower)
                                total = pos + neg
                                agent_data[agent]["sentiments"].append(
                                    (pos - neg) / total if total > 0 else 0.0
                                )
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        # Compute summaries
        profiles = []
        for agent, data in agent_data.items():
            sentiments = data["sentiments"]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            # Classify behavior type
            total = data["total_actions"]
            if total == 0:
                behavior = "inactive"
            elif data["posts"] / total > 0.4:
                behavior = "creator"
            elif data["comments"] / total > 0.3:
                behavior = "engager"
            elif data["likes"] / total > 0.5:
                behavior = "lurker"
            else:
                behavior = "mixed"

            profiles.append({
                "agent_name": agent,
                "behavior_type": behavior,
                "total_actions": total,
                "posts": data["posts"],
                "likes": data["likes"],
                "reposts": data["reposts"],
                "comments": data["comments"],
                "avg_sentiment": round(avg_sentiment, 3),
                "sentiment_consistency": round(
                    1.0 - (max(sentiments) - min(sentiments)) if len(sentiments) >= 2 else 1.0, 3
                ),
            })

        profiles.sort(key=lambda p: p["total_actions"], reverse=True)
        return profiles
