"""
Background task queue for long-running operations.

Tasks run in worker threads, never on the asyncio event loop, so the API stays
responsive while FFmpeg/PIL work is in progress. Task functions are plain
(sync) callables; if they accept a `task` argument they receive their Task to
report progress and check for cancellation.
"""

import inspect
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


FINISHED_STATUSES = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


class Task:
    """Represents a background task"""

    def __init__(self, task_id: str, name: str, func: Callable, args: list = None, kwargs: dict = None):
        self.id = task_id
        self.name = name
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now(timezone.utc)
        self.started_at = None
        self.completed_at = None

    @property
    def is_cancelled(self) -> bool:
        return self.status == TaskStatus.CANCELLED

    def set_progress(self, done: int, total: int):
        if total > 0:
            self.progress = int(done / total * 100)

    def to_dict(self):
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class BackgroundTaskQueue:
    """In-memory task queue backed by a thread pool"""

    def __init__(self, max_workers: int = 3, keep_last_n: int = 100):
        self.tasks: Dict[str, Task] = {}
        self.keep_last_n = keep_last_n
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task")
        self._lock = threading.Lock()

    def enqueue(self, name: str, func: Callable, args: list = None, kwargs: dict = None) -> str:
        """
        Enqueue a task. Safe to call from any thread.

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = Task(task_id, name, func, args, kwargs)
        with self._lock:
            self.tasks[task_id] = task
            self._cleanup_old_tasks()

        logger.info(f"Task enqueued: {name} (ID: {task_id})")
        self._executor.submit(self._run_task, task)

        return task_id

    def _run_task(self, task: Task):
        """Run a task in a worker thread (internal)"""
        if task.is_cancelled:
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        try:
            logger.info(f"Task started: {task.name} (ID: {task.id})")

            kwargs = dict(task.kwargs)
            if "task" in inspect.signature(task.func).parameters:
                kwargs["task"] = task

            task.result = task.func(*task.args, **kwargs)

            if not task.is_cancelled:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
            logger.info(f"Task {task.status.value}: {task.name} (ID: {task.id})")

        except Exception as e:
            task.error = str(e)
            if not task.is_cancelled:
                task.status = TaskStatus.FAILED
            logger.exception(f"Task failed: {task.name} (ID: {task.id})")

        finally:
            task.completed_at = datetime.now(timezone.utc)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status as dictionary"""
        task = self.get_task(task_id)
        return task.to_dict() if task else None

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task: pending tasks never start, running tasks stop at
        their next `task.is_cancelled` check.
        """
        task = self.get_task(task_id)

        if not task or task.status in FINISHED_STATUSES:
            return False

        task.status = TaskStatus.CANCELLED
        logger.info(f"Task cancelled: {task.name} (ID: {task.id})")

        return True

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list:
        """List all tasks, optionally filtered by status"""
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        return [t.to_dict() for t in tasks]

    def _cleanup_old_tasks(self):
        """Forget the oldest finished tasks beyond `keep_last_n` (caller holds the lock)"""
        finished = [t for t in self.tasks.values() if t.status in FINISHED_STATUSES]
        excess = len(finished) - self.keep_last_n
        if excess <= 0:
            return

        finished.sort(key=lambda t: t.completed_at or t.created_at)
        for task in finished[:excess]:
            del self.tasks[task.id]


# Global task queue instance
task_queue = BackgroundTaskQueue(max_workers=3)
