"""
Tests for app/hotel/services/report_service.py
Covers: get_dashboard_stats, get_occupancy_report, get_revenue_report,
        get_room_type_report, get_today_arrivals_count, get_today_departures_count
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, StayRecord, StayRecordStatus,
    Bill, Payment, PaymentMethod, Reservation, ReservationStatus,
    Employee, EmployeeRole,
)
from app.hotel.services.report_service import ReportService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _make_room_type(db, name="标准间", base_price=Decimal("288.00")):
    rt = RoomType(name=name, base_price=base_price, max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _make_room(db, room_type, number="101", floor=1, status=RoomStatus.VACANT_CLEAN):
    r = Room(room_number=number, floor=floor, room_type_id=room_type.id, status=status)
    db.add(r)
    db.flush()
    return r


def _make_guest(db, name="张三", phone="13800138000"):
    g = Guest(name=name, phone=phone, id_type="身份证", id_number="110101199001011234")
    db.add(g)
    db.flush()
    return g


def _make_employee(db, username="op1"):
    e = Employee(
        username=username,
        password_hash=get_password_hash("123456"),
        name="操作员",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True,
    )
    db.add(e)
    db.flush()
    return e


def _make_stay(db, guest, room, check_in, expected_out,
               status=StayRecordStatus.ACTIVE, check_out_time=None, created_by=None):
    s = StayRecord(
        guest_id=guest.id,
        room_id=room.id,
        check_in_time=check_in,
        expected_check_out=expected_out,
        status=status,
        check_out_time=check_out_time,
        created_by=created_by,
    )
    db.add(s)
    db.flush()
    return s


def _make_bill(db, stay, total=Decimal("288"), paid=Decimal("0")):
    b = Bill(stay_record_id=stay.id, total_amount=total, paid_amount=paid)
    db.add(b)
    db.flush()
    return b


def _make_payment(db, bill, amount=Decimal("288"), method=PaymentMethod.CASH, payment_time=None):
    p = Payment(
        bill_id=bill.id,
        amount=amount,
        method=method,
        payment_time=payment_time or datetime.now(),
    )
    db.add(p)
    db.flush()
    return p


def _make_reservation(db, guest, room_type, check_in, check_out,
                      status=ReservationStatus.CONFIRMED):
    r = Reservation(
        reservation_no=f"R{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        guest_id=guest.id,
        room_type_id=room_type.id,
        check_in_date=check_in,
        check_out_date=check_out,
        status=status,
    )
    db.add(r)
    db.flush()
    return r


# ── tests ────────────────────────────────────────────────────────────

class TestGetDashboardStats:
    """Tests for ReportService.get_dashboard_stats()"""

    def test_empty_database(self, db_session):
        svc = ReportService(db_session)
        stats = svc.get_dashboard_stats()
        assert stats["total_rooms"] == 0
        assert stats["occupancy_rate"] == 0
        assert stats["today_revenue"] == Decimal("0")

    def test_room_status_counts(self, db_session):
        rt = _make_room_type(db_session)
        _make_room(db_session, rt, "101", status=RoomStatus.VACANT_CLEAN)
        _make_room(db_session, rt, "102", status=RoomStatus.OCCUPIED)
        _make_room(db_session, rt, "103", status=RoomStatus.VACANT_DIRTY)
        _make_room(db_session, rt, "104", status=RoomStatus.OUT_OF_ORDER)
        db_session.commit()

        stats = ReportService(db_session).get_dashboard_stats()
        assert stats["total_rooms"] == 4
        assert stats["vacant_clean"] == 1
        assert stats["occupied"] == 1
        assert stats["vacant_dirty"] == 1
        assert stats["out_of_order"] == 1

    def test_occupancy_rate_excludes_out_of_order(self, db_session):
        rt = _make_room_type(db_session)
        _make_room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        _make_room(db_session, rt, "102", status=RoomStatus.OCCUPIED)
        _make_room(db_session, rt, "103", status=RoomStatus.OUT_OF_ORDER)
        db_session.commit()

        stats = ReportService(db_session).get_dashboard_stats()
        # 2 occupied out of 2 sellable => 100%
        assert stats["occupancy_rate"] == 100.0

    def test_today_checkins_and_checkouts(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        now = datetime.now()
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # active stay checked in today
        _make_stay(db_session, guest, room, now, tomorrow, created_by=emp.id)

        # another room for checkout today
        room2 = _make_room(db_session, rt, "102", status=RoomStatus.VACANT_DIRTY)
        _make_stay(
            db_session, guest, room2, now - timedelta(days=1),
            today, StayRecordStatus.CHECKED_OUT, check_out_time=now,
            created_by=emp.id,
        )
        db_session.commit()

        stats = ReportService(db_session).get_dashboard_stats()
        assert stats["today_checkins"] >= 1
        assert stats["today_checkouts"] >= 1

    def test_today_revenue(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)
        stay = _make_stay(db_session, guest, room, datetime.now(),
                          date.today() + timedelta(days=1), created_by=emp.id)
        bill = _make_bill(db_session, stay, Decimal("500"), Decimal("500"))
        _make_payment(db_session, bill, Decimal("500"), payment_time=datetime.now())
        db_session.commit()

        stats = ReportService(db_session).get_dashboard_stats()
        assert stats["today_revenue"] == Decimal("500")

    def test_all_rooms_out_of_order_occupancy_zero(self, db_session):
        """When all rooms are out of order, sellable=0, occupancy_rate=0"""
        rt = _make_room_type(db_session)
        _make_room(db_session, rt, "101", status=RoomStatus.OUT_OF_ORDER)
        db_session.commit()
        stats = ReportService(db_session).get_dashboard_stats()
        assert stats["occupancy_rate"] == 0


class TestGetOccupancyReport:
    """Tests for ReportService.get_occupancy_report()"""

    def test_empty_database(self, db_session):
        svc = ReportService(db_session)
        today = date.today()
        report = svc.get_occupancy_report(today, today)
        assert len(report) == 1
        assert report[0]["occupied_rooms"] == 0

    def test_single_day_with_active_stay(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        today = date.today()
        _make_stay(
            db_session, guest, room,
            datetime.combine(today, datetime.min.time()),
            today + timedelta(days=2),
            created_by=emp.id,
        )
        db_session.commit()

        report = ReportService(db_session).get_occupancy_report(today, today)
        assert len(report) == 1
        assert report[0]["occupied_rooms"] == 1
        assert report[0]["total_rooms"] >= 1

    def test_multi_day_range(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        start = date.today() - timedelta(days=2)
        end = date.today()
        _make_stay(
            db_session, guest, room,
            datetime.combine(start, datetime.min.time()),
            end + timedelta(days=1),
            created_by=emp.id,
        )
        db_session.commit()

        report = ReportService(db_session).get_occupancy_report(start, end)
        assert len(report) == 3  # 3 days inclusive

    def test_checked_out_stay_counted_on_checkout_day(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        today = date.today()
        checkout_time = datetime.combine(today, datetime.min.time())
        _make_stay(
            db_session, guest, room,
            datetime.combine(today - timedelta(days=1), datetime.min.time()),
            today + timedelta(days=1),
            StayRecordStatus.CHECKED_OUT,
            check_out_time=checkout_time,
            created_by=emp.id,
        )
        db_session.commit()

        report = ReportService(db_session).get_occupancy_report(today, today)
        assert report[0]["occupied_rooms"] >= 1


class TestGetRevenueReport:
    """Tests for ReportService.get_revenue_report()"""

    def test_empty_database(self, db_session):
        today = date.today()
        report = ReportService(db_session).get_revenue_report(today, today)
        assert len(report) == 1
        assert report[0]["revenue"] == 0
        assert report[0]["payment_count"] == 0

    def test_payments_summed_per_day(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)
        stay = _make_stay(db_session, guest, room, datetime.now(),
                          date.today() + timedelta(days=1), created_by=emp.id)
        bill = _make_bill(db_session, stay)
        now = datetime.now()
        _make_payment(db_session, bill, Decimal("100"), payment_time=now)
        _make_payment(db_session, bill, Decimal("200"), payment_time=now)
        db_session.commit()

        today = date.today()
        report = ReportService(db_session).get_revenue_report(today, today)
        assert report[0]["revenue"] == Decimal("300")
        assert report[0]["payment_count"] == 2

    def test_multi_day_revenue(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)
        stay = _make_stay(db_session, guest, room, datetime.now(),
                          date.today() + timedelta(days=3), created_by=emp.id)
        bill = _make_bill(db_session, stay)

        today = date.today()
        yesterday = today - timedelta(days=1)
        _make_payment(db_session, bill, Decimal("100"),
                      payment_time=datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=10))
        _make_payment(db_session, bill, Decimal("200"),
                      payment_time=datetime.combine(today, datetime.min.time()) + timedelta(hours=10))
        db_session.commit()

        report = ReportService(db_session).get_revenue_report(yesterday, today)
        assert len(report) == 2
        assert report[0]["revenue"] == Decimal("100")
        assert report[1]["revenue"] == Decimal("200")


class TestGetRoomTypeReport:
    """Tests for ReportService.get_room_type_report()"""

    def test_empty_database(self, db_session):
        today = date.today()
        report = ReportService(db_session).get_room_type_report(today, today)
        assert report == []

    def test_room_type_with_stays(self, db_session):
        rt = _make_room_type(db_session, "标准间", Decimal("288"))
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        today = date.today()
        check_in = datetime.combine(today, datetime.min.time())
        stay = _make_stay(
            db_session, guest, room, check_in,
            today + timedelta(days=2),
            StayRecordStatus.CHECKED_OUT,
            check_out_time=datetime.combine(today + timedelta(days=2), datetime.min.time()),
            created_by=emp.id,
        )
        bill = _make_bill(db_session, stay, Decimal("576"), Decimal("576"))
        db_session.commit()

        report = ReportService(db_session).get_room_type_report(today, today + timedelta(days=2))
        assert len(report) == 1
        assert report[0]["room_type_name"] == "标准间"
        assert report[0]["room_nights"] == 2
        assert report[0]["revenue"] == Decimal("576")

    def test_multiple_room_types(self, db_session):
        rt1 = _make_room_type(db_session, "标准间", Decimal("288"))
        rt2 = _make_room_type(db_session, "豪华间", Decimal("588"))
        _make_room(db_session, rt1, "101")
        _make_room(db_session, rt2, "201")
        db_session.commit()

        today = date.today()
        report = ReportService(db_session).get_room_type_report(today, today)
        assert len(report) == 2

    def test_stay_without_bill(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)

        today = date.today()
        _make_stay(
            db_session, guest, room,
            datetime.combine(today, datetime.min.time()),
            today + timedelta(days=1),
            StayRecordStatus.CHECKED_OUT,
            check_out_time=datetime.combine(today + timedelta(days=1), datetime.min.time()),
            created_by=emp.id,
        )
        db_session.commit()

        report = ReportService(db_session).get_room_type_report(today, today + timedelta(days=1))
        assert len(report) == 1
        assert report[0]["revenue"] == Decimal("0")


class TestTodayArrivalsAndDepartures:
    """Tests for get_today_arrivals_count / get_today_departures_count"""

    def test_today_arrivals_count(self, db_session):
        rt = _make_room_type(db_session)
        guest = _make_guest(db_session)

        today = date.today()
        _make_reservation(db_session, guest, rt, today, today + timedelta(days=1),
                          ReservationStatus.CONFIRMED)
        db_session.commit()

        svc = ReportService(db_session)
        assert svc.get_today_arrivals_count() == 1

    def test_today_arrivals_excludes_cancelled(self, db_session):
        rt = _make_room_type(db_session)
        guest = _make_guest(db_session)
        today = date.today()
        _make_reservation(db_session, guest, rt, today, today + timedelta(days=1),
                          ReservationStatus.CANCELLED)
        db_session.commit()

        assert ReportService(db_session).get_today_arrivals_count() == 0

    def test_today_departures_count(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101", status=RoomStatus.OCCUPIED)
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)
        today = date.today()
        _make_stay(db_session, guest, room, datetime.now() - timedelta(days=1),
                   today, created_by=emp.id)
        db_session.commit()

        assert ReportService(db_session).get_today_departures_count() == 1

    def test_today_departures_excludes_checked_out(self, db_session):
        rt = _make_room_type(db_session)
        room = _make_room(db_session, rt, "101")
        guest = _make_guest(db_session)
        emp = _make_employee(db_session)
        today = date.today()
        _make_stay(db_session, guest, room, datetime.now() - timedelta(days=1),
                   today, StayRecordStatus.CHECKED_OUT,
                   check_out_time=datetime.now(), created_by=emp.id)
        db_session.commit()

        assert ReportService(db_session).get_today_departures_count() == 0
