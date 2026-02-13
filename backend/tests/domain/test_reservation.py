"""
测试 core.domain.reservation 模块 - Reservation 领域实体单元测试
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from app.hotel.domain.reservation import (
    ReservationState,
    ReservationEntity,
    ReservationRepository,
)
from app.models.ontology import Reservation, ReservationStatus, RoomType, Guest


@pytest.fixture
def sample_room_type(db_session):
    room_type = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
    db_session.add(room_type)
    db_session.commit()
    return room_type


@pytest.fixture
def sample_guest(db_session):
    guest = Guest(name="测试客人", phone="13800138000")
    db_session.add(guest)
    db_session.commit()
    return guest


@pytest.fixture
def sample_reservation(db_session, sample_guest, sample_room_type):
    reservation = Reservation(
        reservation_no="RES20250201001",
        guest_id=sample_guest.id,
        room_type_id=sample_room_type.id,
        check_in_date=date(2025, 2, 1),
        check_out_date=date(2025, 2, 3),
        status=ReservationStatus.CONFIRMED,
    )
    db_session.add(reservation)
    db_session.commit()
    return reservation


class TestReservationEntity:
    def test_creation(self, sample_reservation):
        entity = ReservationEntity(sample_reservation)
        assert entity.id == sample_reservation.id
        assert entity.reservation_no == "RES20250201001"
        assert entity.status == ReservationState.CONFIRMED

    def test_is_active_when_confirmed(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CONFIRMED
        entity = ReservationEntity(sample_reservation)
        assert entity.is_active() is True

    def test_is_active_when_cancelled(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CANCELLED
        entity = ReservationEntity(sample_reservation)
        assert entity.is_active() is False

    def test_can_cancel_when_confirmed(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CONFIRMED
        entity = ReservationEntity(sample_reservation)
        assert entity.can_cancel() is True

    def test_cannot_cancel_when_checked_in(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CHECKED_IN
        entity = ReservationEntity(sample_reservation)
        assert entity.can_cancel() is False

    def test_check_in_transition(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CONFIRMED
        entity = ReservationEntity(sample_reservation)
        entity.check_in(room_id=1)
        assert entity.status == ReservationState.CHECKED_IN

    def test_cancel(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CONFIRMED
        entity = ReservationEntity(sample_reservation)
        entity.cancel("客人要求取消")
        assert entity.status == ReservationState.CANCELLED
        assert entity.cancel_reason == "客人要求取消"

    def test_mark_no_show(self, sample_reservation):
        sample_reservation.status = ReservationStatus.CONFIRMED
        entity = ReservationEntity(sample_reservation)
        entity.mark_no_show()
        assert entity.status == ReservationState.NO_SHOW

    def test_get_nights(self, sample_reservation):
        entity = ReservationEntity(sample_reservation)
        assert entity.get_nights() == 2  # Feb 1 to Feb 3 = 2 nights

    def test_to_dict(self, sample_reservation):
        entity = ReservationEntity(sample_reservation)
        d = entity.to_dict()
        assert d["reservation_no"] == "RES20250201001"
        assert d["status"] == "confirmed"
        assert d["nights"] == 2


class TestReservationRepository:
    def test_get_by_id(self, db_session, sample_reservation):
        repo = ReservationRepository(db_session)
        entity = repo.get_by_id(sample_reservation.id)
        assert entity is not None
        assert entity.reservation_no == "RES20250201001"

    def test_get_by_no(self, db_session, sample_reservation):
        repo = ReservationRepository(db_session)
        entity = repo.get_by_no("RES20250201001")
        assert entity is not None

    def test_find_by_guest(self, db_session, sample_reservation):
        repo = ReservationRepository(db_session)
        # sample_reservation already exists, use its guest_id
        guest_id = sample_reservation.guest_id

        # Create a second reservation for the same guest
        res2 = Reservation(
            reservation_no="RES20250201002",
            guest_id=guest_id,
            room_type_id=sample_reservation.room_type_id,
            check_in_date=date(2025, 2, 5),
            check_out_date=date(2025, 2, 7),
            status=ReservationStatus.CONFIRMED,
        )
        db_session.add(res2)
        db_session.flush()

        reservations = repo.find_by_guest(guest_id)
        assert len(reservations) >= 2

    def test_find_by_status(self, db_session, sample_reservation):
        repo = ReservationRepository(db_session)
        confirmed = repo.find_by_status("confirmed")
        assert len(confirmed) >= 1

    def test_find_arrivals(self, db_session, sample_reservation):
        repo = ReservationRepository(db_session)
        target_date = date(2025, 2, 1)

        # Ensure the reservation is in CONFIRMED status
        from app.models.ontology import ReservationStatus
        sample_reservation.status = ReservationStatus.CONFIRMED
        db_session.flush()

        arrivals = repo.find_arrivals(target_date)
        assert len(arrivals) >= 1

    def test_save(self, db_session, sample_guest, sample_room_type):
        repo = ReservationRepository(db_session)
        res = Reservation(
            reservation_no="NEW_RES",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=date(2025, 3, 1),
            check_out_date=date(2025, 3, 3),
        )
        entity = ReservationEntity(res)
        repo.save(entity)

        saved = repo.get_by_no("NEW_RES")
        assert saved is not None


class TestReservationState:
    def test_state_values(self):
        assert ReservationState.CONFIRMED == "confirmed"
        assert ReservationState.CHECKED_IN == "checked_in"
        assert ReservationState.COMPLETED == "completed"
        assert ReservationState.CANCELLED == "cancelled"
        assert ReservationState.NO_SHOW == "no_show"
