"""
Tests for app/hotel/services/room_service.py
Covers: get_room_types, get_room_type, get_room_type_by_name, create_room_type,
        update_room_type, delete_room_type, get_room_type_with_count,
        get_rooms, get_room, get_room_by_number, create_room, update_room,
        update_room_status, delete_room, get_available_rooms,
        get_availability_by_room_type, get_room_with_guest,
        get_room_status_summary
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, StayRecord, StayRecordStatus,
    Employee, EmployeeRole,
)
from app.hotel.models.schemas import (
    RoomCreate, RoomUpdate, RoomTypeCreate, RoomTypeUpdate, RoomStatusUpdate,
)
from app.hotel.services.room_service import RoomService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _room_type(db, name="标准间", base_price=Decimal("288")):
    rt = RoomType(name=name, base_price=base_price, max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _room(db, rt, number="101", floor=1, status=RoomStatus.VACANT_CLEAN, is_active=True):
    r = Room(room_number=number, floor=floor, room_type_id=rt.id,
             status=status, is_active=is_active)
    db.add(r)
    db.flush()
    return r


def _guest(db, name="张三"):
    g = Guest(name=name, phone="13800138000", id_type="身份证", id_number="110101199001011234")
    db.add(g)
    db.flush()
    return g


def _employee(db, username="emp1"):
    e = Employee(
        username=username, password_hash=get_password_hash("123456"),
        name="员工", role=EmployeeRole.RECEPTIONIST, is_active=True)
    db.add(e)
    db.flush()
    return e


def _noop_publisher(event):
    """No-op event publisher for testing"""
    pass


# ── Room Type tests ──────────────────────────────────────────────────

class TestRoomTypeOperations:

    def test_get_room_types_empty(self, db_session):
        svc = RoomService(db_session, event_publisher=_noop_publisher)
        assert svc.get_room_types() == []

    def test_get_room_types(self, db_session):
        _room_type(db_session, "A")
        _room_type(db_session, "B", Decimal("500"))
        db_session.commit()
        assert len(RoomService(db_session).get_room_types()) == 2

    def test_get_room_type_found(self, db_session):
        rt = _room_type(db_session)
        db_session.commit()
        result = RoomService(db_session).get_room_type(rt.id)
        assert result is not None
        assert result.name == "标准间"

    def test_get_room_type_not_found(self, db_session):
        assert RoomService(db_session).get_room_type(9999) is None

    def test_get_room_type_by_name(self, db_session):
        _room_type(db_session, "标准间")
        db_session.commit()
        result = RoomService(db_session).get_room_type_by_name("标准间")
        assert result is not None

    def test_get_room_type_by_name_not_found(self, db_session):
        assert RoomService(db_session).get_room_type_by_name("不存在") is None

    def test_create_room_type(self, db_session):
        data = RoomTypeCreate(name="新房型", base_price=Decimal("500"), max_occupancy=3)
        rt = RoomService(db_session).create_room_type(data)
        assert rt.id is not None
        assert rt.name == "新房型"

    def test_create_room_type_duplicate_name(self, db_session):
        _room_type(db_session, "标准间")
        db_session.commit()

        data = RoomTypeCreate(name="标准间", base_price=Decimal("288"))
        with pytest.raises(ValueError, match="已存在"):
            RoomService(db_session).create_room_type(data)

    def test_update_room_type(self, db_session):
        rt = _room_type(db_session, "旧名")
        db_session.commit()

        data = RoomTypeUpdate(name="新名", base_price=Decimal("500"))
        updated = RoomService(db_session).update_room_type(rt.id, data)
        assert updated.name == "新名"
        assert updated.base_price == Decimal("500")

    def test_update_room_type_not_found(self, db_session):
        with pytest.raises(ValueError, match="房型不存在"):
            RoomService(db_session).update_room_type(9999, RoomTypeUpdate(name="X"))

    def test_update_room_type_duplicate_name(self, db_session):
        _room_type(db_session, "A")
        rt_b = _room_type(db_session, "B", Decimal("500"))
        db_session.commit()

        with pytest.raises(ValueError, match="已存在"):
            RoomService(db_session).update_room_type(rt_b.id, RoomTypeUpdate(name="A"))

    def test_update_room_type_same_name_allowed(self, db_session):
        rt = _room_type(db_session, "Same")
        db_session.commit()

        # Updating with same name should not fail
        updated = RoomService(db_session).update_room_type(
            rt.id, RoomTypeUpdate(name="Same", base_price=Decimal("999"))
        )
        assert updated.base_price == Decimal("999")

    def test_delete_room_type(self, db_session):
        rt = _room_type(db_session, "ToDelete")
        db_session.commit()

        svc = RoomService(db_session)
        assert svc.delete_room_type(rt.id) is True
        assert svc.get_room_type(rt.id) is None

    def test_delete_room_type_not_found(self, db_session):
        with pytest.raises(ValueError, match="房型不存在"):
            RoomService(db_session).delete_room_type(9999)

    def test_delete_room_type_with_rooms(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101")
        db_session.commit()

        with pytest.raises(ValueError, match="无法删除"):
            RoomService(db_session).delete_room_type(rt.id)

    def test_get_room_type_with_count(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101")
        _room(db_session, rt, "102")
        _room(db_session, rt, "103", is_active=False)
        db_session.commit()

        result = RoomService(db_session).get_room_type_with_count(rt.id)
        assert result is not None
        assert result["room_count"] == 2  # only active

    def test_get_room_type_with_count_not_found(self, db_session):
        assert RoomService(db_session).get_room_type_with_count(9999) is None


# ── Room CRUD tests ──────────────────────────────────────────────────

class TestRoomCRUD:

    def test_get_rooms_empty(self, db_session):
        assert RoomService(db_session).get_rooms() == []

    def test_get_rooms_filter_floor(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", floor=1)
        _room(db_session, rt, "201", floor=2)
        db_session.commit()

        rooms = RoomService(db_session).get_rooms(floor=1)
        assert len(rooms) == 1
        assert rooms[0].floor == 1

    def test_get_rooms_filter_room_type(self, db_session):
        rt1 = _room_type(db_session, "A")
        rt2 = _room_type(db_session, "B", Decimal("500"))
        _room(db_session, rt1, "101")
        _room(db_session, rt2, "201")
        db_session.commit()

        rooms = RoomService(db_session).get_rooms(room_type_id=rt1.id)
        assert len(rooms) == 1

    def test_get_rooms_filter_status(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        _room(db_session, rt, "102", status=RoomStatus.OCCUPIED)
        db_session.commit()

        rooms = RoomService(db_session).get_rooms(status=RoomStatus.OCCUPIED)
        assert len(rooms) == 1
        assert rooms[0].room_number == "102"

    def test_get_rooms_filter_is_active(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", is_active=True)
        _room(db_session, rt, "102", is_active=False)
        db_session.commit()

        active = RoomService(db_session).get_rooms(is_active=True)
        assert len(active) == 1

        inactive = RoomService(db_session).get_rooms(is_active=False)
        assert len(inactive) == 1

    def test_get_rooms_no_active_filter(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", is_active=True)
        _room(db_session, rt, "102", is_active=False)
        db_session.commit()

        all_rooms = RoomService(db_session).get_rooms(is_active=None)
        assert len(all_rooms) == 2

    def test_get_room_found(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt)
        db_session.commit()
        assert RoomService(db_session).get_room(r.id) is not None

    def test_get_room_not_found(self, db_session):
        assert RoomService(db_session).get_room(9999) is None

    def test_get_room_by_number(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101")
        db_session.commit()
        assert RoomService(db_session).get_room_by_number("101") is not None

    def test_get_room_by_number_not_found(self, db_session):
        assert RoomService(db_session).get_room_by_number("999") is None

    def test_create_room(self, db_session):
        rt = _room_type(db_session)
        db_session.commit()

        data = RoomCreate(room_number="301", floor=3, room_type_id=rt.id)
        r = RoomService(db_session).create_room(data)
        assert r.id is not None
        assert r.room_number == "301"

    def test_create_room_duplicate_number(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101")
        db_session.commit()

        data = RoomCreate(room_number="101", floor=1, room_type_id=rt.id)
        with pytest.raises(ValueError, match="已存在"):
            RoomService(db_session).create_room(data)

    def test_create_room_invalid_room_type(self, db_session):
        data = RoomCreate(room_number="301", floor=3, room_type_id=9999)
        with pytest.raises(ValueError, match="房型不存在"):
            RoomService(db_session).create_room(data)

    def test_update_room(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101")
        db_session.commit()

        data = RoomUpdate(features="海景房")
        updated = RoomService(db_session).update_room(r.id, data)
        assert updated.features == "海景房"

    def test_update_room_not_found(self, db_session):
        with pytest.raises(ValueError, match="房间不存在"):
            RoomService(db_session).update_room(9999, RoomUpdate(features="X"))

    def test_update_room_invalid_room_type(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101")
        db_session.commit()

        with pytest.raises(ValueError, match="房型不存在"):
            RoomService(db_session).update_room(r.id, RoomUpdate(room_type_id=9999))


class TestUpdateRoomStatus:

    def test_success(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        emp = _employee(db_session)
        db_session.commit()

        svc = RoomService(db_session, event_publisher=_noop_publisher)
        updated = svc.update_room_status(r.id, RoomStatus.VACANT_DIRTY, emp.id, "测试")
        assert updated.status == RoomStatus.VACANT_DIRTY

    def test_room_not_found(self, db_session):
        with pytest.raises(ValueError, match="房间不存在"):
            RoomService(db_session, event_publisher=_noop_publisher).update_room_status(
                9999, RoomStatus.VACANT_CLEAN)

    def test_occupied_cannot_change(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        db_session.commit()

        with pytest.raises(ValueError, match="入住中的房间不能手动更改状态"):
            RoomService(db_session, event_publisher=_noop_publisher).update_room_status(
                r.id, RoomStatus.VACANT_CLEAN)

    def test_event_published_on_change(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        emp = _employee(db_session)
        db_session.commit()

        events = []
        svc = RoomService(db_session, event_publisher=lambda e: events.append(e))
        svc.update_room_status(r.id, RoomStatus.OUT_OF_ORDER, emp.id, "维修")
        assert len(events) == 1
        assert "room.status_changed" in events[0].event_type

    def test_no_event_when_status_same(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.VACANT_DIRTY)
        db_session.commit()

        events = []
        svc = RoomService(db_session, event_publisher=lambda e: events.append(e))
        svc.update_room_status(r.id, RoomStatus.VACANT_DIRTY)
        assert len(events) == 0


class TestDeleteRoom:

    def test_success(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101")
        db_session.commit()

        svc = RoomService(db_session)
        assert svc.delete_room(r.id) is True
        assert svc.get_room(r.id) is None

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="房间不存在"):
            RoomService(db_session).delete_room(9999)

    def test_with_stay_records(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        g = _guest(db_session)
        emp = _employee(db_session)
        s = StayRecord(
            guest_id=g.id, room_id=r.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            created_by=emp.id,
        )
        db_session.add(s)
        db_session.commit()

        with pytest.raises(ValueError, match="无法删除"):
            RoomService(db_session).delete_room(r.id)


# ── Availability tests ───────────────────────────────────────────────

class TestAvailability:

    def test_get_available_rooms_all_free(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        _room(db_session, rt, "102", status=RoomStatus.VACANT_DIRTY)
        db_session.commit()

        rooms = RoomService(db_session).get_available_rooms(
            date.today(), date.today() + timedelta(days=1))
        assert len(rooms) == 2

    def test_get_available_rooms_excludes_occupied_with_stay(self, db_session):
        rt = _room_type(db_session)
        r1 = _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        r2 = _room(db_session, rt, "102", status=RoomStatus.VACANT_CLEAN)
        g = _guest(db_session)
        emp = _employee(db_session)

        s = StayRecord(
            guest_id=g.id, room_id=r1.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=3),
            status=StayRecordStatus.ACTIVE,
            created_by=emp.id,
        )
        db_session.add(s)
        db_session.commit()

        rooms = RoomService(db_session).get_available_rooms(
            date.today(), date.today() + timedelta(days=1))
        room_ids = [r.id for r in rooms]
        assert r1.id not in room_ids
        assert r2.id in room_ids

    def test_get_available_rooms_filter_by_type(self, db_session):
        rt1 = _room_type(db_session, "A")
        rt2 = _room_type(db_session, "B", Decimal("500"))
        _room(db_session, rt1, "101")
        _room(db_session, rt2, "201")
        db_session.commit()

        rooms = RoomService(db_session).get_available_rooms(
            date.today(), date.today() + timedelta(days=1), room_type_id=rt1.id)
        assert all(r.room_type_id == rt1.id for r in rooms)

    def test_get_available_rooms_excludes_out_of_order(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", status=RoomStatus.OUT_OF_ORDER)
        db_session.commit()

        rooms = RoomService(db_session).get_available_rooms(
            date.today(), date.today() + timedelta(days=1))
        assert len(rooms) == 0

    def test_get_availability_by_room_type(self, db_session):
        rt1 = _room_type(db_session, "标准间")
        rt2 = _room_type(db_session, "豪华间", Decimal("588"))
        _room(db_session, rt1, "101")
        _room(db_session, rt1, "102")
        _room(db_session, rt2, "201")
        _room(db_session, rt2, "202", status=RoomStatus.OUT_OF_ORDER)
        db_session.commit()

        result = RoomService(db_session).get_availability_by_room_type(
            date.today(), date.today() + timedelta(days=1))
        assert rt1.id in result
        assert result[rt1.id]["total"] == 2
        assert result[rt1.id]["available"] == 2
        assert rt2.id in result
        assert result[rt2.id]["total"] == 1  # excluding out_of_order


class TestRoomWithGuest:

    def test_vacant_room(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101")
        db_session.commit()

        result = RoomService(db_session).get_room_with_guest(r.id)
        assert result is not None
        assert result["current_guest"] is None

    def test_occupied_room_with_guest(self, db_session):
        rt = _room_type(db_session)
        r = _room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        g = _guest(db_session, "张三")
        emp = _employee(db_session)
        s = StayRecord(
            guest_id=g.id, room_id=r.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
            created_by=emp.id,
        )
        db_session.add(s)
        db_session.commit()

        result = RoomService(db_session).get_room_with_guest(r.id)
        assert result["current_guest"] == "张三"
        assert result["status"] == "occupied"

    def test_not_found(self, db_session):
        assert RoomService(db_session).get_room_with_guest(9999) is None


class TestRoomStatusSummary:

    def test_empty(self, db_session):
        summary = RoomService(db_session).get_room_status_summary()
        assert summary["total"] == 0

    def test_all_statuses(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        _room(db_session, rt, "102", status=RoomStatus.OCCUPIED)
        _room(db_session, rt, "103", status=RoomStatus.VACANT_DIRTY)
        _room(db_session, rt, "104", status=RoomStatus.OUT_OF_ORDER)
        _room(db_session, rt, "105", status=RoomStatus.VACANT_CLEAN)
        db_session.commit()

        summary = RoomService(db_session).get_room_status_summary()
        assert summary["total"] == 5
        assert summary["vacant_clean"] == 2
        assert summary["occupied"] == 1
        assert summary["vacant_dirty"] == 1
        assert summary["out_of_order"] == 1

    def test_excludes_inactive(self, db_session):
        rt = _room_type(db_session)
        _room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN, is_active=True)
        _room(db_session, rt, "102", status=RoomStatus.VACANT_CLEAN, is_active=False)
        db_session.commit()

        summary = RoomService(db_session).get_room_status_summary()
        assert summary["total"] == 1
