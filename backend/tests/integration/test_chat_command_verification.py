"""
Comprehensive chat command verification test suite.

Tests every actionable chat command dispatches correctly through
ActionRegistry.dispatch() with real in-memory SQLite, validating
both return values and database state changes.

55 tests across 12 categories:
  1. Guest (3)        2. Room (5)         3. Check-in (4)
  4. Check-out (3)    5. Reservation (4)  6. Stay Record (4)
  7. Task (8)         8. Billing (5)      9. Employee (4)
 10. Room Type (3)   12. Webhook (2)     13. Edge Cases (10)
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.services.ai_service import AIService
from app.services.actions import reset_action_registry
from app.models.ontology import (
    Employee, EmployeeRole,
    Room, RoomStatus, RoomType,
    Guest, StayRecord, StayRecordStatus,
    Task, TaskStatus, TaskType,
    Bill, Payment, PaymentMethod,
    Reservation, ReservationStatus,
)


# ============================================================================
# Helpers & Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the action registry before and after each test."""
    reset_action_registry()
    yield
    reset_action_registry()


def _create_employee(db_session, username, name, role):
    """Helper to create an employee."""
    from app.security.auth import get_password_hash
    user = Employee(
        username=username,
        password_hash=get_password_hash("password"),
        name=name,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _dispatch(db_session, user, action_name, params):
    """Helper: dispatch an action through the registry."""
    service = AIService(db_session)
    registry = service.get_action_registry()
    context = {
        "db": db_session,
        "user": user,
        "param_parser": service.param_parser,
    }
    return registry.dispatch(action_name, params, context)


# --- Users ---

@pytest.fixture
def receptionist(db_session):
    return _create_employee(
        db_session, "cv_receptionist", "测试前台", EmployeeRole.RECEPTIONIST
    )


@pytest.fixture
def manager(db_session):
    return _create_employee(
        db_session, "cv_manager", "测试经理", EmployeeRole.MANAGER
    )


@pytest.fixture
def cleaner(db_session):
    return _create_employee(
        db_session, "cv_cleaner", "测试清洁员", EmployeeRole.CLEANER
    )


@pytest.fixture
def sysadmin(db_session):
    return _create_employee(
        db_session, "cv_sysadmin", "测试管理员", EmployeeRole.SYSADMIN
    )


# --- Room Types ---

@pytest.fixture
def room_type(db_session):
    rt = RoomType(
        name="标准间", description="Standard Room",
        base_price=Decimal("288.00"), max_occupancy=2,
    )
    db_session.add(rt)
    db_session.commit()
    db_session.refresh(rt)
    return rt


@pytest.fixture
def room_type_deluxe(db_session):
    rt = RoomType(
        name="豪华大床房", description="Deluxe King",
        base_price=Decimal("588.00"), max_occupancy=2,
    )
    db_session.add(rt)
    db_session.commit()
    db_session.refresh(rt)
    return rt


# --- Rooms ---

@pytest.fixture
def room_101(db_session, room_type):
    room = Room(
        room_number="101", floor=1,
        room_type_id=room_type.id, status=RoomStatus.VACANT_CLEAN,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def room_201(db_session, room_type):
    room = Room(
        room_number="201", floor=2,
        room_type_id=room_type.id, status=RoomStatus.VACANT_CLEAN,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def room_301(db_session, room_type):
    room = Room(
        room_number="301", floor=3,
        room_type_id=room_type.id, status=RoomStatus.VACANT_CLEAN,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def room_302(db_session, room_type):
    room = Room(
        room_number="302", floor=3,
        room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


# --- Guests ---

@pytest.fixture
def guest_zhang(db_session):
    guest = Guest(
        name="张三", phone="13800138000",
        id_type="身份证", id_number="110101199001011234",
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    return guest


@pytest.fixture
def guest_li(db_session):
    guest = Guest(
        name="李四", phone="13900139000",
        id_type="身份证", id_number="110101199002021234",
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    return guest


# --- Composite Fixtures ---

@pytest.fixture
def active_stay(db_session, room_201, guest_zhang):
    """Active stay: 张三 in room 201 (OCCUPIED)."""
    room_201.status = RoomStatus.OCCUPIED
    db_session.flush()
    stay = StayRecord(
        guest_id=guest_zhang.id,
        room_id=room_201.id,
        check_in_time=datetime.now(),
        expected_check_out=date.today() + timedelta(days=3),
        status=StayRecordStatus.ACTIVE,
    )
    db_session.add(stay)
    db_session.commit()
    db_session.refresh(stay)
    return stay


@pytest.fixture
def active_bill(db_session, active_stay):
    """Bill for active_stay with partial payment."""
    bill = Bill(
        stay_record_id=active_stay.id,
        total_amount=Decimal("864.00"),
        paid_amount=Decimal("288.00"),
        adjustment_amount=Decimal("0"),
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(bill)
    return bill


@pytest.fixture
def payment_on_bill(db_session, active_bill, receptionist):
    """A cash payment record on the active bill."""
    payment = Payment(
        bill_id=active_bill.id,
        amount=Decimal("288.00"),
        method=PaymentMethod.CASH,
        created_by=receptionist.id,
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return payment


@pytest.fixture
def pending_task(db_session, room_201):
    """Pending cleaning task for room 201."""
    task = Task(
        room_id=room_201.id,
        task_type=TaskType.CLEANING,
        status=TaskStatus.PENDING,
        priority=1,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def confirmed_reservation(db_session, room_type, guest_zhang):
    """Confirmed reservation for tomorrow."""
    reservation = Reservation(
        reservation_no="RES20260210001",
        guest_id=guest_zhang.id,
        room_type_id=room_type.id,
        check_in_date=date.today() + timedelta(days=1),
        check_out_date=date.today() + timedelta(days=3),
        status=ReservationStatus.CONFIRMED,
        total_amount=Decimal("576.00"),
        room_count=1,
        adult_count=1,
    )
    db_session.add(reservation)
    db_session.commit()
    db_session.refresh(reservation)
    return reservation


# ============================================================================
# Category 1: Guest Commands (3 tests)
# ============================================================================

class TestGuestCommands:

    def test_update_guest_phone(self, db_session, guest_zhang, receptionist):
        """请把客户张三的联系方式修改为13112345666"""
        result = _dispatch(db_session, receptionist, "update_guest", {
            "guest_name": "张三",
            "phone": "13112345666",
        })
        assert result["success"] is True
        db_session.refresh(guest_zhang)
        assert guest_zhang.phone == "13112345666"

    def test_blacklist_guest(self, db_session, guest_li, receptionist):
        """把李四加入黑名单"""
        result = _dispatch(db_session, receptionist, "update_guest", {
            "guest_name": "李四",
            "is_blacklisted": True,
            "blacklist_reason": "多次违规",
        })
        assert result["success"] is True
        db_session.refresh(guest_li)
        assert guest_li.is_blacklisted is True

    def test_create_guest(self, db_session, receptionist):
        """创建新客人记录"""
        result = _dispatch(db_session, receptionist, "create_guest", {
            "name": "王五",
            "phone": "13500135000",
        })
        assert result["success"] is True
        guest = db_session.query(Guest).filter_by(id=result["guest_id"]).first()
        assert guest is not None
        assert guest.name == "王五"
        assert guest.phone == "13500135000"


# ============================================================================
# Category 2: Room Commands (5 tests)
# ============================================================================

class TestRoomCommands:

    def test_mark_out_of_order(self, db_session, room_101, receptionist):
        """把101房标记为维修"""
        result = _dispatch(db_session, receptionist, "update_room_status", {
            "room_number": "101",
            "status": "out_of_order",
        })
        assert result["success"] is True
        db_session.refresh(room_101)
        assert room_101.status == RoomStatus.OUT_OF_ORDER

    def test_mark_room_clean(self, db_session, room_302, receptionist):
        """把302房标记为已清洁"""
        result = _dispatch(db_session, receptionist, "mark_room_clean", {
            "room_number": "302",
            "status": "vacant_clean",
        })
        assert result["success"] is True
        db_session.refresh(room_302)
        assert room_302.status == RoomStatus.VACANT_CLEAN

    def test_mark_room_dirty(self, db_session, room_101, receptionist):
        """把101房的状态改为脏房"""
        result = _dispatch(db_session, receptionist, "mark_room_dirty", {
            "room_number": "101",
            "status": "vacant_dirty",
        })
        assert result["success"] is True
        db_session.refresh(room_101)
        assert room_101.status == RoomStatus.VACANT_DIRTY

    def test_update_room_status_vacant_clean(self, db_session, room_302, receptionist):
        """更新房间状态为空闲已清洁"""
        result = _dispatch(db_session, receptionist, "update_room_status", {
            "room_number": "302",
            "status": "vacant_clean",
        })
        assert result["success"] is True
        db_session.refresh(room_302)
        assert room_302.status == RoomStatus.VACANT_CLEAN

    def test_nonexistent_room(self, db_session, receptionist):
        """房间不存在时返回错误"""
        result = _dispatch(db_session, receptionist, "update_room_status", {
            "room_number": "999",
            "status": "vacant_clean",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"


# ============================================================================
# Category 3: Check-in Commands (4 tests)
# ============================================================================

class TestCheckinCommands:

    def test_walkin_checkin(self, db_session, room_101, receptionist):
        """办理入住，张三，101房"""
        result = _dispatch(db_session, receptionist, "walkin_checkin", {
            "guest_name": "张三",
            "guest_phone": "13800138000",
            "room_id": room_101.id,
            "expected_check_out": str(date.today() + timedelta(days=1)),
        })
        assert result["success"] is True
        assert "stay_record_id" in result
        # Verify DB state
        stay = db_session.query(StayRecord).filter_by(
            id=result["stay_record_id"]
        ).first()
        assert stay is not None
        assert stay.status == StayRecordStatus.ACTIVE
        db_session.refresh(room_101)
        assert room_101.status == RoomStatus.OCCUPIED

    def test_walkin_checkin_full_params(self, db_session, room_101, receptionist):
        """办理入住，姓名赵六，手机13912345678，身份证"""
        result = _dispatch(db_session, receptionist, "walkin_checkin", {
            "guest_name": "赵六",
            "guest_phone": "13912345678",
            "guest_id_type": "身份证",
            "guest_id_number": "330102199003033456",
            "room_id": room_101.id,
            "expected_check_out": str(date.today() + timedelta(days=2)),
        })
        assert result["success"] is True
        guest = db_session.query(Guest).filter_by(name="赵六").first()
        assert guest is not None
        assert guest.phone == "13912345678"

    def test_checkin_by_reservation_no(
        self, db_session, room_101, confirmed_reservation, receptionist
    ):
        """预订号RES20260210001办理入住"""
        result = _dispatch(db_session, receptionist, "checkin", {
            "reservation_no": confirmed_reservation.reservation_no,
            "room_number": "101",
        })
        assert result["success"] is True
        assert "stay_record_id" in result
        stay = db_session.query(StayRecord).filter_by(
            id=result["stay_record_id"]
        ).first()
        assert stay is not None
        assert stay.room_id == room_101.id

    def test_checkin_with_room_override(
        self, db_session, room_301, confirmed_reservation, receptionist
    ):
        """预订客人到店，分配301房"""
        result = _dispatch(db_session, receptionist, "checkin", {
            "reservation_id": confirmed_reservation.id,
            "room_number": "301",
        })
        assert result["success"] is True
        stay = db_session.query(StayRecord).filter_by(
            id=result["stay_record_id"]
        ).first()
        assert stay.room_id == room_301.id


# ============================================================================
# Category 4: Checkout Commands (3 tests)
# ============================================================================

class TestCheckoutCommands:

    def test_checkout_basic(self, db_session, active_stay, receptionist):
        """退房，201房"""
        result = _dispatch(db_session, receptionist, "checkout", {
            "stay_record_id": active_stay.id,
            "allow_unsettled": True,
        })
        assert result["success"] is True
        assert result["room_number"] == "201"
        db_session.refresh(active_stay)
        assert active_stay.status == StayRecordStatus.CHECKED_OUT
        db_session.refresh(active_stay.room)
        assert active_stay.room.status == RoomStatus.VACANT_DIRTY

    def test_checkout_allow_unsettled(
        self, db_session, active_stay, active_bill, receptionist
    ):
        """201房客人退房，允许未结清"""
        result = _dispatch(db_session, receptionist, "checkout", {
            "stay_record_id": active_stay.id,
            "allow_unsettled": True,
            "unsettled_reason": "VIP客户挂账",
        })
        assert result["success"] is True
        db_session.refresh(active_stay)
        assert active_stay.status == StayRecordStatus.CHECKED_OUT

    def test_early_checkout(self, db_session, active_stay, receptionist):
        """客人提前退房 (expected checkout is today+3)"""
        result = _dispatch(db_session, receptionist, "checkout", {
            "stay_record_id": active_stay.id,
            "allow_unsettled": True,
        })
        assert result["success"] is True
        db_session.refresh(active_stay)
        assert active_stay.status == StayRecordStatus.CHECKED_OUT


# ============================================================================
# Category 5: Reservation Commands (4 tests)
# ============================================================================

class TestReservationCommands:

    def test_create_reservation(self, db_session, room_type, receptionist):
        """创建预订，张三，标准间"""
        result = _dispatch(db_session, receptionist, "create_reservation", {
            "guest_name": "张三",
            "guest_phone": "13800138000",
            "room_type_id": room_type.id,
            "check_in_date": str(date.today() + timedelta(days=1)),
            "check_out_date": str(date.today() + timedelta(days=3)),
        })
        assert result["success"] is True
        assert "reservation_id" in result
        reservation = db_session.query(Reservation).filter_by(
            id=result["reservation_id"]
        ).first()
        assert reservation is not None
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_cancel_reservation(
        self, db_session, confirmed_reservation, receptionist
    ):
        """取消预订号RES20260210001"""
        result = _dispatch(db_session, receptionist, "cancel_reservation", {
            "reservation_no": confirmed_reservation.reservation_no,
            "reason": "客人行程变更",
        })
        assert result["success"] is True
        db_session.refresh(confirmed_reservation)
        assert confirmed_reservation.status == ReservationStatus.CANCELLED

    def test_modify_reservation_date(
        self, db_session, confirmed_reservation, receptionist
    ):
        """修改预订，把入住日期改为后天"""
        new_date = date.today() + timedelta(days=2)
        result = _dispatch(db_session, receptionist, "modify_reservation", {
            "reservation_id": confirmed_reservation.id,
            "check_in_date": str(new_date),
        })
        assert result["success"] is True
        db_session.refresh(confirmed_reservation)
        assert confirmed_reservation.check_in_date == new_date

    def test_modify_reservation_no_fields(
        self, db_session, confirmed_reservation, receptionist
    ):
        """修改预订但不提供任何字段 → no_updates"""
        result = _dispatch(db_session, receptionist, "modify_reservation", {
            "reservation_id": confirmed_reservation.id,
        })
        assert result["success"] is False
        assert result["error"] == "no_updates"


# ============================================================================
# Category 6: Stay Record Commands (4 tests)
# ============================================================================

class TestStayRecordCommands:

    def test_extend_stay(self, db_session, active_stay, active_bill, receptionist):
        """延长张三的住宿到 today+5 (bill required for price recalculation)"""
        new_date = date.today() + timedelta(days=5)
        result = _dispatch(db_session, receptionist, "extend_stay", {
            "stay_record_id": active_stay.id,
            "new_check_out_date": str(new_date),
        })
        assert result["success"] is True
        db_session.refresh(active_stay)
        assert active_stay.expected_check_out == new_date

    def test_change_room(self, db_session, active_stay, room_301, receptionist):
        """201房客人换房到301房"""
        result = _dispatch(db_session, receptionist, "change_room", {
            "stay_record_id": active_stay.id,
            "new_room_number": "301",
        })
        assert result["success"] is True
        db_session.refresh(active_stay)
        assert active_stay.room_id == room_301.id
        db_session.refresh(room_301)
        assert room_301.status == RoomStatus.OCCUPIED

    def test_change_room_upgrade(
        self, db_session, active_stay, active_bill, room_type_deluxe, receptionist
    ):
        """换房升级到豪华大床房 (bill required for price recalculation)"""
        deluxe_room = Room(
            room_number="501", floor=5,
            room_type_id=room_type_deluxe.id,
            status=RoomStatus.VACANT_CLEAN,
        )
        db_session.add(deluxe_room)
        db_session.commit()
        db_session.refresh(deluxe_room)

        result = _dispatch(db_session, receptionist, "change_room", {
            "stay_record_id": active_stay.id,
            "new_room_number": "501",
        })
        assert result["success"] is True
        db_session.refresh(active_stay)
        assert active_stay.room_id == deluxe_room.id

    def test_change_room_nonexistent(self, db_session, active_stay, receptionist):
        """换房目标不存在"""
        result = _dispatch(db_session, receptionist, "change_room", {
            "stay_record_id": active_stay.id,
            "new_room_number": "999",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"


# ============================================================================
# Category 7: Task Commands (8 tests)
# ============================================================================

class TestTaskCommands:

    def test_create_cleaning_task(self, db_session, room_101, receptionist):
        """创建清洁任务给101房"""
        result = _dispatch(db_session, receptionist, "create_task", {
            "room_id": room_101.id,
            "task_type": "CLEANING",
        })
        assert result["success"] is True
        assert "task_id" in result
        task = db_session.query(Task).filter_by(id=result["task_id"]).first()
        assert task is not None
        assert task.task_type == TaskType.CLEANING
        assert task.status == TaskStatus.PENDING

    def test_assign_task(self, db_session, pending_task, cleaner, receptionist):
        """分配清洁任务给测试清洁员"""
        result = _dispatch(db_session, receptionist, "assign_task", {
            "task_id": pending_task.id,
            "assignee_name": "测试清洁员",
        })
        assert result["success"] is True
        db_session.refresh(pending_task)
        assert pending_task.assignee_id == cleaner.id
        assert pending_task.status == TaskStatus.ASSIGNED

    def test_start_task(self, db_session, room_201, cleaner):
        """开始任务"""
        task = Task(
            room_id=room_201.id, task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED, priority=1,
            assignee_id=cleaner.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = _dispatch(db_session, cleaner, "start_task", {
            "task_id": task.id,
        })
        assert result["success"] is True
        db_session.refresh(task)
        assert task.status == TaskStatus.IN_PROGRESS

    def test_complete_task(self, db_session, room_201, cleaner):
        """完成清洁任务"""
        task = Task(
            room_id=room_201.id, task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS, priority=1,
            assignee_id=cleaner.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = _dispatch(db_session, cleaner, "complete_task", {
            "task_id": task.id,
        })
        assert result["success"] is True
        db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED

    def test_create_maintenance_task(self, db_session, room_101, receptionist):
        """创建维修任务，101房空调坏了"""
        result = _dispatch(db_session, receptionist, "create_task", {
            "room_id": room_101.id,
            "task_type": "maintenance",
        })
        assert result["success"] is True
        task = db_session.query(Task).filter_by(id=result["task_id"]).first()
        assert task.task_type == TaskType.MAINTENANCE

    def test_delete_task(self, db_session, pending_task, receptionist):
        """取消/删除任务"""
        task_id = pending_task.id
        result = _dispatch(db_session, receptionist, "delete_task", {
            "task_id": task_id,
        })
        assert result["success"] is True
        assert db_session.query(Task).filter_by(id=task_id).first() is None

    def test_assign_task_employee_not_found(
        self, db_session, pending_task, receptionist
    ):
        """分配任务给不存在的员工"""
        result = _dispatch(db_session, receptionist, "assign_task", {
            "task_id": pending_task.id,
            "assignee_name": "不存在的员工",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_complete_task_with_notes(self, db_session, room_201, cleaner):
        """完成任务带备注"""
        task = Task(
            room_id=room_201.id, task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS, priority=1,
            assignee_id=cleaner.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = _dispatch(db_session, cleaner, "complete_task", {
            "task_id": task.id,
            "notes": "已完成深度清洁",
        })
        assert result["success"] is True
        db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED


# ============================================================================
# Category 8: Billing Commands (5 tests)
# ============================================================================

class TestBillingCommands:

    def test_add_payment_cash(
        self, db_session, active_stay, active_bill, receptionist
    ):
        """收款100元，现金"""
        result = _dispatch(db_session, receptionist, "add_payment", {
            "bill_id": active_bill.id,
            "amount": "100",
            "payment_method": "cash",
        })
        assert result["success"] is True
        assert result["amount"] == 100.0
        payment = db_session.query(Payment).filter_by(
            id=result["payment_id"]
        ).first()
        assert payment is not None
        assert payment.method == PaymentMethod.CASH

    def test_adjust_bill(self, db_session, active_stay, active_bill, manager):
        """调整账单，减免50元房费"""
        result = _dispatch(db_session, manager, "adjust_bill", {
            "bill_id": active_bill.id,
            "amount": "-50",
            "reason": "老顾客优惠减免",
        })
        assert result["success"] is True
        db_session.refresh(active_bill)
        assert active_bill.adjustment_amount == Decimal("-50")

    def test_add_payment_card(
        self, db_session, active_stay, active_bill, receptionist
    ):
        """账单收款200元，刷卡"""
        result = _dispatch(db_session, receptionist, "add_payment", {
            "bill_id": active_bill.id,
            "amount": "200",
            "payment_method": "card",
        })
        assert result["success"] is True
        assert result["method"] == "card"

    def test_refund_payment(
        self, db_session, active_stay, active_bill, payment_on_bill, manager
    ):
        """退款50元到原支付方式"""
        result = _dispatch(db_session, manager, "refund_payment", {
            "payment_id": payment_on_bill.id,
            "amount": "50",
            "reason": "部分退款",
        })
        assert result["success"] is True
        assert result["refund_amount"] == 50.0
        refund = db_session.query(Payment).filter_by(
            id=result["refund_payment_id"]
        ).first()
        assert refund is not None
        assert refund.amount < 0

    def test_refund_exceeds_amount(
        self, db_session, active_stay, active_bill, payment_on_bill, manager
    ):
        """退款超过原金额"""
        result = _dispatch(db_session, manager, "refund_payment", {
            "payment_id": payment_on_bill.id,
            "amount": "500",
            "reason": "超额退款",
        })
        assert result["success"] is False
        assert result["error"] == "validation_error"


# ============================================================================
# Category 9: Employee Commands (4 tests)
# ============================================================================

class TestEmployeeCommands:

    def test_create_employee(self, db_session, manager):
        """创建员工账号，前台小美"""
        result = _dispatch(db_session, manager, "create_employee", {
            "username": "xiaomei",
            "name": "小美",
            "role": "receptionist",
        })
        assert result["success"] is True
        emp = db_session.query(Employee).filter_by(username="xiaomei").first()
        assert emp is not None
        assert emp.name == "小美"
        assert emp.role == EmployeeRole.RECEPTIONIST

    def test_update_employee_role(self, db_session, manager):
        """修改员工角色"""
        target = _create_employee(
            db_session, "role_target", "目标员工", EmployeeRole.RECEPTIONIST
        )
        result = _dispatch(db_session, manager, "update_employee", {
            "employee_id": target.id,
            "role": "manager",
        })
        assert result["success"] is True
        db_session.refresh(target)
        assert target.role == EmployeeRole.MANAGER

    def test_deactivate_employee(self, db_session, manager):
        """停用员工"""
        target = _create_employee(
            db_session, "deact_target", "待停用", EmployeeRole.CLEANER
        )
        result = _dispatch(db_session, manager, "deactivate_employee", {
            "employee_id": target.id,
        })
        assert result["success"] is True
        db_session.refresh(target)
        assert target.is_active is False

    def test_create_employee_duplicate(self, db_session, manager):
        """重复用户名"""
        _create_employee(
            db_session, "dup_user", "已存在", EmployeeRole.RECEPTIONIST
        )
        result = _dispatch(db_session, manager, "create_employee", {
            "username": "dup_user",
            "name": "新员工",
            "role": "receptionist",
        })
        assert result["success"] is False
        assert result["error"] == "duplicate"


# ============================================================================
# Category 10: Room Type Commands (3 tests)
# ============================================================================

class TestRoomTypeCommands:

    def test_update_room_type_price(self, db_session, room_type, manager):
        """修改标准间价格为298元"""
        result = _dispatch(db_session, manager, "update_room_type", {
            "room_type_name": "标准间",
            "base_price": "298",
        })
        assert result["success"] is True
        db_session.refresh(room_type)
        assert room_type.base_price == Decimal("298")

    def test_create_room_type(self, db_session, manager):
        """创建新房型"""
        result = _dispatch(db_session, manager, "create_room_type", {
            "name": "亲子房",
            "base_price": "388",
            "max_occupancy": 3,
        })
        assert result["success"] is True
        rt = db_session.query(RoomType).filter_by(name="亲子房").first()
        assert rt is not None
        assert rt.base_price == Decimal("388")

    def test_update_room_type_no_fields(self, db_session, room_type, manager):
        """更新房型但不提供更新字段 → no_updates"""
        result = _dispatch(db_session, manager, "update_room_type", {
            "room_type_name": "标准间",
        })
        assert result["success"] is False
        assert result["error"] == "no_updates"


# ============================================================================
# Category 12: Webhook & Notification Commands (2 tests)
# ============================================================================

class TestWebhookNotificationCommands:

    def test_sync_ota_availability(self, db_session, manager):
        """同步房态到OTA"""
        result = _dispatch(db_session, manager, "sync_ota_availability", {
            "channel": "all",
        })
        assert result["success"] is True

    def test_notify_task_assigned(self, db_session, receptionist):
        """通知李四有新任务"""
        result = _dispatch(db_session, receptionist, "notify_task_assigned", {
            "target": "李四",
            "message": "有新的清洁任务",
        })
        assert result["success"] is True


# ============================================================================
# Category 13: Edge Cases (10 tests)
# ============================================================================

class TestEdgeCases:

    def test_update_nonexistent_room(self, db_session, receptionist):
        """修改不存在的房间状态"""
        result = _dispatch(db_session, receptionist, "update_room_status", {
            "room_number": "999",
            "status": "vacant_clean",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_walkin_checkin_occupied_room(
        self, db_session, active_stay, receptionist
    ):
        """入住已满房"""
        result = _dispatch(db_session, receptionist, "walkin_checkin", {
            "guest_name": "新客人",
            "guest_phone": "13600136000",
            "room_id": active_stay.room_id,
            "expected_check_out": str(date.today() + timedelta(days=1)),
        })
        assert result["success"] is False

    def test_reservation_checkout_before_checkin(self, db_session, room_type, receptionist):
        """退房日期早于入住日期 → Pydantic validation error"""
        with pytest.raises(Exception):
            _dispatch(db_session, receptionist, "create_reservation", {
                "guest_name": "测试",
                "room_type_id": room_type.id,
                "check_in_date": str(date.today() + timedelta(days=3)),
                "check_out_date": str(date.today() + timedelta(days=1)),
            })

    def test_assign_task_inactive_employee(
        self, db_session, pending_task, receptionist
    ):
        """任务分配给离职员工（is_active=False, 查询不到）"""
        from app.security.auth import get_password_hash
        inactive = Employee(
            username="inactive_emp", name="离职员工",
            password_hash=get_password_hash("pw"),
            role=EmployeeRole.CLEANER, is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()

        result = _dispatch(db_session, receptionist, "assign_task", {
            "task_id": pending_task.id,
            "assignee_name": "离职员工",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_unknown_action(self, db_session, receptionist):
        """未知操作 → ValueError"""
        with pytest.raises(ValueError, match="Unknown action"):
            _dispatch(db_session, receptionist, "nonexistent_action", {})

    def test_update_guest_not_found(self, db_session, receptionist):
        """更新不存在的客人"""
        result = _dispatch(db_session, receptionist, "update_guest", {
            "guest_name": "不存在的人",
            "phone": "13000000000",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_cancel_nonexistent_reservation(self, db_session, receptionist):
        """取消不存在的预订"""
        result = _dispatch(db_session, receptionist, "cancel_reservation", {
            "reservation_no": "NONEXISTENT",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_change_room_to_occupied(
        self, db_session, active_stay, room_type, receptionist
    ):
        """换房到已占用房间"""
        occupied = Room(
            room_number="202", floor=2,
            room_type_id=room_type.id, status=RoomStatus.OCCUPIED,
        )
        db_session.add(occupied)
        db_session.commit()

        result = _dispatch(db_session, receptionist, "change_room", {
            "stay_record_id": active_stay.id,
            "new_room_number": "202",
        })
        assert result["success"] is False

    def test_deactivate_already_inactive(self, db_session, manager):
        """停用已停用的员工"""
        target = _create_employee(
            db_session, "already_off", "已停用", EmployeeRole.CLEANER
        )
        target.is_active = False
        db_session.commit()

        result = _dispatch(db_session, manager, "deactivate_employee", {
            "employee_id": target.id,
        })
        assert result["success"] is False
        assert result["error"] == "already_deactivated"

    def test_refund_nonexistent_payment(self, db_session, manager):
        """退款不存在的支付记录"""
        result = _dispatch(db_session, manager, "refund_payment", {
            "payment_id": 99999,
            "reason": "不存在",
        })
        assert result["success"] is False
        assert result["error"] == "not_found"
