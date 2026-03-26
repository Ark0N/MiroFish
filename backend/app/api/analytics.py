"""
Analytics API routes.
Provides simulation analytics, agent profiling, network analysis, and quality scoring.
"""

from flask import jsonify

from . import analytics_bp
from .. import limiter
from ..services.analytics import AnalyticsService
from ..services.simulation_manager import SimulationManager
from ..utils.logger import get_logger
from .helpers import validate_id_param

logger = get_logger('mirofish.api.analytics')


def _get_sim_dir(simulation_id: str):
    """Resolve simulation directory from ID."""
    return SimulationManager()._get_simulation_dir(simulation_id)


@analytics_bp.route('/simulation/<simulation_id>', methods=['GET'])
@limiter.limit("30 per minute")
def simulation_analytics(simulation_id: str):
    """Get comprehensive analytics for a simulation."""
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        sim_dir = _get_sim_dir(simulation_id)
        svc = AnalyticsService()
        result = svc.simulation_analytics(sim_dir)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Simulation analytics failed: {e}")
        return jsonify({"success": False, "error": "Analytics failed"}), 500


@analytics_bp.route('/agents/<simulation_id>', methods=['GET'])
@limiter.limit("30 per minute")
def agent_profiles(simulation_id: str):
    """Get per-agent analytics for a simulation."""
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        sim_dir = _get_sim_dir(simulation_id)
        svc = AnalyticsService()
        profiles = svc.agent_profiles(sim_dir)
        return jsonify({"success": True, "data": profiles, "count": len(profiles)})
    except Exception as e:
        logger.error(f"Agent profiles failed: {e}")
        return jsonify({"success": False, "error": "Agent analytics failed"}), 500


@analytics_bp.route('/network/<simulation_id>', methods=['GET'])
@limiter.limit("30 per minute")
def network_analytics(simulation_id: str):
    """Get network influence and echo chamber analysis."""
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        from ..services.network_influence import NetworkInfluenceScorer
        from ..services.echo_chamber import EchoChamberDetector

        sim_dir = _get_sim_dir(simulation_id)
        svc = AnalyticsService()
        profiles = svc.agent_profiles(sim_dir)

        # Build sentiment and follow graph from profiles
        sentiments = {p["agent_name"]: p["avg_sentiment"] for p in profiles}

        # Simple follow graph estimation (would use actual follow data in production)
        follow_graph = {}  # TODO: load from simulation config

        # PageRank influence
        scorer = NetworkInfluenceScorer()
        if follow_graph:
            influence = scorer.compute_influence_weighted_sentiment(sentiments, follow_graph)
        else:
            influence = {"standard_sentiment": 0, "influence_weighted_sentiment": 0, "top_influencers": []}

        # Echo chamber detection
        detector = EchoChamberDetector()
        health = detector.compute_network_health(sentiments, follow_graph)

        return jsonify({
            "success": True,
            "data": {
                "influence": influence,
                "network_health": health,
                "agent_count": len(sentiments),
            }
        })
    except Exception as e:
        logger.error(f"Network analytics failed: {e}")
        return jsonify({"success": False, "error": "Network analytics failed"}), 500


@analytics_bp.route('/quality/<simulation_id>', methods=['GET'])
@limiter.limit("30 per minute")
def quality_score(simulation_id: str):
    """Get simulation quality score."""
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        from ..services.simulation_quality import SimulationQualityScorer

        sim_dir = _get_sim_dir(simulation_id)
        svc = AnalyticsService()
        profiles = svc.agent_profiles(sim_dir)

        sentiments = {p["agent_name"]: p["avg_sentiment"] for p in profiles}
        types = {p["agent_name"]: p["behavior_type"] for p in profiles}
        follow_graph = {}  # TODO: load from simulation config
        participation = sum(1 for p in profiles if p["total_actions"] > 0) / max(len(profiles), 1)

        scorer = SimulationQualityScorer()
        result = scorer.score(sentiments, follow_graph, types, participation)

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Quality score failed: {e}")
        return jsonify({"success": False, "error": "Quality score failed"}), 500
