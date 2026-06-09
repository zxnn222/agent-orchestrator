from __future__ import annotations
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

class TaskStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()

@dataclass
class Task:
    """A unit of work for an agent."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None
    sub_tasks: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    result: Optional[str] = None
    agent_id: Optional[str] = None
    context: dict = field(default_factory=dict)

    def add_subtask(self, title, description="", dependencies=None):
        """Add a sub-task with optional dependency IDs."""
        sub = Task(
            title=title,
            description=description,
            parent_id=self.id,
            dependencies=dependencies or [],
        )
        self.sub_tasks.append(sub)
        return sub

    def to_dict(self):
        return {
            "id": self.id, "title": self.title,
            "description": self.description, "status": self.status.name,
            "parent_id": self.parent_id,
            "sub_tasks": [s.to_dict() for s in self.sub_tasks],
            "dependencies": self.dependencies,
            "result": self.result, "agent_id": self.agent_id,
        }

    def __repr__(self):
        return f"Task({self.id[:8]}, {self.title[:30]}, {self.status.name})"