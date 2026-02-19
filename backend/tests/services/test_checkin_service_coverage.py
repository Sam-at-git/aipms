"""
Tests for app/hotel/services/checkin_service.py - increasing coverage.
Covers: walkin checkin edge cases, reservation-based checkin errors,
room availability checks, deposit handling, event publishing, extend stay,
change room operations.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Bill, Employee, EmployeeRole,
)
from app.hotel.models.schemas import (
    WalkInCheckIn, CheckInFromReservation, ExtendStay, ChangeRoom,
)
from app.hotel.services.checkin_service import CheckInService
from app.hotel.models.ontology import Bill


@pytest.fixture
def checkin_service(db_session):
    """CheckInService with noop event publisher."""
    return CheckInService(db_session, event_publisher=lambda e: None)


@pytest.fixture
def make_reservation(db_session, sample_guest, sample_room_type):
    """Factory to create a confirmed reservation."""
    def _make(**kwargs):
        defaults = {
            "reservation_no": f"R-TEST-{datetime.now().strftime('%f')}",
            "guest_id": sample_guest.id,
            "room_type_id": sample_room_type.id,
            "check_in_date": date.today(),
            "check_out_date": date.today() + timedelta(days=1),
            "status": ReservationStatus.CONFIRMED,
        }
        defaults.update(kwargs)
        rsv = Reservation(**defaults)
        db_session.add(rsv)
        db_session.commit()
        db_session.refresh(rsv)
        return rsv
    return _make


class TestWalkInCheckIn:
    """Test walk-in check-in scenarios."""

    def test_walkin_success(
        self, checkin_service, db_session, sample_room_type, sample_room
    ):
        """Successful walk-in check-in."""
        data = WalkInCheckIn(
            guest_name="新客人",
            guest_phone="13900139001",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=2),
            deposit_amount=200,
        )
        stay = checkin_service.walk_in_check_in(data, operator_id=1)
        assert stay.status == StayRecordStatus.ACTIVE
        assert stay.deposit_amount == Decimal("200")
        assert stay.room.status == RoomStatus.OCCUPIED
        assert stay.bill is not None

    def test_walkin_room_not_found(self, checkin_service):
        """Walk-in with non-existent room."""
        data = WalkInCheckIn(
            guest_name="客人",
            guest_phone="13900000000",
            room_id=99999,
            expected_check_out=date.today() + timedelta(days=1),
        )
        with pytest.raises(ValueError, match="房间不存在"):
            checkin_service.walk_in_check_in(data, operator_id=1)

    def test_walkin_room_occupied(
        self, checkin_service, db_session, sample_room
    ):
        """Walk-in with occupied room."""
        sample_room.status = RoomStatus.OCCUPIED
        db_session.commit()

        data = WalkInCheckIn(
            guest_name="客人",
            guest_phone="13900000001",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
        )
        with pytest.raises(ValueError, match="无法入住"):
            checkin_service.walk_in_check_in(data, operator_id=1)

    def test_walkin_room_out_of_order(
        self, checkin_service, db_session, sample_room
    ):
        """Walk-in with out-of-order room."""
        sample_room.status = RoomStatus.OUT_OF_ORDER
        db_session.commit()

        data = WalkInCheckIn(
            guest_name="客人",
            guest_phone="13900000002",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
        )
        with pytest.raises(ValueError, match="无法入住"):
            checkin_service.walk_in_check_in(data, operator_id=1)

    def test_walkin_existing_guest(
        self, checkin_service, db_session, sample_room, sample_guest
    ):
        """Walk-in for existing guest (phone match)."""
        data = WalkInCheckIn(
            guest_name="张三",
            guest_phone="13800138000",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
        )
        stay = checkin_service.walk_in_check_in(data, operator_id=1)
        assert stay.guest_id == sample_guest.id

    def test_walkin_dirty_room_allowed(
        self, checkin_service, db_session, sample_room
    ):
        """Walk-in into dirty room is allowed (some hotels allow it)."""
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.commit()

        data = WalkInCheckIn(
            guest_name="紧急客人",
            guest_phone="13900000003",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
        )
        # Dirty room should be allowed (checkin checks vacant_clean or vacant_dirty)
        stay = checkin_service.walk_in_check_in(data, operator_id=1)
        assert stay.status == StayRecordStatus.ACTIVE

    def test_walkin_zero_deposit(
        self, checkin_service, db_session, sample_room
    ):
        """Walk-in with zero deposit."""
        data = WalkInCheckIn(
            guest_name="无押金客人",
            guest_phone="13900000004",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
            deposit_amount=0,
        )
        stay = checkin_service.walk_in_check_in(data, operator_id=1)
        assert stay.deposit_amount == Decimal("0")

    def test_walkin_publishes_event(self, db_session, sample_room):
        """Walk-in publishes GUEST_CHECKED_IN event."""
        events = []
        svc = CheckInService(db_session, event_publisher=lambda e: events.append(e))

        data = WalkInCheckIn(
            guest_name="事件测试",
            guest_phone="13900000005",
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=1),
        )
        svc.walk_in_check_in(data, operator_id=1)
        assert len(events) == 1
        assert events[0].event_type == "guest.checked_in"


class TestReservationCheckIn:
    """Test reservation-based check-in."""

    def test_reservation_checkin_success(
        self, checkin_service, db_session, sample_room, make_reservation
    ):
        """Successful check-in from reservation."""
        rsv = make_reservation()
        data = CheckInFromReservation(
            reservation_id=rsv.id,
            room_id=sample_room.id,
            deposit_amount=300,
        )
        stay = checkin_service.check_in_from_reservation(data, operator_id=1)
        assert stay.status == StayRecordStatus.ACTIVE
        assert stay.reservation_id == rsv.id
        assert stay.room.status == RoomStatus.OCCUPIED

    def test_reservation_not_found(self, checkin_service):
        """Check-in with non-existent reservation."""
        data = CheckInFromReservation(
            reservation_id=99999,
            room_id=1,
        )
        with pytest.raises(ValueError, match="预订不存在"):
            checkin_service.check_in_from_reservation(data, operator_id=1)

    def test_reservation_already_checked_in(
        self, checkin_service, db_session, sample_room, make_reservation
    ):
        """Check-in with already checked-in reservation."""
        rsv = make_reservation(status=ReservationStatus.CHECKED_IN)
        data = CheckInFromReservation(
            reservation_id=rsv.id,
            room_id=sample_room.id,
        )
        with pytest.raises(ValueError, match="无法办理入住"):
            checkin_service.check_in_from_reservation(data, operator_id=1)

    def test_reservation_cancelled(
        self, checkin_service, db_session, sample_room, make_reservation
    ):
        """Check-in with cancelled reservation."""
        rsv = make_reservation(status=ReservationStatus.CANCELLED)
        data = CheckInFromReservation(
            reservation_id=rsv.id,
            room_id=sample_room.id,
        )
        with pytest.raises(ValueError, match="无法办理入住"):
            checkin_service.check_in_from_reservation(data, operator_id=1)

    def test_reservation_room_occupied(
        self, checkin_service, db_session, sample_room, make_reservation
    ):
        """Check-in with occupied room."""
        sample_room.status = RoomStatus.OCCUPIED
        db_session.commit()

        rsv = make_reservation()
        data = CheckInFromReservation(
            reservation_id=rsv.id,
            room_id=sample_room.id,
        )
        with pytest.raises(ValueError, match="无法入住"):
            checkin_service.check_in_from_reservation(data, operator_id=1)

    def test_reservation_checkin_publishes_event(self, db_session, sample_room, make_reservation):
        """Reservation check-in publishes event."""
        events = []
        svc = CheckInService(db_session, event_publisher=lambda e: events.append(e))
        rsv = make_reservation()

        data = CheckInFromReservation(
            reservation_id=rsv.id,
            room_id=sample_room.id,
        )
        svc.check_in_from_reservation(data, operator_id=1)
        assert len(events) == 1


class TestExtendStay:
    """Test extend stay operation."""

    def test_extend_stay_success(
        self, checkin_service, db_session, sample_room, sample_guest
    ):
        """Successful extend stay."""
        sample_room.status = RoomStatus.OCCUPIED
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        new_checkout = date.today() + timedelta(days=3)
        data = ExtendStay(new_check_out_date=new_checkout)
        result = checkin_service.extend_stay(stay.id, data, operator_id=1)
        assert result.expected_check_out == new_checkout

    def test_extend_stay_not_found(self, checkin_service):
        """Extend stay with non-existent stay record."""
        data = ExtendStay(new_check_out_date=date.today() + timedelta(days=3))
        with pytest.raises(ValueError, match="住宿记录不存在"):
            checkin_service.extend_stay(99999, data, operator_id=1)

    def test_extend_stay_already_checked_out(
        self, checkin_service, db_session, sample_room, sample_guest
    ):
        """Extend stay that's already checked out."""
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today(),
            status=StayRecordStatus.CHECKED_OUT,
        )
        db_session.add(stay)
        db_session.commit()

        data = ExtendStay(new_check_out_date=date.today() + timedelta(days=3))
        with pytest.raises(ValueError, match="已退房"):
            checkin_service.extend_stay(stay.id, data, operator_id=1)

    def test_extend_stay_earlier_date(
        self, checkin_service, db_session, sample_room, sample_guest
    ):
        """Extend stay to earlier date raises ValueError."""
        sample_room.status = RoomStatus.OCCUPIED
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=5),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.flush()
        bill = Bill(stay_record_id=stay.id, total_amount=Decimal("288.00"))
        db_session.add(bill)
        db_session.commit()

        data = ExtendStay(new_check_out_date=date.today())
        with pytest.raises(ValueError, match="新离店日期必须晚于"):
            checkin_service.extend_stay(stay.id, data, operator_id=1)


class TestChangeRoom:
    """Test change room operation."""

    def test_change_room_success(
        self, checkin_service, db_session, sample_room, sample_room_type, sample_guest
    ):
        """Successful room change."""
        new_room = Room(
            room_number="202",
            floor=2,
            room_type_id=sample_room_type.id,
            status=RoomStatus.VACANT_CLEAN,
        )
        db_session.add(new_room)
        sample_room.status = RoomStatus.OCCUPIED

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.flush()
        bill = Bill(stay_record_id=stay.id, total_amount=Decimal("288.00"))
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)
        db_session.refresh(new_room)

        data = ChangeRoom(new_room_id=new_room.id)
        result = checkin_service.change_room(stay.id, data, operator_id=1)
        assert result.room_id == new_room.id
        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_DIRTY
        db_session.refresh(new_room)
        assert new_room.status == RoomStatus.OCCUPIED

    def test_change_room_stay_not_found(self, checkin_service):
        """Change room with non-existent stay."""
        data = ChangeRoom(new_room_id=1)
        with pytest.raises(ValueError, match="住宿记录不存在"):
            checkin_service.change_room(99999, data, operator_id=1)

    def test_change_room_new_room_not_found(
        self, checkin_service, db_session, sample_room, sample_guest
    ):
        """Change room with non-existent new room."""
        sample_room.status = RoomStatus.OCCUPIED
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.commit()

        data = ChangeRoom(new_room_id=99999)
        with pytest.raises(ValueError, match="新房间不存在"):
            checkin_service.change_room(stay.id, data, operator_id=1)

    def test_change_room_new_room_occupied(
        self, checkin_service, db_session, sample_room, sample_room_type, sample_guest
    ):
        """Change room to occupied room."""
        new_room = Room(
            room_number="203",
            floor=2,
            room_type_id=sample_room_type.id,
            status=RoomStatus.OCCUPIED,
        )
        db_session.add(new_room)
        sample_room.status = RoomStatus.OCCUPIED
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.commit()

        data = ChangeRoom(new_room_id=new_room.id)
        with pytest.raises(ValueError, match="无法换入"):
            checkin_service.change_room(stay.id, data, operator_id=1)
