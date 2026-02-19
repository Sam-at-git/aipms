"""
Tests for app/hotel/services/checkout_service.py
Covers: check_out (full flow, bill settlement, unsettled, deposit refund),
        batch_check_out, get_today_expected_checkouts, get_overdue_stays
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, StayRecord, StayRecordStatus,
    Bill, Payment, PaymentMethod, Reservation, ReservationStatus,
    Employee, EmployeeRole,
)
from app.hotel.models.schemas import CheckOutRequest
from app.hotel.services.checkout_service import CheckOutService
from app.security.auth import get_password_hash


# ── helpers ──────────────────────────────────────────────────────────

def _room_type(db, name="标准间"):
    rt = RoomType(name=name, base_price=Decimal("288"), max_occupancy=2)
    db.add(rt)
    db.flush()
    return rt


def _room(db, rt, number="101", status=RoomStatus.OCCUPIED):
    r = Room(room_number=number, floor=1, room_type_id=rt.id, status=status)
    db.add(r)
    db.flush()
    return r


def _guest(db, name="张三"):
    g = Guest(name=name, phone="13800138000", id_type="身份证", id_number="110101199001011234")
    db.add(g)
    db.flush()
    return g


def _employee(db, username="co_op"):
    e = Employee(
        username=username, password_hash=get_password_hash("123456"),
        name="操作员", role=EmployeeRole.RECEPTIONIST, is_active=True)
    db.add(e)
    db.flush()
    return e


def _stay(db, guest, room, check_in=None, expected_out=None,
          status=StayRecordStatus.ACTIVE, reservation=None, deposit=Decimal("0"),
          created_by=None):
    s = StayRecord(
        guest_id=guest.id,
        room_id=room.id,
        check_in_time=check_in or (datetime.now() - timedelta(days=1)),
        expected_check_out=expected_out or (date.today() + timedelta(days=1)),
        status=status,
        reservation_id=reservation.id if reservation else None,
        deposit_amount=deposit,
        created_by=created_by,
    )
    db.add(s)
    db.flush()
    return s


def _bill(db, stay, total=Decimal("288"), paid=Decimal("288")):
    b = Bill(stay_record_id=stay.id, total_amount=total, paid_amount=paid)
    db.add(b)
    db.flush()
    return b


def _reservation(db, guest, rt, check_in=None, check_out=None,
                 status=ReservationStatus.CHECKED_IN):
    r = Reservation(
        reservation_no=f"R{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        guest_id=guest.id,
        room_type_id=rt.id,
        check_in_date=check_in or date.today(),
        check_out_date=check_out or (date.today() + timedelta(days=1)),
        status=status,
    )
    db.add(r)
    db.flush()
    return r


def _noop(event):
    pass


# ── tests ────────────────────────────────────────────────────────────

class TestCheckOut:

    def test_basic_checkout(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt, "101")
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        svc = CheckOutService(db_session, _noop)
        result = svc.check_out(data, emp.id)

        assert result.status == StayRecordStatus.CHECKED_OUT
        assert result.check_out_time is not None
        db_session.refresh(room)
        assert room.status == RoomStatus.VACANT_DIRTY

    def test_stay_not_found(self, db_session):
        emp = _employee(db_session)
        db_session.commit()

        data = CheckOutRequest(stay_record_id=9999)
        with pytest.raises(ValueError, match="住宿记录不存在"):
            CheckOutService(db_session, _noop).check_out(data, emp.id)

    def test_already_checked_out(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, status=StayRecordStatus.CHECKED_OUT,
                     created_by=emp.id)
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        with pytest.raises(ValueError, match="已退房"):
            CheckOutService(db_session, _noop).check_out(data, emp.id)

    def test_unsettled_bill_blocked(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("500"), Decimal("200"))  # 300 balance
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id, allow_unsettled=False)
        with pytest.raises(ValueError, match="账单未结清"):
            CheckOutService(db_session, _noop).check_out(data, emp.id)

    def test_unsettled_bill_allowed_with_reason(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("500"), Decimal("200"))
        db_session.commit()

        data = CheckOutRequest(
            stay_record_id=stay.id,
            allow_unsettled=True,
            unsettled_reason="公司挂账",
        )
        result = CheckOutService(db_session, _noop).check_out(data, emp.id)
        assert result.status == StayRecordStatus.CHECKED_OUT

    def test_unsettled_without_reason_rejected(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("500"), Decimal("200"))
        db_session.commit()

        data = CheckOutRequest(
            stay_record_id=stay.id,
            allow_unsettled=True,
            unsettled_reason=None,
        )
        with pytest.raises(ValueError, match="挂账退房需要填写原因"):
            CheckOutService(db_session, _noop).check_out(data, emp.id)

    def test_bill_settled_flag(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        bill = _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        CheckOutService(db_session, _noop).check_out(data, emp.id)
        db_session.refresh(bill)
        assert bill.is_settled is True

    def test_reservation_completed(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        res = _reservation(db_session, guest, rt, status=ReservationStatus.CHECKED_IN)
        stay = _stay(db_session, guest, room, reservation=res, created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        CheckOutService(db_session, _noop).check_out(data, emp.id)
        db_session.refresh(res)
        assert res.status == ReservationStatus.COMPLETED

    def test_checkout_without_bill(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        # No bill created
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        result = CheckOutService(db_session, _noop).check_out(data, emp.id)
        assert result.status == StayRecordStatus.CHECKED_OUT

    def test_deposit_refund_exceeds_deposit(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, deposit=Decimal("200"), created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id, refund_deposit=Decimal("500"))
        with pytest.raises(ValueError, match="退还押金不能超过原押金金额"):
            CheckOutService(db_session, _noop).check_out(data, emp.id)

    def test_deposit_refund_within_limit(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, deposit=Decimal("500"), created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id, refund_deposit=Decimal("500"))
        result = CheckOutService(db_session, _noop).check_out(data, emp.id)
        assert result.status == StayRecordStatus.CHECKED_OUT

    def test_event_published(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        events = []
        data = CheckOutRequest(stay_record_id=stay.id)
        CheckOutService(db_session, lambda e: events.append(e)).check_out(data, emp.id)
        assert len(events) == 1
        assert "guest.checked_out" in events[0].event_type

    def test_snapshot_created(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        _bill(db_session, stay, Decimal("288"), Decimal("288"))
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        CheckOutService(db_session, _noop).check_out(data, emp.id)

        from app.models.snapshots import OperationSnapshot
        snapshots = db_session.query(OperationSnapshot).all()
        assert len(snapshots) == 1
        assert snapshots[0].operation_type == "check_out"

    def test_bill_with_adjustment(self, db_session):
        """Bill with adjustment_amount factored into balance check"""
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        stay = _stay(db_session, guest, room, created_by=emp.id)
        bill = _bill(db_session, stay, Decimal("288"), Decimal("200"))
        bill.adjustment_amount = Decimal("-88")  # discount, balance = 288 + (-88) - 200 = 0
        db_session.commit()

        data = CheckOutRequest(stay_record_id=stay.id)
        result = CheckOutService(db_session, _noop).check_out(data, emp.id)
        assert result.status == StayRecordStatus.CHECKED_OUT
        db_session.refresh(bill)
        assert bill.is_settled is True


class TestBatchCheckOut:

    def test_batch_success(self, db_session):
        rt = _room_type(db_session)
        guest = _guest(db_session)
        emp = _employee(db_session)

        room1 = _room(db_session, rt, "101")
        stay1 = _stay(db_session, guest, room1, created_by=emp.id)
        _bill(db_session, stay1, Decimal("288"), Decimal("288"))

        room2 = _room(db_session, rt, "102")
        stay2 = _stay(db_session, guest, room2, created_by=emp.id)
        _bill(db_session, stay2, Decimal("288"), Decimal("288"))
        db_session.commit()

        svc = CheckOutService(db_session, _noop)
        results = svc.batch_check_out([stay1.id, stay2.id], emp.id)
        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_batch_partial_failure(self, db_session):
        rt = _room_type(db_session)
        guest = _guest(db_session)
        emp = _employee(db_session)

        room1 = _room(db_session, rt, "101")
        stay1 = _stay(db_session, guest, room1, created_by=emp.id)
        _bill(db_session, stay1, Decimal("288"), Decimal("288"))

        room2 = _room(db_session, rt, "102")
        stay2 = _stay(db_session, guest, room2, created_by=emp.id)
        _bill(db_session, stay2, Decimal("500"), Decimal("100"))  # unsettled
        db_session.commit()

        svc = CheckOutService(db_session, _noop)
        results = svc.batch_check_out([stay1.id, stay2.id], emp.id)
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "账单未结清" in results[1]["message"]

    def test_batch_with_invalid_id(self, db_session):
        emp = _employee(db_session)
        db_session.commit()

        svc = CheckOutService(db_session, _noop)
        results = svc.batch_check_out([9999], emp.id)
        assert len(results) == 1
        assert results[0]["success"] is False


class TestTodayExpectedCheckouts:

    def test_returns_active_stays_due_today(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        today = date.today()
        _stay(db_session, guest, room, expected_out=today, created_by=emp.id)
        db_session.commit()

        stays = CheckOutService(db_session, _noop).get_today_expected_checkouts()
        assert len(stays) == 1

    def test_excludes_checked_out(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        today = date.today()
        _stay(db_session, guest, room, expected_out=today,
              status=StayRecordStatus.CHECKED_OUT, created_by=emp.id)
        db_session.commit()

        stays = CheckOutService(db_session, _noop).get_today_expected_checkouts()
        assert len(stays) == 0

    def test_excludes_future_stays(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        _stay(db_session, guest, room, expected_out=date.today() + timedelta(days=3),
              created_by=emp.id)
        db_session.commit()

        stays = CheckOutService(db_session, _noop).get_today_expected_checkouts()
        assert len(stays) == 0


class TestOverdueStays:

    def test_returns_overdue(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        yesterday = date.today() - timedelta(days=1)
        _stay(db_session, guest, room, expected_out=yesterday, created_by=emp.id)
        db_session.commit()

        overdue = CheckOutService(db_session, _noop).get_overdue_stays()
        assert len(overdue) == 1

    def test_excludes_today(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        _stay(db_session, guest, room, expected_out=date.today(), created_by=emp.id)
        db_session.commit()

        overdue = CheckOutService(db_session, _noop).get_overdue_stays()
        assert len(overdue) == 0

    def test_excludes_checked_out(self, db_session):
        rt = _room_type(db_session)
        room = _room(db_session, rt)
        guest = _guest(db_session)
        emp = _employee(db_session)
        yesterday = date.today() - timedelta(days=1)
        _stay(db_session, guest, room, expected_out=yesterday,
              status=StayRecordStatus.CHECKED_OUT, created_by=emp.id)
        db_session.commit()

        overdue = CheckOutService(db_session, _noop).get_overdue_stays()
        assert len(overdue) == 0
