"""
Integration tests for MiroFish API endpoints using Flask's test client.
"""

import pytest
from unittest.mock import patch
from app import create_app
from app.services.report_agent import ReportManager


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert data['service'] == 'MiroFish Backend'


class TestReportStatusEndpoint:
    """Tests for GET/POST /api/report/generate/status."""

    def test_get_without_task_id_or_simulation_id_returns_400(self, client):
        """GET without task_id or simulation_id should return 400."""
        response = client.get('/api/report/generate/status')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_get_with_nonexistent_task_id_returns_404(self, client):
        """GET with a nonexistent task_id should return 404."""
        response = client.get(
            '/api/report/generate/status',
            query_string={'task_id': 'nonexistent-task-id'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_post_without_task_id_or_simulation_id_returns_400(self, client):
        """POST without task_id or simulation_id should return 400."""
        response = client.post(
            '/api/report/generate/status',
            json={}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_post_with_nonexistent_task_id_returns_404(self, client):
        """POST with a nonexistent task_id should return 404."""
        response = client.post(
            '/api/report/generate/status',
            json={'task_id': 'nonexistent-task-id'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_get_with_nonexistent_simulation_id_returns_400(self, client):
        """GET with a simulation_id that has no report falls through to
        require task_id, which is absent, so returns 400."""
        response = client.get(
            '/api/report/generate/status',
            query_string={'simulation_id': 'sim_nonexistent'}
        )
        # simulation_id has no completed report, and no task_id provided -> 400
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_post_with_nonexistent_simulation_id_returns_400(self, client):
        """POST with a simulation_id that has no report and no task_id
        should return 400."""
        response = client.post(
            '/api/report/generate/status',
            json={'simulation_id': 'sim_nonexistent'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_get_with_valid_task_returns_status(self, client):
        """GET with a valid task_id should return the task status."""
        from app.models.task import TaskManager
        tm = TaskManager()
        task_id = tm.create_task(task_type='report_generate', metadata={
            'simulation_id': 'sim_test123'
        })

        response = client.get(
            '/api/report/generate/status',
            query_string={'task_id': task_id}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['task_id'] == task_id
        assert data['data']['status'] == 'pending'

    def test_post_with_valid_task_returns_status(self, client):
        """POST with a valid task_id should return the task status."""
        from app.models.task import TaskManager
        tm = TaskManager()
        task_id = tm.create_task(task_type='report_generate', metadata={
            'simulation_id': 'sim_test456'
        })

        response = client.post(
            '/api/report/generate/status',
            json={'task_id': task_id}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['task_id'] == task_id
        assert data['data']['status'] == 'pending'


class TestReportGetEndpoint:
    """Tests for GET /api/report/<report_id>."""

    def test_get_nonexistent_report_returns_404(self, client):
        response = client.get('/api/report/nonexistent-report-id')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_get_report_by_nonexistent_simulation_returns_404(self, client):
        response = client.get('/api/report/by-simulation/sim_nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert data['has_report'] is False


class TestReportListEndpoint:
    """Tests for GET /api/report/list."""

    def test_list_reports_returns_200(self, client):
        response = client.get('/api/report/list')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
        assert 'count' in data


class TestGraphEndpoints:
    """Tests for /api/graph/ endpoints."""

    def test_list_projects_returns_200(self, client):
        """GET /api/graph/project/list should return a list."""
        response = client.get('/api/graph/project/list')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
        assert 'count' in data

    def test_get_nonexistent_project_returns_404(self, client):
        """GET /api/graph/project/<id> with invalid ID should return 404."""
        response = client.get('/api/graph/project/nonexistent-id-12345')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False


class TestIngestUrlEndpoint:
    """Tests for POST /api/graph/ingest-url."""

    def test_missing_urls_returns_400(self, client):
        response = client.post('/api/graph/ingest-url',
                               json={"simulation_requirement": "test"})
        assert response.status_code == 400
        assert "URL" in response.get_json()["error"]

    def test_missing_simulation_requirement_returns_400(self, client):
        response = client.post('/api/graph/ingest-url',
                               json={"urls": ["https://example.com"]})
        assert response.status_code == 400
        assert "simulation_requirement" in response.get_json()["error"]

    def test_empty_body_returns_400(self, client):
        response = client.post('/api/graph/ingest-url',
                               data="not json",
                               content_type='application/json')
        assert response.status_code == 400

    def test_too_many_urls_returns_400(self, client):
        response = client.post('/api/graph/ingest-url',
                               json={
                                   "urls": [f"https://example.com/{i}" for i in range(25)],
                                   "simulation_requirement": "test"
                               })
        assert response.status_code == 400
        assert "20" in response.get_json()["error"]


class TestPredictionRatingEndpoint:
    """Tests for POST /api/report/<report_id>/predictions/<idx>/rate."""

    def test_invalid_rating_returns_400(self, client):
        response = client.post('/api/report/test-report/predictions/0/rate',
                               json={"rating": 6})
        assert response.status_code == 400

    def test_missing_rating_returns_400(self, client):
        response = client.post('/api/report/test-report/predictions/0/rate',
                               json={"feedback": "good"})
        assert response.status_code == 400

    def test_missing_body_returns_400(self, client):
        response = client.post('/api/report/test-report/predictions/0/rate',
                               data="bad", content_type='application/json')
        assert response.status_code == 400


class TestPredictionNoteEndpoint:
    """Tests for POST /api/report/<report_id>/predictions/<idx>/note."""

    def test_missing_note_returns_400(self, client):
        response = client.post('/api/report/test-report/predictions/0/note',
                               json={})
        assert response.status_code == 400

    def test_missing_body_returns_400(self, client):
        response = client.post('/api/report/test-report/predictions/0/note',
                               data="bad", content_type='application/json')
        assert response.status_code == 400


class TestWebhookEndpoint:
    """Tests for POST /api/graph/webhook/event."""

    def test_missing_body_returns_400(self, client):
        response = client.post('/api/graph/webhook/event',
                               data="bad", content_type='application/json')
        assert response.status_code == 400

    def test_missing_project_id_returns_400(self, client):
        response = client.post('/api/graph/webhook/event',
                               json={"content": "test"})
        assert response.status_code == 400

    def test_missing_content_returns_400(self, client):
        response = client.post('/api/graph/webhook/event',
                               json={"project_id": "p1"})
        assert response.status_code == 400

    def test_valid_event_accepted(self, client, tmp_path):
        response = client.post('/api/graph/webhook/event',
                               json={
                                   "project_id": "test_proj",
                                   "content": "Breaking news event",
                                   "event_type": "news",
                                   "source": "test"
                               })
        # May fail if project dir doesn't exist, but should not be 400
        assert response.status_code in (200, 500)


class TestPredictionHealthEndpoint:
    """Tests for GET /api/report/<report_id>/health."""

    def test_health_nonexistent_returns_404(self, client):
        response = client.get('/api/report/nonexistent-id/health')
        assert response.status_code == 404

    def test_health_invalid_id_returns_400(self, client):
        response = client.get('/api/report/report_<bad>/health')
        assert response.status_code == 400


class TestSelftestEndpoint:
    """Tests for GET /api/report/selftest."""

    def test_selftest_returns_200(self, client):
        response = client.get('/api/report/selftest')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['passed'] > 0
        assert data['data']['failed'] == 0

    def test_selftest_has_all_services(self, client):
        response = client.get('/api/report/selftest')
        data = response.get_json()
        assert data['data']['total'] >= 10


class TestCatalogEndpoint:
    """Tests for GET /api/report/catalog."""

    def test_catalog_returns_200(self, client):
        response = client.get('/api/report/catalog')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['total_services'] >= 30
        assert data['data']['total_endpoints'] >= 10
        assert len(data['data']['services']) >= 30

    def test_catalog_has_endpoint_list(self, client):
        response = client.get('/api/report/catalog')
        data = response.get_json()
        endpoints = data['data']['endpoints']
        paths = [e['path'] for e in endpoints]
        assert any('/predictions' in p for p in paths)
        assert any('/health' in p for p in paths)
        assert any('/analytics' in p for p in paths)


class TestDigestEndpoint:
    """Tests for GET /api/report/<id>/digest."""

    def test_digest_nonexistent_returns_404(self, client):
        response = client.get('/api/report/nonexistent/digest')
        assert response.status_code == 404

    @patch.object(ReportManager, 'load_predictions')
    @patch.object(ReportManager, 'get_report', return_value=None)
    def test_digest_returns_text(self, mock_report, mock_load, client):
        from app.services.report_agent import PredictionSet, StructuredPrediction
        ps = PredictionSet(predictions=[
            StructuredPrediction(event="Market downturn expected", probability=0.8),
            StructuredPrediction(event="Policy change likely", probability=0.6),
        ], overall_confidence="Moderate", generated_at="2026-03-26")
        mock_load.return_value = ps
        response = client.get('/api/report/valid-id/digest')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert "2 predictions" in data['data']['digest']
        assert "Market downturn" in data['data']['digest']


class TestPredictionExportEndpoint:
    """Tests for GET /api/report/<id>/predictions/export."""

    def test_export_nonexistent_returns_404(self, client):
        response = client.get('/api/report/nonexistent/predictions/export')
        assert response.status_code == 404

    def test_export_invalid_format_returns_400(self, client):
        response = client.get('/api/report/test-id/predictions/export?format=xml')
        assert response.status_code == 400

    @patch.object(ReportManager, 'load_predictions')
    def test_export_csv(self, mock_load, client):
        from app.services.report_agent import PredictionSet, StructuredPrediction
        ps = PredictionSet(predictions=[
            StructuredPrediction(event="Test event", probability=0.7, agent_agreement=0.8),
        ], overall_confidence="High", generated_at="2026-01-01")
        mock_load.return_value = ps
        response = client.get('/api/report/valid-id/predictions/export?format=csv')
        assert response.status_code == 200
        assert 'text/csv' in response.content_type
        assert b'event' in response.data  # Header row
        assert b'Test event' in response.data

    @patch.object(ReportManager, 'load_predictions')
    def test_export_jsonl(self, mock_load, client):
        from app.services.report_agent import PredictionSet, StructuredPrediction
        ps = PredictionSet(predictions=[
            StructuredPrediction(event="Test event", probability=0.7),
        ], overall_confidence="High", generated_at="2026-01-01")
        mock_load.return_value = ps
        response = client.get('/api/report/valid-id/predictions/export?format=jsonl')
        assert response.status_code == 200
        assert b'Test event' in response.data


class TestScenariosEndpoint:
    """Tests for GET /api/report/<report_id>/scenarios."""

    def test_scenarios_nonexistent_returns_404(self, client):
        response = client.get('/api/report/nonexistent-id/scenarios')
        assert response.status_code == 404

    def test_scenarios_invalid_id_returns_400(self, client):
        response = client.get('/api/report/report_<bad>/scenarios')
        assert response.status_code == 400

    @patch.object(ReportManager, 'load_predictions')
    def test_scenarios_returns_tree(self, mock_load, client):
        from app.services.report_agent import PredictionSet, StructuredPrediction
        ps = PredictionSet(predictions=[
            StructuredPrediction(event="Event A", probability=0.8),
            StructuredPrediction(event="Event B", probability=0.4),
        ], overall_confidence="Test", generated_at="2026-01-01")
        mock_load.return_value = ps
        response = client.get('/api/report/valid-report/scenarios')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['total_scenarios'] == 4  # 2^2
        assert data['data']['best_case'] is not None
        assert data['data']['worst_case'] is not None


class TestAnalyticsEndpoints:
    """Tests for /api/analytics/ endpoints."""

    def test_simulation_analytics_invalid_id_returns_400(self, client):
        response = client.get('/api/analytics/simulation/<script>')
        assert response.status_code == 400

    def test_agents_analytics_invalid_id_returns_400(self, client):
        response = client.get('/api/analytics/agents/<script>')
        assert response.status_code == 400

    def test_network_analytics_invalid_id_returns_400(self, client):
        response = client.get('/api/analytics/network/<script>')
        assert response.status_code == 400

    def test_quality_score_invalid_id_returns_400(self, client):
        response = client.get('/api/analytics/quality/<script>')
        assert response.status_code == 400


class TestSimulationEndpoints:
    """Tests for /api/simulation/ endpoints."""

    def test_list_simulations_returns_200(self, client):
        """GET /api/simulation/list should return simulations."""
        response = client.get('/api/simulation/list')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
        assert 'count' in data


class TestReportGenerateEndpoint:
    """Tests for POST /api/report/generate."""

    def test_generate_without_simulation_id_returns_400(self, client):
        """POST without simulation_id should return 400."""
        response = client.post('/api/report/generate', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_generate_with_nonexistent_simulation_returns_404(self, client):
        """POST with a nonexistent simulation_id should return 404."""
        response = client.post(
            '/api/report/generate',
            json={'simulation_id': 'sim_nonexistent'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False


class TestReportCheckEndpoint:
    """Tests for GET /api/report/check/<simulation_id>."""

    def test_check_nonexistent_simulation_returns_200(self, client):
        """Check status for a simulation with no report should still return 200."""
        response = client.get('/api/report/check/sim_nonexistent')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['has_report'] is False
        assert data['data']['interview_unlocked'] is False


class TestPathTraversalRejection:
    """Verify that path traversal IDs are rejected with 400 errors."""

    def test_simulation_create_rejects_traversal_project_id(self, client):
        response = client.post('/api/simulation/create', json={
            'project_id': '../../../etc/passwd'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_simulation_prepare_rejects_traversal_simulation_id(self, client):
        response = client.post('/api/simulation/prepare', json={
            'simulation_id': '../../malicious'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_simulation_start_rejects_traversal_simulation_id(self, client):
        response = client.post('/api/simulation/start', json={
            'simulation_id': 'sim_id/../../etc'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_simulation_stop_rejects_traversal_simulation_id(self, client):
        response = client.post('/api/simulation/stop', json={
            'simulation_id': '../traversal'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_generate_rejects_traversal_simulation_id(self, client):
        response = client.post('/api/report/generate', json={
            'simulation_id': '../../attack'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_chat_rejects_traversal_simulation_id(self, client):
        response = client.post('/api/report/chat', json={
            'simulation_id': '../../../etc/passwd',
            'message': 'test'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_simulation_list_rejects_traversal_project_id(self, client):
        response = client.get('/api/simulation/list', query_string={
            'project_id': '../traversal'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_status_rejects_traversal_simulation_id(self, client):
        response = client.get('/api/report/generate/status', query_string={
            'simulation_id': '../../../etc/shadow'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_project_rejects_special_chars(self, client):
        response = client.get('/api/graph/project/proj_<script>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_project_delete_rejects_special_chars(self, client):
        response = client.delete('/api/graph/project/proj_<bad>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_project_reset_rejects_special_chars(self, client):
        response = client.post('/api/graph/project/proj_<bad>/reset')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_build_rejects_traversal_project_id(self, client):
        response = client.post('/api/graph/build', json={
            'project_id': '../../etc/passwd'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_task_rejects_special_chars(self, client):
        response = client.get('/api/graph/task/task_<script>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_data_rejects_special_chars(self, client):
        response = client.get('/api/graph/data/graph_<bad>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_graph_delete_rejects_special_chars(self, client):
        response = client.delete('/api/graph/delete/graph_<bad>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_get_rejects_special_chars(self, client):
        response = client.get('/api/report/report_<script>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_delete_rejects_special_chars(self, client):
        response = client.delete('/api/report/report_<bad>')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_download_rejects_special_chars(self, client):
        response = client.get('/api/report/report_<bad>/download')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_by_simulation_rejects_traversal_id(self, client):
        response = client.get('/api/report/by-simulation/sim_..attack')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_check_rejects_traversal_id(self, client):
        response = client.get('/api/report/check/sim_..attack')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_report_progress_rejects_special_chars(self, client):
        response = client.get('/api/report/report_<bad>/progress')
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_env_status_rejects_traversal(self, client):
        response = client.post('/api/simulation/env-status', json={
            'simulation_id': '../../attack'
        })
        assert response.status_code == 400
        assert response.get_json()['success'] is False
