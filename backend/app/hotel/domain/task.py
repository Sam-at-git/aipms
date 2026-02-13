"""
core/domain/task.py

Task 领域实体 - OODA 运行时的领域层
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import logging

from core.ontology.base import BaseEntity
from core.engine.state_machine import StateMachine, StateMachineConfig, StateTransition

if TYPE_CHECKING:
    from app.models.ontology import Task

logger = logging.getLogger(__name__)


class TaskState(str):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskType(str):
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"


def _create_task_state_machine(initial_status: str) -> StateMachine:
    return StateMachine(
        config=StateMachineConfig(
            name="Task",
            states=[TaskState.PENDING, TaskState.ASSIGNED, TaskState.IN_PROGRESS, TaskState.COMPLETED],
            transitions=[
                StateTransition(TaskState.PENDING, TaskState.ASSIGNED, "assign"),
                StateTransition(TaskState.ASSIGNED, TaskState.IN_PROGRESS, "start"),
                StateTransition(TaskState.IN_PROGRESS, TaskState.COMPLETED, "complete"),
            ],
            initial_state=initial_status,
        )
    )


class TaskEntity(BaseEntity):
    def __init__(self, orm_model: "Task"):
        self._orm_model = orm_model
        initial_status = orm_model.status.value if orm_model.status else TaskState.PENDING
        self._state_machine = _create_task_state_machine(initial_status)

    @property
    def id(self) -> int:
        return self._orm_model.id

    @property
    def room_id(self) -> int:
        return self._orm_model.room_id

    @property
    def task_type(self) -> str:
        return self._orm_model.task_type.value if self._orm_model.task_type else TaskType.CLEANING

    @property
    def status(self) -> str:
        return self._orm_model.status.value if self._orm_model.status else TaskState.PENDING

    @property
    def assignee_id(self) -> Optional[int]:
        return self._orm_model.assignee_id

    @property
    def description(self) -> Optional[str]:
        return self._orm_model.notes

    @property
    def created_at(self) -> datetime:
        return self._orm_model.created_at

    def assign(self, assignee_id: int) -> None:
        from app.models.ontology import TaskStatus
        if not self._state_machine.can_transition_to(TaskState.ASSIGNED, "assign"):
            raise ValueError(f"任务状态 {self.status} 不允许分配")
        self._state_machine.transition_to(TaskState.ASSIGNED, "assign")
        self._orm_model.status = TaskStatus.ASSIGNED
        self._orm_model.assignee_id = assignee_id

    def start(self) -> None:
        from app.models.ontology import TaskStatus
        if not self._state_machine.can_transition_to(TaskState.IN_PROGRESS, "start"):
            raise ValueError(f"任务状态 {self.status} 不允许开始")
        self._state_machine.transition_to(TaskState.IN_PROGRESS, "start")
        self._orm_model.status = TaskStatus.IN_PROGRESS

    def complete(self) -> None:
        from app.models.ontology import TaskStatus
        if not self._state_machine.can_transition_to(TaskState.COMPLETED, "complete"):
            raise ValueError(f"任务状态 {self.status} 不允许完成")
        self._state_machine.transition_to(TaskState.COMPLETED, "complete")
        self._orm_model.status = TaskStatus.COMPLETED

    def is_pending(self) -> bool:
        return self.status == TaskState.PENDING

    def is_completed(self) -> bool:
        return self.status == TaskState.COMPLETED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "task_type": self.task_type,
            "status": self.status,
            "assignee_id": self.assignee_id,
            "description": self.description,
            "is_pending": self.is_pending(),
            "is_completed": self.is_completed(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskRepository:
    def __init__(self, db_session):
        self._db = db_session

    def get_by_id(self, task_id: int) -> Optional[TaskEntity]:
        from app.models.ontology import Task
        orm_model = self._db.query(Task).filter(Task.id == task_id).first()
        if orm_model is None:
            return None
        return TaskEntity(orm_model)

    def find_by_room(self, room_id: int) -> List[TaskEntity]:
        from app.models.ontology import Task
        orm_models = self._db.query(Task).filter(Task.room_id == room_id).all()
        return [TaskEntity(m) for m in orm_models]

    def find_by_status(self, status: str) -> List[TaskEntity]:
        from app.models.ontology import Task, TaskStatus
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            return []
        orm_models = self._db.query(Task).filter(Task.status == status_enum).all()
        return [TaskEntity(m) for m in orm_models]

    def find_pending(self) -> List[TaskEntity]:
        return self.find_by_status(TaskState.PENDING)

    def find_by_assignee(self, assignee_id: int) -> List[TaskEntity]:
        from app.models.ontology import Task
        orm_models = self._db.query(Task).filter(Task.assignee_id == assignee_id).all()
        return [TaskEntity(m) for m in orm_models]

    def save(self, task: TaskEntity) -> None:
        self._db.add(task._orm_model)
        self._db.commit()

    def list_all(self) -> List[TaskEntity]:
        from app.models.ontology import Task
        orm_models = self._db.query(Task).all()
        return [TaskEntity(m) for m in orm_models]


__all__ = ["TaskState", "TaskType", "TaskEntity", "TaskRepository"]
