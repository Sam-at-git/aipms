"""
Tests for app/hotel/services/task_service.py
Covers: get_tasks, get_task, get_my_tasks, get_pending_tasks, create_task,
        assign_task, start_task, complete_task, update_task, get_cleaners,
        get_task_detail, delete_task, batch_delete_tasks, get_task_summary
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Employee, EmployeeRole,
    Task, TaskType, TaskStatus, Guest,
)
from app.hotel.models.schemas import TaskCreate, TaskAssign, TaskUpdate
from app.hotel.services.task_service import TaskService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _room_type(db, name="标准间"):
    rt = RoomType(name=name, base_price=Decimal("288"), max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _room(db, rt, number="101", status=RoomStatus.VACANT_DIRTY):
    r = Room(room_number=number, floor=1, room_type_id=rt.id, status=status)
    db.add(r)
    db.flush()
    return r


def _cleaner(db, username="cleaner_svc"):
    e = Employee(
        username=username, password_hash=get_password_hash("123456"),
        name="清洁员", role=EmployeeRole.CLEANER, is_active=True)
    db.add(e)
    db.flush()
    return e


def _manager(db, username="mgr_svc"):
    e = Employee(
        username=username, password_hash=get_password_hash("123456"),
        name="经理", role=EmployeeRole.MANAGER, is_active=True)
    db.add(e)
    db.flush()
    return e


def _task(db, room, task_type=TaskType.CLEANING, status=TaskStatus.PENDING,
          assignee_id=None, priority=1, created_by=None):
    t = Task(
        room_id=room.id, task_type=task_type, status=status,
        assignee_id=assignee_id, priority=priority, created_by=created_by,
    )
    db.add(t)
    db.flush()
    return t


def _noop(event):
    pass


# ── tests ────────────────────────────────────────────────────────────

class TestGetTasks:

    def test_empty(self, db_session):
        assert TaskService(db_session, _noop).get_tasks() == []

    def test_list_all(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r)
        _task(db_session, r, task_type=TaskType.MAINTENANCE)
        db_session.commit()

        tasks = TaskService(db_session, _noop).get_tasks()
        assert len(tasks) == 2

    def test_filter_by_type(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, TaskType.CLEANING)
        _task(db_session, r, TaskType.MAINTENANCE)
        db_session.commit()

        tasks = TaskService(db_session, _noop).get_tasks(task_type=TaskType.CLEANING)
        assert len(tasks) == 1

    def test_filter_by_status(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, status=TaskStatus.PENDING)
        _task(db_session, r, status=TaskStatus.COMPLETED)
        db_session.commit()

        tasks = TaskService(db_session, _noop).get_tasks(status=TaskStatus.PENDING)
        assert len(tasks) == 1

    def test_filter_by_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        _task(db_session, r, assignee_id=c.id, status=TaskStatus.ASSIGNED)
        _task(db_session, r)
        db_session.commit()

        tasks = TaskService(db_session, _noop).get_tasks(assignee_id=c.id)
        assert len(tasks) == 1

    def test_filter_by_room(self, db_session):
        rt = _room_type(db_session)
        r1 = _room(db_session, rt, "101")
        r2 = _room(db_session, rt, "102")
        _task(db_session, r1)
        _task(db_session, r2)
        db_session.commit()

        tasks = TaskService(db_session, _noop).get_tasks(room_id=r1.id)
        assert len(tasks) == 1


class TestGetTask:

    def test_found(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r)
        db_session.commit()

        assert TaskService(db_session, _noop).get_task(t.id) is not None

    def test_not_found(self, db_session):
        assert TaskService(db_session, _noop).get_task(9999) is None


class TestGetMyTasks:

    def test_returns_assigned_and_in_progress(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        _task(db_session, r, assignee_id=c.id, status=TaskStatus.ASSIGNED)
        _task(db_session, r, assignee_id=c.id, status=TaskStatus.IN_PROGRESS)
        _task(db_session, r, assignee_id=c.id, status=TaskStatus.COMPLETED)
        _task(db_session, r, status=TaskStatus.PENDING)
        db_session.commit()

        my_tasks = TaskService(db_session, _noop).get_my_tasks(c.id)
        assert len(my_tasks) == 2


class TestGetPendingTasks:

    def test_returns_only_pending(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, status=TaskStatus.PENDING)
        _task(db_session, r, status=TaskStatus.ASSIGNED)
        db_session.commit()

        pending = TaskService(db_session, _noop).get_pending_tasks()
        assert len(pending) == 1
        assert pending[0].status == TaskStatus.PENDING


class TestCreateTask:

    def test_without_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        mgr = _manager(db_session)
        db_session.commit()

        data = TaskCreate(room_id=r.id, task_type=TaskType.CLEANING, priority=3)
        svc = TaskService(db_session, _noop)
        t = svc.create_task(data, created_by=mgr.id)
        assert t.status == TaskStatus.PENDING
        assert t.assignee_id is None

    def test_with_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        mgr = _manager(db_session)
        db_session.commit()

        data = TaskCreate(room_id=r.id, task_type=TaskType.CLEANING, assignee_id=c.id)
        t = TaskService(db_session, _noop).create_task(data, mgr.id)
        assert t.status == TaskStatus.ASSIGNED
        assert t.assignee_id == c.id

    def test_invalid_room(self, db_session):
        mgr = _manager(db_session)
        db_session.commit()

        data = TaskCreate(room_id=9999, task_type=TaskType.CLEANING)
        with pytest.raises(ValueError, match="房间不存在"):
            TaskService(db_session, _noop).create_task(data, mgr.id)

    def test_invalid_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        mgr = _manager(db_session)
        db_session.commit()

        # Manager is not a cleaner, so assignee validation fails
        data = TaskCreate(room_id=r.id, task_type=TaskType.CLEANING, assignee_id=mgr.id)
        with pytest.raises(ValueError, match="清洁员不存在或已停用"):
            TaskService(db_session, _noop).create_task(data, mgr.id)

    def test_inactive_cleaner(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session, "inactive_cleaner")
        c.is_active = False
        mgr = _manager(db_session)
        db_session.commit()

        data = TaskCreate(room_id=r.id, task_type=TaskType.CLEANING, assignee_id=c.id)
        with pytest.raises(ValueError, match="清洁员不存在或已停用"):
            TaskService(db_session, _noop).create_task(data, mgr.id)

    def test_event_published(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        mgr = _manager(db_session)
        db_session.commit()

        events = []
        data = TaskCreate(room_id=r.id, task_type=TaskType.CLEANING)
        TaskService(db_session, lambda e: events.append(e)).create_task(data, mgr.id)
        assert len(events) == 1
        assert "task.created" in events[0].event_type


class TestAssignTask:

    def test_success(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.PENDING)
        mgr = _manager(db_session)
        db_session.commit()

        data = TaskAssign(assignee_id=c.id)
        svc = TaskService(db_session, _noop)
        updated = svc.assign_task(t.id, data, assigned_by=mgr.id)
        assert updated.status == TaskStatus.ASSIGNED
        assert updated.assignee_id == c.id

    def test_reassign_from_assigned(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c1 = _cleaner(db_session, "c1")
        c2 = _cleaner(db_session, "c2")
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c1.id)
        db_session.commit()

        data = TaskAssign(assignee_id=c2.id)
        updated = TaskService(db_session, _noop).assign_task(t.id, data)
        assert updated.assignee_id == c2.id

    def test_task_not_found(self, db_session):
        c = _cleaner(db_session)
        db_session.commit()

        with pytest.raises(ValueError, match="任务不存在"):
            TaskService(db_session, _noop).assign_task(9999, TaskAssign(assignee_id=c.id))

    def test_wrong_status(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.COMPLETED, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="无法分配"):
            TaskService(db_session, _noop).assign_task(t.id, TaskAssign(assignee_id=c.id))

    def test_invalid_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r, status=TaskStatus.PENDING)
        db_session.commit()

        with pytest.raises(ValueError, match="清洁员不存在或已停用"):
            TaskService(db_session, _noop).assign_task(t.id, TaskAssign(assignee_id=9999))


class TestStartTask:

    def test_success(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        updated = TaskService(db_session, _noop).start_task(t.id, c.id)
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.started_at is not None

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="任务不存在"):
            TaskService(db_session, _noop).start_task(9999, 1)

    def test_wrong_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="只能开始分配给自己的任务"):
            TaskService(db_session, _noop).start_task(t.id, c.id + 100)

    def test_wrong_status(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.PENDING, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="无法开始"):
            TaskService(db_session, _noop).start_task(t.id, c.id)

    def test_event_published(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        events = []
        TaskService(db_session, lambda e: events.append(e)).start_task(t.id, c.id)
        assert any("task.started" in e.event_type for e in events)


class TestCompleteTask:

    def test_from_in_progress(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        db_session.commit()

        updated = TaskService(db_session, _noop).complete_task(t.id, c.id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.completed_at is not None

    def test_from_assigned(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        updated = TaskService(db_session, _noop).complete_task(t.id, c.id)
        assert updated.status == TaskStatus.COMPLETED

    def test_with_notes(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        db_session.commit()

        updated = TaskService(db_session, _noop).complete_task(t.id, c.id, notes="清洁完成")
        assert "清洁完成" in updated.notes

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="任务不存在"):
            TaskService(db_session, _noop).complete_task(9999, 1)

    def test_wrong_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="只能完成分配给自己的任务"):
            TaskService(db_session, _noop).complete_task(t.id, c.id + 100)

    def test_wrong_status(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.PENDING, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="无法完成"):
            TaskService(db_session, _noop).complete_task(t.id, c.id)

    def test_cleaning_task_creates_snapshot(self, db_session):
        """Cleaning task completion should create an undo snapshot"""
        rt = _room_type(db_session)
        r = _room(db_session, rt, status=RoomStatus.VACANT_DIRTY)
        c = _cleaner(db_session)
        t = _task(db_session, r, TaskType.CLEANING, TaskStatus.IN_PROGRESS, c.id)
        db_session.commit()

        TaskService(db_session, _noop).complete_task(t.id, c.id)
        # Verify snapshot was created by checking the DB
        from app.models.snapshots import OperationSnapshot
        snapshots = db_session.query(OperationSnapshot).all()
        assert len(snapshots) == 1
        assert snapshots[0].operation_type == "complete_task"

    def test_maintenance_task_no_snapshot(self, db_session):
        """Maintenance task completion should NOT create a snapshot"""
        rt = _room_type(db_session)
        r = _room(db_session, rt, status=RoomStatus.OUT_OF_ORDER)
        c = _cleaner(db_session)
        t = _task(db_session, r, TaskType.MAINTENANCE, TaskStatus.IN_PROGRESS, c.id)
        db_session.commit()

        TaskService(db_session, _noop).complete_task(t.id, c.id)
        from app.models.snapshots import OperationSnapshot
        snapshots = db_session.query(OperationSnapshot).all()
        assert len(snapshots) == 0

    def test_event_published(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        db_session.commit()

        events = []
        TaskService(db_session, lambda e: events.append(e)).complete_task(t.id, c.id)
        assert any("task.completed" in e.event_type for e in events)


class TestUpdateTask:

    def test_success(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r)
        db_session.commit()

        data = TaskUpdate(notes="新备注", priority=5)
        updated = TaskService(db_session, _noop).update_task(t.id, data)
        assert updated.notes == "新备注"
        assert updated.priority == 5

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="任务不存在"):
            TaskService(db_session, _noop).update_task(9999, TaskUpdate(notes="x"))


class TestGetCleaners:

    def test_returns_only_active_cleaners(self, db_session):
        _cleaner(db_session, "active1")
        c2 = _cleaner(db_session, "inactive1")
        c2.is_active = False
        _manager(db_session, "mgr1")
        db_session.commit()

        cleaners = TaskService(db_session, _noop).get_cleaners()
        assert len(cleaners) == 1
        assert cleaners[0].role == EmployeeRole.CLEANER


class TestGetTaskDetail:

    def test_found(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101")
        c = _cleaner(db_session)
        t = _task(db_session, r, assignee_id=c.id, status=TaskStatus.ASSIGNED)
        db_session.commit()

        detail = TaskService(db_session, _noop).get_task_detail(t.id)
        assert detail is not None
        assert detail["room_number"] == "101"
        assert detail["assignee_name"] == "清洁员"

    def test_not_found(self, db_session):
        assert TaskService(db_session, _noop).get_task_detail(9999) is None

    def test_without_assignee(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r)
        db_session.commit()

        detail = TaskService(db_session, _noop).get_task_detail(t.id)
        assert detail["assignee_name"] is None


class TestDeleteTask:

    def test_delete_pending(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r, status=TaskStatus.PENDING)
        db_session.commit()

        deleted = TaskService(db_session, _noop).delete_task(t.id)
        assert deleted.id == t.id

    def test_delete_assigned(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        deleted = TaskService(db_session, _noop).delete_task(t.id)
        assert deleted.id == t.id

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="任务不存在"):
            TaskService(db_session, _noop).delete_task(9999)

    def test_cannot_delete_in_progress(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        t = _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        db_session.commit()

        with pytest.raises(ValueError, match="无法删除"):
            TaskService(db_session, _noop).delete_task(t.id)

    def test_cannot_delete_completed(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        t = _task(db_session, r, status=TaskStatus.COMPLETED)
        db_session.commit()

        with pytest.raises(ValueError, match="无法删除"):
            TaskService(db_session, _noop).delete_task(t.id)


class TestBatchDeleteTasks:

    def test_delete_all_deletable(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, status=TaskStatus.PENDING)
        _task(db_session, r, status=TaskStatus.ASSIGNED)
        _task(db_session, r, status=TaskStatus.COMPLETED)
        db_session.commit()

        count = TaskService(db_session, _noop).batch_delete_tasks()
        assert count == 2  # pending + assigned, not completed

    def test_filter_by_status(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, status=TaskStatus.PENDING)
        c = _cleaner(db_session)
        _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        db_session.commit()

        count = TaskService(db_session, _noop).batch_delete_tasks(status=TaskStatus.PENDING)
        assert count == 1

    def test_filter_by_task_type(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        _task(db_session, r, TaskType.CLEANING, TaskStatus.PENDING)
        _task(db_session, r, TaskType.MAINTENANCE, TaskStatus.PENDING)
        db_session.commit()

        count = TaskService(db_session, _noop).batch_delete_tasks(task_type=TaskType.CLEANING)
        assert count == 1

    def test_filter_by_room(self, db_session):
        rt = _room_type(db_session)
        r1 = _room(db_session, rt, "101")
        r2 = _room(db_session, rt, "102")
        _task(db_session, r1, status=TaskStatus.PENDING)
        _task(db_session, r2, status=TaskStatus.PENDING)
        db_session.commit()

        count = TaskService(db_session, _noop).batch_delete_tasks(room_id=r1.id)
        assert count == 1


class TestGetTaskSummary:

    def test_empty(self, db_session):
        summary = TaskService(db_session, _noop).get_task_summary()
        assert summary == {"pending": 0, "assigned": 0, "in_progress": 0}

    def test_counts(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        c = _cleaner(db_session)
        _task(db_session, r, status=TaskStatus.PENDING)
        _task(db_session, r, status=TaskStatus.PENDING)
        _task(db_session, r, status=TaskStatus.ASSIGNED, assignee_id=c.id)
        _task(db_session, r, status=TaskStatus.IN_PROGRESS, assignee_id=c.id)
        _task(db_session, r, status=TaskStatus.COMPLETED)  # excluded
        db_session.commit()

        summary = TaskService(db_session, _noop).get_task_summary()
        assert summary["pending"] == 2
        assert summary["assigned"] == 1
        assert summary["in_progress"] == 1
