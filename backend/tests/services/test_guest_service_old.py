"""
Tests for app/hotel/services/guest_service.py
Covers: get_guests, get_guest, get_guest_by_phone, get_guest_by_id_number,
        create_guest, update_guest, get_or_create_guest, get_guest_stay_history,
        get_guest_reservation_history, get_guest_stats, update_tier, add_to_blacklist,
        remove_from_blacklist, update_preferences, increment_stays, _auto_upgrade_tier
"""
import pytest
import json
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Guest, GuestTier, Room, RoomType, RoomStatus, StayRecord, StayRecordStatus,
    Reservation, ReservationStatus, Employee, EmployeeRole,
)
from app.hotel.models.schemas import GuestCreate, GuestUpdate
from app.hotel.services.guest_service import GuestService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _room_type(db, name="标准间"):
    rt = RoomType(name=name, base_price=Decimal("288"), max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _room(db, rt, number="101"):
    r = Room(room_number=number, floor=1, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
    db.add(r)
    db.flush()
    return r


def _employee(db, username="emp1"):
    e = Employee(
        username=username, password_hash=get_password_hash("123456"),
        name="员工", role=EmployeeRole.RECEPTIONIST, is_active=True)
    db.add(e)
    db.flush()
    return e


def _guest(db, name="张三", phone="13800138000", id_number="110101199001011234", tier=GuestTier.NORMAL):
    g = Guest(name=name, phone=phone, id_type="身份证", id_number=id_number, tier=tier)
    db.add(g)
    db.flush()
    return g


# ── tests ────────────────────────────────────────────────────────────

class TestGetGuests:

    def test_empty(self, db_session):
        assert GuestService(db_session).get_guests() == []

    def test_list_all(self, db_session):
        _guest(db_session, "A", "13800000001", "ID001")
        _guest(db_session, "B", "13800000002", "ID002")
        db_session.commit()
        assert len(GuestService(db_session).get_guests()) == 2

    def test_search_by_name(self, db_session):
        _guest(db_session, "张三", "13800000001", "ID001")
        _guest(db_session, "李四", "13800000002", "ID002")
        db_session.commit()

        guests = GuestService(db_session).get_guests(search="张")
        assert len(guests) == 1
        assert guests[0].name == "张三"

    def test_search_by_phone(self, db_session):
        _guest(db_session, "张三", "13800000001", "ID001")
        db_session.commit()

        guests = GuestService(db_session).get_guests(search="13800000001")
        assert len(guests) == 1

    def test_search_by_id_number(self, db_session):
        _guest(db_session, "张三", "13800000001", "ID001XYZ")
        db_session.commit()

        guests = GuestService(db_session).get_guests(search="ID001XYZ")
        assert len(guests) == 1

    def test_filter_by_tier(self, db_session):
        _guest(db_session, "Normal", "13800000001", "ID001", GuestTier.NORMAL)
        _guest(db_session, "Gold", "13800000002", "ID002", GuestTier.GOLD)
        db_session.commit()

        guests = GuestService(db_session).get_guests(tier=GuestTier.GOLD)
        assert len(guests) == 1
        assert guests[0].name == "Gold"

    def test_filter_blacklisted(self, db_session):
        g1 = _guest(db_session, "Normal", "13800000001", "ID001")
        g2 = _guest(db_session, "Blacklisted", "13800000002", "ID002")
        g2.is_blacklisted = True
        db_session.commit()

        guests = GuestService(db_session).get_guests(is_blacklisted=True)
        assert len(guests) == 1
        assert guests[0].is_blacklisted is True

    def test_limit(self, db_session):
        for i in range(5):
            _guest(db_session, f"Guest{i}", f"1380000{i:04d}", f"ID{i:04d}")
        db_session.commit()

        guests = GuestService(db_session).get_guests(limit=3)
        assert len(guests) == 3


class TestGetGuest:

    def test_found(self, db_session):
        g = _guest(db_session)
        db_session.commit()
        result = GuestService(db_session).get_guest(g.id)
        assert result is not None
        assert result.name == "张三"

    def test_not_found(self, db_session):
        assert GuestService(db_session).get_guest(9999) is None


class TestGetGuestByPhone:

    def test_found(self, db_session):
        _guest(db_session, "张三", "13800138000")
        db_session.commit()
        result = GuestService(db_session).get_guest_by_phone("13800138000")
        assert result is not None

    def test_not_found(self, db_session):
        assert GuestService(db_session).get_guest_by_phone("13999999999") is None


class TestGetGuestByIdNumber:

    def test_found(self, db_session):
        _guest(db_session, "张三", "13800138000", "ABC123")
        db_session.commit()
        result = GuestService(db_session).get_guest_by_id_number("ABC123")
        assert result is not None

    def test_not_found(self, db_session):
        assert GuestService(db_session).get_guest_by_id_number("NOPE") is None


class TestCreateGuest:

    def test_success(self, db_session):
        data = GuestCreate(name="新客人", phone="13900139000", id_type="身份证", id_number="X123")
        g = GuestService(db_session).create_guest(data)
        assert g.id is not None
        assert g.name == "新客人"
        assert g.phone == "13900139000"

    def test_without_phone(self, db_session):
        data = GuestCreate(name="NoPhone")
        g = GuestService(db_session).create_guest(data)
        assert g.id is not None
        assert g.phone is None


class TestUpdateGuest:

    def test_success(self, db_session):
        g = _guest(db_session)
        db_session.commit()

        data = GuestUpdate(name="新名字", email="new@example.com")
        updated = GuestService(db_session).update_guest(g.id, data)
        assert updated.name == "新名字"
        assert updated.email == "new@example.com"
        assert updated.phone == "13800138000"  # unchanged

    def test_not_found(self, db_session):
        data = GuestUpdate(name="X")
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).update_guest(9999, data)


class TestGetOrCreateGuest:

    def test_create_new(self, db_session):
        svc = GuestService(db_session)
        g = svc.get_or_create_guest("新客人", "13900139000")
        assert g.id is not None
        assert g.name == "新客人"

    def test_return_existing(self, db_session):
        existing = _guest(db_session, "张三", "13800138000")
        db_session.commit()

        g = GuestService(db_session).get_or_create_guest("张三", "13800138000")
        assert g.id == existing.id


class TestGetGuestStayHistory:

    def test_empty(self, db_session):
        g = _guest(db_session)
        db_session.commit()
        history = GuestService(db_session).get_guest_stay_history(g.id)
        assert history == []

    def test_with_stays(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        g = _guest(db_session)
        emp = _employee(db_session)

        s = StayRecord(
            guest_id=g.id, room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE,
            created_by=emp.id,
        )
        db_session.add(s)
        db_session.commit()

        history = GuestService(db_session).get_guest_stay_history(g.id)
        assert len(history) == 1
        assert history[0]["room_number"] == "101"
        assert history[0]["room_type"] == "标准间"

    def test_limit(self, db_session):
        rt = _room_type(db_session)
        g = _guest(db_session)
        emp = _employee(db_session)

        for i in range(5):
            r = _room(db_session, rt, f"10{i}")
            s = StayRecord(
                guest_id=g.id, room_id=r.id,
                check_in_time=datetime.now() - timedelta(days=i+1),
                expected_check_out=date.today() + timedelta(days=1),
                status=StayRecordStatus.ACTIVE,
                created_by=emp.id,
            )
            db_session.add(s)
        db_session.commit()

        history = GuestService(db_session).get_guest_stay_history(g.id, limit=3)
        assert len(history) == 3


class TestGetGuestReservationHistory:

    def test_empty(self, db_session):
        g = _guest(db_session)
        db_session.commit()
        history = GuestService(db_session).get_guest_reservation_history(g.id)
        assert history == []

    def test_with_reservations(self, db_session):
        rt = _room_type(db_session)
        g = _guest(db_session)
        db_session.flush()

        r = Reservation(
            reservation_no="R20250101001",
            guest_id=g.id, room_type_id=rt.id,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=1),
            status=ReservationStatus.CONFIRMED,
        )
        db_session.add(r)
        db_session.commit()

        history = GuestService(db_session).get_guest_reservation_history(g.id)
        assert len(history) == 1
        assert history[0]["reservation_no"] == "R20250101001"
        assert history[0]["room_type"] == "标准间"


class TestGetGuestStats:

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).get_guest_stats(9999)

    def test_basic_stats(self, db_session):
        g = _guest(db_session)
        g.total_stays = 5
        g.total_amount = Decimal("3000")
        db_session.commit()

        stats = GuestService(db_session).get_guest_stats(g.id)
        assert stats["total_stays"] == 5
        assert stats["total_amount"] == 3000.0
        assert stats["reservation_count"] == 0
        assert stats["last_stay_date"] is None
        assert stats["last_room_type"] is None

    def test_stats_with_last_stay(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        g = _guest(db_session)
        emp = _employee(db_session)

        checkout_time = datetime.now() - timedelta(hours=2)
        s = StayRecord(
            guest_id=g.id, room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today(),
            status=StayRecordStatus.CHECKED_OUT,
            check_out_time=checkout_time,
            created_by=emp.id,
        )
        db_session.add(s)
        db_session.commit()

        # Note: guest_service checks status == "checked_out" (string), but the enum
        # StayRecordStatus.CHECKED_OUT has value "checked_out".
        stats = GuestService(db_session).get_guest_stats(g.id)
        assert stats["last_stay_date"] is not None
        assert stats["last_room_type"] == "标准间"


class TestUpdateTier:

    def test_success(self, db_session):
        g = _guest(db_session)
        db_session.commit()

        updated = GuestService(db_session).update_tier(g.id, GuestTier.GOLD)
        assert updated.tier == GuestTier.GOLD

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).update_tier(9999, GuestTier.GOLD)


class TestBlacklist:

    def test_add_to_blacklist(self, db_session):
        g = _guest(db_session)
        db_session.commit()

        result = GuestService(db_session).add_to_blacklist(g.id, "问题客人")
        assert result.is_blacklisted is True
        assert result.blacklist_reason == "问题客人"

    def test_add_to_blacklist_not_found(self, db_session):
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).add_to_blacklist(9999, "reason")

    def test_remove_from_blacklist(self, db_session):
        g = _guest(db_session)
        g.is_blacklisted = True
        g.blacklist_reason = "旧原因"
        db_session.commit()

        result = GuestService(db_session).remove_from_blacklist(g.id)
        assert result.is_blacklisted is False
        assert result.blacklist_reason is None

    def test_remove_from_blacklist_not_found(self, db_session):
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).remove_from_blacklist(9999)


class TestUpdatePreferences:

    def test_set_preferences_from_empty(self, db_session):
        g = _guest(db_session)
        db_session.commit()

        result = GuestService(db_session).update_preferences(g.id, {"floor": "high", "bed": "king"})
        prefs = json.loads(result.preferences)
        assert prefs["floor"] == "high"
        assert prefs["bed"] == "king"

    def test_merge_with_existing(self, db_session):
        g = _guest(db_session)
        g.preferences = json.dumps({"floor": "low"})
        db_session.commit()

        result = GuestService(db_session).update_preferences(g.id, {"bed": "twin"})
        prefs = json.loads(result.preferences)
        assert prefs["floor"] == "low"  # preserved
        assert prefs["bed"] == "twin"   # added

    def test_overwrite_existing_key(self, db_session):
        g = _guest(db_session)
        g.preferences = json.dumps({"floor": "low"})
        db_session.commit()

        result = GuestService(db_session).update_preferences(g.id, {"floor": "high"})
        prefs = json.loads(result.preferences)
        assert prefs["floor"] == "high"

    def test_invalid_json_preferences_reset(self, db_session):
        g = _guest(db_session)
        g.preferences = "not-json"
        db_session.commit()

        result = GuestService(db_session).update_preferences(g.id, {"key": "val"})
        prefs = json.loads(result.preferences)
        assert prefs == {"key": "val"}

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="客人不存在"):
            GuestService(db_session).update_preferences(9999, {"x": "y"})


class TestIncrementStays:

    def test_basic_increment(self, db_session):
        g = _guest(db_session)
        g.total_stays = 0
        g.total_amount = Decimal("0")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=500)
        db_session.refresh(g)
        assert g.total_stays == 1
        assert float(g.total_amount) == 500

    def test_increment_without_amount(self, db_session):
        g = _guest(db_session)
        g.total_stays = 2
        g.total_amount = Decimal("1000")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id)
        db_session.refresh(g)
        assert g.total_stays == 3
        assert float(g.total_amount) == 1000  # unchanged

    def test_nonexistent_guest_no_error(self, db_session):
        # Should silently do nothing
        GuestService(db_session).increment_stays(9999, amount=100)


class TestAutoUpgradeTier:

    def test_upgrade_to_silver(self, db_session):
        g = _guest(db_session)
        g.total_stays = 0
        g.total_amount = Decimal("0")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=5000)
        db_session.refresh(g)
        assert g.tier == GuestTier.SILVER

    def test_upgrade_to_gold(self, db_session):
        g = _guest(db_session)
        g.total_amount = Decimal("0")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=20000)
        db_session.refresh(g)
        assert g.tier == GuestTier.GOLD

    def test_upgrade_to_platinum(self, db_session):
        g = _guest(db_session)
        g.total_amount = Decimal("0")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=50000)
        db_session.refresh(g)
        assert g.tier == GuestTier.PLATINUM

    def test_high_tier_preserved_on_low_amount(self, db_session):
        """Gold/Platinum tier not downgraded when total_amount < threshold"""
        g = _guest(db_session, tier=GuestTier.GOLD)
        g.total_amount = Decimal("1000")
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=100)
        db_session.refresh(g)
        # 1100 total - below gold threshold but tier is preserved
        assert g.tier == GuestTier.GOLD

    def test_normal_stays_normal(self, db_session):
        g = _guest(db_session)
        g.total_amount = Decimal("0")
        g.tier = GuestTier.NORMAL
        db_session.commit()

        GuestService(db_session).increment_stays(g.id, amount=100)
        db_session.refresh(g)
        assert g.tier == GuestTier.NORMAL
