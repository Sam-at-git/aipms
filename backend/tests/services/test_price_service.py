"""
Tests for app/hotel/services/price_service.py
Covers: get_rate_plans, get_rate_plan, create_rate_plan, update_rate_plan,
        delete_rate_plan, get_price_for_date, calculate_total_price, get_price_calendar
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.hotel.models.ontology import RoomType, RatePlan, Employee, EmployeeRole
from app.hotel.models.schemas import RatePlanCreate, RatePlanUpdate
from app.hotel.services.price_service import PriceService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _make_room_type(db, name="标准间", base_price=Decimal("288.00")):
    rt = RoomType(name=name, base_price=base_price, max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _make_employee(db, username="price_op"):
    e = Employee(
        username=username,
        password_hash=get_password_hash("123456"),
        name="价格操作员",
        role=EmployeeRole.MANAGER,
        is_active=True,
    )
    db.add(e)
    db.flush()
    return e


def _make_rate_plan(db, room_type, name="旺季", start_date=None, end_date=None,
                    price=Decimal("388"), priority=1, is_weekend=False, is_active=True):
    start = start_date or date.today()
    end = end_date or (date.today() + timedelta(days=30))
    rp = RatePlan(
        name=name,
        room_type_id=room_type.id,
        start_date=start,
        end_date=end,
        price=price,
        priority=priority,
        is_weekend=is_weekend,
        is_active=is_active,
    )
    db.add(rp)
    db.flush()
    return rp


# ── tests ────────────────────────────────────────────────────────────

class TestGetRatePlans:

    def test_empty(self, db_session):
        svc = PriceService(db_session)
        assert svc.get_rate_plans() == []

    def test_list_all(self, db_session):
        rt = _make_room_type(db_session)
        _make_rate_plan(db_session, rt, "Plan A")
        _make_rate_plan(db_session, rt, "Plan B")
        db_session.commit()

        plans = PriceService(db_session).get_rate_plans()
        assert len(plans) == 2

    def test_filter_by_room_type_id(self, db_session):
        rt1 = _make_room_type(db_session, "标准间")
        rt2 = _make_room_type(db_session, "豪华间", Decimal("588"))
        _make_rate_plan(db_session, rt1, "Plan A")
        _make_rate_plan(db_session, rt2, "Plan B")
        db_session.commit()

        plans = PriceService(db_session).get_rate_plans(room_type_id=rt1.id)
        assert len(plans) == 1
        assert plans[0].room_type_id == rt1.id

    def test_filter_by_is_active(self, db_session):
        rt = _make_room_type(db_session)
        _make_rate_plan(db_session, rt, "Active", is_active=True)
        _make_rate_plan(db_session, rt, "Inactive", is_active=False)
        db_session.commit()

        active = PriceService(db_session).get_rate_plans(is_active=True)
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_ordered_by_priority_desc(self, db_session):
        rt = _make_room_type(db_session)
        _make_rate_plan(db_session, rt, "Low", priority=1)
        _make_rate_plan(db_session, rt, "High", priority=10)
        db_session.commit()

        plans = PriceService(db_session).get_rate_plans()
        assert plans[0].priority >= plans[1].priority


class TestGetRatePlan:

    def test_found(self, db_session):
        rt = _make_room_type(db_session)
        rp = _make_rate_plan(db_session, rt, "MyPlan")
        db_session.commit()

        result = PriceService(db_session).get_rate_plan(rp.id)
        assert result is not None
        assert result.name == "MyPlan"

    def test_not_found(self, db_session):
        assert PriceService(db_session).get_rate_plan(9999) is None


class TestCreateRatePlan:

    def test_success(self, db_session):
        rt = _make_room_type(db_session)
        emp = _make_employee(db_session)
        db_session.commit()

        data = RatePlanCreate(
            name="春节特惠",
            room_type_id=rt.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            price=Decimal("338"),
            priority=2,
        )
        svc = PriceService(db_session)
        rp = svc.create_rate_plan(data, created_by=emp.id)
        assert rp.id is not None
        assert rp.name == "春节特惠"
        assert rp.price == Decimal("338")

    def test_invalid_room_type(self, db_session):
        emp = _make_employee(db_session)
        db_session.commit()

        data = RatePlanCreate(
            name="Bad",
            room_type_id=9999,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            price=Decimal("100"),
        )
        with pytest.raises(ValueError, match="房型不存在"):
            PriceService(db_session).create_rate_plan(data, created_by=emp.id)

    def test_end_before_start(self, db_session):
        rt = _make_room_type(db_session)
        emp = _make_employee(db_session)
        db_session.commit()

        data = RatePlanCreate(
            name="Bad dates",
            room_type_id=rt.id,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today(),
            price=Decimal("100"),
        )
        with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
            PriceService(db_session).create_rate_plan(data, created_by=emp.id)


class TestUpdateRatePlan:

    def test_success(self, db_session):
        rt = _make_room_type(db_session)
        rp = _make_rate_plan(db_session, rt, "OrigName", price=Decimal("300"))
        db_session.commit()

        data = RatePlanUpdate(name="NewName", price=Decimal("400"))
        updated = PriceService(db_session).update_rate_plan(rp.id, data)
        assert updated.name == "NewName"
        assert updated.price == Decimal("400")

    def test_not_found(self, db_session):
        data = RatePlanUpdate(name="Nope")
        with pytest.raises(ValueError, match="价格策略不存在"):
            PriceService(db_session).update_rate_plan(9999, data)

    def test_end_before_start_after_update(self, db_session):
        rt = _make_room_type(db_session)
        rp = _make_rate_plan(
            db_session, rt, "Plan",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
        )
        db_session.commit()

        # Move end_date before start_date
        data = RatePlanUpdate(end_date=date.today() - timedelta(days=1))
        with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
            PriceService(db_session).update_rate_plan(rp.id, data)

    def test_partial_update(self, db_session):
        rt = _make_room_type(db_session)
        rp = _make_rate_plan(db_session, rt, "Original", price=Decimal("300"), priority=1)
        db_session.commit()

        data = RatePlanUpdate(priority=5)
        updated = PriceService(db_session).update_rate_plan(rp.id, data)
        assert updated.priority == 5
        assert updated.name == "Original"  # unchanged


class TestDeleteRatePlan:

    def test_success(self, db_session):
        rt = _make_room_type(db_session)
        rp = _make_rate_plan(db_session, rt, "ToDelete")
        db_session.commit()

        svc = PriceService(db_session)
        result = svc.delete_rate_plan(rp.id)
        assert result is True
        assert svc.get_rate_plan(rp.id) is None

    def test_not_found(self, db_session):
        with pytest.raises(ValueError, match="价格策略不存在"):
            PriceService(db_session).delete_rate_plan(9999)


class TestGetPriceForDate:

    def test_base_price_when_no_plans(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, date.today())
        assert price == Decimal("288")

    def test_invalid_room_type(self, db_session):
        with pytest.raises(ValueError, match="房型不存在"):
            PriceService(db_session).get_price_for_date(9999, date.today())

    def test_matching_weekday_plan(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        # Find next Monday (weekday 0)
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        monday = today + timedelta(days=days_until_monday)

        _make_rate_plan(
            db_session, rt, "Weekday",
            start_date=monday - timedelta(days=1),
            end_date=monday + timedelta(days=1),
            price=Decimal("350"),
            is_weekend=False,
            priority=5,
        )
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, monday)
        assert price == Decimal("350")

    def test_weekend_plan_on_friday(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        # Find next Friday (weekday 4)
        today = date.today()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.weekday() != 4:
            days_until_friday = 7
        friday = today + timedelta(days=days_until_friday)
        if friday.weekday() != 4:
            friday = today + timedelta(days=(4 - today.weekday()) % 7 or 7)

        _make_rate_plan(
            db_session, rt, "Weekend",
            start_date=friday - timedelta(days=1),
            end_date=friday + timedelta(days=1),
            price=Decimal("450"),
            is_weekend=True,
            priority=5,
        )
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, friday)
        assert price == Decimal("450")

    def test_weekend_fallback_to_weekday_plan(self, db_session):
        """On a weekend, if no weekend plan, fall back to weekday plan"""
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        # Find next Saturday (weekday 5)
        today = date.today()
        days_until_sat = (5 - today.weekday()) % 7
        if days_until_sat == 0 and today.weekday() != 5:
            days_until_sat = 7
        saturday = today + timedelta(days=days_until_sat)
        if saturday.weekday() != 5:
            saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)

        _make_rate_plan(
            db_session, rt, "Weekday Only",
            start_date=saturday - timedelta(days=1),
            end_date=saturday + timedelta(days=1),
            price=Decimal("320"),
            is_weekend=False,
            priority=5,
        )
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, saturday)
        assert price == Decimal("320")

    def test_inactive_plan_ignored(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        _make_rate_plan(
            db_session, rt, "Inactive",
            price=Decimal("999"),
            is_active=False,
        )
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, date.today())
        assert price == Decimal("288")

    def test_priority_ordering(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        today = date.today()
        _make_rate_plan(db_session, rt, "LowPriority",
                        start_date=today, end_date=today + timedelta(days=1),
                        price=Decimal("300"), priority=1)
        _make_rate_plan(db_session, rt, "HighPriority",
                        start_date=today, end_date=today + timedelta(days=1),
                        price=Decimal("400"), priority=10)
        db_session.commit()

        price = PriceService(db_session).get_price_for_date(rt.id, today)
        assert price == Decimal("400")


class TestCalculateTotalPrice:

    def test_single_night(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        db_session.commit()

        today = date.today()
        total = PriceService(db_session).calculate_total_price(
            rt.id, today, today + timedelta(days=1)
        )
        assert total == Decimal("288")

    def test_multiple_nights(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("100"))
        db_session.commit()

        today = date.today()
        total = PriceService(db_session).calculate_total_price(
            rt.id, today, today + timedelta(days=3)
        )
        assert total == Decimal("300")

    def test_multiple_rooms(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("100"))
        db_session.commit()

        today = date.today()
        total = PriceService(db_session).calculate_total_price(
            rt.id, today, today + timedelta(days=2), room_count=3
        )
        assert total == Decimal("600")

    def test_zero_nights(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("100"))
        db_session.commit()

        today = date.today()
        total = PriceService(db_session).calculate_total_price(
            rt.id, today, today
        )
        assert total == Decimal("0")


class TestGetPriceCalendar:

    def test_calendar_structure(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        db_session.commit()

        today = date.today()
        end = today + timedelta(days=2)
        calendar = PriceService(db_session).get_price_calendar(rt.id, today, end)
        assert len(calendar) == 3
        for entry in calendar:
            assert "date" in entry
            assert "price" in entry
            assert "is_weekend" in entry

    def test_calendar_weekend_flag(self, db_session):
        rt = _make_room_type(db_session, base_price=Decimal("288"))
        db_session.commit()

        # Find next Friday
        today = date.today()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.weekday() != 4:
            days_until_friday = 7
        friday = today + timedelta(days=days_until_friday)
        if friday.weekday() != 4:
            friday = today + timedelta(days=(4 - today.weekday()) % 7 or 7)

        saturday = friday + timedelta(days=1)

        calendar = PriceService(db_session).get_price_calendar(rt.id, friday, saturday)
        assert len(calendar) == 2
        # Both Friday (weekday 4) and Saturday (weekday 5) are >= 4 → is_weekend True
        assert calendar[0]["is_weekend"] is True
        assert calendar[1]["is_weekend"] is True
