"""测试 core.domain.stay_record 模块"""
import pytest
from datetime import datetime, date

from app.hotel.domain.stay_record import StayRecordState, StayRecordEntity, StayRecordRepository
from app.models.ontology import StayRecord, StayRecordStatus, Guest, Room, RoomType


@pytest.fixture
def sample_stay_record(db_session):
    guest = Guest(name="测试客人", phone="13800138000")
    rt = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
    db_session.add(guest)
    db_session.add(rt)
    db_session.flush()  # Flush to get IDs

    room = Room(room_number="101", floor=1, room_type_id=rt.id)
    db_session.add(room)
    db_session.flush()

    stay = StayRecord(
        guest_id=guest.id,
        room_id=room.id,
        check_in_time=datetime(2025, 2, 1, 14, 0),
        expected_check_out=date(2025, 2, 3),
    )
    db_session.add(stay)
    db_session.commit()
    return stay


class TestStayRecordEntity:
    def test_creation(self, sample_stay_record):
        entity = StayRecordEntity(sample_stay_record)
        assert entity.status == StayRecordState.ACTIVE

    def test_check_out(self, sample_stay_record):
        entity = StayRecordEntity(sample_stay_record)
        entity.check_out(datetime(2025, 2, 3, 11, 0))
        assert entity.status == StayRecordState.CHECKED_OUT
        assert entity.check_out_time is not None

    def test_extend_stay(self, sample_stay_record):
        entity = StayRecordEntity(sample_stay_record)
        entity.extend_stay(date(2025, 2, 5))
        assert entity.expected_check_out == date(2025, 2, 5)

    def test_get_nights(self, sample_stay_record):
        sample_stay_record.check_out_time = datetime(2025, 2, 3, 11, 0)
        entity = StayRecordEntity(sample_stay_record)
        assert entity.get_nights() == 2

    def test_to_dict(self, sample_stay_record):
        entity = StayRecordEntity(sample_stay_record)
        d = entity.to_dict()
        assert d["status"] == "active"


class TestStayRecordRepository:
    def test_get_by_id(self, db_session, sample_stay_record):
        repo = StayRecordRepository(db_session)
        entity = repo.get_by_id(sample_stay_record.id)
        assert entity is not None


class TestStayRecordState:
    def test_values(self):
        assert StayRecordState.ACTIVE == "active"
        assert StayRecordState.CHECKED_OUT == "checked_out"
