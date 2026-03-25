"""
Action logger.
Records each agent's actions during OASIS simulation for backend monitoring.

Log structure:
    sim_xxx/
    ├── twitter/
    │   └── actions.jsonl    # Twitter platform action log
    ├── reddit/
    │   └── actions.jsonl    # Reddit platform action log
    ├── simulation.log       # Main simulation process log
    └── run_state.json       # Run state (for API queries)
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional


class PlatformActionLogger:
    """Single platform action logger."""
    
    def __init__(self, platform: str, base_dir: str):
        """
        Initialize logger
        
        Args:
            platform: Platform name (twitter/reddit)
            base_dir: Base path of simulation directory
        """
        self.platform = platform
        self.base_dir = base_dir
        self.log_dir = os.path.join(base_dir, platform)
        self.log_path = os.path.join(self.log_dir, "actions.jsonl")
        self._ensure_dir()
    
    def _ensure_dir(self):
        """Ensure directory exists."""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def log_action(
        self,
        round_num: int,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True
    ):
        """Log an action."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "action_args": action_args or {},
            "result": result,
            "success": success,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_start(self, round_num: int, simulated_hour: int):
        """Log round start."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "event_type": "round_start",
            "simulated_hour": simulated_hour,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_end(self, round_num: int, actions_count: int, simulated_hours: int = 0):
        """Log round end."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "event_type": "round_end",
            "actions_count": actions_count,
            "simulated_hours": simulated_hours,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_start(self, config: Dict[str, Any]):
        """Log simulation start."""
        minutes_per_round = config.get("time_config", {}).get("minutes_per_round", 60)
        total_hours = config.get("time_config", {}).get("total_simulation_hours", 72)
        total_rounds = int(total_hours * 60 / minutes_per_round) if minutes_per_round > 0 else total_hours
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "simulation_start",
            "platform": self.platform,
            "total_rounds": total_rounds,
            "agents_count": len(config.get("agent_configs", [])),
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_end(self, total_rounds: int, total_actions: int):
        """Log simulation end."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "simulation_end",
            "platform": self.platform,
            "total_rounds": total_rounds,
            "total_actions": total_actions,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


class SimulationLogManager:
    """
    Simulation log manager
    Unified management of all log files, separated by platform
    """
    
    def __init__(self, simulation_dir: str):
        """
        Initialize log manager
        
        Args:
            simulation_dir: Simulation directory path
        """
        self.simulation_dir = simulation_dir
        self.twitter_logger: Optional[PlatformActionLogger] = None
        self.reddit_logger: Optional[PlatformActionLogger] = None
        self._main_logger: Optional[logging.Logger] = None
        
        # Set up main logger
        self._setup_main_logger()
    
    def _setup_main_logger(self):
        """Set up main simulation logger."""
        log_path = os.path.join(self.simulation_dir, "simulation.log")
        
        # Create logger
        self._main_logger = logging.getLogger(f"simulation.{os.path.basename(self.simulation_dir)}")
        self._main_logger.setLevel(logging.INFO)
        self._main_logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_path, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self._main_logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        self._main_logger.addHandler(console_handler)
        
        self._main_logger.propagate = False
    
    def get_twitter_logger(self) -> PlatformActionLogger:
        """Get Twitter platform action logger."""
        if self.twitter_logger is None:
            self.twitter_logger = PlatformActionLogger("twitter", self.simulation_dir)
        return self.twitter_logger
    
    def get_reddit_logger(self) -> PlatformActionLogger:
        """Get Reddit platform action logger."""
        if self.reddit_logger is None:
            self.reddit_logger = PlatformActionLogger("reddit", self.simulation_dir)
        return self.reddit_logger
    
    def log(self, message: str, level: str = "info"):
        """Log to main logger."""
        if self._main_logger:
            getattr(self._main_logger, level.lower(), self._main_logger.info)(message)
    
    def info(self, message: str):
        self.log(message, "info")
    
    def warning(self, message: str):
        self.log(message, "warning")
    
    def error(self, message: str):
        self.log(message, "error")
    
    def debug(self, message: str):
        self.log(message, "debug")


class RoundMetricsTracker:
    """Tracks per-round aggregate metrics for swarm intelligence analysis.

    Computes sentiment distribution, action type counts, and engagement metrics
    after each round. Saves to round_metrics.jsonl for report agent analysis.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.metrics_file = os.path.join(output_dir, "round_metrics.jsonl")
        self._current_round_actions: List[Dict[str, Any]] = []
        self._previous_sentiment: Optional[float] = None
        self._sentiment_history: List[float] = []  # last N rounds for momentum

    def add_action(self, action: Dict[str, Any]):
        """Buffer an action for current round metrics computation."""
        self._current_round_actions.append(action)

    def _compute_momentum(self, current_sentiment: float) -> Dict[str, Any]:
        """Compute sentiment momentum indicators.

        Returns:
            Dict with:
                - velocity: rate of change from previous round
                - acceleration: change in velocity (is momentum increasing or decreasing?)
                - direction: "accelerating", "decelerating", "reversing", or "stable"
                - signal: "strong_positive", "strong_negative", "weak", or "neutral"
        """
        velocity = 0.0
        acceleration = 0.0
        direction = "stable"
        signal = "neutral"

        if self._previous_sentiment is not None:
            velocity = current_sentiment - self._previous_sentiment

        # Compute acceleration from last 3 data points
        history = self._sentiment_history
        if len(history) >= 2:
            prev_velocity = history[-1] - history[-2]
            acceleration = velocity - prev_velocity

        # Determine direction
        if abs(velocity) < 0.05:
            direction = "stable"
        elif velocity > 0 and acceleration > 0:
            direction = "accelerating"
        elif velocity > 0 and acceleration < 0:
            direction = "decelerating"
        elif velocity < 0 and acceleration < 0:
            direction = "accelerating"  # accelerating in negative direction
        elif velocity < 0 and acceleration > 0:
            direction = "decelerating"  # decelerating from negative
        else:
            direction = "stable"

        # Check for reversal (sign change in velocity)
        if len(history) >= 2:
            prev_vel = history[-1] - history[-2]
            if prev_vel * velocity < 0 and abs(velocity) > 0.05:
                direction = "reversing"

        # Determine signal strength
        if abs(velocity) > 0.15:
            signal = "strong_positive" if velocity > 0 else "strong_negative"
        elif abs(velocity) > 0.05:
            signal = "weak"
        else:
            signal = "neutral"

        return {
            "velocity": round(velocity, 4),
            "acceleration": round(acceleration, 4),
            "direction": direction,
            "signal": signal,
        }

    def flush_round(self, round_num: int, platform: str, total_agents: int, active_agents: int):
        """Compute and save metrics for the completed round."""
        actions = self._current_round_actions

        # Action type distribution
        action_counts: Dict[str, int] = {}
        for a in actions:
            atype = a.get("action_type", "UNKNOWN")
            action_counts[atype] = action_counts.get(atype, 0) + 1

        # Content-bearing actions (posts, comments, quotes)
        content_actions = [
            a for a in actions
            if a.get("action_type") in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST")
        ]

        # Simple keyword-based sentiment estimation
        positive_keywords = {"good", "great", "support", "agree", "happy", "love", "excellent", "wonderful", "hope", "thank", "progress", "solution"}
        negative_keywords = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail", "problem", "scandal", "corrupt", "outrage"}

        sentiment_scores = []
        for a in content_actions:
            content = str(a.get("content", "")).lower()
            pos = sum(1 for w in positive_keywords if w in content)
            neg = sum(1 for w in negative_keywords if w in content)
            total = pos + neg
            if total > 0:
                score = (pos - neg) / total  # -1.0 to 1.0
            else:
                score = 0.0
            sentiment_scores.append(score)

        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        positive_count = sum(1 for s in sentiment_scores if s > 0.2)
        negative_count = sum(1 for s in sentiment_scores if s < -0.2)
        neutral_count = len(sentiment_scores) - positive_count - negative_count

        # Engagement metrics
        likes = sum(1 for a in actions if a.get("action_type") in ("LIKE_POST", "LIKE_COMMENT"))
        dislikes = sum(1 for a in actions if a.get("action_type") in ("DISLIKE_POST", "DISLIKE_COMMENT"))
        reposts = sum(1 for a in actions if a.get("action_type") == "REPOST")

        # Faction detection: group agents by stance and track per round
        agent_sentiments: Dict[str, float] = {}
        for a in content_actions:
            agent = a.get("agent_name", a.get("user_name", "unknown"))
            content = str(a.get("content", "")).lower()
            pos = sum(1 for w in positive_keywords if w in content)
            neg = sum(1 for w in negative_keywords if w in content)
            total_kw = pos + neg
            score = (pos - neg) / total_kw if total_kw > 0 else 0.0
            if agent not in agent_sentiments:
                agent_sentiments[agent] = []
            agent_sentiments[agent].append(score)

        # Compute per-agent average for this round
        agent_avg = {a: sum(s) / len(s) for a, s in agent_sentiments.items() if s}

        factions = {"supportive": [], "opposing": [], "neutral": []}
        for agent, avg in agent_avg.items():
            if avg > 0.15:
                factions["supportive"].append(agent)
            elif avg < -0.15:
                factions["opposing"].append(agent)
            else:
                factions["neutral"].append(agent)

        faction_summary = {
            stance: {
                "count": len(members),
                "members": members[:10],
                "avg_sentiment": round(
                    sum(agent_avg[m] for m in members) / len(members), 3
                ) if members else 0.0,
            }
            for stance, members in factions.items()
        }

        metrics = {
            "round": round_num,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_actions": len(actions),
            "action_counts": action_counts,
            "content_posts": len(content_actions),
            "sentiment": {
                "average": round(avg_sentiment, 3),
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
            },
            "engagement": {
                "likes": likes,
                "dislikes": dislikes,
                "reposts": reposts,
            },
            "factions": faction_summary,
            "momentum": self._compute_momentum(avg_sentiment),
            "participation_rate": round(active_agents / total_agents, 3) if total_agents > 0 else 0,
        }

        # Update sentiment history for next round's momentum
        self._previous_sentiment = avg_sentiment
        self._sentiment_history.append(avg_sentiment)

        # Write to JSONL
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.getLogger("mirofish.metrics").warning(f"Failed to write round metrics: {e}")

        # Write faction metrics to separate file for drift tracking
        try:
            faction_file = os.path.join(self.output_dir, "faction_metrics.jsonl")
            faction_entry = {
                "round": round_num,
                "platform": platform,
                "timestamp": datetime.now().isoformat(),
                "factions": faction_summary,
                "total_content_agents": len(agent_avg),
            }
            with open(faction_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(faction_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.getLogger("mirofish.metrics").warning(f"Failed to write faction metrics: {e}")

        # Reset buffer
        self._current_round_actions = []

        return metrics


class InfluenceTracker:
    """Tracks influence propagation across the agent network.

    Monitors which agents' posts generate the most engagement (likes, reposts,
    comments) and logs opinion adoption chains — when agent B's post after
    engaging with agent A's content shifts to match A's stance.

    Outputs to influence_metrics.jsonl per platform.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.influence_file = os.path.join(output_dir, "influence_metrics.jsonl")
        self._posts: Dict[str, Dict[str, Any]] = {}  # post_id -> {agent, content, sentiment, round}
        self._engagements: List[Dict[str, Any]] = []  # {agent, target_post_id, action_type, round}

    def track_action(self, action: Dict[str, Any]):
        """Track an action for influence analysis."""
        atype = action.get("action_type", "")
        agent = action.get("agent_name", action.get("user_name", ""))
        round_num = action.get("round", 0)

        if atype in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"):
            content = str(action.get("content", ""))
            post_id = action.get("post_id", f"{agent}_{round_num}_{len(self._posts)}")
            self._posts[post_id] = {
                "agent": agent,
                "content": content,
                "sentiment": self._score_sentiment(content),
                "round": round_num,
                "engagements": 0,
            }

        elif atype in ("LIKE_POST", "REPOST", "LIKE_COMMENT"):
            target_id = action.get("target_post_id", action.get("post_id", ""))
            self._engagements.append({
                "agent": agent,
                "target_post_id": target_id,
                "action_type": atype,
                "round": round_num,
            })
            if target_id in self._posts:
                self._posts[target_id]["engagements"] += 1

    def flush_round(self, round_num: int, platform: str):
        """Compute and save influence metrics for the completed round."""
        # Compute per-agent influence scores
        agent_influence: Dict[str, Dict[str, Any]] = {}

        for post_id, post in self._posts.items():
            if post["round"] != round_num:
                continue
            agent = post["agent"]
            if agent not in agent_influence:
                agent_influence[agent] = {"posts": 0, "total_engagements": 0, "avg_sentiment": 0.0, "sentiments": []}
            agent_influence[agent]["posts"] += 1
            agent_influence[agent]["total_engagements"] += post["engagements"]
            agent_influence[agent]["sentiments"].append(post["sentiment"])

        # Compute averages and rank
        influence_rankings = []
        for agent, data in agent_influence.items():
            avg_sent = sum(data["sentiments"]) / len(data["sentiments"]) if data["sentiments"] else 0.0
            influence_rankings.append({
                "agent": agent,
                "posts": data["posts"],
                "total_engagements": data["total_engagements"],
                "engagement_rate": round(data["total_engagements"] / data["posts"], 2) if data["posts"] > 0 else 0,
                "avg_sentiment": round(avg_sent, 3),
            })

        influence_rankings.sort(key=lambda x: x["total_engagements"], reverse=True)

        metrics = {
            "round": round_num,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "top_influencers": influence_rankings[:10],
            "total_posts_this_round": sum(1 for p in self._posts.values() if p["round"] == round_num),
            "total_engagements_this_round": sum(
                p["engagements"] for p in self._posts.values() if p["round"] == round_num
            ),
        }

        try:
            os.makedirs(os.path.dirname(self.influence_file) or ".", exist_ok=True)
            with open(self.influence_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.getLogger("mirofish.influence").warning(f"Failed to write influence metrics: {e}")

        return metrics

    @staticmethod
    def _score_sentiment(content: str) -> float:
        positive_kw = {"good", "great", "support", "agree", "happy", "love", "excellent", "hope", "progress"}
        negative_kw = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail"}
        lower = content.lower()
        pos = sum(1 for w in positive_kw if w in lower)
        neg = sum(1 for w in negative_kw if w in lower)
        total = pos + neg
        return (pos - neg) / total if total > 0 else 0.0


# ============ Legacy interface compatibility ============

class ActionLogger:
    """
    Action logger (legacy interface compatibility)
    Use SimulationLogManager instead
    """
    
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._ensure_dir()
    
    def _ensure_dir(self):
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    def log_action(
        self,
        round_num: int,
        platform: str,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True
    ):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "action_args": action_args or {},
            "result": result,
            "success": success,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_start(self, round_num: int, simulated_hour: int, platform: str):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "round_start",
            "simulated_hour": simulated_hour,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_end(self, round_num: int, actions_count: int, platform: str, simulated_hours: int = 0):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "round_end",
            "actions_count": actions_count,
            "simulated_hours": simulated_hours,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_start(self, platform: str, config: Dict[str, Any]):
        minutes_per_round = config.get("time_config", {}).get("minutes_per_round", 60)
        total_hours = config.get("time_config", {}).get("total_simulation_hours", 72)
        total_rounds = int(total_hours * 60 / minutes_per_round) if minutes_per_round > 0 else total_hours
        entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "simulation_start",
            "total_rounds": total_rounds,
            "agents_count": len(config.get("agent_configs", [])),
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_end(self, platform: str, total_rounds: int, total_actions: int):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "simulation_end",
            "total_rounds": total_rounds,
            "total_actions": total_actions,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# Global logger instance (legacy interface compatibility)
_global_logger: Optional[ActionLogger] = None


def get_logger(log_path: Optional[str] = None) -> ActionLogger:
    """Get global logger instance (legacy interface compatibility)."""
    global _global_logger
    
    if log_path:
        _global_logger = ActionLogger(log_path)
    
    if _global_logger is None:
        _global_logger = ActionLogger("actions.jsonl")
    
    return _global_logger
