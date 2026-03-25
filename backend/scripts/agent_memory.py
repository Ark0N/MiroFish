"""
Agent memory system for simulation continuity.

Maintains a rolling buffer of each agent's recent posts and interactions,
enabling opinion evolution across rounds. The memory is injected into
the agent's context (persona extension) before each round.

Usage:
    memory = AgentMemoryManager(max_history=5)
    memory.record_action(agent_name, action)
    context = memory.get_context(agent_name)  # inject into agent prompt
"""

import json
from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime


class AgentMemoryManager:
    """Manages short-term memory for simulation agents.

    Each agent maintains a rolling buffer of their last N posts/interactions.
    This memory is formatted as a context string that can be appended to
    the agent's persona to provide continuity across rounds.
    """

    def __init__(self, max_history: int = 5):
        """
        Args:
            max_history: Maximum number of recent actions to remember per agent
        """
        self.max_history = max_history
        self._memory: Dict[str, deque] = {}  # agent_name -> deque of memory entries

    def record_action(self, agent_name: str, action: Dict[str, Any]) -> None:
        """Record an agent's action for memory.

        Args:
            agent_name: The agent who performed the action
            action: Action dict with at least 'action_type' and optionally 'content'
        """
        if agent_name not in self._memory:
            self._memory[agent_name] = deque(maxlen=self.max_history)

        action_type = action.get("action_type", "")
        content = action.get("content", "")
        round_num = action.get("round", 0)

        # Only remember content-bearing actions
        if action_type in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST") and content:
            entry = {
                "round": round_num,
                "type": action_type,
                "content": content[:500],  # Truncate to prevent context bloat
                "timestamp": datetime.now().isoformat(),
            }
            self._memory[agent_name].append(entry)

        elif action_type in ("LIKE_POST", "REPOST"):
            # Record engagement actions briefly
            target = action.get("target_content", "")[:200] if action.get("target_content") else ""
            entry = {
                "round": round_num,
                "type": action_type,
                "content": f"Engaged with: {target}" if target else action_type,
                "timestamp": datetime.now().isoformat(),
            }
            self._memory[agent_name].append(entry)

    def get_context(self, agent_name: str) -> str:
        """Get memory context string for an agent.

        Returns a formatted string describing the agent's recent activity,
        suitable for appending to their persona/system prompt.

        Args:
            agent_name: The agent to get memory for

        Returns:
            Formatted context string, or empty string if no memory
        """
        if agent_name not in self._memory or not self._memory[agent_name]:
            return ""

        entries = list(self._memory[agent_name])
        parts = ["\n[Your recent activity on this platform:]"]

        for entry in entries:
            action_desc = {
                "CREATE_POST": "You posted",
                "CREATE_COMMENT": "You commented",
                "QUOTE_POST": "You quoted a post saying",
                "LIKE_POST": "You liked a post",
                "REPOST": "You reposted",
            }.get(entry["type"], "You did")

            content = entry["content"]
            parts.append(f"- Round {entry['round']}: {action_desc}: \"{content}\"")

        parts.append(
            "\nBased on your recent activity above, maintain consistency with your "
            "established opinions while naturally evolving your views as you encounter "
            "new information and perspectives from other participants."
        )

        return "\n".join(parts)

    def get_agent_stance(self, agent_name: str) -> Optional[str]:
        """Infer agent's current stance from memory.

        Returns "positive", "negative", "neutral", or None if no memory.
        """
        if agent_name not in self._memory or not self._memory[agent_name]:
            return None

        positive_kw = {"good", "great", "support", "agree", "happy", "love", "excellent", "hope", "progress"}
        negative_kw = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful", "crisis", "fail"}

        scores = []
        has_content = False
        for entry in self._memory[agent_name]:
            if entry["type"] in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"):
                has_content = True
                lower = entry["content"].lower()
                pos = sum(1 for w in positive_kw if w in lower)
                neg = sum(1 for w in negative_kw if w in lower)
                total = pos + neg
                scores.append((pos - neg) / total if total > 0 else 0.0)

        if not has_content:
            return None

        avg = sum(scores) / len(scores)
        if avg > 0.15:
            return "positive"
        elif avg < -0.15:
            return "negative"
        return "neutral"

    def get_all_agents(self) -> List[str]:
        """Get list of all agents with memory."""
        return list(self._memory.keys())

    def get_memory_size(self, agent_name: str) -> int:
        """Get number of memory entries for an agent."""
        return len(self._memory.get(agent_name, []))

    def clear(self, agent_name: Optional[str] = None) -> None:
        """Clear memory for a specific agent or all agents."""
        if agent_name:
            self._memory.pop(agent_name, None)
        else:
            self._memory.clear()

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Serialize memory state."""
        return {
            agent: list(entries)
            for agent, entries in self._memory.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, List[Dict[str, Any]]], max_history: int = 5) -> 'AgentMemoryManager':
        """Deserialize memory state."""
        mgr = cls(max_history=max_history)
        for agent, entries in data.items():
            mgr._memory[agent] = deque(entries, maxlen=max_history)
        return mgr
