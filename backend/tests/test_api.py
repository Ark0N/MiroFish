"""
Integration tests for MiroFish API endpoints using Flask's test client.
"""

import pytest
from app import create_app


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
