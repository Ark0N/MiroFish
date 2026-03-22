"""
Tests for retry_with_backoff decorator, RetryableAPIClient, and TaskManager.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytest

from app.utils.retry import retry_with_backoff, RetryableAPIClient
from app.models.task import TaskManager, TaskStatus, Task


# ---------------------------------------------------------------------------
# retry_with_backoff decorator tests
# ---------------------------------------------------------------------------


class TestRetryWithBackoffDecorator:
    """Tests for the retry_with_backoff decorator."""

    def test_succeeds_on_first_try(self):
        """Function succeeds immediately - no retries, no sleep."""
        call_count = 0

        @retry_with_backoff(max_retries=3, jitter=False)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            result = succeed()

        assert result == "ok"
        assert call_count == 1
        mock_sleep.assert_not_called()

    def test_fails_then_succeeds(self):
        """Function fails twice then succeeds on third attempt."""
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=1.0, jitter=False)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "finally"

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            result = flaky()

        assert result == "finally"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    def test_always_fails_raises_after_max_retries(self):
        """Function always fails - raises the exception after exhausting retries."""

        @retry_with_backoff(max_retries=2, initial_delay=0.1, jitter=False)
        def always_fail():
            raise RuntimeError("permanent failure")

        with patch("app.utils.retry.time.sleep"):
            with pytest.raises(RuntimeError, match="permanent failure"):
                always_fail()

    def test_custom_exception_types_caught(self):
        """Only specified exception types trigger retries."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            exceptions=(ConnectionError,),
            jitter=False,
        )
        def network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("timeout")
            return "connected"

        with patch("app.utils.retry.time.sleep"):
            result = network_call()

        assert result == "connected"
        assert call_count == 2

    def test_non_matching_exceptions_not_retried(self):
        """Exceptions not in the exceptions tuple propagate immediately."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            exceptions=(ConnectionError,),
            jitter=False,
        )
        def bad_call():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(TypeError, match="wrong type"):
                bad_call()

        assert call_count == 1
        mock_sleep.assert_not_called()

    def test_backoff_timing_increases(self):
        """Sleep is called with increasing delays (exponential backoff)."""

        @retry_with_backoff(
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=False,
        )
        def always_fail():
            raise ValueError("fail")

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                always_fail()

        # Without jitter: delays should be 1.0, 2.0, 4.0
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    def test_max_delay_cap(self):
        """Delay is capped at max_delay."""

        @retry_with_backoff(
            max_retries=4,
            initial_delay=10.0,
            max_delay=15.0,
            backoff_factor=2.0,
            jitter=False,
        )
        def always_fail():
            raise ValueError("fail")

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                always_fail()

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        # initial=10, then 20 capped to 15, then 40 capped to 15, then 80 capped to 15
        assert delays == [10.0, 15.0, 15.0, 15.0]

    def test_on_retry_callback(self):
        """The on_retry callback is called with exception and attempt number."""
        callback = MagicMock()
        call_count = 0

        @retry_with_backoff(
            max_retries=2,
            jitter=False,
            on_retry=callback,
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError(f"fail {call_count}")
            return "ok"

        with patch("app.utils.retry.time.sleep"):
            result = flaky()

        assert result == "ok"
        assert callback.call_count == 2
        # on_retry receives (exception, retry_count) where retry_count is 1-indexed
        assert callback.call_args_list[0][0][1] == 1
        assert callback.call_args_list[1][0][1] == 2

    def test_preserves_function_name(self):
        """functools.wraps preserves the original function name."""

        @retry_with_backoff()
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


# ---------------------------------------------------------------------------
# RetryableAPIClient tests
# ---------------------------------------------------------------------------


class TestRetryableAPIClient:
    """Tests for the RetryableAPIClient class."""

    def test_call_with_retry_succeeds(self):
        client = RetryableAPIClient(max_retries=2)
        func = MagicMock(return_value="result")

        with patch("app.utils.retry.time.sleep"):
            result = client.call_with_retry(func, "arg1", key="val")

        assert result == "result"
        func.assert_called_once_with("arg1", key="val")

    def test_call_with_retry_retries_on_failure(self):
        client = RetryableAPIClient(max_retries=3, initial_delay=0.1)
        func = MagicMock(side_effect=[ConnectionError("err"), "ok"])

        with patch("app.utils.retry.time.sleep"):
            result = client.call_with_retry(
                func, exceptions=(ConnectionError,)
            )

        assert result == "ok"
        assert func.call_count == 2

    def test_call_with_retry_raises_after_exhaustion(self):
        client = RetryableAPIClient(max_retries=1)
        func = MagicMock(side_effect=RuntimeError("boom"))

        with patch("app.utils.retry.time.sleep"):
            with pytest.raises(RuntimeError, match="boom"):
                client.call_with_retry(func, exceptions=(RuntimeError,))

        assert func.call_count == 2  # initial + 1 retry

    def test_call_batch_with_retry(self):
        client = RetryableAPIClient(max_retries=1)
        items = [1, 2, 3]

        def process(item):
            if item == 2:
                raise ValueError("bad item")
            return item * 10

        with patch("app.utils.retry.time.sleep"):
            results, failures = client.call_batch_with_retry(
                items, process, exceptions=(ValueError,)
            )

        assert results == [10, 30]
        assert len(failures) == 1
        assert failures[0]["index"] == 1


# ---------------------------------------------------------------------------
# TaskManager tests
# ---------------------------------------------------------------------------


class TestTaskManager:
    """Tests for TaskManager."""

    @pytest.fixture(autouse=True)
    def fresh_task_manager(self):
        """Reset the TaskManager singleton before each test."""
        # Clear the singleton so each test starts fresh
        TaskManager._instance = None
        self.tm = TaskManager()
        yield
        TaskManager._instance = None

    def test_create_task_initial_state(self):
        task_id = self.tm.create_task("graph_build")

        task = self.tm.get_task(task_id)
        assert task is not None
        assert task.task_id == task_id
        assert task.task_type == "graph_build"
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0
        assert task.message == ""
        assert task.result is None
        assert task.error is None

    def test_create_task_with_metadata(self):
        meta = {"project_id": "proj_abc"}
        task_id = self.tm.create_task("simulation", metadata=meta)

        task = self.tm.get_task(task_id)
        assert task.metadata == meta

    def test_get_task_returns_created_task(self):
        task_id = self.tm.create_task("report")
        task = self.tm.get_task(task_id)

        assert task is not None
        assert task.task_id == task_id

    def test_get_task_nonexistent_returns_none(self):
        task = self.tm.get_task("nonexistent-id")
        assert task is None

    def test_update_task_changes_status(self):
        task_id = self.tm.create_task("build")

        self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=50)

        task = self.tm.get_task(task_id)
        assert task.status == TaskStatus.PROCESSING
        assert task.progress == 50

    def test_update_task_changes_message(self):
        task_id = self.tm.create_task("build")

        self.tm.update_task(task_id, message="Processing chunk 3/10")

        task = self.tm.get_task(task_id)
        assert task.message == "Processing chunk 3/10"

    def test_complete_task(self):
        task_id = self.tm.create_task("build")
        result = {"graph_id": "g_123"}

        self.tm.complete_task(task_id, result)

        task = self.tm.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100
        assert task.result == result

    def test_fail_task(self):
        task_id = self.tm.create_task("build")

        self.tm.fail_task(task_id, "Connection timeout")

        task = self.tm.get_task(task_id)
        assert task.status == TaskStatus.FAILED
        assert task.error == "Connection timeout"

    def test_max_tasks_eviction_removes_oldest_completed(self):
        """When exceeding MAX_TASKS, oldest completed tasks are evicted."""
        original_max = TaskManager.MAX_TASKS
        TaskManager.MAX_TASKS = 5

        try:
            # Create 5 tasks and complete the first 3
            task_ids = []
            for i in range(5):
                tid = self.tm.create_task(f"type_{i}")
                task_ids.append(tid)

            # Complete first 3 tasks (making them eligible for eviction)
            for tid in task_ids[:3]:
                self.tm.complete_task(tid, {"done": True})

            # Create one more task - should trigger eviction
            new_tid = self.tm.create_task("overflow")

            # The oldest completed task should be evicted
            evicted_task = self.tm.get_task(task_ids[0])
            assert evicted_task is None

            # The new task and non-completed tasks should still exist
            assert self.tm.get_task(new_tid) is not None
            assert self.tm.get_task(task_ids[3]) is not None
            assert self.tm.get_task(task_ids[4]) is not None
        finally:
            TaskManager.MAX_TASKS = original_max

    def test_list_tasks(self):
        self.tm.create_task("build")
        self.tm.create_task("simulation")

        tasks = self.tm.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filter_by_type(self):
        self.tm.create_task("build")
        self.tm.create_task("simulation")
        self.tm.create_task("build")

        build_tasks = self.tm.list_tasks(task_type="build")
        assert len(build_tasks) == 2

    def test_task_to_dict(self):
        task_id = self.tm.create_task("report")
        task = self.tm.get_task(task_id)

        d = task.to_dict()
        assert d["task_id"] == task_id
        assert d["task_type"] == "report"
        assert d["status"] == "pending"
        assert d["progress"] == 0
        assert "created_at" in d
        assert "updated_at" in d
