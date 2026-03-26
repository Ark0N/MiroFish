"""
Integration tests for the MiroFish prediction engine.

Tests that all services can be imported, instantiated, and their primary
methods work together with synthetic data. Verifies no import cycles
or missing dependencies.
"""

import json
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# 19.1 Service integration smoke tests
# ---------------------------------------------------------------------------


class TestServiceImports:
    """Verify all prediction services can be imported without errors."""

    def test_import_prediction_calibrator(self):
        from app.services.prediction_calibrator import PredictionCalibrator
        assert PredictionCalibrator is not None

    def test_import_bayesian_updater(self):
        from app.services.bayesian_updater import BayesianUpdater
        assert BayesianUpdater is not None

    def test_import_ensemble_predictor(self):
        from app.services.ensemble_predictor import EnsemblePredictor
        assert EnsemblePredictor is not None

    def test_import_pattern_matcher(self):
        from app.services.pattern_matcher import PatternMatcher
        assert PatternMatcher is not None

    def test_import_prediction_backtester(self):
        from app.services.prediction_backtester import PredictionBacktester
        assert PredictionBacktester is not None

    def test_import_prediction_pipeline(self):
        from app.services.prediction_pipeline import PredictionPipeline
        assert PredictionPipeline is not None

    def test_import_bootstrap_confidence(self):
        from app.services.bootstrap_confidence import BootstrapConfidence
        assert BootstrapConfidence is not None

    def test_import_cross_validator(self):
        from app.services.cross_validator import CrossValidator
        assert CrossValidator is not None

    def test_import_prediction_decay(self):
        from app.services.prediction_decay import PredictionDecayTracker
        assert PredictionDecayTracker is not None

    def test_import_analytics(self):
        from app.services.analytics import AnalyticsService
        assert AnalyticsService is not None

    def test_import_prediction_dedup(self):
        from app.services.prediction_dedup import PredictionDeduplicator
        assert PredictionDeduplicator is not None

    def test_import_prediction_dependencies(self):
        from app.services.prediction_dependencies import PredictionDependencyManager
        assert PredictionDependencyManager is not None

    def test_import_minority_amplifier(self):
        from app.services.minority_amplifier import MinorityAmplifier
        assert MinorityAmplifier is not None

    def test_import_uncertainty_decomposer(self):
        from app.services.uncertainty_decomposer import UncertaintyDecomposer
        assert UncertaintyDecomposer is not None

    def test_import_opinion_drift(self):
        from app.services.opinion_drift import OpinionDriftModel
        assert OpinionDriftModel is not None

    def test_import_network_influence(self):
        from app.services.network_influence import NetworkInfluenceScorer
        assert NetworkInfluenceScorer is not None

    def test_import_echo_chamber(self):
        from app.services.echo_chamber import EchoChamberDetector
        assert EchoChamberDetector is not None

    def test_import_simulation_quality(self):
        from app.services.simulation_quality import SimulationQualityScorer
        assert SimulationQualityScorer is not None

    def test_import_prediction_versioning(self):
        from app.services.prediction_versioning import PredictionVersionManager
        assert PredictionVersionManager is not None

    def test_import_prediction_provenance(self):
        from app.services.prediction_provenance import ProvenanceTracker
        assert ProvenanceTracker is not None

    def test_import_counterfactual(self):
        from app.services.counterfactual import CounterfactualAnalyzer
        assert CounterfactualAnalyzer is not None

    def test_import_prediction_narrative(self):
        from app.services.prediction_narrative import PredictionNarrativeGenerator
        assert PredictionNarrativeGenerator is not None

    def test_import_disagreement_analyzer(self):
        from app.services.disagreement_analyzer import DisagreementAnalyzer
        assert DisagreementAnalyzer is not None

    def test_import_adaptive_rounds(self):
        from app.services.adaptive_rounds import AdaptiveRoundController
        assert AdaptiveRoundController is not None

    def test_import_coalition_detector(self):
        from app.services.coalition_detector import CoalitionDetector
        assert CoalitionDetector is not None

    def test_import_prediction_market(self):
        from app.services.prediction_market import PredictionMarket
        assert PredictionMarket is not None

    def test_import_stress_tester(self):
        from app.services.stress_tester import PredictionStressTester
        assert PredictionStressTester is not None

    def test_import_prediction_chaining(self):
        from app.services.prediction_chaining import PredictionChainingEngine
        assert PredictionChainingEngine is not None

    def test_import_scenario_tree(self):
        from app.services.scenario_tree import ScenarioTreeBuilder
        assert ScenarioTreeBuilder is not None

    def test_import_contradiction_detector(self):
        from app.services.contradiction_detector import ContradictionDetector
        assert ContradictionDetector is not None

    def test_import_rss_monitor(self):
        from app.services.rss_monitor import RSSMonitor
        assert RSSMonitor is not None

    def test_import_trend_detector(self):
        from app.services.trend_detector import TrendDetector
        assert TrendDetector is not None

    def test_import_source_credibility(self):
        from app.services.source_credibility import SourceCredibilityTracker
        assert SourceCredibilityTracker is not None

    def test_import_multi_wave(self):
        from app.services.multi_wave import MultiWaveManager
        assert MultiWaveManager is not None

    def test_import_batch_ingester(self):
        from app.services.batch_ingester import BatchIngester
        assert BatchIngester is not None

    def test_import_parameter_learner(self):
        from app.services.parameter_learner import ParameterLearner
        assert ParameterLearner is not None


# ---------------------------------------------------------------------------
# 19.2 Data flow integration test
# ---------------------------------------------------------------------------


class TestPredictionDataFlow:
    """Test full prediction data flow across services."""

    def test_prediction_through_calibration_and_bayesian(self):
        """Create prediction → calibrate → Bayesian update → verify consistency."""
        from app.services.report_agent import StructuredPrediction, PredictionSet
        from app.services.prediction_calibrator import PredictionCalibrator
        from app.services.bayesian_updater import BayesianUpdater

        # Step 1: Create prediction
        pred = StructuredPrediction(
            event="Market downturn expected",
            probability=0.6,
            confidence_interval=[0.4, 0.8],
            agent_agreement=0.7,
        )
        ps = PredictionSet(predictions=[pred], overall_confidence="Moderate")

        # Step 2: Calibrate
        calibrator = PredictionCalibrator()
        calibrated = calibrator.calibrate(
            predictions=[pred.to_dict()],
            consensus_data={"agreement_score": 0.7, "consensus_strength": {
                "diversity_score": 0.6, "conviction_score": 0.5, "stability_score": 0.8,
                "weighted_score": 0.66,
            }},
        )
        assert len(calibrated) == 1
        assert "calibration" in calibrated[0]
        cal_prob = calibrated[0]["probability"]

        # Step 3: Bayesian update
        updater = BayesianUpdater()
        posterior, _ = updater.update_from_consensus(
            prior=cal_prob,
            agreement_score=0.8,
            stance_distribution={"supportive": 14, "opposing": 3, "neutral": 3},
            total_agents=20,
        )
        assert 0.01 <= posterior <= 0.99

    def test_prediction_decay_and_narrative(self):
        """Create prediction → check decay → generate narrative."""
        from datetime import datetime
        from app.services.prediction_decay import PredictionDecayTracker
        from app.services.prediction_narrative import PredictionNarrativeGenerator

        pred = {"event": "Policy change", "probability": 0.7, "evidence": ["Report A"], "agent_agreement": 0.8}

        # Decay check
        tracker = PredictionDecayTracker()
        health = tracker.compute_health([pred], datetime.now().isoformat())
        assert health[0].health_status == "fresh"

        # Narrative
        gen = PredictionNarrativeGenerator()
        narrative = gen.generate_narrative(pred)
        assert "Policy change" in narrative
        assert len(narrative) > 50


# ---------------------------------------------------------------------------
# 19.3 Analytics pipeline test
# ---------------------------------------------------------------------------


class TestAnalyticsPipeline:
    """Test full analytics pipeline with synthetic data."""

    def test_simulation_analytics_to_quality_score(self, tmp_path):
        """Create metrics → analytics → pattern fingerprint → quality score."""
        from app.services.analytics import AnalyticsService
        from app.services.pattern_matcher import PatternMatcher
        from app.services.simulation_quality import SimulationQualityScorer

        sim_dir = str(tmp_path)
        twitter_dir = os.path.join(sim_dir, "twitter")
        os.makedirs(twitter_dir)

        # Create synthetic round metrics
        metrics = []
        for r in range(5):
            metrics.append({
                "round": r + 1,
                "sentiment": {"average": 0.1 * (r + 1), "positive": 5, "negative": 3, "neutral": 2},
                "participation_rate": 0.8,
                "momentum": {"velocity": 0.05, "direction": "accelerating", "signal": "weak", "acceleration": 0.01},
                "factions": {
                    "supportive": {"count": 5, "members": ["a1", "a2"]},
                    "opposing": {"count": 3, "members": ["a3"]},
                    "neutral": {"count": 2, "members": ["a4"]},
                },
            })
        with open(os.path.join(twitter_dir, "round_metrics.jsonl"), "w") as f:
            for m in metrics:
                f.write(json.dumps(m) + "\n")

        # Create synthetic actions
        actions = []
        for i in range(10):
            actions.append({"action_type": "CREATE_POST", "agent_name": f"agent_{i}",
                           "content": f"Post {i} about topic"})
        with open(os.path.join(twitter_dir, "actions.jsonl"), "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        # Step 1: Analytics
        analytics = AnalyticsService()
        result = analytics.simulation_analytics(sim_dir)
        assert result["total_rounds"] == 5
        assert len(result["sentiment_curve"]) == 5

        # Step 2: Pattern fingerprint
        matcher = PatternMatcher()
        fp = matcher.extract_fingerprint(sim_dir, "test_sim")
        assert fp.total_rounds == 5

        # Step 3: Agent profiles
        profiles = analytics.agent_profiles(sim_dir)
        assert len(profiles) == 10

        # Step 4: Quality score
        sentiments = {f"agent_{i}": 0.1 * (i - 5) for i in range(10)}
        follow_graph = {f"agent_{i}": [f"agent_{(i+1)%10}"] for i in range(10)}
        types = {f"agent_{i}": "Person" for i in range(10)}
        quality = SimulationQualityScorer()
        score = quality.score(sentiments, follow_graph, types, 0.8)
        assert score["grade"] in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# 19.4 Prediction lifecycle test
# ---------------------------------------------------------------------------


class TestPredictionLifecycle:
    """Test complete prediction lifecycle across multiple services."""

    def test_full_lifecycle(self, tmp_path):
        """Create → version → calibrate → evidence → decay → backtest → stability."""
        from datetime import datetime
        from app.services.prediction_versioning import PredictionVersionManager
        from app.services.prediction_calibrator import PredictionCalibrator
        from app.services.prediction_decay import PredictionDecayTracker
        from app.services.prediction_backtester import PredictionBacktester
        from app.services.stress_tester import PredictionStressTester

        # Setup versioning
        vmgr = PredictionVersionManager()
        vmgr.VERSIONS_DIR = str(tmp_path / "versions")

        # Step 1: Create initial version
        v1 = vmgr.create_initial_version("r1", 0, 0.6, [0.4, 0.8])
        assert v1.version == 1

        # Step 2: Calibrate
        calibrator = PredictionCalibrator()
        calibrated = calibrator.calibrate(
            [{"event": "Test", "probability": 0.6, "agent_agreement": 0.7}],
            consensus_data={"agreement_score": 0.7},
        )
        new_prob = calibrated[0]["probability"]

        # Step 3: Record version update
        v2 = vmgr.record_update("r1", 0, new_prob, [0.3, 0.9], "calibration", "Post-calibration")
        assert v2.version == 2

        # Step 4: Check decay
        decay_tracker = PredictionDecayTracker()
        health = decay_tracker.compute_health(
            [{"event": "Test", "probability": new_prob}],
            datetime.now().isoformat(),
            evidence_log=[{"prediction_idx": 0, "timestamp": datetime.now().isoformat()}],
        )
        assert health[0].health_status in ("fresh", "boosted")

        # Step 5: Backtest
        backtester = PredictionBacktester()
        backtester.OUTCOMES_DIR = str(tmp_path / "outcomes")
        os.makedirs(backtester.OUTCOMES_DIR, exist_ok=True)
        backtester.resolve_prediction("p1", "r1", 0, "Test", new_prob, True)
        cal = backtester.compute_calibration("p1")
        assert cal.total_predictions == 1

        # Step 6: Stability index
        tester = PredictionStressTester()
        history = [v1.probability, v2.probability]
        # Need 2+ versions
        stability = tester.compute_stability_index(history)
        assert stability["num_versions"] == 2

        # Verify data consistency
        latest = vmgr.get_latest("r1", 0)
        assert latest.probability == new_prob
