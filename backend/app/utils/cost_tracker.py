"""
Centralized LLM cost tracking and budget enforcement.

Thread-safe singleton that accumulates token usage and costs across a pipeline run.
Raises BudgetExceededError when the cumulative cost exceeds the configured limit.

Usage:
    tracker = CostTracker.get_instance()
    tracker.reset("my-pipeline-run")  # Start a new run
    tracker.record_usage(input_tokens=1000, output_tokens=500, model="claude-haiku-4-5-20251001")
    tracker.check_budget()  # Raises BudgetExceededError if over limit
    summary = tracker.get_summary()
"""

import threading
from typing import Dict, Any, Optional

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.cost_tracker')


class BudgetExceededError(Exception):
    """Raised when cumulative LLM costs exceed the configured budget limit."""

    def __init__(self, current_cost: float, limit: float, phase: str = ""):
        self.current_cost = current_cost
        self.limit = limit
        self.phase = phase
        phase_msg = f" during {phase}" if phase else ""
        super().__init__(
            f"Pipeline budget exceeded{phase_msg}: ${current_cost:.2f} >= ${limit:.2f} limit. "
            f"Increase PIPELINE_BUDGET_LIMIT or use a cheaper model."
        )


# Pricing per million tokens (USD) — kept in sync with settings.py catalog
MODEL_PRICING = {
    # Claude 4.5 Haiku
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    # Claude 4 Sonnet
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # Claude 4 Opus
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}

# Fallback pricing (assumes Haiku-class costs for unknown models)
_FALLBACK_PRICING = {"input": 1.00, "output": 5.00}


def _get_pricing(model_name: str) -> Dict[str, float]:
    """Get pricing for a model, falling back to conservative estimate."""
    # Exact match
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    # Partial match (e.g., "claude-haiku" matches "claude-haiku-4-5-20251001")
    model_lower = model_name.lower()
    for key, pricing in MODEL_PRICING.items():
        if key.startswith(model_lower) or model_lower.startswith(key.split("-20")[0]):
            return pricing
    # Keyword match
    if "opus" in model_lower:
        return MODEL_PRICING.get("claude-opus-4-20250514", _FALLBACK_PRICING)
    if "sonnet" in model_lower:
        return MODEL_PRICING.get("claude-sonnet-4-20250514", _FALLBACK_PRICING)
    if "haiku" in model_lower:
        return MODEL_PRICING.get("claude-haiku-4-5-20251001", _FALLBACK_PRICING)
    return _FALLBACK_PRICING


class CostTracker:
    """Thread-safe singleton for tracking LLM costs across a pipeline run."""

    _instance: Optional["CostTracker"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._run_id: str = ""
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost: float = 0.0
        self._total_api_calls: int = 0
        self._cost_by_phase: Dict[str, float] = {}
        self._tokens_by_phase: Dict[str, Dict[str, int]] = {}
        try:
            self._budget_limit: float = float(Config.PIPELINE_BUDGET_LIMIT)
        except (TypeError, ValueError):
            self._budget_limit = 20.0

    @classmethod
    def get_instance(cls) -> "CostTracker":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Reset singleton (for testing only)."""
        with cls._instance_lock:
            cls._instance = None

    def reset(self, run_id: str = "") -> None:
        """Reset tracking for a new pipeline run."""
        with self._lock:
            self._run_id = run_id
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._total_cost = 0.0
            self._total_api_calls = 0
            self._cost_by_phase = {}
            self._tokens_by_phase = {}
            try:
                self._budget_limit = float(Config.PIPELINE_BUDGET_LIMIT)
            except (TypeError, ValueError):
                self._budget_limit = 20.0
            logger.info(f"Cost tracker reset: run_id={run_id}, budget=${self._budget_limit:.2f}")

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
        phase: str = "unknown",
    ) -> float:
        """Record token usage from an LLM call and return the incremental cost.

        Args:
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens consumed
            model: Model name (for pricing lookup)
            phase: Pipeline phase name (e.g., "ontology", "profiles", "report")

        Returns:
            Incremental cost in USD for this call
        """
        # Coerce to int to handle MagicMock or other non-numeric values from tests
        try:
            input_tokens = int(input_tokens)
            output_tokens = int(output_tokens)
        except (TypeError, ValueError):
            return 0.0

        if input_tokens == 0 and output_tokens == 0:
            return 0.0

        model = model or Config.LLM_MODEL_NAME or ""
        pricing = _get_pricing(model)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        with self._lock:
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._total_cost += cost
            self._total_api_calls += 1

            self._cost_by_phase[phase] = self._cost_by_phase.get(phase, 0.0) + cost
            if phase not in self._tokens_by_phase:
                self._tokens_by_phase[phase] = {"input": 0, "output": 0}
            self._tokens_by_phase[phase]["input"] += input_tokens
            self._tokens_by_phase[phase]["output"] += output_tokens

            current_total = self._total_cost

        try:
            budget_str = f"${self._budget_limit:.2f}" if isinstance(self._budget_limit, (int, float)) else str(self._budget_limit)
        except (TypeError, ValueError):
            budget_str = "N/A"
        logger.debug(
            f"Cost +${cost:.4f} ({phase}): "
            f"in={input_tokens:,} out={output_tokens:,} | "
            f"cumulative=${current_total:.2f}/{budget_str}"
        )

        return cost

    def check_budget(self, phase: str = "") -> None:
        """Check if the budget has been exceeded. Raises BudgetExceededError if so."""
        with self._lock:
            try:
                limit = float(self._budget_limit)
            except (TypeError, ValueError):
                limit = 20.0
            if self._total_cost >= limit:
                raise BudgetExceededError(self._total_cost, limit, phase)

    @property
    def total_cost(self) -> float:
        with self._lock:
            return self._total_cost

    @property
    def remaining_budget(self) -> float:
        with self._lock:
            return max(0.0, self._budget_limit - self._total_cost)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of costs for the current run."""
        with self._lock:
            return {
                "run_id": self._run_id,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_api_calls": self._total_api_calls,
                "total_cost_usd": round(self._total_cost, 4),
                "budget_limit_usd": self._budget_limit,
                "remaining_budget_usd": round(max(0, self._budget_limit - self._total_cost), 4),
                "cost_by_phase": {k: round(v, 4) for k, v in self._cost_by_phase.items()},
                "tokens_by_phase": dict(self._tokens_by_phase),
            }

    def log_summary(self) -> None:
        """Log a human-readable cost summary."""
        s = self.get_summary()
        logger.info(
            f"=== Cost Summary (run: {s['run_id']}) ===\n"
            f"  API calls:     {s['total_api_calls']}\n"
            f"  Input tokens:  {s['total_input_tokens']:,}\n"
            f"  Output tokens: {s['total_output_tokens']:,}\n"
            f"  Total cost:    ${s['total_cost_usd']:.4f}\n"
            f"  Budget limit:  ${s['budget_limit_usd']:.2f}\n"
            f"  Remaining:     ${s['remaining_budget_usd']:.4f}\n"
            f"  By phase:      {s['cost_by_phase']}"
        )
