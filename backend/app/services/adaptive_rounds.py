"""
Adaptive round count controller.

Instead of fixed round counts, detects when consensus has stabilized
(sentiment velocity below threshold for consecutive rounds) and signals
the simulation to stop. Saves compute without losing prediction quality.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger('mirofish.adaptive_rounds')


@dataclass
class StabilityCheck:
    """Result of a consensus stability check."""
    is_stable: bool
    consecutive_stable_rounds: int
    current_velocity: float
    should_stop: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_stable": self.is_stable,
            "consecutive_stable_rounds": self.consecutive_stable_rounds,
            "current_velocity": round(self.current_velocity, 4),
            "should_stop": self.should_stop,
            "reason": self.reason,
        }


class AdaptiveRoundController:
    """Control simulation length based on consensus stabilization."""

    def __init__(
        self,
        velocity_threshold: float = 0.03,
        required_stable_rounds: int = 3,
        min_rounds: int = 5,
        max_rounds: int = 100,
    ):
        """
        Args:
            velocity_threshold: Sentiment velocity below which round is "stable"
            required_stable_rounds: Consecutive stable rounds before stopping
            min_rounds: Minimum rounds before considering early stop
            max_rounds: Hard maximum rounds
        """
        self.velocity_threshold = velocity_threshold
        self.required_stable_rounds = required_stable_rounds
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self._stable_count = 0
        self._round_count = 0

    def check_round(
        self,
        round_num: int,
        sentiment_velocity: float,
        participation_rate: float = 1.0,
    ) -> StabilityCheck:
        """Check if the simulation should stop after this round.

        Args:
            round_num: Current round number
            sentiment_velocity: Rate of change of sentiment this round
            participation_rate: Fraction of agents that were active

        Returns:
            StabilityCheck with stop recommendation
        """
        self._round_count = round_num

        is_stable = abs(sentiment_velocity) < self.velocity_threshold

        if is_stable:
            self._stable_count += 1
        else:
            self._stable_count = 0

        # Check stop conditions
        if round_num >= self.max_rounds:
            return StabilityCheck(
                is_stable=is_stable,
                consecutive_stable_rounds=self._stable_count,
                current_velocity=sentiment_velocity,
                should_stop=True,
                reason=f"Maximum rounds ({self.max_rounds}) reached",
            )

        if round_num < self.min_rounds:
            return StabilityCheck(
                is_stable=is_stable,
                consecutive_stable_rounds=self._stable_count,
                current_velocity=sentiment_velocity,
                should_stop=False,
                reason=f"Minimum rounds not yet reached ({round_num}/{self.min_rounds})",
            )

        # Low participation also signals to stop (agents have disengaged)
        if participation_rate < 0.1 and round_num >= self.min_rounds:
            return StabilityCheck(
                is_stable=True,
                consecutive_stable_rounds=self._stable_count,
                current_velocity=sentiment_velocity,
                should_stop=True,
                reason=f"Very low participation rate ({participation_rate:.1%})",
            )

        if self._stable_count >= self.required_stable_rounds:
            return StabilityCheck(
                is_stable=True,
                consecutive_stable_rounds=self._stable_count,
                current_velocity=sentiment_velocity,
                should_stop=True,
                reason=f"Consensus stabilized for {self._stable_count} consecutive rounds",
            )

        return StabilityCheck(
            is_stable=is_stable,
            consecutive_stable_rounds=self._stable_count,
            current_velocity=sentiment_velocity,
            should_stop=False,
            reason="Simulation still evolving" if not is_stable else f"Stable for {self._stable_count}/{self.required_stable_rounds} rounds",
        )

    def reset(self) -> None:
        """Reset the controller for a new simulation."""
        self._stable_count = 0
        self._round_count = 0

    def get_status(self) -> Dict[str, Any]:
        """Get current controller status."""
        return {
            "rounds_completed": self._round_count,
            "consecutive_stable_rounds": self._stable_count,
            "velocity_threshold": self.velocity_threshold,
            "required_stable_rounds": self.required_stable_rounds,
            "min_rounds": self.min_rounds,
            "max_rounds": self.max_rounds,
        }
