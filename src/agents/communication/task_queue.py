"""
Task queue for managing development tasks.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import heapq

from ..types import Task, TaskStatus, AgentRole


@dataclass(order=True)
class PrioritizedTask:
    """Task with priority for queue ordering."""
    priority: int
    task: Task = field(compare=False)


class TaskQueue:
    """
    Priority queue for development tasks.

    Tasks are ordered by:
    1. Dependencies (tasks with no deps first)
    2. Priority (lower number = higher priority)
    3. Creation time (FIFO for same priority)
    """

    def __init__(self):
        self._queue: List[PrioritizedTask] = []
        self._tasks: Dict[str, Task] = {}
        self._completed: Dict[str, Task] = {}

    def add(self, task: Task, priority: int = 5) -> None:
        """Add a task to the queue."""
        self._tasks[task.id] = task
        heapq.heappush(self._queue, PrioritizedTask(priority=priority, task=task))

    def add_batch(self, tasks: List[Task], base_priority: int = 5) -> None:
        """Add multiple tasks, respecting dependencies."""
        # Sort by dependency count (fewer deps = higher priority)
        sorted_tasks = sorted(tasks, key=lambda t: len(t.dependencies))

        for i, task in enumerate(sorted_tasks):
            self.add(task, priority=base_priority + i)

    def pop(self) -> Optional[Task]:
        """
        Get the next ready task.

        A task is ready if all its dependencies are completed.
        """
        # Find first task with all deps satisfied
        ready_items = []
        not_ready = []

        while self._queue:
            item = heapq.heappop(self._queue)
            if self._deps_satisfied(item.task):
                # Put back the not-ready items
                for nr in not_ready:
                    heapq.heappush(self._queue, nr)
                return item.task
            else:
                not_ready.append(item)

        # No ready tasks, put everything back
        for item in not_ready:
            heapq.heappush(self._queue, item)

        return None

    def peek(self) -> Optional[Task]:
        """Peek at the next ready task without removing it."""
        task = self.pop()
        if task:
            # Re-add with high priority to maintain order
            self.add(task, priority=0)
        return task

    def complete(self, task_id: str) -> bool:
        """Mark a task as completed."""
        if task_id in self._tasks:
            task = self._tasks.pop(task_id)
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.utcnow()
            self._completed[task_id] = task
            return True
        return False

    def fail(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as failed/blocked."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.BLOCKED
            task.metadata["failure_reason"] = reason
            task.updated_at = datetime.utcnow()
            return True
        return False

    def _deps_satisfied(self, task: Task) -> bool:
        """Check if all dependencies are completed."""
        return all(dep_id in self._completed for dep_id in task.dependencies)

    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id) or self._completed.get(task_id)

    def get_by_agent(self, agent: AgentRole) -> List[Task]:
        """Get all tasks assigned to an agent."""
        return [t for t in self._tasks.values() if t.assigned_to == agent]

    def get_pending(self) -> List[Task]:
        """Get all pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_in_progress(self) -> List[Task]:
        """Get all in-progress tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS]

    def get_blocked(self) -> List[Task]:
        """Get all blocked tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.BLOCKED]

    def get_completed(self) -> List[Task]:
        """Get all completed tasks."""
        return list(self._completed.values())

    @property
    def size(self) -> int:
        """Get queue size."""
        return len(self._queue)

    @property
    def total_tasks(self) -> int:
        """Get total task count (pending + completed)."""
        return len(self._tasks) + len(self._completed)

    def clear(self) -> None:
        """Clear all tasks."""
        self._queue.clear()
        self._tasks.clear()
        self._completed.clear()

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        return {
            "queue_size": self.size,
            "pending": len(self.get_pending()),
            "in_progress": len(self.get_in_progress()),
            "blocked": len(self.get_blocked()),
            "completed": len(self._completed),
            "total": self.total_tasks,
        }
