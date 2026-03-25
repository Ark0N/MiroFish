"""
Agent opinion drift model.

Mathematical model for how agent opinions evolve over rounds.
Each agent has:
- Opinion inertia: resistance to change (0=easily swayed, 1=immovable)
- Susceptibility: how much influenced by others (0=independent, 1=conformist)
- Current opinion: scalar sentiment (-1 to 1)

Opinion update rule per round:
    new_opinion = inertia * old_opinion + susceptibility * social_influence + (1 - inertia - susceptibility) * noise

Social influence is the weighted average of opinions from followed agents.
"""

import math
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ..utils.logger import get_logger

logger = get_logger('mirofish.opinion_drift')


@dataclass
class AgentOpinionState:
    """Opinion state for a single agent."""
    agent_name: str
    opinion: float  # -1 to 1
    inertia: float  # 0 to 1
    susceptibility: float  # 0 to 1
    opinion_history: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "opinion": round(self.opinion, 4),
            "inertia": round(self.inertia, 2),
            "susceptibility": round(self.susceptibility, 2),
            "opinion_history": [round(o, 4) for o in self.opinion_history[-20:]],
            "total_drift": round(abs(self.opinion - self.opinion_history[0]), 4) if self.opinion_history else 0.0,
        }


class OpinionDriftModel:
    """Model agent opinion evolution across simulation rounds."""

    # Inertia defaults by persona type
    INERTIA_MAP = {
        "Official": 0.9,       # Government accounts rarely change position
        "MediaOutlet": 0.7,    # Media follows evidence but has editorial stance
        "Organization": 0.8,   # Organizations are slow to shift
        "Person": 0.5,         # People are moderately flexible
        "Student": 0.3,        # Students are more easily influenced
        "Activist": 0.6,       # Activists are committed but can be moved by evidence
    }

    SUSCEPTIBILITY_MAP = {
        "Official": 0.05,
        "MediaOutlet": 0.2,
        "Organization": 0.1,
        "Person": 0.4,
        "Student": 0.6,
        "Activist": 0.3,
    }

    def initialize_agents(
        self,
        agents: List[Dict[str, Any]],
        initial_sentiments: Optional[Dict[str, float]] = None,
    ) -> Dict[str, AgentOpinionState]:
        """Initialize opinion states for all agents.

        Args:
            agents: List of agent dicts with 'agent_name' and optionally 'entity_type'
            initial_sentiments: Optional pre-existing sentiments per agent

        Returns:
            Dict mapping agent_name -> AgentOpinionState
        """
        states = {}
        for agent in agents:
            name = agent.get("agent_name", agent.get("name", ""))
            entity_type = agent.get("entity_type", agent.get("source_entity_type", "Person"))

            initial_opinion = 0.0
            if initial_sentiments and name in initial_sentiments:
                initial_opinion = initial_sentiments[name]

            inertia = self.INERTIA_MAP.get(entity_type, 0.5)
            susceptibility = self.SUSCEPTIBILITY_MAP.get(entity_type, 0.3)

            # Ensure inertia + susceptibility <= 1
            total = inertia + susceptibility
            if total > 0.95:
                scale = 0.95 / total
                inertia *= scale
                susceptibility *= scale

            state = AgentOpinionState(
                agent_name=name,
                opinion=initial_opinion,
                inertia=inertia,
                susceptibility=susceptibility,
                opinion_history=[initial_opinion],
            )
            states[name] = state

        return states

    def update_round(
        self,
        states: Dict[str, AgentOpinionState],
        follow_graph: Dict[str, List[str]],
        noise_scale: float = 0.05,
        seed: Optional[int] = None,
    ) -> Dict[str, AgentOpinionState]:
        """Update all agent opinions for one round.

        Args:
            states: Current agent opinion states
            follow_graph: agent_name -> list of followed agent names
            noise_scale: Scale of random noise (exploration)
            seed: Random seed for reproducibility

        Returns:
            Updated states (modified in-place and returned)
        """
        rng = random.Random(seed)

        # Compute social influence for each agent first (snapshot)
        social_influences = {}
        for agent_name, state in states.items():
            followed = follow_graph.get(agent_name, [])
            if followed:
                followed_opinions = [
                    states[f].opinion for f in followed if f in states
                ]
                if followed_opinions:
                    social_influences[agent_name] = sum(followed_opinions) / len(followed_opinions)
                else:
                    social_influences[agent_name] = 0.0
            else:
                social_influences[agent_name] = 0.0

        # Update opinions
        for agent_name, state in states.items():
            noise_weight = max(0.0, 1.0 - state.inertia - state.susceptibility)
            noise = rng.gauss(0, noise_scale) * noise_weight

            new_opinion = (
                state.inertia * state.opinion +
                state.susceptibility * social_influences[agent_name] +
                noise
            )

            # Clamp to [-1, 1]
            state.opinion = max(-1.0, min(1.0, new_opinion))
            state.opinion_history.append(state.opinion)

        return states

    def compute_drift_summary(
        self,
        states: Dict[str, AgentOpinionState],
    ) -> Dict[str, Any]:
        """Compute aggregate drift statistics."""
        if not states:
            return {"total_agents": 0, "avg_drift": 0.0, "max_drift": 0.0}

        drifts = []
        for state in states.values():
            if state.opinion_history:
                drift = abs(state.opinion - state.opinion_history[0])
                drifts.append(drift)

        return {
            "total_agents": len(states),
            "avg_drift": round(sum(drifts) / len(drifts), 4) if drifts else 0.0,
            "max_drift": round(max(drifts), 4) if drifts else 0.0,
            "min_drift": round(min(drifts), 4) if drifts else 0.0,
            "high_drift_agents": sum(1 for d in drifts if d > 0.5),
            "stable_agents": sum(1 for d in drifts if d < 0.1),
        }
