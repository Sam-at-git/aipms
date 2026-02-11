"""
tests/integration/test_event_driven_flows.py

SPEC-3: Integration tests for event-driven business flows.
Verifies that events properly trigger side effects through the event bus.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from app.services.event_bus import Event
from app.models.events import EventType


class TestCheckoutCreatesCleaningTask:
    """Checkout event should auto-create cleaning task."""

    def test_checkout_event_creates_cleaning_task(self, db_session, test_event_bus):
        """Publishing a GUEST_CHECKED_OUT event creates a cleaning task."""
        from app.models.ontology import (
            Room, RoomType, RoomStatus, Task, TaskType, TaskStatus, Employee, EmployeeRole
        )
        from app.security.auth import get_password_hash

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="501", floor=5, room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY)
        db_session.add(room)
        operator = Employee(
            username="op1", password_hash=get_password_hash("123"),
            name="操作员", role=EmployeeRole.RECEPTIONIST, is_active=True
        )
        db_session.add(operator)
        db_session.commit()

        # Publish checkout event directly
        test_event_bus.publish(Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                'room_id': room.id,
                'room_number': '501',
                'guest_name': '测试客人',
                'operator_id': operator.id
            },
            source='test'
        ))

        # Verify cleaning task was created (handler uses its own session)
        task = db_session.query(Task).filter(
            Task.room_id == room.id,
            Task.task_type == TaskType.CLEANING
        ).first()
        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert "测试客人" in task.notes


class TestTaskCompletionUpdatesRoom:
    """Task completion event should update room status."""

    def test_cleaning_task_completion_marks_room_clean(self, db_session, test_event_bus):
        """Completing a cleaning task sets room status to VACANT_CLEAN."""
        from app.models.ontology import Room, RoomType, RoomStatus

        room_type = RoomType(name="大床房", base_price=Decimal("328"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="502", floor=5, room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY)
        db_session.add(room)
        db_session.commit()

        # Publish task completed event
        test_event_bus.publish(Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                'task_type': 'cleaning',
                'room_id': room.id,
                'room_number': '502'
            },
            source='test'
        ))

        # Room should now be VACANT_CLEAN
        db_session.expire(room)
        room = db_session.query(Room).filter(Room.id == room.id).first()
        assert room.status == RoomStatus.VACANT_CLEAN

    def test_non_cleaning_task_does_not_change_room(self, db_session, test_event_bus):
        """Non-cleaning task completion should not affect room status."""
        from app.models.ontology import Room, RoomType, RoomStatus

        room_type = RoomType(name="大床房", base_price=Decimal("328"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="503", floor=5, room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY)
        db_session.add(room)
        db_session.commit()

        test_event_bus.publish(Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                'task_type': 'maintenance',
                'room_id': room.id,
                'room_number': '503'
            },
            source='test'
        ))

        db_session.expire(room)
        room = db_session.query(Room).filter(Room.id == room.id).first()
        assert room.status == RoomStatus.VACANT_DIRTY  # Unchanged


class TestRoomChangeCreatesCleaningTask:
    """Room change event should create cleaning task for old room."""

    def test_room_change_creates_task_for_old_room(self, db_session, test_event_bus):
        """Changing room creates cleaning task for the old room."""
        from app.models.ontology import (
            Room, RoomType, RoomStatus, Task, TaskType, TaskStatus, Employee, EmployeeRole
        )
        from app.security.auth import get_password_hash

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        old_room = Room(room_number="601", floor=6, room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY)
        db_session.add(old_room)
        operator = Employee(
            username="op2", password_hash=get_password_hash("123"),
            name="操作员2", role=EmployeeRole.RECEPTIONIST, is_active=True
        )
        db_session.add(operator)
        db_session.commit()

        test_event_bus.publish(Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data={
                'old_room_id': old_room.id,
                'old_room_number': '601',
                'guest_name': '换房客人',
                'operator_id': operator.id
            },
            source='test'
        ))

        task = db_session.query(Task).filter(
            Task.room_id == old_room.id,
            Task.task_type == TaskType.CLEANING
        ).first()
        assert task is not None
        assert "换房客人" in task.notes
