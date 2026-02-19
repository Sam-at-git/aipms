"""
Tests for app/hotel/services/event_handlers.py - increasing coverage.
Covers: checkout event handler, task completed handler, room changed handler,
error handling in handlers, register/unregister, missing data edge cases.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import sessionmaker

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, Task, TaskType, TaskStatus,
    Employee, EmployeeRole,
)
from app.hotel.services.event_handlers import EventHandlers, event_handlers, register_event_handlers
from app.services.event_bus import event_bus, Event, EventBus
from app.models.events import EventType
from decimal import Decimal


class TestEventHandlerCheckout:
    """Test handle_guest_checked_out handler."""

    def test_checkout_creates_cleaning_task(self, db_session, db_engine, sample_room):
        """Checkout event creates a cleaning task for the room."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                "room_id": sample_room.id,
                "room_number": sample_room.room_number,
                "guest_name": "Test Guest",
                "operator_id": 1,
            },
            source="test",
        )

        handlers.handle_guest_checked_out(event)

        # Verify task was created
        task = db_session.query(Task).filter(Task.room_id == sample_room.id).first()
        assert task is not None
        assert task.task_type == TaskType.CLEANING
        assert task.status == TaskStatus.PENDING
        assert task.priority == 2

    def test_checkout_missing_room_id(self, db_engine):
        """Checkout event with missing room_id logs warning and returns."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={"guest_name": "Test", "operator_id": 1},
            source="test",
        )

        # Should not raise
        handlers.handle_guest_checked_out(event)

    def test_checkout_handler_error(self, db_engine):
        """Checkout handler propagates session factory errors (_get_db is outside try)."""

        def failing_session_factory():
            raise Exception("DB connection failed")

        handlers = EventHandlers(db_session_factory=failing_session_factory)

        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={"room_id": 1, "guest_name": "Test"},
            source="test",
        )

        # _get_db() is called before the try block, so the exception propagates
        with pytest.raises(Exception, match="DB connection failed"):
            handlers.handle_guest_checked_out(event)


class TestEventHandlerTaskCompleted:
    """Test handle_task_completed handler."""

    def test_task_completed_updates_room_status(self, db_session, db_engine, sample_room):
        """Cleaning task completion updates room from dirty to clean."""
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.commit()

        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_type": "cleaning",
                "room_id": sample_room.id,
                "room_number": sample_room.room_number,
            },
            source="test",
        )

        handlers.handle_task_completed(event)

        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_task_completed_non_cleaning_type(self, db_session, db_engine, sample_room):
        """Non-cleaning task completion does not change room status."""
        original_status = sample_room.status

        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_type": "maintenance",
                "room_id": sample_room.id,
            },
            source="test",
        )

        handlers.handle_task_completed(event)

        db_session.refresh(sample_room)
        assert sample_room.status == original_status

    def test_task_completed_missing_room_id(self, db_engine):
        """Task completed with missing room_id logs warning."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={"task_type": "cleaning"},
            source="test",
        )

        # Should not raise
        handlers.handle_task_completed(event)

    def test_task_completed_room_not_dirty(self, db_session, db_engine, sample_room):
        """Task completed on room not in VACANT_DIRTY does nothing."""
        assert sample_room.status == RoomStatus.VACANT_CLEAN

        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_type": "cleaning",
                "room_id": sample_room.id,
            },
            source="test",
        )

        handlers.handle_task_completed(event)

        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_task_completed_handler_error(self, db_engine):
        """Task completed handler propagates session factory errors."""

        def failing_session_factory():
            raise Exception("DB connection failed")

        handlers = EventHandlers(db_session_factory=failing_session_factory)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={"task_type": "cleaning", "room_id": 1},
            source="test",
        )

        with pytest.raises(Exception, match="DB connection failed"):
            handlers.handle_task_completed(event)


class TestEventHandlerRoomChanged:
    """Test handle_room_changed handler."""

    def test_room_changed_creates_cleaning_task(self, db_session, db_engine, sample_room):
        """Room change creates cleaning task for old room."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data={
                "old_room_id": sample_room.id,
                "old_room_number": sample_room.room_number,
                "guest_name": "换房客人",
                "operator_id": 1,
            },
            source="test",
        )

        handlers.handle_room_changed(event)

        task = db_session.query(Task).filter(Task.room_id == sample_room.id).first()
        assert task is not None
        assert task.task_type == TaskType.CLEANING
        assert task.priority == 1

    def test_room_changed_missing_old_room_id(self, db_engine):
        """Room changed with missing old_room_id returns early."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        event = Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data={"guest_name": "Test"},
            source="test",
        )

        handlers.handle_room_changed(event)

    def test_room_changed_handler_error(self, db_engine):
        """Room changed handler propagates session factory errors."""

        def failing_session_factory():
            raise Exception("DB connection failed")

        handlers = EventHandlers(db_session_factory=failing_session_factory)

        event = Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data={"old_room_id": 1, "guest_name": "Test"},
            source="test",
        )

        with pytest.raises(Exception, match="DB connection failed"):
            handlers.handle_room_changed(event)


class TestEventHandlerRegistration:
    """Test handler registration and unregistration."""

    def test_register_handlers(self, db_engine):
        """Register handlers subscribes to event bus."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        test_bus = EventBus.__new__(EventBus)
        test_bus._subscribers = {}
        test_bus._event_history = []
        test_bus._subscriber_lock = __import__("threading").Lock()
        test_bus._initialized = True

        handlers.register_handlers(event_bus_instance=test_bus)
        assert handlers._registered is True

        # Calling again should be idempotent
        handlers.register_handlers(event_bus_instance=test_bus)
        assert handlers._registered is True

        subs = test_bus.get_subscribers()
        assert EventType.GUEST_CHECKED_OUT in subs
        assert EventType.TASK_COMPLETED in subs
        assert EventType.ROOM_CHANGED in subs

    def test_unregister_handlers(self, db_engine):
        """Unregister handlers removes from event bus."""
        test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        handlers = EventHandlers(db_session_factory=test_session_factory)

        test_bus = EventBus.__new__(EventBus)
        test_bus._subscribers = {}
        test_bus._event_history = []
        test_bus._subscriber_lock = __import__("threading").Lock()
        test_bus._initialized = True

        handlers.register_handlers(event_bus_instance=test_bus)
        handlers.unregister_handlers(event_bus_instance=test_bus)
        assert handlers._registered is False

    def test_dependency_injection_factories(self, db_engine):
        """Test dependency injection for task and room service factories."""
        mock_task_svc = MagicMock()
        mock_room_svc = MagicMock()

        handlers = EventHandlers(
            db_session_factory=lambda: MagicMock(),
            task_service_factory=lambda db: mock_task_svc,
            room_service_factory=lambda db: mock_room_svc,
        )

        mock_db = MagicMock()
        assert handlers._get_task_service(mock_db) is mock_task_svc
        assert handlers._get_room_service(mock_db) is mock_room_svc

    def test_default_factories(self, db_session):
        """Test default factories without injection."""
        handlers = EventHandlers(db_session_factory=lambda: db_session)

        task_svc = handlers._get_task_service(db_session)
        room_svc = handlers._get_room_service(db_session)

        from app.hotel.services.task_service import TaskService
        from app.hotel.services.room_service import RoomService
        assert isinstance(task_svc, TaskService)
        assert isinstance(room_svc, RoomService)


class TestRegisterEventHandlersFunction:
    """Test the module-level register_event_handlers function."""

    def test_register_event_handlers_function(self):
        """The register_event_handlers function calls register_handlers on the global instance."""
        # Save original state
        original_registered = event_handlers._registered

        # Reset to allow re-registration
        event_handlers._registered = False

        try:
            register_event_handlers()
            assert event_handlers._registered is True
        finally:
            # Restore
            event_handlers._registered = original_registered
