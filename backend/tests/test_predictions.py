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
