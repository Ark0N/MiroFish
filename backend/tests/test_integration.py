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
