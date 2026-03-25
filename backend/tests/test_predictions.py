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
