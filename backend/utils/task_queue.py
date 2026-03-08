"""
Simple background task queue for long-running operations
"""

import asyncio
import uuid
import logging
import inspect
from datetime import datetime
from typing import Dict, Callable, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
    
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
    """Simple in-memory task queue for background operations"""
    
    def __init__(self, max_workers: int = 3):
        self.tasks: Dict[str, Task] = {}
        self.max_workers = max_workers
        self.running_tasks = set()
        self.loop = None
    
    def enqueue(self, name: str, func: Callable, args: list = None, kwargs: dict = None) -> str:
        """
        Enqueue a task
        
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = Task(task_id, name, func, args, kwargs)
        self.tasks[task_id] = task
        
        logger.info(f"Task enqueued: {name} (ID: {task_id})")
        
        # Try to run task immediately
        asyncio.create_task(self._run_task(task_id))
        
        return task_id
    
    async def _run_task(self, task_id: str):
        """Run a task (internal)"""
        task = self.tasks[task_id]
        
        # Wait if at max workers
        while len(self.running_tasks) >= self.max_workers:
            await asyncio.sleep(0.5)
        
        self.running_tasks.add(task_id)
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        try:
            logger.info(f"Task started: {task.name} (ID: {task_id})")
            
            # Run the async or sync function
            kwargs = dict(task.kwargs)
            if "task" in inspect.signature(task.func).parameters:
                kwargs["task"] = task

            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **kwargs)
            else:
                result = task.func(*task.args, **kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            
            logger.info(f"Task completed: {task.name} (ID: {task_id})")
        
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            logger.error(f"Task failed: {task.name} (ID: {task_id}): {e}")
        
        finally:
            task.completed_at = datetime.utcnow()
            self.running_tasks.remove(task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status as dictionary"""
        task = self.get_task(task_id)
        return task.to_dict() if task else None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        task = self.get_task(task_id)
        
        if not task:
            return False
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        task.status = TaskStatus.CANCELLED
        logger.info(f"Task cancelled: {task.name} (ID: {task_id})")
        
        return True
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> list:
        """List all tasks, optionally filtered by status"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return [t.to_dict() for t in tasks]
    
    def cleanup_old_tasks(self, keep_last_n: int = 100):
        """Remove old completed tasks to free memory"""
        if len(self.tasks) <= keep_last_n:
            return
        
        # Sort by completed_at (oldest first)
        completed = [
            (tid, t) for tid, t in self.tasks.items()
            if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        ]
        completed.sort(key=lambda x: x[1].completed_at or datetime.utcnow())
        
        # Remove oldest
        to_remove = len(completed) - keep_last_n
        for task_id, _ in completed[:to_remove]:
            del self.tasks[task_id]
            logger.info(f"Cleaned up old task: {task_id}")


# Global task queue instance
task_queue = BackgroundTaskQueue(max_workers=3)
