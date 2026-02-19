"""
Comprehensive tests for UndoService to increase coverage.

Tests all undo rollback paths (_undo_checkin, _undo_checkout,
_undo_extend_stay, _undo_change_room, _undo_complete_task,
_undo_payment), helper functions, and edge cases.
"""
import json
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import MagicMock

from app.services.undo_service import (
    UndoService,
    create_checkin_snapshot,
    create_checkout_snapshot,
)
from app.models.snapshots import OperationSnapshot, OperationType
from app.hotel.models.ontology import (
    StayRecord, StayRecordStatus, Room, RoomStatus,
    Reservation, ReservationStatus, Task, TaskStatus, TaskType,
    Bill, Payment, PaymentMethod, Employee, EmployeeRole,
)
from app.security.auth import get_password_hash


@pytest.fixture
def operator(db_session):
    """Create a test operator."""
    emp = Employee(
        username="undo_operator",
        password_hash=get_password_hash("123456"),
        name="Undo Operator",
        role=EmployeeRole.MANAGER,
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def mock_publisher():
    return MagicMock()


@pytest.fixture
def undo_service(db_session, mock_publisher):
    return UndoService(db_session, event_publisher=mock_publisher)


# ========== get_snapshot_by_id ==========


class TestGetSnapshotById:
    """Tests for get_snapshot_by_id()."""

    def test_returns_snapshot(self, undo_service, operator):
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={"room": {"status": "vacant_clean"}},
            after_state={"room": {"status": "occupied"}},
            operator_id=operator.id,
        )
        found = undo_service.get_snapshot_by_id(snapshot.id)
        assert found is not None
        assert found.snapshot_uuid == snapshot.snapshot_uuid

    def test_returns_none_for_missing(self, undo_service):
        found = undo_service.get_snapshot_by_id(99999)
        assert found is None


# ========== get_undoable_operations with entity_id filter ==========


class TestGetUndoableOperationsEntityIdFilter:
    """Tests for get_undoable_operations() with entity_id filter."""

    def test_filter_by_entity_id(self, undo_service, operator):
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=10,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=20,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        ops = undo_service.get_undoable_operations(entity_id=10)
        assert len(ops) == 1
        assert ops[0].entity_id == 10

    def test_excludes_already_undone(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        snap.is_undone = True
        db_session.flush()

        ops = undo_service.get_undoable_operations()
        assert len(ops) == 0

    def test_excludes_expired(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        snap.expires_at = datetime.now() - timedelta(hours=1)
        db_session.flush()

        ops = undo_service.get_undoable_operations()
        assert len(ops) == 0


# ========== get_undo_history ==========


class TestGetUndoHistory:
    """Tests for get_undo_history()."""

    def test_returns_only_undone_snapshots(self, undo_service, db_session, operator):
        snap1 = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        snap1.is_undone = True
        snap1.undone_time = datetime.now()

        # Not undone
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=2,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        history = undo_service.get_undo_history()
        assert len(history) == 1
        assert history[0].is_undone is True

    def test_limit(self, undo_service, db_session, operator):
        for i in range(5):
            snap = undo_service.create_snapshot(
                operation_type=OperationType.CHECK_IN,
                entity_type="stay_record",
                entity_id=i,
                before_state={},
                after_state={},
                operator_id=operator.id,
            )
            snap.is_undone = True
            snap.undone_time = datetime.now()
        db_session.flush()

        history = undo_service.get_undo_history(limit=3)
        assert len(history) == 3


# ========== undo_operation with invalid snapshot ==========


class TestUndoOperationErrors:
    """Tests for undo_operation() error cases."""

    def test_nonexistent_snapshot_raises(self, undo_service, operator):
        with pytest.raises(ValueError, match="不存在"):
            undo_service.undo_operation("nonexistent-uuid", operator.id)

    def test_already_undone_raises(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        snap.is_undone = True
        db_session.flush()

        with pytest.raises(ValueError, match="已撤销"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_expired_snapshot_raises(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        snap.expires_at = datetime.now() - timedelta(hours=1)
        db_session.flush()

        with pytest.raises(ValueError, match="过期"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)


# ========== _execute_rollback: unsupported type ==========


class TestUnsupportedOperationType:
    """Tests for _execute_rollback() with unsupported type."""

    def test_unsupported_raises_value_error(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type="unsupported_type",
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="不支持撤销"):
            undo_service._execute_rollback(snap)


# ========== _undo_checkin ==========


class TestUndoCheckin:
    """Tests for _undo_checkin()."""

    def test_undo_checkin_without_reservation(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        # Set up: create stay record + bill, room occupied
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(stay_record_id=stay.id, total_amount=Decimal("288.00"))
        db_session.add(bill)
        sample_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "vacant_clean",
                }
            },
            after_state={"stay_record_id": stay.id},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "入住已撤销" in result["message"]

        # Stay record should be deleted
        assert db_session.query(StayRecord).filter(StayRecord.id == stay.id).first() is None

        # Room should be restored
        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_undo_checkin_with_reservation(
        self, undo_service, db_session, sample_room, sample_guest, sample_room_type, operator
    ):
        # Create reservation
        reservation = Reservation(
            reservation_no="R202501001",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=datetime.now().date(),
            check_out_date=datetime.now().date() + timedelta(days=2),
            status=ReservationStatus.CHECKED_IN,
        )
        db_session.add(reservation)
        db_session.flush()

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            reservation_id=reservation.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=2),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(stay_record_id=stay.id, total_amount=Decimal("576.00"))
        db_session.add(bill)
        sample_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "vacant_clean",
                },
                "reservation": {
                    "id": reservation.id,
                    "status": "confirmed",
                },
            },
            after_state={"stay_record_id": stay.id},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "入住已撤销" in result["message"]

        # Reservation should be restored
        db_session.refresh(reservation)
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_undo_checkin_stay_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=99999,
            before_state={"room": {"id": 1, "status": "vacant_clean"}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="住宿记录不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_undo_checkin_no_bill(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """Checkin undo when there is no bill attached."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        sample_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "vacant_clean",
                }
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        assert "入住已撤销" in result["message"]


# ========== _undo_checkout ==========


class TestUndoCheckout:
    """Tests for _undo_checkout()."""

    def test_undo_checkout_basic(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            check_out_time=datetime.now(),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.CHECKED_OUT,
            created_by=operator.id,
        )
        db_session.add(stay)
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "stay_record": {"id": stay.id, "status": "active"},
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "occupied",
                },
            },
            after_state={
                "stay_record_status": "checked_out",
                "room_status": "vacant_dirty",
            },
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "退房已撤销" in result["message"]

        db_session.refresh(stay)
        assert stay.status == StayRecordStatus.ACTIVE
        assert stay.check_out_time is None

        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.OCCUPIED

    def test_undo_checkout_with_auto_task(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """When checkout created an auto-cleaning task, undo should delete it."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            check_out_time=datetime.now(),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.CHECKED_OUT,
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        # Auto-created pending task
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=operator.id,
        )
        db_session.add(task)
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "stay_record": {"id": stay.id, "status": "active"},
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "occupied",
                },
            },
            after_state={
                "stay_record_status": "checked_out",
                "room_status": "vacant_dirty",
                "created_task_id": task.id,
            },
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "退房已撤销" in result["message"]

        # Task should be deleted (it was pending)
        assert db_session.query(Task).filter(Task.id == task.id).first() is None

    def test_undo_checkout_auto_task_not_pending(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """If auto-task is already started, it should not be deleted."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            check_out_time=datetime.now(),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.CHECKED_OUT,
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,  # Already started
            created_by=operator.id,
        )
        db_session.add(task)
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "stay_record": {"id": stay.id, "status": "active"},
                "room": {"id": sample_room.id, "status": "occupied"},
            },
            after_state={
                "stay_record_status": "checked_out",
                "created_task_id": task.id,
            },
            operator_id=operator.id,
        )
        db_session.flush()

        undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        # Task should still exist
        assert db_session.query(Task).filter(Task.id == task.id).first() is not None

    def test_undo_checkout_with_reservation(
        self, undo_service, db_session, sample_room, sample_guest, sample_room_type, operator
    ):
        """Undo checkout should restore reservation status to CHECKED_IN."""
        reservation = Reservation(
            reservation_no="R202501002",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=datetime.now().date() - timedelta(days=1),
            check_out_date=datetime.now().date(),
            status=ReservationStatus.COMPLETED,
        )
        db_session.add(reservation)
        db_session.flush()

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            reservation_id=reservation.id,
            check_in_time=datetime.now() - timedelta(days=1),
            check_out_time=datetime.now(),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.CHECKED_OUT,
            created_by=operator.id,
        )
        db_session.add(stay)
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "stay_record": {"id": stay.id, "status": "active"},
                "room": {"id": sample_room.id, "status": "occupied"},
            },
            after_state={"stay_record_status": "checked_out"},
            operator_id=operator.id,
        )
        db_session.flush()

        undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        db_session.refresh(reservation)
        assert reservation.status == ReservationStatus.CHECKED_IN

    def test_undo_checkout_stay_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=99999,
            before_state={"stay_record": {"status": "active"}, "room": {}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="住宿记录不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)


# ========== _undo_extend_stay ==========


class TestUndoExtendStay:
    """Tests for _undo_extend_stay()."""

    def test_restores_dates_and_bill(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        original_checkout = datetime.now().date() + timedelta(days=1)
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=original_checkout + timedelta(days=3),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("1152.00"),
        )
        db_session.add(bill)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.EXTEND_STAY,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "expected_check_out": original_checkout.isoformat(),
                "bill": {"total_amount": 288.00},
            },
            after_state={
                "expected_check_out": (original_checkout + timedelta(days=3)).isoformat(),
                "bill": {"total_amount": 1152.00},
            },
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "续住已撤销" in result["message"]

        db_session.refresh(stay)
        assert stay.expected_check_out == original_checkout

        db_session.refresh(bill)
        assert float(bill.total_amount) == 288.00

    def test_stay_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.EXTEND_STAY,
            entity_type="stay_record",
            entity_id=99999,
            before_state={"expected_check_out": "2025-01-15"},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="住宿记录不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_no_bill_state(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """Extend stay undo when no bill state is recorded."""
        original_checkout = datetime.now().date() + timedelta(days=1)
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=original_checkout + timedelta(days=2),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.EXTEND_STAY,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "expected_check_out": original_checkout.isoformat(),
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        assert "续住已撤销" in result["message"]

        db_session.flush()
        db_session.expire_all()
        db_session.refresh(stay)
        assert stay.expected_check_out == original_checkout


# ========== _undo_change_room ==========


class TestUndoChangeRoom:
    """Tests for _undo_change_room()."""

    def test_restores_room_assignments(
        self, undo_service, db_session, sample_room, sample_room_102, sample_guest, operator
    ):
        old_room = sample_room
        new_room = sample_room_102

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=new_room.id,  # Now in new room
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        old_room.status = RoomStatus.VACANT_DIRTY
        new_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHANGE_ROOM,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "stay_record": {"room_id": old_room.id},
                "old_room": {"id": old_room.id, "status": "occupied"},
                "new_room": {"id": new_room.id, "status": "vacant_clean"},
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "换房已撤销" in result["message"]

        db_session.refresh(stay)
        assert stay.room_id == old_room.id

        db_session.refresh(old_room)
        assert old_room.status == RoomStatus.OCCUPIED

        db_session.refresh(new_room)
        assert new_room.status == RoomStatus.VACANT_CLEAN

    def test_stay_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHANGE_ROOM,
            entity_type="stay_record",
            entity_id=99999,
            before_state={"stay_record": {"room_id": 1}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="住宿记录不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_no_room_states(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """Change room undo with empty room states."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHANGE_ROOM,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={"stay_record": {}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        assert "换房已撤销" in result["message"]


# ========== _undo_complete_task ==========


class TestUndoCompleteTask:
    """Tests for _undo_complete_task()."""

    def test_restores_task_status(
        self, undo_service, db_session, sample_room, operator
    ):
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now(),
            created_by=operator.id,
        )
        db_session.add(task)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.COMPLETE_TASK,
            entity_type="task",
            entity_id=task.id,
            before_state={
                "task": {"status": "in_progress"},
            },
            after_state={"task": {"status": "completed"}},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "任务完成已撤销" in result["message"]

        db_session.refresh(task)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.completed_at is None

    def test_restores_room_status_for_cleaning_task(
        self, undo_service, db_session, sample_room, operator
    ):
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now(),
            created_by=operator.id,
        )
        db_session.add(task)
        sample_room.status = RoomStatus.VACANT_CLEAN  # Set by task completion
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.COMPLETE_TASK,
            entity_type="task",
            entity_id=task.id,
            before_state={
                "task": {"status": "in_progress"},
                "room": {"id": sample_room.id, "status": "vacant_dirty"},
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_DIRTY

    def test_task_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.COMPLETE_TASK,
            entity_type="task",
            entity_id=99999,
            before_state={"task": {"status": "in_progress"}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="任务不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_no_room_state(self, undo_service, db_session, sample_room, operator):
        """Complete task undo without room state in before_state."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.MAINTENANCE,
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now(),
            created_by=operator.id,
        )
        db_session.add(task)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.COMPLETE_TASK,
            entity_type="task",
            entity_id=task.id,
            before_state={
                "task": {"status": "assigned"},
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        assert "任务完成已撤销" in result["message"]


# ========== _undo_payment ==========


class TestUndoPayment:
    """Tests for _undo_payment()."""

    def test_undo_payment_restores_bill(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
            paid_amount=Decimal("288.00"),
        )
        db_session.add(bill)
        db_session.flush()

        payment = Payment(
            bill_id=bill.id,
            amount=Decimal("288.00"),
            method=PaymentMethod.CASH,
            created_by=operator.id,
        )
        db_session.add(payment)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.ADD_PAYMENT,
            entity_type="payment",
            entity_id=payment.id,
            before_state={
                "bill": {
                    "id": bill.id,
                    "paid_amount": 0,
                },
            },
            after_state={"bill": {"paid_amount": 288.00}},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        assert "支付已撤销" in result["message"]

        # Payment should be deleted
        assert db_session.query(Payment).filter(Payment.id == payment.id).first() is None

        # Bill paid_amount should be restored
        db_session.refresh(bill)
        assert float(bill.paid_amount) == 0

    def test_payment_not_found(self, undo_service, db_session, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.ADD_PAYMENT,
            entity_type="payment",
            entity_id=99999,
            before_state={"bill": {"id": 1, "paid_amount": 0}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        with pytest.raises(ValueError, match="支付记录不存在"):
            undo_service.undo_operation(snap.snapshot_uuid, operator.id)

    def test_no_bill_state(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        """Payment undo when no bill state is recorded -- payment is still deleted."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("100.00"),
            paid_amount=Decimal("50.00"),
        )
        db_session.add(bill)
        db_session.flush()

        payment = Payment(
            bill_id=bill.id,
            amount=Decimal("50.00"),
            method=PaymentMethod.CARD,
            created_by=operator.id,
        )
        db_session.add(payment)
        db_session.flush()
        payment_id = payment.id

        snap = undo_service.create_snapshot(
            operation_type=OperationType.ADD_PAYMENT,
            entity_type="payment",
            entity_id=payment_id,
            before_state={},  # No bill state
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        result = undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        assert "支付已撤销" in result["message"]
        # Flush and expire to see the deletion
        db_session.flush()
        db_session.expire_all()
        assert db_session.query(Payment).filter(Payment.id == payment_id).first() is None


# ========== undo_operation event publishing ==========


class TestUndoOperationPublishesEvent:
    """Tests that undo_operation publishes an event."""

    def test_event_published_on_success(
        self, undo_service, mock_publisher, db_session, sample_room, sample_guest, operator
    ):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "vacant_clean",
                }
            },
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        undo_service.undo_operation(snap.snapshot_uuid, operator.id)

        mock_publisher.assert_called_once()
        published_event = mock_publisher.call_args[0][0]
        assert published_event.event_type == "operation.undone"
        assert published_event.source == "undo_service"

    def test_snapshot_marked_as_undone(
        self, undo_service, db_session, sample_room, sample_guest, operator
    ):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=operator.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay.id,
            before_state={"room": {"id": sample_room.id, "status": "vacant_clean"}},
            after_state={},
            operator_id=operator.id,
        )
        db_session.flush()

        undo_service.undo_operation(snap.snapshot_uuid, operator.id)
        db_session.flush()

        db_session.refresh(snap)
        assert snap.is_undone is True
        assert snap.undone_by == operator.id
        assert snap.undone_time is not None


# ========== create_checkin_snapshot helper ==========


class TestCreateCheckinSnapshotHelper:
    """Tests for the module-level create_checkin_snapshot() function."""

    def test_without_reservation(self, db_session, sample_room, sample_guest, sample_employee):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = create_checkin_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
            operator_id=sample_employee.id,
        )

        assert snap.operation_type == "check_in"
        assert snap.entity_type == "stay_record"
        before = json.loads(snap.before_state)
        assert "room" in before
        assert "reservation" not in before

    def test_with_reservation(
        self, db_session, sample_room, sample_guest, sample_room_type, sample_employee
    ):
        reservation = Reservation(
            reservation_no="R202501010",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=datetime.now().date(),
            check_out_date=datetime.now().date() + timedelta(days=1),
            status=ReservationStatus.CONFIRMED,
        )
        db_session.add(reservation)
        db_session.flush()

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            reservation_id=reservation.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = create_checkin_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
            reservation=reservation,
            operator_id=sample_employee.id,
        )

        before = json.loads(snap.before_state)
        assert "reservation" in before
        assert before["reservation"]["id"] == reservation.id
        assert before["reservation"]["status"] == "confirmed"

    def test_default_operator_id(self, db_session, sample_room, sample_guest, sample_employee):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = create_checkin_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
        )
        assert snap.operator_id == 0


# ========== create_checkout_snapshot helper ==========


class TestCreateCheckoutSnapshotHelper:
    """Tests for the module-level create_checkout_snapshot() function."""

    def test_basic_checkout(self, db_session, sample_room, sample_guest, sample_employee):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.ACTIVE,
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        sample_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = create_checkout_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
            operator_id=sample_employee.id,
        )

        assert snap.operation_type == "check_out"
        before = json.loads(snap.before_state)
        assert before["stay_record"]["status"] == "active"
        assert before["room"]["status"] == "occupied"

        after = json.loads(snap.after_state)
        assert after["stay_record_status"] == "checked_out"
        assert after["created_task_id"] is None

    def test_with_created_task_id(self, db_session, sample_room, sample_guest, sample_employee):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.ACTIVE,
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        sample_room.status = RoomStatus.OCCUPIED
        db_session.flush()

        snap = create_checkout_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
            created_task_id=42,
            operator_id=sample_employee.id,
        )

        after = json.loads(snap.after_state)
        assert after["created_task_id"] == 42

    def test_default_operator_id(self, db_session, sample_room, sample_guest, sample_employee):
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=datetime.now().date(),
            status=StayRecordStatus.ACTIVE,
            created_by=sample_employee.id,
        )
        db_session.add(stay)
        db_session.flush()

        snap = create_checkout_snapshot(
            db=db_session,
            stay_record=stay,
            room=sample_room,
        )
        assert snap.operator_id == 0


# ========== create_snapshot with related_snapshots ==========


class TestCreateSnapshotRelatedSnapshots:
    """Tests for create_snapshot with related_snapshots parameter."""

    def test_stores_related_snapshots(self, undo_service, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
            related_snapshots=["uuid-1", "uuid-2"],
        )
        related = json.loads(snap.related_snapshots)
        assert related == ["uuid-1", "uuid-2"]

    def test_empty_related_snapshots(self, undo_service, operator):
        snap = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=operator.id,
        )
        related = json.loads(snap.related_snapshots)
        assert related == []
