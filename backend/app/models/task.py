"""
Task state management.
Tracks long-running tasks (e.g., graph building).
"""

import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"          # Waiting
    PROCESSING = "processing"    # In progress
    COMPLETED = "completed"      # Completed
    FAILED = "failed"            # Failed


@dataclass
class Task:
    """Task data class."""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # Overall progress percentage 0-100
    message: str = ""              # Status message
    result: Optional[Dict] = None  # Task result
    error: Optional[str] = None    # Error message
    metadata: Dict = field(default_factory=dict)  # Additional metadata
    progress_detail: Dict = field(default_factory=dict)  # Detailed progress info

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    Task manager.
    Thread-safe task state management.
    """

    _instance = None
    _lock = threading.Lock()

    # Maximum number of tasks to keep in memory
    MAX_TASKS = 1000

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance

    def _evict_completed_tasks(self):
        """
        Evict oldest completed/failed tasks when over MAX_TASKS limit.
        Must be called while holding self._task_lock.
        """
        if len(self._tasks) <= self.MAX_TASKS:
            return

        # Find completed/failed tasks sorted by creation time (oldest first)
        finished = [
            (tid, task) for tid, task in self._tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        ]
        finished.sort(key=lambda x: x[1].created_at)

        # Remove oldest finished tasks until we're at or below MAX_TASKS
        to_remove = len(self._tasks) - self.MAX_TASKS
        for i, (tid, _) in enumerate(finished):
            if i >= to_remove:
                break
            del self._tasks[tid]

    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        Create a new task.

        Args:
            task_type: Task type
            metadata: Additional metadata

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()

        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )

        with self._task_lock:
            self._tasks[task_id] = task
            self._evict_completed_tasks()

        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task."""
        with self._task_lock:
            return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        Update task state.

        Args:
            task_id: Task ID
            status: New status
            progress: Progress percentage
            message: Status message
            result: Task result
            error: Error message
            progress_detail: Detailed progress info
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail

    def complete_task(self, task_id: str, result: Dict):
        """Mark task as completed."""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="Task completed",
            result=result
        )

    def fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="Task failed",
            error=error
        )

    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """List tasks."""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old tasks."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]
