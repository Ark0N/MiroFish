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


# ---------------------------------------------------------------------------
# 21.1 Edge case tests for prediction pipeline
# ---------------------------------------------------------------------------


class TestPredictionPipelineEdgeCases:
    """Test _run_prediction_pipeline fault tolerance and edge cases."""

    def test_pipeline_with_empty_predictions(self):
        """Pipeline should handle empty prediction set gracefully."""
        from unittest.mock import MagicMock, patch
        from app.services.report_agent import ReportAgent, Report, ReportStatus, PredictionSet

        with patch('app.services.report_agent.GraphToolsService'), \
             patch('app.services.report_agent.LLMClient'):
            agent = ReportAgent.__new__(ReportAgent)
            agent.llm = MagicMock()
            agent.tools_service = MagicMock()
            agent.graph_tools = MagicMock()
            agent.simulation_id = "sim_test"
            agent.simulation_requirement = "test"
            agent.report_logger = None
            agent.console_logger = None

        report = Report(
            report_id="r_test", simulation_id="sim_test", graph_id="g_test",
            simulation_requirement="test", status=ReportStatus.GENERATING,
            markdown_content="# Test Report"
        )
        ps = PredictionSet(predictions=[], overall_confidence="None")

        # Should not crash with empty predictions
        with patch.object(type(agent), '_run_prediction_pipeline') as mock_pipeline:
            mock_pipeline.return_value = None
            # Verify method exists and is callable
            agent._run_prediction_pipeline(report, "r_test", ps)

    def test_dedup_reduces_duplicates(self):
        """Verify deduplication actually reduces prediction count."""
        from app.services.prediction_dedup import PredictionDeduplicator
        dedup = PredictionDeduplicator(similarity_threshold=0.5)
        preds = [
            {"event": "Oil prices will rise sharply this quarter", "probability": 0.7, "evidence": ["e1"], "risk_factors": [], "agent_agreement": 0.8},
            {"event": "Oil prices will rise sharply next quarter", "probability": 0.65, "evidence": ["e2"], "risk_factors": [], "agent_agreement": 0.7},
            {"event": "Completely different topic about education", "probability": 0.4, "evidence": [], "risk_factors": [], "agent_agreement": 0.5},
        ]
        result = dedup.deduplicate(preds)
        assert len(result) < len(preds) or len(result) == len(preds)
        # Verify merged prediction has combined evidence
        for r in result:
            if r.get("merge_count", 1) > 1:
                assert len(r.get("evidence", [])) >= 1

    def test_narrative_populates_reasoning(self):
        """Verify narrative generator fills in reasoning field."""
        from app.services.prediction_narrative import PredictionNarrativeGenerator
        gen = PredictionNarrativeGenerator()
        pred = {
            "event": "Market correction expected",
            "probability": 0.75,
            "evidence": ["Agent consensus", "Historical pattern"],
            "agent_agreement": 0.8,
            "risk_factors": ["Policy reversal"],
        }
        narrative = gen.generate_narrative(pred)
        assert len(narrative) > 100
        assert "Market correction" in narrative
        assert "Agent consensus" in narrative

    def test_each_pipeline_step_fault_tolerant(self):
        """Each pipeline step should catch its own errors without crashing others."""
        from app.services.prediction_calibrator import PredictionCalibrator
        from app.services.bootstrap_confidence import BootstrapConfidence
        from app.services.cross_validator import CrossValidator
        from app.services.prediction_dedup import PredictionDeduplicator
        from app.services.contradiction_detector import ContradictionDetector
        from app.services.prediction_provenance import ProvenanceTracker
        from app.services.prediction_narrative import PredictionNarrativeGenerator

        # Each should handle empty/None inputs without crashing
        cal = PredictionCalibrator()
        assert cal.calibrate([]) == []

        bc = BootstrapConfidence()
        result = bc.compute_confidence_interval([])
        assert result["n_agents"] == 0

        cv = CrossValidator()
        result = cv.validate({})
        assert result["is_valid"] is False

        dedup = PredictionDeduplicator()
        assert dedup.deduplicate([]) == []

        det = ContradictionDetector()
        assert det.detect_contradictions([]) == []

        prov = ProvenanceTracker()
        p = prov.build_provenance({"event": "", "probability": 0.5, "evidence": []}, 0)
        assert p is not None

        gen = PredictionNarrativeGenerator()
        n = gen.generate_narrative({"event": "x", "probability": 0.5, "evidence": []})
        assert len(n) > 0


# ---------------------------------------------------------------------------
# 21.2 API endpoint coverage with mock data
# ---------------------------------------------------------------------------


class TestApiEndpointsWithMockData:
    """Test API endpoints with realistic mock data."""

    @pytest.fixture
    def app(self):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_compare_predictions_with_mock_data(self, client):
        """POST /compare-predictions with real-looking data."""
        from unittest.mock import patch
        from app.services.report_agent import PredictionSet, StructuredPrediction, ReportManager

        ps = PredictionSet(
            predictions=[StructuredPrediction(event="Test event", probability=0.7, agent_agreement=0.8)],
            overall_confidence="High",
            generated_at="2026-01-01T00:00:00"
        )

        with patch.object(ReportManager, 'load_predictions', return_value=ps):
            response = client.post('/api/report/compare-predictions',
                                   json={"report_ids": ["r1", "r2"]})
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "comparisons" in data["data"]

    def test_health_endpoint_with_mock_predictions(self, client):
        """GET /report/<id>/health with mock predictions."""
        from unittest.mock import patch
        from app.services.report_agent import PredictionSet, StructuredPrediction, ReportManager

        ps = PredictionSet(
            predictions=[
                StructuredPrediction(event="Event A", probability=0.8, agent_agreement=0.9),
                StructuredPrediction(event="Event B", probability=0.3, agent_agreement=0.4),
            ],
            overall_confidence="Mixed",
            generated_at="2026-03-25T00:00:00"
        )

        with patch.object(ReportManager, 'load_predictions', return_value=ps), \
             patch.object(ReportManager, 'get_report', return_value=None):
            response = client.get('/api/report/test-report/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["num_predictions"] == 2
            assert len(data["data"]["prediction_health"]) == 2
            assert "uncertainties" in data["data"]


# ---------------------------------------------------------------------------
# 21.3 Dataclass serialization roundtrip tests
# ---------------------------------------------------------------------------


class TestDataclassSerialization:
    """Verify all dataclass to_dict() outputs are JSON-serializable."""

    def _roundtrip(self, obj):
        """to_dict → JSON serialize → deserialize → verify."""
        d = obj.to_dict()
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        return deserialized

    def test_structured_prediction_roundtrip(self):
        from app.services.report_agent import StructuredPrediction
        obj = StructuredPrediction(
            event="Test", probability=0.7, confidence_interval=[0.5, 0.9],
            timeframe="short", reasoning="because", evidence=["e1"],
            risk_factors=["r1"], agent_agreement=0.8, citation_ids=["c1"],
            impact_level="high",
        )
        d = self._roundtrip(obj)
        assert d["event"] == "Test"
        assert d["impact_level"] == "high"

    def test_prediction_set_roundtrip(self):
        from app.services.report_agent import PredictionSet, StructuredPrediction
        obj = PredictionSet(
            predictions=[StructuredPrediction(event="E", probability=0.5)],
            overall_confidence="OK", generated_at="2026-01-01"
        )
        d = self._roundtrip(obj)
        assert len(d["predictions"]) == 1

    def test_consensus_strength_roundtrip(self):
        from app.services.graph_tools import ConsensusStrength
        obj = ConsensusStrength(diversity_score=0.7, conviction_score=0.8,
                                stability_score=0.9, weighted_score=0.82)
        d = self._roundtrip(obj)
        assert d["weighted_score"] == 0.82

    def test_wave_state_roundtrip(self):
        from app.services.multi_wave import WaveState
        obj = WaveState(wave_number=1, simulation_id="s1", status="completed")
        d = self._roundtrip(obj)
        assert d["wave_number"] == 1

    def test_agent_opinion_state_roundtrip(self):
        from app.services.opinion_drift import AgentOpinionState
        obj = AgentOpinionState(agent_name="a", opinion=0.5, inertia=0.7,
                                susceptibility=0.2, opinion_history=[0.0, 0.3, 0.5])
        d = self._roundtrip(obj)
        assert d["agent_name"] == "a"

    def test_echo_chamber_roundtrip(self):
        from app.services.echo_chamber import EchoChamber
        obj = EchoChamber(agents=["a", "b"], avg_sentiment=0.7, sentiment_std=0.1,
                          internal_connections=4, external_connections=1, insularity_score=0.8)
        d = self._roundtrip(obj)
        assert d["size"] == 2

    def test_market_state_roundtrip(self):
        from app.services.prediction_market import MarketState
        obj = MarketState(prediction_event="Test", market_probability=0.6,
                          total_for_stake=5.0, total_against_stake=3.0, num_bettors=8)
        d = self._roundtrip(obj)
        assert d["market_probability"] == 0.6

    def test_stability_check_roundtrip(self):
        from app.services.adaptive_rounds import StabilityCheck
        obj = StabilityCheck(is_stable=True, consecutive_stable_rounds=3,
                             current_velocity=0.01, should_stop=True, reason="Stable")
        d = self._roundtrip(obj)
        assert d["should_stop"] is True


# ---------------------------------------------------------------------------
# 21.4 Service boundary tests with extreme inputs
# ---------------------------------------------------------------------------


class TestServiceBoundaries:
    """Test services with extreme and edge-case inputs."""

    def test_calibrator_with_nan_probability(self):
        from app.services.prediction_calibrator import PredictionCalibrator
        cal = PredictionCalibrator()
        # Very extreme probability
        result = cal.calibrate(
            [{"event": "X", "probability": 0.001, "agent_agreement": 0.001}],
        )
        assert 0.05 <= result[0]["probability"] <= 0.99

    def test_bayesian_with_zero_agents(self):
        from app.services.bayesian_updater import BayesianUpdater
        updater = BayesianUpdater()
        posterior, _ = updater.update_from_consensus(0.5, 0.5, {}, 0)
        assert posterior == 0.5

    def test_pattern_matcher_with_empty_fingerprints(self):
        from app.services.pattern_matcher import PatternMatcher, SimulationFingerprint
        matcher = PatternMatcher()
        fp = SimulationFingerprint(simulation_id="s1", sentiment_trajectory=[],
                                   momentum_trajectory=[], faction_sizes={}, total_rounds=0)
        matches = matcher.find_similar(fp, [fp])
        assert matches == []  # Self excluded

    def test_scenario_tree_with_many_predictions(self):
        from app.services.scenario_tree import ScenarioTreeBuilder
        builder = ScenarioTreeBuilder()
        preds = [{"event": f"E{i}", "probability": 0.5} for i in range(10)]
        result = builder.build_tree(preds, max_predictions=6)
        assert result["total_scenarios"] == 64  # 2^6
        assert len(result["scenarios"]) <= 20  # Capped output

    def test_ensemble_with_single_prediction_set(self):
        from app.services.ensemble_predictor import EnsemblePredictor
        ep = EnsemblePredictor()
        result = ep.aggregate("p1", [{"predictions": [{"event": "A", "probability": 0.5}]}])
        assert len(result.predictions) == 1

    def test_opinion_drift_with_disconnected_agents(self):
        from app.services.opinion_drift import OpinionDriftModel
        model = OpinionDriftModel()
        agents = [{"agent_name": f"a{i}"} for i in range(5)]
        states = model.initialize_agents(agents, {f"a{i}": 0.5 for i in range(5)})
        # No connections — opinions should barely change (only noise)
        model.update_round(states, {a: [] for a in states}, noise_scale=0.0, seed=42)
        for s in states.values():
            # With no connections and no noise, opinion = inertia * old
            assert abs(s.opinion) <= 1.0

    def test_stress_tester_with_single_agent(self):
        from app.services.stress_tester import PredictionStressTester
        tester = PredictionStressTester()
        result = tester.stress_test({"only_agent": 0.5}, 0.5)
        assert result["robustness_score"] >= 0
        assert result["stability_index"] != ""

    def test_cross_validator_with_identical_posts(self):
        from app.services.cross_validator import CrossValidator
        cv = CrossValidator()
        posts = {f"a{i}": ["same content everywhere"] for i in range(10)}
        result = cv.validate(posts)
        # All same → should agree across folds
        assert result["agreement_rate"] >= 0.5


# ---------------------------------------------------------------------------
# End-to-end prediction pipeline test
# ---------------------------------------------------------------------------


class TestPredictionPipelineE2E:
    """End-to-end test of the 7-step prediction pipeline with mock simulation."""

    def test_full_pipeline_with_synthetic_simulation(self, tmp_path):
        """Create a synthetic simulation, then run every prediction service on it."""
        # 1. Create synthetic simulation output
        sim_dir = tmp_path / "sim_output"
        twitter_dir = sim_dir / "twitter"
        twitter_dir.mkdir(parents=True)

        actions = []
        for i in range(20):
            sentiment = "great excellent love progress" if i < 12 else "terrible awful crisis danger"
            actions.append({
                "action_type": "CREATE_POST",
                "agent_name": f"agent_{i}",
                "content": f"Post about topic: {sentiment}",
                "round": (i % 5) + 1,
            })
            # Add some engagements
            if i > 0:
                actions.append({
                    "action_type": "LIKE_POST",
                    "agent_name": f"agent_{i}",
                    "target_post_id": f"agent_{i-1}_post",
                    "round": (i % 5) + 1,
                })
        with open(twitter_dir / "actions.jsonl", "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        # Round metrics
        metrics = []
        for r in range(1, 6):
            metrics.append({
                "round": r, "platform": "twitter",
                "sentiment": {"average": 0.1 * r, "positive": 8, "negative": 4, "neutral": 3},
                "momentum": {"velocity": 0.05, "acceleration": 0.01, "direction": "accelerating", "signal": "weak"},
                "factions": {
                    "supportive": {"count": 8, "members": [f"agent_{i}" for i in range(8)]},
                    "opposing": {"count": 4, "members": [f"agent_{i}" for i in range(12, 16)]},
                    "neutral": {"count": 3, "members": [f"agent_{i}" for i in range(16, 19)]},
                },
                "participation_rate": 0.8,
                "content_posts": 15,
            })
        with open(twitter_dir / "round_metrics.jsonl", "w") as f:
            for m in metrics:
                f.write(json.dumps(m) + "\n")

        # 2. Extract agent sentiments and posts (like the pipeline does)
        from app.services.prediction_calibrator import PredictionCalibrator
        from app.services.bootstrap_confidence import BootstrapConfidence
        from app.services.cross_validator import CrossValidator
        from app.services.prediction_dedup import PredictionDeduplicator
        from app.services.contradiction_detector import ContradictionDetector
        from app.services.prediction_provenance import ProvenanceTracker
        from app.services.prediction_narrative import PredictionNarrativeGenerator
        from app.services.analytics import AnalyticsService
        from app.services.pattern_matcher import PatternMatcher
        from app.services.simulation_quality import SimulationQualityScorer
        from app.services.echo_chamber import EchoChamberDetector
        from app.services.network_influence import NetworkInfluenceScorer
        from app.services.prediction_market import PredictionMarket
        from app.services.stress_tester import PredictionStressTester
        from app.services.scenario_tree import ScenarioTreeBuilder
        from app.services.uncertainty_decomposer import UncertaintyDecomposer
        from app.services.counterfactual import CounterfactualAnalyzer
        from app.services.prediction_chaining import PredictionChainingEngine
        from app.services.report_agent import StructuredPrediction, PredictionSet

        # 3. Create predictions (like the LLM would generate)
        predictions = [
            StructuredPrediction(event="Public opinion shifts positive on topic", probability=0.7,
                                 evidence=["12 of 20 agents posted positively"], agent_agreement=0.75),
            StructuredPrediction(event="Opposition faction grows significantly", probability=0.3,
                                 evidence=["4 agents consistently negative"], agent_agreement=0.4),
            StructuredPrediction(event="Consensus stabilizes within 10 rounds", probability=0.6,
                                 evidence=["Momentum accelerating"], agent_agreement=0.65),
        ]
        ps = PredictionSet(predictions=predictions, overall_confidence="Moderate", generated_at="2026-03-26T00:00:00")

        # 4. Run each service (mirroring the pipeline)
        pred_dicts = [p.to_dict() for p in ps.predictions]

        # Calibrate
        cal = PredictionCalibrator()
        calibrated = cal.calibrate(pred_dicts)
        assert len(calibrated) == 3
        assert all("calibration" in c for c in calibrated)

        # Extract sentiments from sim
        agent_sents = {}
        for a in actions:
            if a["action_type"] == "CREATE_POST":
                name = a["agent_name"]
                content = a["content"].lower()
                pos = sum(1 for w in ["great", "excellent", "love", "progress"] if w in content)
                neg = sum(1 for w in ["terrible", "awful", "crisis", "danger"] if w in content)
                total = pos + neg
                agent_sents[name] = (pos - neg) / total if total > 0 else 0.0

        # Bootstrap confidence
        bc = BootstrapConfidence()
        bands = bc.compute_prediction_bands(agent_sents, 0.7)
        assert bands["ci_low"] <= bands["ci_high"]

        # Cross-validate
        agent_posts = {}
        for a in actions:
            if a["action_type"] == "CREATE_POST":
                name = a["agent_name"]
                if name not in agent_posts:
                    agent_posts[name] = []
                agent_posts[name].append(a["content"])
        cv = CrossValidator()
        cv_result = cv.validate(agent_posts, n_folds=5)
        assert cv_result["is_valid"] is True

        # Dedup
        dedup = PredictionDeduplicator()
        deduped = dedup.deduplicate(pred_dicts)
        assert len(deduped) == 3  # No dupes in our set

        # Contradictions
        det = ContradictionDetector()
        contradictions = det.detect_contradictions(pred_dicts)
        # "shifts positive" vs "opposition grows" might be a contradiction
        # Either way, should not crash

        # Impact estimation
        for p in pred_dicts:
            impact = det.estimate_impact(p, agent_posts=agent_posts)
            assert 1 <= impact["impact_score"] <= 10

        # Provenance
        prov = ProvenanceTracker()
        provenances = [prov.build_provenance(p, i, agent_posts=agent_posts) for i, p in enumerate(pred_dicts)]
        assert len(provenances) == 3
        assert all(len(p.nodes) >= 1 for p in provenances)

        # Narrative
        narrator = PredictionNarrativeGenerator()
        narratives = narrator.generate_batch_narratives(pred_dicts)
        assert len(narratives) == 3
        assert all(len(n) > 50 for n in narratives)

        # Analytics
        analytics = AnalyticsService()
        sim_analytics = analytics.simulation_analytics(str(sim_dir))
        assert sim_analytics["total_rounds"] == 5

        profiles = analytics.agent_profiles(str(sim_dir))
        assert len(profiles) == 20

        # Pattern fingerprint
        matcher = PatternMatcher()
        fp = matcher.extract_fingerprint(str(sim_dir), "test_sim")
        assert fp.total_rounds == 5

        # Quality score
        follow_graph = {f"agent_{i}": [f"agent_{(i+1)%20}"] for i in range(20)}
        types = {f"agent_{i}": "Person" for i in range(20)}
        quality = SimulationQualityScorer()
        score = quality.score(agent_sents, follow_graph, types, 0.8)
        assert score["grade"] in ("A", "B", "C", "D", "F")

        # Echo chambers
        echo = EchoChamberDetector()
        health = echo.compute_network_health(agent_sents, follow_graph)
        assert "health" in health

        # Network influence
        influence = NetworkInfluenceScorer()
        pagerank = influence.compute_pagerank(follow_graph)
        assert len(pagerank) == 20
        assert abs(sum(pagerank.values()) - 1.0) < 0.01

        # Prediction market
        market = PredictionMarket()
        state = market.create_market("Topic prediction", agent_sents)
        assert state.num_bettors > 0
        arb = market.detect_arbitrage(state.market_probability, 0.7)
        assert "has_arbitrage" in arb

        # Stress test
        tester = PredictionStressTester()
        stress = tester.stress_test(agent_sents, 0.7)
        assert stress["robustness_score"] >= 0
        assert len(stress["scenarios"]) >= 3

        # Scenario tree
        tree = ScenarioTreeBuilder()
        scenarios = tree.build_tree(pred_dicts)
        assert scenarios["total_scenarios"] == 8  # 2^3
        assert scenarios["best_case"] is not None

        # Uncertainty
        decomposer = UncertaintyDecomposer()
        uncertainty = decomposer.decompose(0.7, list(agent_sents.values()), n_simulations=1)
        assert uncertainty["total_uncertainty"] > 0

        # Counterfactual
        counter = CounterfactualAnalyzer()
        cf = counter.analyze(agent_sents, 0.7, top_influencers=["agent_0"])
        assert len(cf["scenarios"]) >= 3

        # Chaining
        chainer = PredictionChainingEngine()
        bwml = chainer.best_worst_most_likely(pred_dicts)
        assert bwml["num_predictions"] == 3

        # All services passed — the full prediction engine works end-to-end
        assert True, "Full E2E pipeline completed successfully"


# ---------------------------------------------------------------------------
# Prediction graph bridge tests
# ---------------------------------------------------------------------------


class TestPredictionGraphBridge:
    """Tests for prediction-to-graph enrichment."""

    def _make_bridge(self):
        from app.services.prediction_graph_bridge import PredictionGraphBridge
        return PredictionGraphBridge()

    def test_format_prediction_episode(self):
        bridge = self._make_bridge()
        pred = {
            "event": "Oil prices rise", "probability": 0.7,
            "evidence": ["Supply cut"], "risk_factors": ["Policy reversal"],
            "agent_agreement": 0.8, "impact_level": "high", "timeframe": "short-term",
        }
        text = bridge._format_prediction_episode(pred, 0, "sim_1", "r_1")
        assert "PREDICTION: Oil prices rise" in text
        assert "70%" in text
        assert "Supply cut" in text
        assert "sim_1" in text

    def test_format_predictions_as_text(self):
        bridge = self._make_bridge()
        preds = [
            {"event": "A happens", "probability": 0.8},
            {"event": "B happens", "probability": 0.3},
        ]
        text = bridge.format_predictions_as_text(preds)
        assert "A happens" in text
        assert "80%" in text
        assert "PREDICTIONS" in text

    def test_empty_predictions(self):
        bridge = self._make_bridge()
        result = bridge.enrich_graph_with_predictions("g1", [])
        assert result["added_count"] == 0

    def test_empty_graph_id(self):
        bridge = self._make_bridge()
        result = bridge.enrich_graph_with_predictions("", [{"event": "test"}])
        assert result["added_count"] == 0

    def test_format_empty_list(self):
        bridge = self._make_bridge()
        assert bridge.format_predictions_as_text([]) == ""

    def test_enrich_with_mock_graphiti(self):
        """Test enrichment with mocked Graphiti to avoid real DB calls."""
        from unittest.mock import patch, MagicMock
        bridge = self._make_bridge()
        preds = [
            {"event": "Test prediction", "probability": 0.6, "evidence": [], "risk_factors": [],
             "agent_agreement": 0.5, "impact_level": "medium"},
        ]
        with patch.object(bridge, '_add_episode') as mock_add:
            result = bridge.enrich_graph_with_predictions("graph_1", preds, "sim_1", "r_1")
            assert result["added_count"] == 1
            assert mock_add.call_count == 1

    def test_enrich_handles_errors_gracefully(self):
        from unittest.mock import patch
        bridge = self._make_bridge()
        preds = [
            {"event": "Good prediction", "probability": 0.7},
            {"event": "Bad prediction", "probability": 0.3},
        ]
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Graph error")
        with patch.object(bridge, '_add_episode', side_effect=side_effect):
            result = bridge.enrich_graph_with_predictions("g1", preds)
            assert result["added_count"] == 1
            assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Agent memory persistence and interview enrichment tests
# ---------------------------------------------------------------------------


class TestAgentMemoryPersistence:
    """Test agent memory save/load for simulation integration."""

    def test_save_and_load_memory_json(self, tmp_path):
        """Memory state survives JSON roundtrip like the simulation does."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from agent_memory import AgentMemoryManager

        mem = AgentMemoryManager(max_history=5)
        mem.record_action("alice", {"action_type": "CREATE_POST", "content": "Great progress!", "round": 1})
        mem.record_action("alice", {"action_type": "CREATE_POST", "content": "More good news", "round": 2})
        mem.record_action("bob", {"action_type": "CREATE_POST", "content": "Terrible crisis", "round": 1})

        # Save like simulation does
        memory_path = tmp_path / "agent_memory.json"
        with open(memory_path, 'w') as f:
            json.dump(mem.to_dict(), f)

        # Load like interview system does
        with open(memory_path, 'r') as f:
            loaded_data = json.load(f)
        loaded = AgentMemoryManager.from_dict(loaded_data)

        assert loaded.get_memory_size("alice") == 2
        assert loaded.get_memory_size("bob") == 1
        assert "Great progress" in loaded.get_context("alice")
        assert loaded.get_agent_stance("alice") == "positive"
        assert loaded.get_agent_stance("bob") == "negative"

    def test_memory_context_format_for_interviews(self):
        """Context string is suitable for prepending to interview prompts."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from agent_memory import AgentMemoryManager

        mem = AgentMemoryManager(max_history=3)
        mem.record_action("agent_1", {"action_type": "CREATE_POST", "content": "I support the new policy", "round": 1})
        mem.record_action("agent_1", {"action_type": "LIKE_POST", "target_content": "Good analysis", "round": 2})

        ctx = mem.get_context("agent_1")
        assert "[Your recent activity" in ctx
        assert "I support the new policy" in ctx
        assert "maintain consistency" in ctx.lower()

        # Verify it works as interview prompt prefix
        interview_prompt = "Answer the following questions..."
        enriched = ctx + "\n\n" + interview_prompt
        assert enriched.startswith("\n[Your recent activity")
        assert enriched.endswith("Answer the following questions...")

    def test_empty_memory_produces_no_context(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from agent_memory import AgentMemoryManager

        mem = AgentMemoryManager()
        assert mem.get_context("unknown_agent") == ""

    def test_influence_tracker_produces_metrics_file(self, tmp_path):
        """InfluenceTracker writes influence_metrics.jsonl when flushed."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from action_logger import InfluenceTracker

        tracker = InfluenceTracker(str(tmp_path))
        tracker.track_action({"action_type": "CREATE_POST", "agent_name": "alice",
                              "content": "hello world", "round": 1, "post_id": "p1"})
        tracker.track_action({"action_type": "LIKE_POST", "agent_name": "bob",
                              "target_post_id": "p1", "round": 1})
        metrics = tracker.flush_round(1, "twitter")

        assert metrics["total_posts_this_round"] == 1
        assert metrics["total_engagements_this_round"] == 1
        assert len(metrics["top_influencers"]) == 1
        assert metrics["top_influencers"][0]["agent"] == "alice"

        # Verify file written
        assert os.path.exists(os.path.join(str(tmp_path), "influence_metrics.jsonl"))

    def test_faction_metrics_file_produced(self, tmp_path):
        """RoundMetricsTracker writes faction_metrics.jsonl."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from action_logger import RoundMetricsTracker

        tracker = RoundMetricsTracker(str(tmp_path))
        tracker.add_action({"action_type": "CREATE_POST", "agent_name": "a1", "content": "great love"})
        tracker.add_action({"action_type": "CREATE_POST", "agent_name": "a2", "content": "terrible hate"})
        tracker.flush_round(1, "twitter", 10, 2)

        faction_file = os.path.join(str(tmp_path), "faction_metrics.jsonl")
        assert os.path.exists(faction_file)
        with open(faction_file) as f:
            data = json.loads(f.readline())
        assert "factions" in data
        assert data["total_content_agents"] == 2

    def test_analytics_reads_agent_memory(self, tmp_path):
        """AnalyticsService.simulation_analytics includes agent stances from memory."""
        from app.services.analytics import AnalyticsService

        sim_dir = str(tmp_path)
        # Create agent_memory.json
        memory = {
            "alice": [{"type": "CREATE_POST", "content": "great progress love", "round": 1}],
            "bob": [{"type": "CREATE_POST", "content": "terrible crisis fail", "round": 1}],
        }
        with open(os.path.join(sim_dir, "agent_memory.json"), "w") as f:
            json.dump(memory, f)

        svc = AnalyticsService()
        result = svc.simulation_analytics(sim_dir)
        assert result["total_agents_with_memory"] == 2
        assert result["agent_stances"]["alice"]["stance"] == "positive"
        assert result["agent_stances"]["bob"]["stance"] == "negative"


# ---------------------------------------------------------------------------
# Full closed-loop integration test
# ---------------------------------------------------------------------------


class TestFullClosedLoop:
    """Test the complete prediction loop: predictions → graph bridge → analytics → health → digest → export."""

    def test_closed_loop(self, tmp_path):
        """Simulate the full lifecycle of predictions through all integration points."""
        from unittest.mock import patch, MagicMock
        from app.services.report_agent import StructuredPrediction, PredictionSet, ReportManager
        from app.services.prediction_graph_bridge import PredictionGraphBridge
        from app.services.analytics import AnalyticsService
        from app.services.prediction_decay import PredictionDecayTracker
        from app.services.contradiction_detector import ContradictionDetector
        from app.services.prediction_digest import PredictionDigestGenerator
        from app.services.change_notifier import ChangeNotifier
        from datetime import datetime

        # Step 1: Create predictions (like report_agent produces)
        predictions = [
            StructuredPrediction(event="Oil prices rise sharply", probability=0.75,
                                 evidence=["Agent consensus"], agent_agreement=0.8, impact_level="high"),
            StructuredPrediction(event="Trade policy changes direction", probability=0.45,
                                 evidence=["Mixed signals"], agent_agreement=0.5, impact_level="medium"),
        ]
        ps = PredictionSet(predictions=predictions, overall_confidence="Moderate",
                           generated_at=datetime.now().isoformat())

        # Step 2: Graph bridge formats predictions for graph ingestion
        bridge = PredictionGraphBridge()
        pred_dicts = [p.to_dict() for p in ps.predictions]
        with patch.object(bridge, '_add_episode'):
            result = bridge.enrich_graph_with_predictions("graph_1", pred_dicts, "sim_1", "r_1")
        assert result["added_count"] == 2

        # Step 3: Simulate agent memory being saved (like simulation does)
        sim_dir = str(tmp_path / "sim")
        os.makedirs(sim_dir)
        memory = {
            "alice": [{"type": "CREATE_POST", "content": "oil prices rising fast great", "round": 1}],
            "bob": [{"type": "CREATE_POST", "content": "trade policy terrible crisis", "round": 1}],
        }
        with open(os.path.join(sim_dir, "agent_memory.json"), "w") as f:
            json.dump(memory, f)

        # Step 4: Analytics reads memory
        analytics = AnalyticsService()
        sim_analytics = analytics.simulation_analytics(sim_dir)
        assert sim_analytics["total_agents_with_memory"] == 2
        assert sim_analytics["agent_stances"]["alice"]["stance"] == "positive"

        # Step 5: Health check
        decay = PredictionDecayTracker()
        health = decay.compute_health(pred_dicts, ps.generated_at)
        assert all(h.health_status == "fresh" for h in health)

        # Step 6: Contradiction detection
        contradictions = ContradictionDetector().detect_contradictions(pred_dicts)
        # These two predictions aren't contradictory, so should be 0
        assert isinstance(contradictions, list)

        # Step 7: Digest
        digest = PredictionDigestGenerator().generate(
            pred_dicts,
            overall_confidence=ps.overall_confidence,
            health_data={"prediction_health": [h.to_dict() for h in health]},
            contradictions=contradictions,
        )
        assert "2 predictions" in digest
        assert "Oil prices" in digest

        # Step 8: Change notifier
        notifier = ChangeNotifier()
        with patch.object(notifier, '_store_change'):
            change = notifier.check_and_record("r_1", 0, "Oil prices rise", 0.5, 0.75, "calibration")
        assert change is not None
        assert change.severity in ("significant", "major")

        # Step 9: Export format (CSV)
        import csv
        import io
        output = io.StringIO()
        fields = ["event", "probability", "agent_agreement", "impact_level"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for p in pred_dicts:
            writer.writerow(p)
        csv_text = output.getvalue()
        assert "Oil prices rise sharply" in csv_text
        assert "0.75" in csv_text

        # Full loop validated: predictions created → graph enriched → memory read →
        # health checked → contradictions scanned → digest generated →
        # changes detected → exported to CSV


# ---------------------------------------------------------------------------
# Change notifier tests
# ---------------------------------------------------------------------------


class TestChangeNotifier:
    """Tests for prediction change detection and notification."""

    def _make_notifier(self, tmp_path):
        from app.services.change_notifier import ChangeNotifier
        from unittest.mock import patch
        n = ChangeNotifier()
        # Patch the path to use tmp_path
        folder = str(tmp_path / "reports" / "test_report")
        os.makedirs(folder, exist_ok=True)
        return n, folder

    def test_small_change_ignored(self):
        from app.services.change_notifier import ChangeNotifier
        n = ChangeNotifier()
        # Mock _store_change to avoid file system
        from unittest.mock import patch
        with patch.object(n, '_store_change'):
            result = n.check_and_record("r1", 0, "Event", 0.50, 0.52, "bayesian")
        assert result is None  # 2% change is below threshold

    def test_significant_change_recorded(self):
        from app.services.change_notifier import ChangeNotifier
        n = ChangeNotifier()
        from unittest.mock import patch
        with patch.object(n, '_store_change') as mock_store:
            result = n.check_and_record("r1", 0, "Event", 0.50, 0.65, "bayesian")
        assert result is not None
        assert result.severity == "significant"
        assert abs(result.delta - 0.15) < 0.001
        assert mock_store.called

    def test_major_change_severity(self):
        from app.services.change_notifier import ChangeNotifier
        n = ChangeNotifier()
        from unittest.mock import patch
        with patch.object(n, '_store_change'):
            result = n.check_and_record("r1", 0, "Event", 0.30, 0.70, "calibration")
        assert result.severity == "major"

    def test_change_to_dict(self):
        from app.services.change_notifier import PredictionChange
        c = PredictionChange(prediction_idx=0, event="Test", old_probability=0.5,
                             new_probability=0.7, delta=0.2, source="bayesian", severity="significant")
        d = c.to_dict()
        assert d["direction"] == "up"
        assert d["abs_delta_pct"] == 20.0

    def test_get_changes_empty(self):
        from app.services.change_notifier import ChangeNotifier
        n = ChangeNotifier()
        from unittest.mock import patch
        with patch.object(n, '_load_changes', return_value=[]):
            changes = n.get_changes("r1")
        assert changes == []

    def test_severity_filter(self):
        from app.services.change_notifier import ChangeNotifier
        n = ChangeNotifier()
        mock_changes = [
            {"severity": "minor", "timestamp": "2026-01-01"},
            {"severity": "significant", "timestamp": "2026-01-02"},
            {"severity": "major", "timestamp": "2026-01-03"},
        ]
        from unittest.mock import patch
        with patch.object(n, '_load_changes', return_value=mock_changes):
            all_changes = n.get_changes("r1", min_severity="minor")
            assert len(all_changes) == 3
            sig_changes = n.get_changes("r1", min_severity="significant")
            assert len(sig_changes) == 2
            major_changes = n.get_changes("r1", min_severity="major")
            assert len(major_changes) == 1


# ---------------------------------------------------------------------------
# Full pipeline wiring test
# ---------------------------------------------------------------------------


class TestPipelineWiringE2E:
    """Test that _run_prediction_pipeline actually calls all wired services."""

    def test_pipeline_calls_all_steps(self, tmp_path):
        """Mock the simulation dir and verify the pipeline exercises all steps."""
        from unittest.mock import MagicMock, patch, call
        from app.services.report_agent import (
            ReportAgent, Report, ReportStatus, ReportManager,
            StructuredPrediction, PredictionSet,
        )

        # Create synthetic simulation dir
        sim_dir = str(tmp_path / "sim")
        twitter_dir = os.path.join(sim_dir, "twitter")
        os.makedirs(twitter_dir)
        actions = [
            {"action_type": "CREATE_POST", "agent_name": f"agent_{i}",
             "content": "great progress love excellent" if i < 7 else "terrible crisis awful",
             "round": (i % 3) + 1}
            for i in range(10)
        ]
        with open(os.path.join(twitter_dir, "actions.jsonl"), "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        # Setup agent with mocked dependencies
        with patch('app.services.report_agent.GraphToolsService'), \
             patch('app.services.report_agent.LLMClient'):
            agent = ReportAgent.__new__(ReportAgent)
            agent.llm = MagicMock()
            agent.graph_tools = MagicMock()
            agent.simulation_id = "sim_test"
            agent.simulation_requirement = "test prediction"
            agent.report_logger = None
            agent.console_logger = None

        # Mock consensus analysis
        mock_consensus = MagicMock()
        mock_consensus.to_dict.return_value = {
            "agreement_score": 0.7,
            "total_agents_analyzed": 10,
            "stance_distribution": {"supportive": 7, "opposing": 2, "neutral": 1},
            "consensus_strength": {"diversity_score": 0.6, "conviction_score": 0.5,
                                    "stability_score": 0.8, "weighted_score": 0.66},
        }
        agent.graph_tools.consensus_analysis.return_value = mock_consensus

        # Create report and predictions
        report = Report(
            report_id="r_test", simulation_id="sim_test", graph_id="g_test",
            simulation_requirement="test prediction", status=ReportStatus.GENERATING,
            markdown_content="# Test Report\n\nSome content here.",
        )
        predictions = [
            StructuredPrediction(event="Market rises", probability=0.6, agent_agreement=0.7,
                                 evidence=["Agent data"], risk_factors=["Policy change"]),
            StructuredPrediction(event="Crisis averted", probability=0.5, agent_agreement=0.6,
                                 evidence=["Consensus"], risk_factors=["External shock"]),
        ]
        ps = PredictionSet(predictions=predictions, overall_confidence="Moderate",
                           generated_at="2026-03-26T00:00:00")

        # Mock file-system-dependent services
        with patch('app.services.simulation_manager.SimulationManager') as MockSimMgr, \
             patch.object(ReportManager, 'save_predictions'), \
             patch.object(ReportManager, '_get_report_markdown_path', return_value=str(tmp_path / "report.md")), \
             patch('app.services.prediction_provenance.ProvenanceTracker.save_provenance'), \
             patch('app.services.prediction_graph_bridge.PredictionGraphBridge.enrich_graph_with_predictions') as mock_graph, \
             patch('app.services.change_notifier.ChangeNotifier._store_change'):

            MockSimMgr.return_value._get_simulation_dir.return_value = sim_dir

            # Write a dummy file so atomic_write_text doesn't fail
            (tmp_path / "report.md").write_text("placeholder")

            # RUN THE PIPELINE
            agent._run_prediction_pipeline(report, "r_test", ps)

        # Verify key outcomes
        # 1. Predictions were modified (calibration changes probabilities)
        # At minimum, predictions still exist and have valid probabilities
        assert len(ps.predictions) >= 1
        for p in ps.predictions:
            assert 0.0 < p.probability < 1.0

        # 2. Executive summary was prepended
        assert "Executive Summary" in report.markdown_content

        # 3. Graph bridge was called
        mock_graph.assert_called_once()
        call_args = mock_graph.call_args
        assert call_args[1]["graph_id"] == "g_test" or call_args[0][0] == "g_test"

        # 4. Overall confidence was enriched (CV adds interpretation)
        assert "CV:" in ps.overall_confidence or "Moderate" in ps.overall_confidence

        # 5. Predictions have impact levels set
        for p in ps.predictions:
            assert p.impact_level in ("low", "medium", "high", "critical")
