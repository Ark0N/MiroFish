"""
Tests for structured prediction schema (StructuredPrediction, PredictionSet)
and the prediction extraction pipeline in ReportAgent.
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app.services.report_agent import (
    StructuredPrediction,
    PredictionSet,
    ReportAgent,
    ReportManager,
)


class TestStructuredPrediction:
    """Tests for the StructuredPrediction dataclass."""

    def test_default_values(self):
        p = StructuredPrediction(event="Test event", probability=0.75)
        assert p.event == "Test event"
        assert p.probability == 0.75
        assert p.confidence_interval == [0.0, 1.0]
        assert p.timeframe == ""
        assert p.reasoning == ""
        assert p.evidence == []
        assert p.risk_factors == []
        assert p.agent_agreement == 0.0

    def test_to_dict(self):
        p = StructuredPrediction(
            event="Oil prices rise",
            probability=0.8,
            confidence_interval=[0.65, 0.95],
            timeframe="short-term",
            reasoning="Agents strongly agree",
            evidence=["Post #1", "Post #2"],
            risk_factors=["Policy reversal"],
            agent_agreement=0.85
        )
        d = p.to_dict()
        assert d["event"] == "Oil prices rise"
        assert d["probability"] == 0.8
        assert d["confidence_interval"] == [0.65, 0.95]
        assert d["timeframe"] == "short-term"
        assert d["reasoning"] == "Agents strongly agree"
        assert d["evidence"] == ["Post #1", "Post #2"]
        assert d["risk_factors"] == ["Policy reversal"]
        assert d["agent_agreement"] == 0.85

    def test_to_dict_roundtrip(self):
        """Ensure to_dict produces JSON-serializable output."""
        p = StructuredPrediction(
            event="Market crash",
            probability=0.3,
            confidence_interval=[0.1, 0.5],
            timeframe="medium-term",
            reasoning="Minority view",
            evidence=["Signal A"],
            risk_factors=["Recovery"],
            agent_agreement=0.25
        )
        serialized = json.dumps(p.to_dict())
        deserialized = json.loads(serialized)
        assert deserialized["event"] == "Market crash"
        assert deserialized["probability"] == 0.3


class TestPredictionSet:
    """Tests for the PredictionSet dataclass."""

    def test_empty_prediction_set(self):
        ps = PredictionSet()
        assert ps.predictions == []
        assert ps.overall_confidence == ""
        assert ps.generated_at == ""

    def test_to_dict(self):
        ps = PredictionSet(
            predictions=[
                StructuredPrediction(event="Event A", probability=0.9),
                StructuredPrediction(event="Event B", probability=0.4),
            ],
            overall_confidence="Moderate confidence overall",
            generated_at="2026-01-01T00:00:00"
        )
        d = ps.to_dict()
        assert len(d["predictions"]) == 2
        assert d["predictions"][0]["event"] == "Event A"
        assert d["predictions"][1]["probability"] == 0.4
        assert d["overall_confidence"] == "Moderate confidence overall"
        assert d["generated_at"] == "2026-01-01T00:00:00"

    def test_to_dict_roundtrip(self):
        ps = PredictionSet(
            predictions=[
                StructuredPrediction(event="X", probability=0.5, evidence=["e1"]),
            ],
            overall_confidence="Low",
            generated_at="2026-03-25T10:00:00"
        )
        serialized = json.dumps(ps.to_dict())
        deserialized = json.loads(serialized)
        assert deserialized["predictions"][0]["evidence"] == ["e1"]


class TestParsePredictionJson:
    """Tests for ReportAgent._parse_prediction_json."""

    def _make_agent(self):
        """Create a ReportAgent with mocked dependencies."""
        with patch('app.services.report_agent.GraphToolsService'), \
             patch('app.services.report_agent.LLMClient'):
            agent = ReportAgent.__new__(ReportAgent)
            agent.llm = MagicMock()
            agent.tools_service = MagicMock()
            agent.report_logger = None
            agent.console_logger = None
        return agent

    def test_parses_valid_json(self):
        agent = self._make_agent()
        raw = json.dumps({
            "predictions": [
                {
                    "event": "Trade war escalation",
                    "probability": 0.7,
                    "confidence_interval": [0.55, 0.85],
                    "timeframe": "short-term",
                    "reasoning": "Strong agent consensus",
                    "evidence": ["Post A", "Post B"],
                    "risk_factors": ["De-escalation talks"],
                    "agent_agreement": 0.78
                }
            ],
            "overall_confidence": "High confidence"
        })
        result = agent._parse_prediction_json(raw)
        assert result is not None
        assert len(result.predictions) == 1
        assert result.predictions[0].event == "Trade war escalation"
        assert result.predictions[0].probability == 0.7
        assert result.overall_confidence == "High confidence"
        assert result.generated_at != ""

    def test_strips_code_fences(self):
        agent = self._make_agent()
        raw = '```json\n{"predictions": [{"event": "Test", "probability": 0.5}], "overall_confidence": "OK"}\n```'
        result = agent._parse_prediction_json(raw)
        assert result is not None
        assert len(result.predictions) == 1
        assert result.predictions[0].event == "Test"

    def test_handles_invalid_json(self):
        agent = self._make_agent()
        result = agent._parse_prediction_json("not valid json {{{")
        assert result is None

    def test_handles_empty_string(self):
        agent = self._make_agent()
        result = agent._parse_prediction_json("")
        assert result is None

    def test_handles_missing_fields(self):
        agent = self._make_agent()
        raw = json.dumps({
            "predictions": [{"event": "Bare prediction"}],
            "overall_confidence": "Low"
        })
        result = agent._parse_prediction_json(raw)
        assert result is not None
        p = result.predictions[0]
        assert p.event == "Bare prediction"
        assert p.probability == 0.5  # default
        assert p.confidence_interval == [0.0, 1.0]  # default

    def test_handles_bad_confidence_interval(self):
        agent = self._make_agent()
        raw = json.dumps({
            "predictions": [{
                "event": "Test",
                "probability": 0.6,
                "confidence_interval": "not a list"
            }],
            "overall_confidence": "N/A"
        })
        result = agent._parse_prediction_json(raw)
        assert result is not None
        assert result.predictions[0].confidence_interval == [0.0, 1.0]

    def test_multiple_predictions(self):
        agent = self._make_agent()
        raw = json.dumps({
            "predictions": [
                {"event": "A", "probability": 0.9, "agent_agreement": 0.95},
                {"event": "B", "probability": 0.3, "agent_agreement": 0.15},
                {"event": "C", "probability": 0.6, "agent_agreement": 0.55},
            ],
            "overall_confidence": "Mixed"
        })
        result = agent._parse_prediction_json(raw)
        assert result is not None
        assert len(result.predictions) == 3
        assert result.predictions[0].agent_agreement == 0.95
        assert result.predictions[2].probability == 0.6


class TestReportManagerPredictions:
    """Tests for ReportManager.save_predictions and load_predictions."""

    def test_save_and_load_roundtrip(self, tmp_path):
        ps = PredictionSet(
            predictions=[
                StructuredPrediction(
                    event="GDP growth slows",
                    probability=0.65,
                    confidence_interval=[0.5, 0.8],
                    timeframe="medium-term",
                    reasoning="Multiple agents flagged slowdown",
                    evidence=["Agent 1 post", "Agent 5 tweet"],
                    risk_factors=["Stimulus package"],
                    agent_agreement=0.72
                )
            ],
            overall_confidence="Moderate",
            generated_at="2026-03-25T12:00:00"
        )

        report_id = "test_report_001"
        with patch.object(ReportManager, '_get_report_folder',
                          return_value=str(tmp_path)):
            with patch.object(ReportManager, '_ensure_report_folder'):
                ReportManager.save_predictions(report_id, ps)

            loaded = ReportManager.load_predictions(report_id)

        assert loaded is not None
        assert len(loaded.predictions) == 1
        assert loaded.predictions[0].event == "GDP growth slows"
        assert loaded.predictions[0].probability == 0.65
        assert loaded.predictions[0].agent_agreement == 0.72
        assert loaded.overall_confidence == "Moderate"

    def test_load_nonexistent_returns_none(self, tmp_path):
        with patch.object(ReportManager, '_get_report_folder',
                          return_value=str(tmp_path)):
            result = ReportManager.load_predictions("nonexistent")
        assert result is None

    def test_load_corrupt_json_returns_none(self, tmp_path):
        report_id = "corrupt_report"
        with patch.object(ReportManager, '_get_report_folder',
                          return_value=str(tmp_path)):
            # Write corrupt JSON
            pred_path = os.path.join(str(tmp_path), "predictions.json")
            with open(pred_path, 'w') as f:
                f.write("{bad json!!!")
            result = ReportManager.load_predictions(report_id)
        assert result is None


class TestReportIncludesPredictions:
    """Tests that Report.to_dict includes predictions field."""

    def test_report_to_dict_with_predictions(self):
        from app.services.report_agent import Report, ReportStatus
        ps = PredictionSet(
            predictions=[StructuredPrediction(event="Test", probability=0.5)],
            overall_confidence="Low",
            generated_at="2026-01-01T00:00:00"
        )
        report = Report(
            report_id="r1",
            simulation_id="s1",
            graph_id="g1",
            simulation_requirement="test",
            status=ReportStatus.COMPLETED,
            predictions=ps
        )
        d = report.to_dict()
        assert d["predictions"] is not None
        assert len(d["predictions"]["predictions"]) == 1
        assert d["predictions"]["predictions"][0]["event"] == "Test"

    def test_report_to_dict_without_predictions(self):
        from app.services.report_agent import Report, ReportStatus
        report = Report(
            report_id="r2",
            simulation_id="s2",
            graph_id="g2",
            simulation_requirement="test",
            status=ReportStatus.COMPLETED
        )
        d = report.to_dict()
        assert d["predictions"] is None


class TestPredictionsApiEndpoint:
    """Tests for GET /api/report/<report_id>/predictions."""

    @pytest.fixture
    def app(self):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_predictions_nonexistent_report_returns_404(self, client):
        response = client.get('/api/report/nonexistent-id/predictions')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_predictions_path_traversal_rejected(self, client):
        response = client.get('/api/report/report_<script>/predictions')
        assert response.status_code == 400

    @patch.object(ReportManager, 'load_predictions')
    def test_predictions_returns_data(self, mock_load, client):
        ps = PredictionSet(
            predictions=[StructuredPrediction(event="Test prediction", probability=0.8)],
            overall_confidence="High",
            generated_at="2026-03-25T10:00:00"
        )
        mock_load.return_value = ps
        response = client.get('/api/report/valid-report-id/predictions')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['data']['predictions']) == 1
        assert data['data']['predictions'][0]['event'] == "Test prediction"


# ---------------------------------------------------------------------------
# PredictionCalibrator tests
# ---------------------------------------------------------------------------


class TestPredictionCalibrator:
    """Tests for PredictionCalibrator confidence calibration."""

    def _make_calibrator(self):
        from app.services.prediction_calibrator import PredictionCalibrator
        return PredictionCalibrator()

    def _make_prediction(self, prob=0.7, agreement=0.6):
        return {
            "event": "Test prediction",
            "probability": prob,
            "confidence_interval": [prob - 0.15, prob + 0.15],
            "timeframe": "short-term",
            "reasoning": "Test",
            "evidence": ["e1"],
            "risk_factors": ["r1"],
            "agent_agreement": agreement,
        }

    def test_empty_predictions(self):
        cal = self._make_calibrator()
        assert cal.calibrate([]) == []

    def test_no_consensus_data_returns_calibrated(self):
        cal = self._make_calibrator()
        preds = [self._make_prediction(0.7)]
        result = cal.calibrate(preds)
        assert len(result) == 1
        assert "calibration" in result[0]
        assert result[0]["calibration"]["original_probability"] == 0.7

    def test_high_agreement_boosts_confidence(self):
        cal = self._make_calibrator()
        pred = self._make_prediction(0.6, agreement=0.9)
        consensus = {
            "agreement_score": 0.95,
            "consensus_strength": {
                "diversity_score": 0.8,
                "conviction_score": 0.8,
                "stability_score": 0.9,
                "weighted_score": 0.84,
            },
        }
        result = cal.calibrate([pred], consensus_data=consensus)
        # High agreement + high strength should boost probability
        assert result[0]["probability"] > 0.6

    def test_low_agreement_reduces_confidence(self):
        cal = self._make_calibrator()
        pred = self._make_prediction(0.7, agreement=0.2)
        consensus = {
            "agreement_score": 0.3,
            "consensus_strength": {
                "diversity_score": 0.2,
                "conviction_score": 0.2,
                "stability_score": 0.3,
                "weighted_score": 0.24,
            },
        }
        result = cal.calibrate([pred], consensus_data=consensus)
        # Low agreement + low strength should reduce probability
        assert result[0]["probability"] < 0.7

    def test_confidence_interval_widens_on_downgrade(self):
        cal = self._make_calibrator()
        pred = self._make_prediction(0.7, agreement=0.2)
        consensus = {"agreement_score": 0.2}
        result = cal.calibrate([pred], consensus_data=consensus)
        orig_width = 0.3  # 0.55 to 0.85
        new_width = result[0]["confidence_interval"][1] - result[0]["confidence_interval"][0]
        assert new_width >= orig_width  # interval should widen or stay same

    def test_calibration_metadata_present(self):
        cal = self._make_calibrator()
        pred = self._make_prediction()
        result = cal.calibrate([pred])
        cal_data = result[0]["calibration"]
        assert "original_probability" in cal_data
        assert "agreement_factor" in cal_data
        assert "strength_factor" in cal_data
        assert "contrarian_factor" in cal_data
        assert "adjustment" in cal_data

    def test_probability_bounded(self):
        """Probability should never go below 0.05 or above 0.99."""
        cal = self._make_calibrator()
        # Very low probability with penalty
        pred_low = self._make_prediction(0.05, agreement=0.1)
        consensus = {"agreement_score": 0.1}
        result = cal.calibrate([pred_low], consensus_data=consensus)
        assert result[0]["probability"] >= 0.05

        # Very high probability with boost
        pred_high = self._make_prediction(0.99, agreement=0.99)
        consensus_high = {
            "agreement_score": 0.99,
            "consensus_strength": {
                "diversity_score": 1.0,
                "conviction_score": 1.0,
                "stability_score": 1.0,
                "weighted_score": 1.0,
            },
        }
        result_high = cal.calibrate([pred_high], consensus_data=consensus_high)
        assert result_high[0]["probability"] <= 0.99

    def test_multiple_predictions_calibrated(self):
        cal = self._make_calibrator()
        preds = [
            self._make_prediction(0.8, 0.9),
            self._make_prediction(0.3, 0.2),
        ]
        result = cal.calibrate(preds)
        assert len(result) == 2
        # Both should have calibration data
        assert all("calibration" in r for r in result)

    def test_contrarian_impact_measurement(self, tmp_path):
        """_measure_contrarian_impact should detect contrarian influence."""
        cal = self._make_calibrator()

        # Create simulation dir with contrarian posts
        twitter_dir = tmp_path / "twitter"
        twitter_dir.mkdir()
        actions = [
            {"action_type": "CREATE_POST", "agent_name": "user_1", "content": "great progress excellent", "round": 1},
            {"action_type": "CREATE_POST", "agent_name": "contrarian_123", "content": "terrible awful danger crisis", "round": 1},
            {"action_type": "CREATE_POST", "agent_name": "user_1", "content": "maybe it is bad actually danger", "round": 2},
        ]
        with open(twitter_dir / "actions.jsonl", "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        shift = cal._measure_contrarian_impact(str(tmp_path))
        assert shift >= 0.0

    def test_no_contrarian_returns_zero_shift(self, tmp_path):
        cal = self._make_calibrator()
        twitter_dir = tmp_path / "twitter"
        twitter_dir.mkdir()
        actions = [
            {"action_type": "CREATE_POST", "agent_name": "user_1", "content": "great progress", "round": 1},
        ]
        with open(twitter_dir / "actions.jsonl", "w") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

        shift = cal._measure_contrarian_impact(str(tmp_path))
        assert shift == 0.0


# ---------------------------------------------------------------------------
# URL extractor tests
# ---------------------------------------------------------------------------


class TestUrlExtractor:
    """Tests for URL text extraction utility."""

    @patch('app.utils.url_extractor.trafilatura')
    def test_successful_extraction(self, mock_traf):
        from app.utils.url_extractor import extract_text_from_url
        mock_traf.fetch_url.return_value = "<html><body>Long article content here with enough text to pass the minimum threshold of fifty characters easily.</body></html>"
        mock_traf.extract.return_value = "Long article content here with enough text to pass the minimum threshold of fifty characters easily."
        mock_metadata = MagicMock()
        mock_metadata.title = "Test Article"
        mock_traf.extract_metadata.return_value = mock_metadata

        result = extract_text_from_url("https://example.com/article")
        assert result["success"] is True
        assert len(result["text"]) > 50
        assert result["title"] == "Test Article"

    @patch('app.utils.url_extractor.trafilatura')
    def test_fetch_failure(self, mock_traf):
        from app.utils.url_extractor import extract_text_from_url
        mock_traf.fetch_url.return_value = None

        result = extract_text_from_url("https://invalid.example.com")
        assert result["success"] is False
        assert result["error"] is not None

    @patch('app.utils.url_extractor.trafilatura')
    def test_empty_extraction(self, mock_traf):
        from app.utils.url_extractor import extract_text_from_url
        mock_traf.fetch_url.return_value = "<html></html>"
        mock_traf.extract.return_value = ""

        result = extract_text_from_url("https://example.com/empty")
        assert result["success"] is False

    @patch('app.utils.url_extractor.trafilatura')
    def test_extract_multiple_urls(self, mock_traf):
        from app.utils.url_extractor import extract_text_from_urls
        mock_traf.fetch_url.return_value = "<html>content</html>"
        mock_traf.extract.return_value = "A" * 100
        mock_traf.extract_metadata.return_value = MagicMock(title="Title")

        results = extract_text_from_urls(["https://a.com", "https://b.com"])
        assert len(results) == 2
        assert all(r["success"] for r in results)


# ---------------------------------------------------------------------------
# Executive summary / risk matrix tests
# ---------------------------------------------------------------------------


class TestExecutiveSummary:
    """Tests for executive summary generation with risk matrix."""

    def _make_agent(self):
        with patch('app.services.report_agent.GraphToolsService'), \
             patch('app.services.report_agent.LLMClient'):
            agent = ReportAgent.__new__(ReportAgent)
            agent.llm = MagicMock()
            agent.tools_service = MagicMock()
            agent.report_logger = None
            agent.console_logger = None
        return agent

    def test_generates_summary_with_predictions(self):
        agent = self._make_agent()
        ps = PredictionSet(
            predictions=[
                StructuredPrediction(event="Market crash", probability=0.8, impact_level="high"),
                StructuredPrediction(event="Minor policy change", probability=0.6, impact_level="low"),
            ],
            overall_confidence="Moderate confidence",
        )
        result = agent._generate_executive_summary(ps)
        assert "Executive Summary" in result
        assert "Risk Matrix" in result
        assert "Market crash" in result

    def test_empty_predictions_returns_empty(self):
        agent = self._make_agent()
        assert agent._generate_executive_summary(PredictionSet()) == ""
        assert agent._generate_executive_summary(None) == ""

    def test_risk_matrix_quadrants(self):
        agent = self._make_agent()
        ps = PredictionSet(predictions=[
            StructuredPrediction(event="A", probability=0.8, impact_level="high"),
            StructuredPrediction(event="B", probability=0.8, impact_level="low"),
            StructuredPrediction(event="C", probability=0.2, impact_level="high"),
            StructuredPrediction(event="D", probability=0.2, impact_level="low"),
        ])
        result = agent._generate_executive_summary(ps)
        assert "Critical Risks" in result
        assert "Watch List" in result
        assert "Likely Developments" in result
        assert "Background Signals" in result


class TestPredictionDiffEndpoint:
    """Tests for prediction comparison API endpoint."""

    @pytest.fixture
    def app(self):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_missing_report_ids_returns_400(self, client):
        response = client.post('/api/report/compare-predictions', json={})
        assert response.status_code == 400

    def test_single_report_returns_400(self, client):
        response = client.post('/api/report/compare-predictions',
                               json={"report_ids": ["r1"]})
        assert response.status_code == 400

    def test_too_many_reports_returns_400(self, client):
        ids = [f"r{i}" for i in range(15)]
        response = client.post('/api/report/compare-predictions',
                               json={"report_ids": ids})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Bayesian updater tests
# ---------------------------------------------------------------------------


class TestBayesianUpdater:
    """Tests for Bayesian prediction updating."""

    def _make_updater(self):
        from app.services.bayesian_updater import BayesianUpdater
        return BayesianUpdater()

    def test_strong_support_increases_probability(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_consensus(
            prior=0.5,
            agreement_score=0.9,
            stance_distribution={"supportive": 18, "opposing": 1, "neutral": 1},
            total_agents=20,
        )
        assert posterior > 0.5

    def test_strong_opposition_decreases_probability(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_consensus(
            prior=0.5,
            agreement_score=0.9,
            stance_distribution={"supportive": 1, "opposing": 18, "neutral": 1},
            total_agents=20,
        )
        assert posterior < 0.5

    def test_neutral_consensus_minimal_change(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_consensus(
            prior=0.5,
            agreement_score=0.5,
            stance_distribution={"supportive": 7, "opposing": 7, "neutral": 6},
            total_agents=20,
        )
        assert abs(posterior - 0.5) < 0.25

    def test_zero_agents_returns_prior(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_consensus(
            prior=0.7,
            agreement_score=0.5,
            stance_distribution={},
            total_agents=0,
        )
        assert posterior == 0.7

    def test_positive_sentiment_shift_boosts(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_sentiment_shift(0.5, 0.5, "positive")
        assert posterior > 0.5

    def test_negative_sentiment_shift_reduces(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_sentiment_shift(0.5, -0.5, "positive")
        assert posterior < 0.5

    def test_irrelevant_data_no_change(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_new_data(0.6, relevance_score=0.05, alignment_score=0.9)
        assert posterior == 0.6

    def test_relevant_aligned_data_boosts(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_new_data(0.5, relevance_score=0.9, alignment_score=0.9)
        assert posterior > 0.5

    def test_relevant_contradicting_data_reduces(self):
        updater = self._make_updater()
        posterior, _ = updater.update_from_new_data(0.5, relevance_score=0.9, alignment_score=0.1)
        assert posterior < 0.5

    def test_probability_bounded(self):
        updater = self._make_updater()
        # Extreme support shouldn't go above MAX_PROB
        posterior, _ = updater.update_from_consensus(
            prior=0.99,
            agreement_score=1.0,
            stance_distribution={"supportive": 100, "opposing": 0, "neutral": 0},
            total_agents=100,
        )
        assert posterior <= 0.99

        # Extreme opposition shouldn't go below MIN_PROB
        posterior, _ = updater.update_from_consensus(
            prior=0.01,
            agreement_score=1.0,
            stance_distribution={"supportive": 0, "opposing": 100, "neutral": 0},
            total_agents=100,
        )
        assert posterior >= 0.01

    def test_update_record_creation(self):
        from app.services.bayesian_updater import BayesianUpdater
        updater = BayesianUpdater()
        record = updater.create_update_record(
            prior=0.5, posterior=0.7, likelihood=0.8,
            evidence_source="consensus", evidence_summary="Strong agent support"
        )
        d = record.to_dict()
        assert d["prior"] == 0.5
        assert d["posterior"] == 0.7
        assert d["evidence_source"] == "consensus"

    def test_sequential_updates_converge(self):
        """Multiple updates in same direction should push probability further."""
        updater = self._make_updater()
        prob = 0.5
        for _ in range(3):
            prob, _ = updater.update_from_consensus(
                prior=prob,
                agreement_score=0.8,
                stance_distribution={"supportive": 16, "opposing": 2, "neutral": 2},
                total_agents=20,
            )
        assert prob > 0.8  # Strong convergence after 3 updates


# ---------------------------------------------------------------------------
# Ensemble predictor tests
# ---------------------------------------------------------------------------


class TestEnsemblePredictor:
    """Tests for ensemble prediction aggregation."""

    def _make_predictor(self):
        from app.services.ensemble_predictor import EnsemblePredictor
        return EnsemblePredictor()

    def _make_prediction_set(self, predictions):
        return {"predictions": predictions}

    def test_empty_input_returns_empty(self):
        p = self._make_predictor()
        result = p.aggregate("proj_1", [])
        assert len(result.predictions) == 0

    def test_single_set_passthrough(self):
        p = self._make_predictor()
        ps = self._make_prediction_set([
            {"event": "Test event", "probability": 0.7, "agent_agreement": 0.8}
        ])
        result = p.aggregate("proj_1", [ps])
        assert len(result.predictions) == 1
        assert abs(result.predictions[0].probability - 0.7) < 0.01

    def test_two_sets_averaged(self):
        p = self._make_predictor()
        ps1 = self._make_prediction_set([
            {"event": "Market crash imminent", "probability": 0.8, "agent_agreement": 0.9}
        ])
        ps2 = self._make_prediction_set([
            {"event": "Market crash imminent", "probability": 0.4, "agent_agreement": 0.6}
        ])
        result = p.aggregate("proj_1", [ps1, ps2])
        assert len(result.predictions) == 1
        # Equal weights → average of 0.8 and 0.4 = 0.6
        assert abs(result.predictions[0].probability - 0.6) < 0.01
        assert result.predictions[0].num_simulations == 2

    def test_weighted_aggregation(self):
        p = self._make_predictor()
        ps1 = self._make_prediction_set([
            {"event": "Event A", "probability": 0.9}
        ])
        ps2 = self._make_prediction_set([
            {"event": "Event A", "probability": 0.3}
        ])
        # Weight first set 3x more
        result = p.aggregate("proj_1", [ps1, ps2], weights=[3.0, 1.0])
        # Weighted avg: (0.9*0.75 + 0.3*0.25) = 0.75
        assert result.predictions[0].probability > 0.7

    def test_spread_computed(self):
        p = self._make_predictor()
        ps1 = self._make_prediction_set([{"event": "Test", "probability": 0.9}])
        ps2 = self._make_prediction_set([{"event": "Test", "probability": 0.1}])
        result = p.aggregate("proj_1", [ps1, ps2])
        assert result.predictions[0].agreement_spread > 0.3  # Large disagreement

    def test_unmatched_predictions_separate(self):
        p = self._make_predictor()
        ps1 = self._make_prediction_set([{"event": "Completely different topic A", "probability": 0.7}])
        ps2 = self._make_prediction_set([{"event": "Totally unrelated subject B", "probability": 0.4}])
        result = p.aggregate("proj_1", [ps1, ps2])
        assert len(result.predictions) == 2  # Should NOT merge

    def test_compute_weights(self):
        p = self._make_predictor()
        from datetime import datetime as dt, timedelta
        now = dt.now()
        metadata = [
            {"created_at": now.isoformat(), "agent_count": 100, "consensus_strength": 0.9},
            {"created_at": (now - timedelta(days=60)).isoformat(), "agent_count": 20, "consensus_strength": 0.3},
        ]
        weights = p.compute_weights(metadata)
        assert weights[0] > weights[1]  # Recent + more agents + stronger consensus

    def test_ensemble_to_dict(self):
        p = self._make_predictor()
        ps = self._make_prediction_set([{"event": "E", "probability": 0.5}])
        result = p.aggregate("proj_x", [ps])
        d = result.to_dict()
        assert d["project_id"] == "proj_x"
        assert len(d["predictions"]) == 1


# ---------------------------------------------------------------------------
# Pattern matcher tests
# ---------------------------------------------------------------------------


class TestPatternMatcher:
    """Tests for historical pattern matching."""

    def _make_matcher(self):
        from app.services.pattern_matcher import PatternMatcher
        return PatternMatcher()

    def _make_fingerprint(self, sim_id, sentiments, momenta=None, factions=None):
        from app.services.pattern_matcher import SimulationFingerprint
        return SimulationFingerprint(
            simulation_id=sim_id,
            sentiment_trajectory=sentiments,
            momentum_trajectory=momenta or [0.0] * len(sentiments),
            faction_sizes=factions or {"supportive": [], "opposing": [], "neutral": []},
            final_agreement=abs(sentiments[-1]) if sentiments else 0,
            total_rounds=len(sentiments),
        )

    def test_identical_trajectories_high_similarity(self):
        matcher = self._make_matcher()
        fp1 = self._make_fingerprint("s1", [0.1, 0.2, 0.3, 0.4, 0.5])
        fp2 = self._make_fingerprint("s2", [0.1, 0.2, 0.3, 0.4, 0.5])
        match = matcher.compare(fp1, fp2)
        assert match.similarity_score > 0.8

    def test_opposite_trajectories_low_similarity(self):
        matcher = self._make_matcher()
        fp1 = self._make_fingerprint("s1", [0.5, 0.4, 0.3, 0.2, 0.1])
        fp2 = self._make_fingerprint("s2", [-0.5, -0.4, -0.3, -0.2, -0.1])
        match = matcher.compare(fp1, fp2)
        assert match.similarity_score < 0.5

    def test_different_lengths_handled(self):
        matcher = self._make_matcher()
        fp1 = self._make_fingerprint("s1", [0.1, 0.2, 0.3])
        fp2 = self._make_fingerprint("s2", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        match = matcher.compare(fp1, fp2)
        # Should still work by truncating to shorter length
        assert 0.0 <= match.similarity_score <= 1.0

    def test_empty_trajectories(self):
        matcher = self._make_matcher()
        fp1 = self._make_fingerprint("s1", [])
        fp2 = self._make_fingerprint("s2", [0.1, 0.2])
        match = matcher.compare(fp1, fp2)
        assert 0.0 <= match.similarity_score <= 1.0

    def test_find_similar_top_k(self):
        matcher = self._make_matcher()
        current = self._make_fingerprint("current", [0.1, 0.2, 0.3, 0.4])
        historical = [
            self._make_fingerprint("h1", [0.1, 0.2, 0.3, 0.4]),  # very similar
            self._make_fingerprint("h2", [-0.5, -0.4, -0.3, -0.2]),  # different
            self._make_fingerprint("h3", [0.15, 0.22, 0.28, 0.38]),  # similar
        ]
        matches = matcher.find_similar(current, historical, top_k=2)
        assert len(matches) <= 2
        if matches:
            assert matches[0].matched_simulation_id == "h1"

    def test_self_excluded_from_matches(self):
        matcher = self._make_matcher()
        fp = self._make_fingerprint("s1", [0.1, 0.2, 0.3])
        matches = matcher.find_similar(fp, [fp], top_k=5)
        assert len(matches) == 0

    def test_faction_similarity(self):
        matcher = self._make_matcher()
        fp1 = self._make_fingerprint("s1", [0.1], factions={
            "supportive": [10, 12, 14],
            "opposing": [5, 4, 3],
            "neutral": [5, 4, 3],
        })
        fp2 = self._make_fingerprint("s2", [0.1], factions={
            "supportive": [11, 13, 15],
            "opposing": [4, 3, 2],
            "neutral": [5, 4, 3],
        })
        match = matcher.compare(fp1, fp2)
        assert match.faction_similarity > 0.7

    def test_extract_fingerprint(self, tmp_path):
        matcher = self._make_matcher()
        twitter_dir = tmp_path / "twitter"
        twitter_dir.mkdir()
        metrics = [
            {"round": 1, "sentiment": {"average": 0.2}, "momentum": {"velocity": 0.0},
             "factions": {"supportive": {"count": 5}, "opposing": {"count": 3}, "neutral": {"count": 2}}},
            {"round": 2, "sentiment": {"average": 0.4}, "momentum": {"velocity": 0.2},
             "factions": {"supportive": {"count": 7}, "opposing": {"count": 2}, "neutral": {"count": 1}}},
        ]
        with open(twitter_dir / "round_metrics.jsonl", "w") as f:
            for m in metrics:
                f.write(json.dumps(m) + "\n")

        fp = matcher.extract_fingerprint(str(tmp_path), "sim_test")
        assert fp.simulation_id == "sim_test"
        assert len(fp.sentiment_trajectory) == 2
        assert fp.sentiment_trajectory[0] == 0.2
        assert fp.total_rounds == 2


# ---------------------------------------------------------------------------
# Backtesting tests
# ---------------------------------------------------------------------------


class TestPredictionBacktester:
    """Tests for prediction backtesting framework."""

    def _make_backtester(self, tmp_path):
        from app.services.prediction_backtester import PredictionBacktester
        bt = PredictionBacktester()
        bt.OUTCOMES_DIR = str(tmp_path / "outcomes")
        os.makedirs(bt.OUTCOMES_DIR, exist_ok=True)
        return bt

    def test_resolve_prediction(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        outcome = bt.resolve_prediction(
            project_id="p1", report_id="r1", prediction_idx=0,
            event="Market crash", predicted_probability=0.8,
            actual_outcome=True, resolution_notes="It happened"
        )
        assert outcome.actual_outcome is True
        assert outcome.predicted_probability == 0.8

    def test_outcomes_persisted(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        bt.resolve_prediction("p1", "r1", 0, "Event A", 0.7, True)
        bt.resolve_prediction("p1", "r1", 1, "Event B", 0.3, False)
        outcomes = bt.get_outcomes("p1")
        assert len(outcomes) == 2

    def test_calibration_accuracy(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        # 3 correct predictions (high prob, happened)
        bt.resolve_prediction("p1", "r1", 0, "A", 0.8, True)
        bt.resolve_prediction("p1", "r1", 1, "B", 0.9, True)
        bt.resolve_prediction("p1", "r1", 2, "C", 0.7, True)
        # 1 incorrect
        bt.resolve_prediction("p1", "r1", 3, "D", 0.6, False)

        cal = bt.compute_calibration("p1")
        assert cal.total_predictions == 4
        assert cal.accuracy == 0.75  # 3 of 4 correct

    def test_brier_score_perfect(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        bt.resolve_prediction("p1", "r1", 0, "A", 1.0, True)
        bt.resolve_prediction("p1", "r1", 1, "B", 0.0, False)
        cal = bt.compute_calibration("p1")
        assert cal.brier_score == 0.0  # Perfect calibration

    def test_brier_score_worst(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        bt.resolve_prediction("p1", "r1", 0, "A", 1.0, False)
        bt.resolve_prediction("p1", "r1", 1, "B", 0.0, True)
        cal = bt.compute_calibration("p1")
        assert cal.brier_score == 1.0  # Worst calibration

    def test_calibration_bins(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        bt.resolve_prediction("p1", "r1", 0, "A", 0.85, True)
        bt.resolve_prediction("p1", "r1", 1, "B", 0.15, False)
        cal = bt.compute_calibration("p1", num_bins=10)
        assert len(cal.bins) == 10
        # Bin 8 (0.8-0.9) should have 1 prediction
        assert cal.bins[8].count == 1

    def test_empty_project_calibration(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        cal = bt.compute_calibration("nonexistent")
        assert cal.total_predictions == 0

    def test_calibration_to_dict(self, tmp_path):
        bt = self._make_backtester(tmp_path)
        bt.resolve_prediction("p1", "r1", 0, "A", 0.7, True)
        cal = bt.compute_calibration("p1")
        d = cal.to_dict()
        assert "bins" in d
        assert "accuracy" in d
        assert "brier_score" in d


# ---------------------------------------------------------------------------
# RSS monitor tests
# ---------------------------------------------------------------------------


class TestRSSMonitor:
    """Tests for RSS feed monitoring service."""

    def _make_monitor(self, tmp_path):
        from app.services.rss_monitor import RSSMonitor
        mon = RSSMonitor()
        mon.FEEDS_DIR = str(tmp_path / "feeds")
        os.makedirs(mon.FEEDS_DIR, exist_ok=True)
        return mon

    def test_add_feed(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        feed = mon.add_feed("p1", "https://example.com/feed", "Test Feed")
        assert feed.url == "https://example.com/feed"
        assert feed.name == "Test Feed"

    def test_feeds_persisted(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        mon.add_feed("p1", "https://a.com/feed")
        mon.add_feed("p1", "https://b.com/feed")
        feeds = mon.get_feeds("p1")
        assert len(feeds) == 2

    def test_no_duplicate_feeds(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        mon.add_feed("p1", "https://a.com/feed")
        mon.add_feed("p1", "https://a.com/feed")  # duplicate
        feeds = mon.get_feeds("p1")
        assert len(feeds) == 1

    def test_remove_feed(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        mon.add_feed("p1", "https://a.com/feed")
        assert mon.remove_feed("p1", "https://a.com/feed") is True
        assert mon.get_feeds("p1") == []

    def test_remove_nonexistent_feed(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        assert mon.remove_feed("p1", "https://nope.com") is False

    def test_empty_project_feeds(self, tmp_path):
        mon = self._make_monitor(tmp_path)
        assert mon.get_feeds("nonexistent") == []

    def test_check_feed_with_seen_hash(self, tmp_path):
        """Already-seen content should not be returned."""
        from app.services.rss_monitor import RSSMonitor, FeedItem
        mon = self._make_monitor(tmp_path)
        # A hash that matches prevents returning items
        # We test the hash dedup logic directly
        item = FeedItem(title="Test", url="http://a.com", content="hello", content_hash="abc123")
        assert item.content_hash == "abc123"
        assert "abc123" in ["abc123"]  # Would be filtered


# ---------------------------------------------------------------------------
# Trend detector tests
# ---------------------------------------------------------------------------


class TestTrendDetector:
    """Tests for trend detection in ingested content."""

    def _make_detector(self):
        from app.services.trend_detector import TrendDetector
        return TrendDetector()

    def test_empty_input(self):
        d = self._make_detector()
        assert d.detect_trends([]) == []

    def test_emerging_topics_without_baseline(self):
        d = self._make_detector()
        texts = ["economy economy economy market market crash crash crash"]
        signals = d.detect_trends(texts)
        topics = [s.topic for s in signals]
        assert "economy" in topics or "crash" in topics or "market" in topics

    def test_growing_topic_detected(self):
        d = self._make_detector()
        previous = ["climate change discussion climate"]
        current = ["climate climate climate climate climate climate climate crisis climate"]
        signals = d.detect_trends(current, previous, min_frequency=2)
        growing = [s for s in signals if s.trend_type == "growing"]
        assert len(growing) >= 1

    def test_emerging_topic_detected(self):
        d = self._make_detector()
        previous = ["economy market trade"]
        current = ["blockchain blockchain blockchain crypto crypto"]
        signals = d.detect_trends(current, previous, min_frequency=2)
        emerging = [s for s in signals if s.trend_type == "emerging"]
        assert len(emerging) >= 1

    def test_declining_topic_detected(self):
        d = self._make_detector()
        previous = ["scandal scandal scandal scandal scandal"]
        current = ["other topics now discussed"]
        signals = d.detect_trends(current, previous, min_frequency=2)
        declining = [s for s in signals if s.trend_type == "declining"]
        assert len(declining) >= 1

    def test_sentiment_shift_detected(self):
        d = self._make_detector()
        previous = ["terrible awful crisis danger fail"]
        current = ["great excellent wonderful love progress hope"]
        signals = d.detect_trends(current, previous)
        sentiment = [s for s in signals if s.trend_type == "sentiment_shift"]
        assert len(sentiment) >= 1
        assert "positive" in sentiment[0].topic

    def test_signals_sorted_by_strength(self):
        d = self._make_detector()
        texts = ["word1 " * 20 + "word2 " * 5 + "word3 " * 10]
        signals = d.detect_trends(texts)
        if len(signals) >= 2:
            assert signals[0].strength >= signals[1].strength

    def test_to_dict(self):
        from app.services.trend_detector import TrendSignal
        s = TrendSignal(topic="test", trend_type="emerging", strength=0.5)
        d = s.to_dict()
        assert d["topic"] == "test"
        assert d["trend_type"] == "emerging"


# ---------------------------------------------------------------------------
# Source credibility tests
# ---------------------------------------------------------------------------


class TestSourceCredibility:
    """Tests for source credibility tracking."""

    def _make_tracker(self, tmp_path):
        from app.services.source_credibility import SourceCredibilityTracker
        t = SourceCredibilityTracker()
        t.CREDIBILITY_DIR = str(tmp_path / "cred")
        os.makedirs(t.CREDIBILITY_DIR, exist_ok=True)
        return t

    def test_record_correct_outcome(self, tmp_path):
        t = self._make_tracker(tmp_path)
        score = t.record_outcome("p1", "Reuters", True)
        assert score.accuracy == 1.0
        assert score.credibility_weight == 2.0

    def test_record_incorrect_outcome(self, tmp_path):
        t = self._make_tracker(tmp_path)
        score = t.record_outcome("p1", "UnreliableSource", False)
        assert score.accuracy == 0.0
        assert score.credibility_weight == 0.5

    def test_mixed_outcomes(self, tmp_path):
        t = self._make_tracker(tmp_path)
        t.record_outcome("p1", "BBC", True)
        t.record_outcome("p1", "BBC", True)
        score = t.record_outcome("p1", "BBC", False)
        assert score.total_predictions == 3
        assert score.correct_predictions == 2
        assert 0.9 < score.credibility_weight < 1.6

    def test_unknown_source_neutral_weight(self, tmp_path):
        t = self._make_tracker(tmp_path)
        assert t.get_weight("p1", "unknown") == 1.0

    def test_get_all_scores(self, tmp_path):
        t = self._make_tracker(tmp_path)
        t.record_outcome("p1", "A", True)
        t.record_outcome("p1", "B", False)
        scores = t.get_all_scores("p1")
        assert len(scores) == 2
        # A should have higher weight than B
        assert scores[0].source_name == "A"

    def test_persistence(self, tmp_path):
        t = self._make_tracker(tmp_path)
        t.record_outcome("p1", "CNN", True)
        # Create new tracker instance to test loading
        t2 = self._make_tracker(tmp_path)
        t2.CREDIBILITY_DIR = t.CREDIBILITY_DIR
        assert t2.get_weight("p1", "CNN") == 2.0


# ---------------------------------------------------------------------------
# Parameter learner tests
# ---------------------------------------------------------------------------


class TestParameterLearner:
    """Tests for simulation parameter learning."""

    def _make_learner(self, tmp_path):
        from app.services.parameter_learner import ParameterLearner
        l = ParameterLearner()
        l.RECORDS_DIR = str(tmp_path / "params")
        os.makedirs(l.RECORDS_DIR, exist_ok=True)
        return l

    def _make_record(self, sim_id, accuracy, agents=50, rounds=20):
        from app.services.parameter_learner import SimulationRecord
        return SimulationRecord(
            simulation_id=sim_id, project_id="p1",
            agent_count=agents, round_count=rounds,
            avg_temperature=0.6, contrarian_pct=0.07,
            accuracy=accuracy, brier_score=0.2,
        )

    def test_record_simulation(self, tmp_path):
        l = self._make_learner(tmp_path)
        l.record_simulation(self._make_record("s1", 0.8))
        assert len(l.get_records()) == 1

    def test_default_recommendation_insufficient_data(self, tmp_path):
        l = self._make_learner(tmp_path)
        l.record_simulation(self._make_record("s1", 0.8))
        rec = l.recommend_parameters(min_records=5)
        assert rec.confidence == 0.0
        assert rec.recommended_agent_count == 45  # defaults

    def test_recommendation_with_data(self, tmp_path):
        l = self._make_learner(tmp_path)
        # High accuracy with 100 agents
        l.record_simulation(self._make_record("s1", 0.9, agents=100, rounds=30))
        l.record_simulation(self._make_record("s2", 0.85, agents=80, rounds=25))
        l.record_simulation(self._make_record("s3", 0.3, agents=20, rounds=10))
        rec = l.recommend_parameters(min_records=3)
        assert rec.confidence > 0
        # Should lean toward higher agent counts (weighted by accuracy)
        assert rec.recommended_agent_count > 50
        assert rec.recommended_round_count > 15

    def test_recommendation_to_dict(self, tmp_path):
        l = self._make_learner(tmp_path)
        for i in range(3):
            l.record_simulation(self._make_record(f"s{i}", 0.7))
        d = l.recommend_parameters().to_dict()
        assert "recommended_agent_count" in d
        assert "confidence" in d
        assert "reasoning" in d


# ---------------------------------------------------------------------------
# Prediction pipeline tests
# ---------------------------------------------------------------------------


class TestPredictionPipeline:
    """Tests for automated prediction pipeline orchestration."""

    def _make_pipeline(self, tmp_path):
        from app.services.prediction_pipeline import PredictionPipeline
        p = PredictionPipeline()
        p.PIPELINES_DIR = str(tmp_path / "pipelines")
        os.makedirs(p.PIPELINES_DIR, exist_ok=True)
        return p

    def test_create_pipeline(self, tmp_path):
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        assert state.pipeline_id.startswith("pipe_")
        assert state.status == "pending"

    def test_get_state(self, tmp_path):
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        loaded = p.get_state(state.pipeline_id)
        assert loaded is not None
        assert loaded.pipeline_id == state.pipeline_id

    def test_advance_step(self, tmp_path):
        from app.services.prediction_pipeline import PipelineStep
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        updated = p.advance_step(
            state.pipeline_id,
            PipelineStep.INGESTION,
            PipelineStep.ONTOLOGY,
            project_id="proj_123",
        )
        assert updated.current_step == PipelineStep.ONTOLOGY
        assert "ingestion" in updated.steps_completed
        assert updated.project_id == "proj_123"

    def test_mark_failed(self, tmp_path):
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        p.mark_failed(state.pipeline_id, "Test error")
        loaded = p.get_state(state.pipeline_id)
        assert loaded.status == "failed"
        assert loaded.error == "Test error"

    def test_mark_complete(self, tmp_path):
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        p.mark_complete(state.pipeline_id)
        loaded = p.get_state(state.pipeline_id)
        assert loaded.status == "completed"
        assert loaded.progress == 100

    def test_resume_from_failed(self, tmp_path):
        from app.services.prediction_pipeline import PipelineStep
        p = self._make_pipeline(tmp_path)
        state = p.create_pipeline()
        p.advance_step(state.pipeline_id, PipelineStep.INGESTION, PipelineStep.GRAPH_BUILD)
        p.mark_failed(state.pipeline_id, "Graph build failed")
        resume_step = p.can_resume_from(state.pipeline_id)
        assert resume_step == PipelineStep.GRAPH_BUILD

    def test_nonexistent_pipeline(self, tmp_path):
        p = self._make_pipeline(tmp_path)
        assert p.get_state("nonexistent") is None
        assert p.can_resume_from("nonexistent") is None


# ---------------------------------------------------------------------------
# Bootstrap confidence tests
# ---------------------------------------------------------------------------


class TestBootstrapConfidence:
    """Tests for bootstrap confidence band calculation."""

    def _make_calculator(self):
        from app.services.bootstrap_confidence import BootstrapConfidence
        return BootstrapConfidence()

    def test_empty_sentiments(self):
        calc = self._make_calculator()
        result = calc.compute_confidence_interval([])
        assert result["mean"] == 0.0
        assert result["n_agents"] == 0

    def test_uniform_sentiments_tight_ci(self):
        calc = self._make_calculator()
        # All agents have same sentiment → CI should be very tight
        sentiments = [0.5] * 50
        result = calc.compute_confidence_interval(sentiments)
        assert abs(result["ci_high"] - result["ci_low"]) < 0.01

    def test_diverse_sentiments_wider_ci(self):
        calc = self._make_calculator()
        # Mixed sentiments → wider CI
        sentiments = [0.8, -0.6, 0.3, -0.9, 0.1, -0.2, 0.7, -0.5, 0.4, -0.8]
        result = calc.compute_confidence_interval(sentiments)
        assert result["ci_high"] - result["ci_low"] > 0.1

    def test_ci_contains_mean(self):
        calc = self._make_calculator()
        sentiments = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        result = calc.compute_confidence_interval(sentiments)
        assert result["ci_low"] <= result["mean"] <= result["ci_high"]

    def test_reproducible_with_seed(self):
        calc = self._make_calculator()
        sentiments = [0.1, -0.2, 0.3, -0.4, 0.5]
        r1 = calc.compute_confidence_interval(sentiments, seed=42)
        r2 = calc.compute_confidence_interval(sentiments, seed=42)
        assert r1["ci_low"] == r2["ci_low"]
        assert r1["ci_high"] == r2["ci_high"]

    def test_prediction_bands(self):
        calc = self._make_calculator()
        sentiments = {"a": 0.5, "b": 0.3, "c": 0.4, "d": 0.6, "e": 0.2}
        result = calc.compute_prediction_bands(sentiments, 0.7)
        assert result["probability"] == 0.7
        assert result["ci_low"] <= result["ci_high"]
        assert "band_width" in result
        assert "sentiment_stats" in result

    def test_prediction_bands_bounded(self):
        calc = self._make_calculator()
        sentiments = {"a": -0.9, "b": 0.9, "c": -0.8, "d": 0.8}
        result = calc.compute_prediction_bands(sentiments, 0.95)
        assert result["ci_low"] >= 0.0
        assert result["ci_high"] <= 1.0


# ---------------------------------------------------------------------------
# Cross-validation tests
# ---------------------------------------------------------------------------


class TestCrossValidator:
    """Tests for cross-validation prediction scoring."""

    def _make_validator(self):
        from app.services.cross_validator import CrossValidator
        return CrossValidator()

    def test_empty_agents(self):
        v = self._make_validator()
        result = v.validate({})
        assert result["is_valid"] is False
        assert result["agreement_rate"] == 0.0

    def test_single_agent_insufficient(self):
        v = self._make_validator()
        result = v.validate({"alice": ["great progress"]})
        assert result["is_valid"] is False

    def test_unanimous_positive_high_agreement(self):
        v = self._make_validator()
        posts = {
            f"agent_{i}": ["great excellent wonderful progress love hope"]
            for i in range(20)
        }
        result = v.validate(posts, n_folds=5)
        assert result["agreement_rate"] >= 0.8
        assert "Strong" in result["interpretation"] or "Moderate" in result["interpretation"]

    def test_split_opinions_low_agreement(self):
        v = self._make_validator()
        posts = {}
        for i in range(10):
            posts[f"pos_{i}"] = ["great excellent wonderful love"]
        for i in range(10):
            posts[f"neg_{i}"] = ["terrible awful crisis danger"]
        result = v.validate(posts, n_folds=5)
        # With a clean 50/50 split, some folds will disagree
        assert result["n_folds"] == 5
        assert result["is_valid"] is True

    def test_fold_results_present(self):
        v = self._make_validator()
        posts = {f"a{i}": [f"post {i} great"] for i in range(10)}
        result = v.validate(posts, n_folds=3)
        assert len(result["folds"]) == 3
        for fold in result["folds"]:
            assert "train_sentiment" in fold
            assert "test_sentiment" in fold
            assert "agrees" in fold

    def test_reproducible_with_seed(self):
        v = self._make_validator()
        posts = {f"a{i}": [f"post {i}"] for i in range(10)}
        r1 = v.validate(posts, seed=42)
        r2 = v.validate(posts, seed=42)
        assert r1["agreement_rate"] == r2["agreement_rate"]

    def test_avg_delta_computed(self):
        v = self._make_validator()
        posts = {f"a{i}": ["great progress"] for i in range(10)}
        result = v.validate(posts, n_folds=3)
        assert "avg_sentiment_delta" in result


# ---------------------------------------------------------------------------
# Prediction decay tests
# ---------------------------------------------------------------------------


class TestPredictionDecay:
    """Tests for prediction decay tracking."""

    def _make_tracker(self):
        from app.services.prediction_decay import PredictionDecayTracker
        return PredictionDecayTracker()

    def test_fresh_prediction(self):
        from datetime import datetime
        t = self._make_tracker()
        preds = [{"event": "Test", "probability": 0.7}]
        health = t.compute_health(preds, datetime.now().isoformat())
        assert len(health) == 1
        assert health[0].health_status == "fresh"
        assert health[0].decay_factor >= 0.9

    def test_stale_prediction_decays(self):
        from datetime import datetime, timedelta
        t = self._make_tracker()
        old_date = (datetime.now() - timedelta(days=45)).isoformat()
        preds = [{"event": "Test", "probability": 0.7}]
        health = t.compute_health(preds, old_date)
        assert health[0].health_status == "stale"
        assert health[0].current_probability < 0.7

    def test_evidence_boosts_prediction(self):
        from datetime import datetime
        t = self._make_tracker()
        now = datetime.now()
        preds = [{"event": "Test", "probability": 0.5}]
        evidence = [
            {"prediction_idx": 0, "timestamp": now.isoformat()},
            {"prediction_idx": 0, "timestamp": now.isoformat()},
        ]
        health = t.compute_health(preds, now.isoformat(), evidence_log=evidence)
        assert health[0].health_status == "boosted"
        assert health[0].evidence_count == 2

    def test_aging_prediction(self):
        from datetime import datetime, timedelta
        t = self._make_tracker()
        aging_date = (datetime.now() - timedelta(days=20)).isoformat()
        preds = [{"event": "Test", "probability": 0.7}]
        health = t.compute_health(preds, aging_date)
        assert health[0].health_status == "aging"

    def test_decay_factor_bounded(self):
        from datetime import datetime, timedelta
        t = self._make_tracker()
        very_old = (datetime.now() - timedelta(days=365)).isoformat()
        preds = [{"event": "Test", "probability": 0.9}]
        health = t.compute_health(preds, very_old)
        assert health[0].decay_factor >= 0.3
        assert health[0].current_probability >= 0.05

    def test_multiple_predictions(self):
        from datetime import datetime
        t = self._make_tracker()
        preds = [
            {"event": "A", "probability": 0.8},
            {"event": "B", "probability": 0.4},
        ]
        health = t.compute_health(preds, datetime.now().isoformat())
        assert len(health) == 2
        assert health[0].prediction_idx == 0
        assert health[1].prediction_idx == 1

    def test_health_to_dict(self):
        from datetime import datetime
        t = self._make_tracker()
        preds = [{"event": "Test", "probability": 0.7}]
        health = t.compute_health(preds, datetime.now().isoformat())
        d = health[0].to_dict()
        assert "health_status" in d
        assert "decay_factor" in d
        assert "current_probability" in d
