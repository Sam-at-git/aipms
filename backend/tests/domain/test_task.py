"""测试 core.domain.task 模块"""
import pytest
from datetime import datetime

from app.hotel.domain.task import TaskState, TaskType, TaskEntity, TaskRepository
from app.models.ontology import Task, TaskStatus, TaskType as ORMTaskType, Room, RoomType


@pytest.fixture
def sample_room(db_session):
    rt = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
    db_session.add(rt)
    db_session.commit()

    room = Room(room_number="101", floor=1, room_type_id=rt.id)
    db_session.add(room)
    db_session.commit()

    task = Task(
        room_id=room.id,
        task_type=ORMTaskType.CLEANING,
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    db_session.commit()
    return task


class TestTaskEntity:
    def test_creation(self, sample_room):
        entity = TaskEntity(sample_room)
        assert entity.status == TaskState.PENDING

    def test_assign(self, db_session):
        rt = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
        db_session.add(rt)
        db_session.commit()

        room = Room(room_number="102", floor=1, room_type_id=rt.id)
        db_session.add(room)
        db_session.commit()

        from app.models.ontology import Task, TaskStatus, TaskType as ORMTaskType
        task = Task(room_id=room.id, task_type=ORMTaskType.CLEANING, status=TaskStatus.PENDING)
        db_session.add(task)
        db_session.commit()

        entity = TaskEntity(task)
        entity.assign(1)
        assert entity.status == TaskState.ASSIGNED
        assert entity.assignee_id == 1

    def test_start(self, sample_room):
        sample_room.status = TaskStatus.ASSIGNED
        sample_room.assignee_id = 1
        entity = TaskEntity(sample_room)
        entity.start()
        assert entity.status == TaskState.IN_PROGRESS

    def test_complete(self, sample_room):
        sample_room.status = TaskStatus.IN_PROGRESS
        entity = TaskEntity(sample_room)
        entity.complete()
        assert entity.status == TaskState.COMPLETED

    def test_to_dict(self, sample_room):
        entity = TaskEntity(sample_room)
        d = entity.to_dict()
        assert d["status"] == "pending"


class TestTaskRepository:
    def test_get_by_id(self, db_session, sample_room):
        repo = TaskRepository(db_session)
        entity = repo.get_by_id(sample_room.id)
        assert entity is not None

    def test_find_by_status(self, db_session, sample_room):
        repo = TaskRepository(db_session)
        pending = repo.find_by_status("pending")
        assert len(pending) >= 1


class TestTaskState:
    def test_values(self):
        assert TaskState.PENDING == "pending"
        assert TaskState.ASSIGNED == "assigned"
        assert TaskState.IN_PROGRESS == "in_progress"
        assert TaskState.COMPLETED == "completed"
