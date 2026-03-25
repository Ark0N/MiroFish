"""
Automated prediction pipeline orchestrator.

Chains the full prediction workflow into a single orchestration:
URL ingestion → ontology → graph build → simulation → report →
prediction extraction → calibration → output.

Includes progress tracking and step-level resumption on failure.
"""

import json
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from ..utils.file_utils import atomic_write_json

logger = get_logger('mirofish.pipeline')


class PipelineStep(str, Enum):
    """Pipeline execution steps."""
    INGESTION = "ingestion"
    ONTOLOGY = "ontology"
    GRAPH_BUILD = "graph_build"
    SIMULATION_PREP = "simulation_prep"
    SIMULATION_RUN = "simulation_run"
    REPORT = "report"
    PREDICTIONS = "predictions"
    CALIBRATION = "calibration"
    COMPLETE = "complete"


@dataclass
class PipelineState:
    """State of a pipeline execution."""
    pipeline_id: str
    project_id: str = ""
    graph_id: str = ""
    simulation_id: str = ""
    report_id: str = ""
    current_step: PipelineStep = PipelineStep.INGESTION
    steps_completed: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, paused, completed, failed
    error: Optional[str] = None
    progress: int = 0  # 0-100
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_id": self.simulation_id,
            "report_id": self.report_id,
            "current_step": self.current_step.value,
            "steps_completed": self.steps_completed,
            "status": self.status,
            "error": self.error,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# Step progress ranges
STEP_PROGRESS = {
    PipelineStep.INGESTION: (0, 10),
    PipelineStep.ONTOLOGY: (10, 25),
    PipelineStep.GRAPH_BUILD: (25, 45),
    PipelineStep.SIMULATION_PREP: (45, 55),
    PipelineStep.SIMULATION_RUN: (55, 75),
    PipelineStep.REPORT: (75, 90),
    PipelineStep.PREDICTIONS: (90, 95),
    PipelineStep.CALIBRATION: (95, 100),
}


class PredictionPipeline:
    """Orchestrate the full prediction pipeline."""

    PIPELINES_DIR = os.path.join(Config.UPLOAD_FOLDER, 'pipelines')

    def create_pipeline(
        self,
        urls: Optional[List[str]] = None,
        simulation_requirement: str = "",
        project_name: str = "Pipeline Project",
    ) -> PipelineState:
        """Create a new pipeline execution.

        Args:
            urls: URLs to ingest (optional — can use existing project)
            simulation_requirement: What to simulate/predict
            project_name: Name for the project

        Returns:
            PipelineState with pipeline_id
        """
        import uuid
        pipeline_id = f"pipe_{uuid.uuid4().hex[:12]}"

        state = PipelineState(
            pipeline_id=pipeline_id,
        )

        self._save_state(state)
        logger.info(f"Created pipeline: {pipeline_id}")
        return state

    def get_state(self, pipeline_id: str) -> Optional[PipelineState]:
        """Get current pipeline state."""
        path = os.path.join(self.PIPELINES_DIR, f"{pipeline_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return PipelineState(
                pipeline_id=data["pipeline_id"],
                project_id=data.get("project_id", ""),
                graph_id=data.get("graph_id", ""),
                simulation_id=data.get("simulation_id", ""),
                report_id=data.get("report_id", ""),
                current_step=PipelineStep(data.get("current_step", "ingestion")),
                steps_completed=data.get("steps_completed", []),
                status=data.get("status", "pending"),
                error=data.get("error"),
                progress=data.get("progress", 0),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load pipeline {pipeline_id}: {e}")
            return None

    def advance_step(
        self,
        pipeline_id: str,
        completed_step: PipelineStep,
        next_step: PipelineStep,
        **kwargs,
    ) -> Optional[PipelineState]:
        """Advance the pipeline to the next step.

        Args:
            pipeline_id: Pipeline to advance
            completed_step: Step that just completed
            next_step: Next step to execute
            **kwargs: Additional state updates (project_id, graph_id, etc.)
        """
        state = self.get_state(pipeline_id)
        if not state:
            return None

        state.steps_completed.append(completed_step.value)
        state.current_step = next_step
        state.progress = STEP_PROGRESS.get(next_step, (0, 0))[0]
        state.updated_at = datetime.now().isoformat()
        state.status = "running"

        # Apply additional state updates
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)

        self._save_state(state)
        return state

    def mark_failed(self, pipeline_id: str, error: str) -> None:
        """Mark a pipeline as failed."""
        state = self.get_state(pipeline_id)
        if state:
            state.status = "failed"
            state.error = error
            state.updated_at = datetime.now().isoformat()
            self._save_state(state)

    def mark_complete(self, pipeline_id: str) -> None:
        """Mark a pipeline as successfully completed."""
        state = self.get_state(pipeline_id)
        if state:
            state.status = "completed"
            state.current_step = PipelineStep.COMPLETE
            state.progress = 100
            state.updated_at = datetime.now().isoformat()
            self._save_state(state)

    def can_resume_from(self, pipeline_id: str) -> Optional[PipelineStep]:
        """Check if a failed pipeline can be resumed and from which step.

        Returns the step to resume from, or None if not resumable.
        """
        state = self.get_state(pipeline_id)
        if not state or state.status != "failed":
            return None

        # Can resume from the failed step
        return state.current_step

    def _save_state(self, state: PipelineState) -> None:
        os.makedirs(self.PIPELINES_DIR, exist_ok=True)
        path = os.path.join(self.PIPELINES_DIR, f"{state.pipeline_id}.json")
        atomic_write_json(path, state.to_dict())
