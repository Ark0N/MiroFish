"""
Settings API routes
Provides model configuration and pricing information
"""

from flask import request, jsonify

from . import settings_bp
from ..config import Config


# Claude model catalog with pricing (per million tokens)
CLAUDE_MODELS = [
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "tier": "fast",
        "input_cost_per_mtok": 1.00,
        "output_cost_per_mtok": 5.00,
        "description": "Fastest, most cost-effective. Good for simulation prep and simple analysis.",
    },
    {
        "id": "claude-sonnet-4-20250514",
        "name": "Claude Sonnet 4",
        "tier": "balanced",
        "input_cost_per_mtok": 3.00,
        "output_cost_per_mtok": 15.00,
        "description": "Balanced speed and intelligence. Recommended for most tasks.",
    },
    {
        "id": "claude-opus-4-20250514",
        "name": "Claude Opus 4",
        "tier": "powerful",
        "input_cost_per_mtok": 15.00,
        "output_cost_per_mtok": 75.00,
        "description": "Most capable. Best for complex ontology extraction and report generation.",
    },
]

# Baseline model for cost comparison (Haiku)
_BASELINE = CLAUDE_MODELS[0]


def _enrich_with_cost_multiplier(models):
    """Add cost_multiplier field relative to baseline (Haiku)."""
    baseline_avg = (_BASELINE["input_cost_per_mtok"] + _BASELINE["output_cost_per_mtok"]) / 2
    result = []
    for m in models:
        m = dict(m)
        avg = (m["input_cost_per_mtok"] + m["output_cost_per_mtok"]) / 2
        m["cost_multiplier"] = round(avg / baseline_avg, 1)
        result.append(m)
    return result


@settings_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Returns available Claude models with pricing info.

    Response:
        {
            "success": true,
            "data": {
                "models": [...],
                "current_model": "claude-haiku-4-5-20251001",
                "is_anthropic": true
            }
        }
    """
    is_anthropic = Config.LLM_API_KEY and Config.LLM_API_KEY.startswith("sk-ant-")

    return jsonify({
        "success": True,
        "data": {
            "models": _enrich_with_cost_multiplier(CLAUDE_MODELS),
            "current_model": Config.LLM_MODEL_NAME,
            "is_anthropic": is_anthropic,
        }
    })
