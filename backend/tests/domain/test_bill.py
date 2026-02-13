"""测试 core.domain.bill 模块"""
import pytest
from datetime import datetime, date

from app.hotel.domain.bill import BillEntity, BillRepository
from app.models.ontology import Bill, StayRecord, Guest, Room, RoomType


@pytest.fixture
def sample_bill(db_session):
    # Create required dependencies in order
    guest = Guest(name="测试客人", phone="13800138000")
    rt = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
    db_session.add(guest)
    db_session.add(rt)
    db_session.flush()

    room = Room(room_number="101", floor=1, room_type_id=rt.id)
    db_session.add(room)
    db_session.flush()

    stay = StayRecord(
        guest_id=guest.id,
        room_id=room.id,
        check_in_time=datetime(2025, 2, 1, 12, 0),
        expected_check_out=date(2025, 2, 3),
    )
    db_session.add(stay)
    db_session.flush()

    bill = Bill(
        stay_record_id=stay.id,
        total_amount=250.00,
        paid_amount=100.00,
    )
    db_session.add(bill)
    db_session.commit()
    return bill


class TestBillEntity:
    def test_creation(self, sample_bill):
        entity = BillEntity(sample_bill)
        assert entity.stay_record_id == sample_bill.stay_record_id
        assert entity.total_amount == 250.00

    def test_outstanding_balance(self, sample_bill):
        entity = BillEntity(sample_bill)
        assert entity.outstanding_balance == 150.00

    def test_is_fully_paid_when_partial(self, sample_bill):
        entity = BillEntity(sample_bill)
        assert entity.is_fully_paid() is False

    def test_add_payment(self, sample_bill):
        entity = BillEntity(sample_bill)
        entity.add_payment(50.0, "cash")
        assert entity.paid_amount == 150.00

    def test_apply_discount(self, sample_bill):
        entity = BillEntity(sample_bill)
        entity.apply_discount(25.0, "会员折扣")
        assert entity.adjustment_amount == -25.00

    def test_to_dict(self, sample_bill):
        entity = BillEntity(sample_bill)
        d = entity.to_dict()
        assert d["outstanding_balance"] == 150.00


class TestBillRepository:
    def test_get_by_id(self, db_session, sample_bill):
        repo = BillRepository(db_session)
        entity = repo.get_by_id(sample_bill.id)
        assert entity is not None

    def test_find_unpaid(self, db_session, sample_bill):
        repo = BillRepository(db_session)
        unpaid = repo.find_unpaid()
        assert len(unpaid) >= 1
