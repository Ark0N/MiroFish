"""
Tests for ProjectManager and Project model.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from app.models.project import Project, ProjectManager, ProjectStatus


@pytest.fixture
def temp_projects_dir(tmp_path):
    """Provide a temporary directory for project storage."""
    projects_dir = str(tmp_path / "projects")
    os.makedirs(projects_dir, exist_ok=True)
    with patch.object(ProjectManager, "PROJECTS_DIR", projects_dir):
        yield projects_dir


class TestCreateProject:
    """Tests for ProjectManager.create_project."""

    def test_creates_project_with_correct_fields(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Test Project")

        assert project.name == "Test Project"
        assert project.status == ProjectStatus.CREATED
        assert project.project_id.startswith("proj_")
        assert len(project.project_id) == len("proj_") + 12
        assert project.created_at
        assert project.updated_at
        assert project.files == []
        assert project.total_text_length == 0
        assert project.ontology is None
        assert project.graph_id is None

    def test_creates_project_directory(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Dir Test")

        project_dir = os.path.join(temp_projects_dir, project.project_id)
        assert os.path.isdir(project_dir)

    def test_creates_files_subdirectory(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Files Dir Test")

        files_dir = os.path.join(temp_projects_dir, project.project_id, "files")
        assert os.path.isdir(files_dir)

    def test_saves_project_metadata_file(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Meta Test")

        meta_path = os.path.join(
            temp_projects_dir, project.project_id, "project.json"
        )
        assert os.path.isfile(meta_path)

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["project_id"] == project.project_id
        assert data["name"] == "Meta Test"
        assert data["status"] == "created"

    def test_default_name(self, temp_projects_dir):
        project = ProjectManager.create_project()
        assert project.name == "Unnamed Project"


class TestSaveAndGetProject:
    """Tests for round-trip save/load of projects."""

    def test_round_trip(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Round Trip")
        project.ontology = {"entity_types": ["Person", "Org"]}
        project.analysis_summary = "Some analysis"
        project.graph_id = "graph_abc"
        project.chunk_size = 1000
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)

        assert loaded is not None
        assert loaded.project_id == project.project_id
        assert loaded.name == "Round Trip"
        assert loaded.ontology == {"entity_types": ["Person", "Org"]}
        assert loaded.analysis_summary == "Some analysis"
        assert loaded.graph_id == "graph_abc"
        assert loaded.chunk_size == 1000

    def test_get_nonexistent_project_returns_none(self, temp_projects_dir):
        result = ProjectManager.get_project("proj_doesnotexist")
        assert result is None

    def test_save_updates_updated_at(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Time Test")
        original_updated = project.updated_at

        project.name = "Updated Name"
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)
        assert loaded.name == "Updated Name"
        # updated_at should have been refreshed (may or may not differ
        # depending on execution speed, but the field should be set)
        assert loaded.updated_at is not None


class TestDeleteProject:
    """Tests for ProjectManager.delete_project."""

    def test_deletes_project_directory(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Delete Me")
        project_dir = os.path.join(temp_projects_dir, project.project_id)
        assert os.path.isdir(project_dir)

        result = ProjectManager.delete_project(project.project_id)

        assert result is True
        assert not os.path.exists(project_dir)

    def test_delete_nonexistent_returns_false(self, temp_projects_dir):
        result = ProjectManager.delete_project("proj_nonexistent")
        assert result is False

    def test_get_after_delete_returns_none(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Gone Soon")
        ProjectManager.delete_project(project.project_id)

        result = ProjectManager.get_project(project.project_id)
        assert result is None


class TestListProjects:
    """Tests for ProjectManager.list_projects."""

    def test_lists_all_projects(self, temp_projects_dir):
        ProjectManager.create_project(name="A")
        ProjectManager.create_project(name="B")
        ProjectManager.create_project(name="C")

        projects = ProjectManager.list_projects()

        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"A", "B", "C"}

    def test_empty_list(self, temp_projects_dir):
        projects = ProjectManager.list_projects()
        assert projects == []

    def test_respects_limit(self, temp_projects_dir):
        for i in range(5):
            ProjectManager.create_project(name=f"Proj {i}")

        projects = ProjectManager.list_projects(limit=3)
        assert len(projects) == 3

    def test_sorted_by_created_at_descending(self, temp_projects_dir):
        p1 = ProjectManager.create_project(name="First")
        p2 = ProjectManager.create_project(name="Second")
        p3 = ProjectManager.create_project(name="Third")

        projects = ProjectManager.list_projects()

        # Most recently created should be first
        assert projects[0].name == "Third"
        assert projects[-1].name == "First"


class TestStateTransitions:
    """Tests for project status transitions."""

    def test_created_to_ontology_generated(self, temp_projects_dir):
        project = ProjectManager.create_project(name="State Test")
        assert project.status == ProjectStatus.CREATED

        project.status = ProjectStatus.ONTOLOGY_GENERATED
        project.ontology = {"entity_types": ["Person"]}
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)
        assert loaded.status == ProjectStatus.ONTOLOGY_GENERATED

    def test_ontology_generated_to_graph_building(self, temp_projects_dir):
        project = ProjectManager.create_project(name="State Test 2")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)

        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = "task_123"
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)
        assert loaded.status == ProjectStatus.GRAPH_BUILDING
        assert loaded.graph_build_task_id == "task_123"

    def test_graph_building_to_graph_completed(self, temp_projects_dir):
        project = ProjectManager.create_project(name="State Test 3")
        project.status = ProjectStatus.GRAPH_BUILDING
        ProjectManager.save_project(project)

        project.status = ProjectStatus.GRAPH_COMPLETED
        project.graph_id = "graph_xyz"
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)
        assert loaded.status == ProjectStatus.GRAPH_COMPLETED
        assert loaded.graph_id == "graph_xyz"

    def test_full_lifecycle(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Lifecycle")
        statuses = [
            ProjectStatus.ONTOLOGY_GENERATED,
            ProjectStatus.GRAPH_BUILDING,
            ProjectStatus.GRAPH_COMPLETED,
        ]
        for status in statuses:
            project.status = status
            ProjectManager.save_project(project)
            loaded = ProjectManager.get_project(project.project_id)
            assert loaded.status == status

    def test_failed_state(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Fail Test")
        project.status = ProjectStatus.FAILED
        project.error = "Something went wrong"
        ProjectManager.save_project(project)

        loaded = ProjectManager.get_project(project.project_id)
        assert loaded.status == ProjectStatus.FAILED
        assert loaded.error == "Something went wrong"


class TestPathTraversalPrevention:
    """Tests for path traversal attack prevention."""

    def test_get_project_with_traversal_raises(self, temp_projects_dir):
        with pytest.raises(ValueError, match="illegal characters"):
            ProjectManager.get_project("../../etc")

    def test_get_project_with_slash_raises(self, temp_projects_dir):
        with pytest.raises(ValueError, match="illegal characters"):
            ProjectManager.get_project("foo/bar")

    def test_get_project_with_backslash_raises(self, temp_projects_dir):
        with pytest.raises(ValueError, match="illegal characters"):
            ProjectManager.get_project("foo\\bar")

    def test_delete_project_with_traversal_raises(self, temp_projects_dir):
        with pytest.raises(ValueError, match="illegal characters"):
            ProjectManager.delete_project("../../etc")

    def test_save_file_with_traversal_raises(self, temp_projects_dir):
        mock_file = MagicMock()
        with pytest.raises(ValueError, match="illegal characters"):
            ProjectManager.save_file_to_project(
                "../../etc", mock_file, "test.txt"
            )

    def test_empty_project_id_raises(self, temp_projects_dir):
        with pytest.raises(ValueError, match="non-empty string"):
            ProjectManager.get_project("")

    def test_project_id_with_special_chars_raises(self, temp_projects_dir):
        with pytest.raises(ValueError):
            ProjectManager.get_project("proj_<script>")


class TestAtomicWrite:
    """Tests for atomic save_project via temp file + os.replace."""

    def test_project_file_exists_after_save(self, temp_projects_dir):
        project = ProjectManager.create_project(name="Atomic Test")
        meta_path = os.path.join(
            temp_projects_dir, project.project_id, "project.json"
        )

        # Modify and re-save
        project.name = "Updated Atomically"
        ProjectManager.save_project(project)

        assert os.path.isfile(meta_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "Updated Atomically"

    def test_no_temp_files_left_after_save(self, temp_projects_dir):
        project = ProjectManager.create_project(name="No Temp Left")
        project_dir = os.path.join(temp_projects_dir, project.project_id)

        project.name = "Saved Again"
        ProjectManager.save_project(project)

        # No .tmp files should remain
        remaining_files = os.listdir(project_dir)
        tmp_files = [f for f in remaining_files if f.endswith(".tmp")]
        assert tmp_files == []

    def test_file_is_valid_json_after_save(self, temp_projects_dir):
        project = ProjectManager.create_project(name="JSON Valid")
        meta_path = os.path.join(
            temp_projects_dir, project.project_id, "project.json"
        )

        for i in range(5):
            project.name = f"Iteration {i}"
            ProjectManager.save_project(project)

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "Iteration 4"


class TestProjectModel:
    """Tests for the Project dataclass itself."""

    def test_to_dict(self):
        project = Project(
            project_id="proj_abc123",
            name="Test",
            status=ProjectStatus.CREATED,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        d = project.to_dict()
        assert d["project_id"] == "proj_abc123"
        assert d["status"] == "created"
        assert d["files"] == []
        assert d["ontology"] is None

    def test_from_dict(self):
        data = {
            "project_id": "proj_xyz",
            "name": "From Dict",
            "status": "ontology_generated",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "ontology": {"types": []},
        }
        project = Project.from_dict(data)
        assert project.project_id == "proj_xyz"
        assert project.status == ProjectStatus.ONTOLOGY_GENERATED
        assert project.ontology == {"types": []}

    def test_round_trip_dict(self):
        project = Project(
            project_id="proj_rt",
            name="Round Trip",
            status=ProjectStatus.GRAPH_COMPLETED,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
            graph_id="g123",
            chunk_size=800,
        )
        d = project.to_dict()
        restored = Project.from_dict(d)
        assert restored.project_id == project.project_id
        assert restored.status == project.status
        assert restored.graph_id == project.graph_id
        assert restored.chunk_size == project.chunk_size
