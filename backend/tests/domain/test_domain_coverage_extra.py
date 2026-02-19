"""
tests/domain/test_domain_coverage_extra.py

Additional coverage tests for hotel domain objects - covering uncovered methods,
edge cases, state transitions, and repository operations.
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, Employee, EmployeeRole,
    Reservation, ReservationStatus, StayRecord, StayRecordStatus,
    Task, TaskStatus, TaskType, Bill, Payment, PaymentMethod,
)


# ============== Fixtures ==============

@pytest.fixture
def sample_room_type(db_session):
    rt = RoomType(name="Standard", base_price=Decimal("288.00"), max_occupancy=2)
    db_session.add(rt)
    db_session.commit()
    return rt


@pytest.fixture
def sample_guest(db_session):
    guest = Guest(name="测试客人", phone="13800138000", id_type="身份证", id_number="110101199001011234")
    db_session.add(guest)
    db_session.commit()
    return guest


@pytest.fixture
def sample_room(db_session, sample_room_type):
    room = Room(
        room_number="201", floor=2,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN,
    )
    db_session.add(room)
    db_session.commit()
    return room


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


@pytest.fixture
def sample_stay(db_session, sample_guest, sample_room):
    stay = StayRecord(
        guest_id=sample_guest.id,
        room_id=sample_room.id,
        expected_check_out=date.today() + timedelta(days=2),
        status=StayRecordStatus.ACTIVE,
        check_in_time=datetime.now(),
        deposit_amount=Decimal("500.00"),
    )
    db_session.add(stay)
    db_session.commit()
    return stay


@pytest.fixture
def sample_task(db_session, sample_room):
    task = Task(
        room_id=sample_room.id,
        task_type=TaskType.CLEANING,
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    db_session.commit()
    return task


@pytest.fixture
def sample_bill(db_session, sample_stay):
    bill = Bill(
        stay_record_id=sample_stay.id,
        total_amount=Decimal("576.00"),
        paid_amount=Decimal("0.00"),
    )
    db_session.add(bill)
    db_session.commit()
    return bill


@pytest.fixture
def sample_employee(db_session):
    from app.security.auth import get_password_hash
    emp = Employee(
        username="test_emp_domain",
        password_hash=get_password_hash("123456"),
        name="测试员工",
        role=EmployeeRole.RECEPTIONIST,
        phone="13900139000",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    return emp


# ============== Reservation Domain ==============

class TestReservationEntityExtra:
    """Cover uncovered lines in reservation domain entity."""

    def test_update_amount(self, sample_reservation):
        from app.hotel.domain.reservation import ReservationEntity
        entity = ReservationEntity(sample_reservation)
        entity.update_amount(999.50)
        assert entity.total_amount == Decimal("999.50")

    def test_check_in_invalid_state(self, sample_reservation):
        """Test check_in from cancelled state raises ValueError."""
        from app.hotel.domain.reservation import ReservationEntity
        sample_reservation.status = ReservationStatus.CANCELLED
        entity = ReservationEntity(sample_reservation)
        with pytest.raises(ValueError, match="不允许办理入住"):
            entity.check_in(room_id=1)

    def test_cancel_invalid_state(self, sample_reservation):
        """Test cancel from checked_in state raises ValueError."""
        from app.hotel.domain.reservation import ReservationEntity
        sample_reservation.status = ReservationStatus.CHECKED_IN
        entity = ReservationEntity(sample_reservation)
        with pytest.raises(ValueError, match="不允许取消"):
            entity.cancel("test")

    def test_mark_no_show_invalid_state(self, sample_reservation):
        """Test mark_no_show from cancelled state raises ValueError."""
        from app.hotel.domain.reservation import ReservationEntity
        sample_reservation.status = ReservationStatus.CANCELLED
        entity = ReservationEntity(sample_reservation)
        with pytest.raises(ValueError, match="不允许标记为未到店"):
            entity.mark_no_show()

    def test_is_checked_in(self, sample_reservation):
        """Test is_checked_in method."""
        from app.hotel.domain.reservation import ReservationEntity
        sample_reservation.status = ReservationStatus.CHECKED_IN
        entity = ReservationEntity(sample_reservation)
        assert entity.is_checked_in() is True

    def test_prepaid_amount(self, sample_reservation):
        """Test prepaid_amount property."""
        from app.hotel.domain.reservation import ReservationEntity
        entity = ReservationEntity(sample_reservation)
        assert entity.prepaid_amount == Decimal("0")

    def test_to_dict_full(self, sample_reservation):
        """Test to_dict with all fields populated."""
        from app.hotel.domain.reservation import ReservationEntity
        entity = ReservationEntity(sample_reservation)
        d = entity.to_dict()
        assert "is_active" in d
        assert "nights" in d
        assert d["prepaid_amount"] == 0.0

    def test_repository_find_by_date_range(self, db_session, sample_reservation):
        """Test find_by_date_range repository method."""
        from app.hotel.domain.reservation import ReservationRepository
        repo = ReservationRepository(db_session)
        results = repo.find_by_date_range(date(2025, 1, 1), date(2025, 3, 1))
        assert len(results) >= 1

    def test_repository_find_departures(self, db_session, sample_reservation):
        """Test find_departures repository method."""
        from app.hotel.domain.reservation import ReservationRepository
        sample_reservation.status = ReservationStatus.CHECKED_IN
        db_session.commit()
        repo = ReservationRepository(db_session)
        departures = repo.find_departures(date(2025, 2, 3))
        assert len(departures) >= 1

    def test_repository_list_all(self, db_session, sample_reservation):
        """Test list_all repository method."""
        from app.hotel.domain.reservation import ReservationRepository
        repo = ReservationRepository(db_session)
        all_res = repo.list_all()
        assert len(all_res) >= 1

    def test_repository_find_by_status_invalid(self, db_session):
        """Test find_by_status with invalid status returns empty."""
        from app.hotel.domain.reservation import ReservationRepository
        repo = ReservationRepository(db_session)
        result = repo.find_by_status("nonexistent_status")
        assert result == []

    def test_repository_get_by_id_not_found(self, db_session):
        """Test get_by_id returns None for nonexistent ID."""
        from app.hotel.domain.reservation import ReservationRepository
        repo = ReservationRepository(db_session)
        assert repo.get_by_id(99999) is None

    def test_repository_get_by_no_not_found(self, db_session):
        """Test get_by_no returns None for nonexistent number."""
        from app.hotel.domain.reservation import ReservationRepository
        repo = ReservationRepository(db_session)
        assert repo.get_by_no("NONEXISTENT") is None


# ============== StayRecord Domain ==============

class TestStayRecordEntityExtra:
    """Cover uncovered lines in stay_record domain."""

    def test_check_out_already_checked_out(self, sample_stay):
        """Test check_out on already checked out stay."""
        from app.hotel.domain.stay_record import StayRecordEntity
        sample_stay.status = StayRecordStatus.CHECKED_OUT
        entity = StayRecordEntity(sample_stay)
        with pytest.raises(ValueError, match="已经退房"):
            entity.check_out()

    def test_check_out_with_specific_time(self, sample_stay):
        """Test check_out with explicit checkout time."""
        from app.hotel.domain.stay_record import StayRecordEntity
        entity = StayRecordEntity(sample_stay)
        checkout_time = datetime(2025, 3, 1, 12, 0, 0)
        entity.check_out(checkout_time)
        assert entity.check_out_time == checkout_time

    def test_check_out_default_time(self, sample_stay):
        """Test check_out without explicit time (uses utcnow)."""
        from app.hotel.domain.stay_record import StayRecordEntity
        entity = StayRecordEntity(sample_stay)
        entity.check_out()
        assert entity.check_out_time is not None

    def test_extend_stay(self, sample_stay):
        """Test extend_stay method."""
        from app.hotel.domain.stay_record import StayRecordEntity
        entity = StayRecordEntity(sample_stay)
        new_date = date.today() + timedelta(days=10)
        entity.extend_stay(new_date)
        assert entity.expected_check_out == new_date

    def test_get_nights_with_checkout(self, sample_stay):
        """Test get_nights when checkout is present."""
        from app.hotel.domain.stay_record import StayRecordEntity
        sample_stay.check_out_time = datetime.now() + timedelta(days=2)
        entity = StayRecordEntity(sample_stay)
        nights = entity.get_nights()
        assert nights >= 0

    def test_get_nights_without_checkout(self, sample_stay):
        """Test get_nights with expected_check_out only."""
        from app.hotel.domain.stay_record import StayRecordEntity
        entity = StayRecordEntity(sample_stay)
        nights = entity.get_nights()
        assert nights >= 0

    def test_to_dict(self, sample_stay):
        """Test to_dict method."""
        from app.hotel.domain.stay_record import StayRecordEntity
        entity = StayRecordEntity(sample_stay)
        d = entity.to_dict()
        assert "deposit_amount" in d
        assert "nights" in d

    def test_repository_find_active(self, db_session, sample_stay):
        """Test find_active repository method."""
        from app.hotel.domain.stay_record import StayRecordRepository
        repo = StayRecordRepository(db_session)
        active = repo.find_active()
        assert len(active) >= 1

    def test_repository_find_by_guest(self, db_session, sample_stay, sample_guest):
        """Test find_by_guest repository method."""
        from app.hotel.domain.stay_record import StayRecordRepository
        repo = StayRecordRepository(db_session)
        results = repo.find_by_guest(sample_guest.id)
        assert len(results) >= 1

    def test_repository_find_by_room(self, db_session, sample_stay, sample_room):
        """Test find_by_room repository method."""
        from app.hotel.domain.stay_record import StayRecordRepository
        repo = StayRecordRepository(db_session)
        results = repo.find_by_room(sample_room.id)
        assert len(results) >= 1

    def test_repository_list_all(self, db_session, sample_stay):
        """Test list_all repository method."""
        from app.hotel.domain.stay_record import StayRecordRepository
        repo = StayRecordRepository(db_session)
        all_stays = repo.list_all()
        assert len(all_stays) >= 1

    def test_repository_save(self, db_session, sample_guest, sample_room):
        """Test save repository method."""
        from app.hotel.domain.stay_record import StayRecordEntity, StayRecordRepository
        new_stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            expected_check_out=date.today() + timedelta(days=3),
            check_in_time=datetime.now(),
        )
        entity = StayRecordEntity(new_stay)
        repo = StayRecordRepository(db_session)
        repo.save(entity)
        found = repo.get_by_id(new_stay.id)
        assert found is not None


# ============== Task Domain ==============

class TestTaskEntityExtra:
    """Cover uncovered lines in task domain."""

    def test_assign_invalid_state(self, sample_task):
        """Test assign from completed state raises ValueError."""
        from app.hotel.domain.task import TaskEntity
        sample_task.status = TaskStatus.COMPLETED
        entity = TaskEntity(sample_task)
        with pytest.raises(ValueError, match="不允许分配"):
            entity.assign(1)

    def test_start_invalid_state(self, sample_task):
        """Test start from pending state raises ValueError."""
        from app.hotel.domain.task import TaskEntity
        entity = TaskEntity(sample_task)
        with pytest.raises(ValueError, match="不允许开始"):
            entity.start()

    def test_complete_invalid_state(self, sample_task):
        """Test complete from pending state raises ValueError."""
        from app.hotel.domain.task import TaskEntity
        entity = TaskEntity(sample_task)
        with pytest.raises(ValueError, match="不允许完成"):
            entity.complete()

    def test_is_pending(self, sample_task):
        """Test is_pending method."""
        from app.hotel.domain.task import TaskEntity
        entity = TaskEntity(sample_task)
        assert entity.is_pending() is True

    def test_is_completed(self, sample_task):
        """Test is_completed method."""
        from app.hotel.domain.task import TaskEntity
        sample_task.status = TaskStatus.COMPLETED
        entity = TaskEntity(sample_task)
        assert entity.is_completed() is True

    def test_to_dict(self, sample_task):
        """Test to_dict method."""
        from app.hotel.domain.task import TaskEntity
        entity = TaskEntity(sample_task)
        d = entity.to_dict()
        assert "is_pending" in d
        assert "is_completed" in d
        assert d["task_type"] == "cleaning"

    def test_repository_find_by_room(self, db_session, sample_task, sample_room):
        """Test find_by_room repository method."""
        from app.hotel.domain.task import TaskRepository
        repo = TaskRepository(db_session)
        tasks = repo.find_by_room(sample_room.id)
        assert len(tasks) >= 1

    def test_repository_find_by_status(self, db_session, sample_task):
        """Test find_by_status repository method."""
        from app.hotel.domain.task import TaskRepository
        repo = TaskRepository(db_session)
        tasks = repo.find_by_status("pending")
        assert len(tasks) >= 1

    def test_repository_find_by_status_invalid(self, db_session):
        """Test find_by_status with invalid status."""
        from app.hotel.domain.task import TaskRepository
        repo = TaskRepository(db_session)
        assert repo.find_by_status("invalid_status") == []

    def test_repository_find_pending(self, db_session, sample_task):
        """Test find_pending repository method."""
        from app.hotel.domain.task import TaskRepository
        repo = TaskRepository(db_session)
        tasks = repo.find_pending()
        assert len(tasks) >= 1

    def test_repository_find_by_assignee(self, db_session, sample_task, sample_employee):
        """Test find_by_assignee repository method."""
        from app.hotel.domain.task import TaskRepository
        sample_task.assignee_id = sample_employee.id
        db_session.commit()
        repo = TaskRepository(db_session)
        tasks = repo.find_by_assignee(sample_employee.id)
        assert len(tasks) >= 1

    def test_repository_list_all(self, db_session, sample_task):
        """Test list_all repository method."""
        from app.hotel.domain.task import TaskRepository
        repo = TaskRepository(db_session)
        all_tasks = repo.list_all()
        assert len(all_tasks) >= 1

    def test_repository_save(self, db_session, sample_room):
        """Test save repository method."""
        from app.hotel.domain.task import TaskEntity, TaskRepository
        new_task = Task(
            room_id=sample_room.id,
            task_type=TaskType.MAINTENANCE,
            status=TaskStatus.PENDING,
        )
        entity = TaskEntity(new_task)
        repo = TaskRepository(db_session)
        repo.save(entity)
        found = repo.get_by_id(new_task.id)
        assert found is not None


# ============== Employee Domain ==============

class TestEmployeeEntityExtra:
    """Cover uncovered lines in employee domain."""

    def test_update_role(self, sample_employee):
        """Test update_role method."""
        from app.hotel.domain.employee import EmployeeEntity
        entity = EmployeeEntity(sample_employee)
        entity.update_role("manager")
        assert entity.role == "manager"

    def test_deactivate(self, sample_employee):
        """Test deactivate method."""
        from app.hotel.domain.employee import EmployeeEntity
        entity = EmployeeEntity(sample_employee)
        entity.deactivate()
        assert entity.is_active is False

    def test_activate(self, sample_employee):
        """Test activate method."""
        from app.hotel.domain.employee import EmployeeEntity
        sample_employee.is_active = False
        entity = EmployeeEntity(sample_employee)
        entity.activate()
        assert entity.is_active is True

    def test_is_manager(self, sample_employee):
        """Test is_manager method."""
        from app.hotel.domain.employee import EmployeeEntity
        sample_employee.role = EmployeeRole.MANAGER
        entity = EmployeeEntity(sample_employee)
        assert entity.is_manager() is True

    def test_is_cleaner(self, sample_employee):
        """Test is_cleaner method."""
        from app.hotel.domain.employee import EmployeeEntity
        sample_employee.role = EmployeeRole.CLEANER
        entity = EmployeeEntity(sample_employee)
        assert entity.is_cleaner() is True

    def test_to_dict(self, sample_employee):
        """Test to_dict method."""
        from app.hotel.domain.employee import EmployeeEntity
        entity = EmployeeEntity(sample_employee)
        d = entity.to_dict()
        assert "is_manager" in d
        assert "is_cleaner" in d
        assert d["phone"] == "13900139000"

    def test_repository_get_by_username(self, db_session, sample_employee):
        """Test get_by_username repository method."""
        from app.hotel.domain.employee import EmployeeRepository
        repo = EmployeeRepository(db_session)
        emp = repo.get_by_username("test_emp_domain")
        assert emp is not None
        assert emp.name == "测试员工"

    def test_repository_find_by_role(self, db_session, sample_employee):
        """Test find_by_role repository method."""
        from app.hotel.domain.employee import EmployeeRepository
        repo = EmployeeRepository(db_session)
        results = repo.find_by_role("receptionist")
        assert len(results) >= 1

    def test_repository_find_by_role_invalid(self, db_session):
        """Test find_by_role with invalid role."""
        from app.hotel.domain.employee import EmployeeRepository
        repo = EmployeeRepository(db_session)
        assert repo.find_by_role("invalid_role") == []

    def test_repository_find_active(self, db_session, sample_employee):
        """Test find_active repository method."""
        from app.hotel.domain.employee import EmployeeRepository
        repo = EmployeeRepository(db_session)
        active = repo.find_active()
        assert len(active) >= 1

    def test_repository_find_cleaners(self, db_session):
        """Test find_cleaners repository method."""
        from app.security.auth import get_password_hash
        from app.hotel.domain.employee import EmployeeRepository
        cleaner = Employee(
            username="cleaner_domain_test",
            password_hash=get_password_hash("123456"),
            name="Domain清洁员",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.commit()
        repo = EmployeeRepository(db_session)
        cleaners = repo.find_cleaners()
        assert len(cleaners) >= 1

    def test_repository_list_all(self, db_session, sample_employee):
        """Test list_all repository method."""
        from app.hotel.domain.employee import EmployeeRepository
        repo = EmployeeRepository(db_session)
        all_emps = repo.list_all()
        assert len(all_emps) >= 1


# ============== Bill Domain ==============

class TestBillEntityExtra:
    """Cover uncovered lines in bill domain."""

    def test_add_payment_settles_bill(self, sample_bill):
        """Test add_payment when payment settles the bill."""
        from app.hotel.domain.bill import BillEntity
        entity = BillEntity(sample_bill)
        entity.add_payment(600.00, "cash")  # More than total
        assert entity.is_settled is True

    def test_apply_discount(self, sample_bill):
        """Test apply_discount method."""
        from app.hotel.domain.bill import BillEntity
        entity = BillEntity(sample_bill)
        entity.apply_discount(50.0, "VIP折扣")
        assert entity.adjustment_amount == Decimal("-50.0")
        assert entity.adjustment_reason == "VIP折扣"

    def test_is_fully_paid(self, sample_bill):
        """Test is_fully_paid method."""
        from app.hotel.domain.bill import BillEntity
        entity = BillEntity(sample_bill)
        assert entity.is_fully_paid() is False
        entity.add_payment(576.00, "card")
        assert entity.is_fully_paid() is True

    def test_outstanding_balance(self, sample_bill):
        """Test outstanding_balance property."""
        from app.hotel.domain.bill import BillEntity
        entity = BillEntity(sample_bill)
        assert entity.outstanding_balance == Decimal("576.00")

    def test_to_dict(self, sample_bill):
        """Test to_dict method."""
        from app.hotel.domain.bill import BillEntity
        entity = BillEntity(sample_bill)
        d = entity.to_dict()
        assert "outstanding_balance" in d
        assert "is_fully_paid" in d

    def test_repository_get_by_stay_record(self, db_session, sample_bill, sample_stay):
        """Test get_by_stay_record repository method."""
        from app.hotel.domain.bill import BillRepository
        repo = BillRepository(db_session)
        bill = repo.get_by_stay_record(sample_stay.id)
        assert bill is not None

    def test_repository_find_unpaid(self, db_session, sample_bill):
        """Test find_unpaid repository method."""
        from app.hotel.domain.bill import BillRepository
        repo = BillRepository(db_session)
        unpaid = repo.find_unpaid()
        assert len(unpaid) >= 1

    def test_repository_list_all(self, db_session, sample_bill):
        """Test list_all repository method."""
        from app.hotel.domain.bill import BillRepository
        repo = BillRepository(db_session)
        all_bills = repo.list_all()
        assert len(all_bills) >= 1


# ============== Room Rules ==============

class TestRoomRulesExtra:
    """Cover uncovered lines in room_rules.py."""

    def test_set_room_dirty(self):
        """Cover lines 103-118: _set_room_dirty action."""
        from app.hotel.domain.rules.room_rules import _set_room_dirty
        from core.engine.rule_engine import RuleContext

        mock_room = Mock()
        mock_room.status = "occupied"

        context = RuleContext(
            entity=mock_room,
            entity_type="Room",
            action="checkout",
            parameters={},
        )

        # Should not raise; just publishes event
        _set_room_dirty(context)

    def test_set_room_occupied(self):
        """Cover lines 129-142: _set_room_occupied action."""
        from app.hotel.domain.rules.room_rules import _set_room_occupied
        from core.engine.rule_engine import RuleContext

        mock_room = Mock()
        mock_room.status = "vacant_clean"

        context = RuleContext(
            entity=mock_room,
            entity_type="Room",
            action="checkin",
            parameters={},
        )

        _set_room_occupied(context)

    def test_set_room_vacant_clean(self):
        """Cover lines 153-166: _set_room_vacant_clean action."""
        from app.hotel.domain.rules.room_rules import _set_room_vacant_clean
        from core.engine.rule_engine import RuleContext

        mock_room = Mock()
        mock_room.status = "vacant_dirty"

        context = RuleContext(
            entity=mock_room,
            entity_type="Room",
            action="complete_task",
            parameters={"task_type": "cleaning"},
        )

        _set_room_vacant_clean(context)

    def test_set_room_dirty_no_status(self):
        """Test _set_room_dirty with entity without status attribute."""
        from app.hotel.domain.rules.room_rules import _set_room_dirty
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity="not_a_room",
            entity_type="Room",
            action="checkout",
            parameters={},
        )

        # Should not raise even when entity has no status
        _set_room_dirty(context)


# ============== Pricing Rules ==============

class TestPricingRulesExtra:
    """Cover uncovered lines in pricing_rules.py."""

    def test_weekend_surcharge(self):
        """Test _apply_weekend_surcharge."""
        from app.hotel.domain.rules.pricing_rules import _apply_weekend_surcharge
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={"base_price": 288.0},
        )

        _apply_weekend_surcharge(context)
        assert "weekend_surcharge" in context.metadata
        assert context.metadata["adjusted_price"] == pytest.approx(345.6)

    def test_holiday_surcharge(self):
        """Test _apply_holiday_surcharge."""
        from app.hotel.domain.rules.pricing_rules import _apply_holiday_surcharge
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={"base_price": 288.0},
        )

        _apply_holiday_surcharge(context)
        assert "holiday_surcharge" in context.metadata

    def test_member_discount_vip(self):
        """Test _apply_member_discount for VIP guest."""
        from app.hotel.domain.rules.pricing_rules import _apply_member_discount
        from core.engine.rule_engine import RuleContext

        mock_guest = Mock()
        mock_guest.tier = "vip"

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={"guest": mock_guest, "base_price": 288.0},
        )

        _apply_member_discount(context)
        assert "member_discount" in context.metadata
        assert context.metadata["discount_rate"] == 0.15

    def test_member_discount_dict_guest(self):
        """Test _apply_member_discount with dict guest."""
        from app.hotel.domain.rules.pricing_rules import _apply_member_discount
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={"guest": {"tier": "gold"}, "base_price": 288.0},
        )

        _apply_member_discount(context)
        assert context.metadata["discount_rate"] == 0.10

    def test_member_discount_basic(self):
        """Test _apply_member_discount for basic tier (no discount)."""
        from app.hotel.domain.rules.pricing_rules import _apply_member_discount
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={"guest": {"tier": "basic"}, "base_price": 288.0},
        )

        _apply_member_discount(context)
        assert "member_discount" not in context.metadata

    def test_long_stay_discount_14_days(self):
        """Test _apply_long_stay_discount for 14+ days."""
        from app.hotel.domain.rules.pricing_rules import _apply_long_stay_discount
        from core.engine.rule_engine import RuleContext

        ci = date.today()
        co = ci + timedelta(days=14)

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={
                "check_in_date": ci,
                "check_out_date": co,
                "base_price": 288.0,
            },
        )

        _apply_long_stay_discount(context)
        assert context.metadata["discount_rate"] == 0.15
        assert context.metadata["nights"] == 14

    def test_long_stay_discount_7_days(self):
        """Test _apply_long_stay_discount for 7 days."""
        from app.hotel.domain.rules.pricing_rules import _apply_long_stay_discount
        from core.engine.rule_engine import RuleContext

        ci = date.today()
        co = ci + timedelta(days=7)

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={
                "check_in_date": ci,
                "check_out_date": co,
                "base_price": 288.0,
            },
        )

        _apply_long_stay_discount(context)
        assert context.metadata["discount_rate"] == 0.10

    def test_long_stay_discount_short_stay(self):
        """Test _apply_long_stay_discount for short stay (no discount)."""
        from app.hotel.domain.rules.pricing_rules import _apply_long_stay_discount
        from core.engine.rule_engine import RuleContext

        ci = date.today()
        co = ci + timedelta(days=3)

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={
                "check_in_date": ci,
                "check_out_date": co,
                "base_price": 288.0,
            },
        )

        _apply_long_stay_discount(context)
        assert "discount_rate" not in context.metadata

    def test_long_stay_with_string_dates(self):
        """Test _apply_long_stay_discount with string dates."""
        from app.hotel.domain.rules.pricing_rules import _apply_long_stay_discount
        from core.engine.rule_engine import RuleContext

        ci = date.today()
        co = ci + timedelta(days=10)

        context = RuleContext(
            entity=None,
            entity_type="Reservation",
            action="create_reservation",
            parameters={
                "check_in_date": ci.isoformat(),
                "check_out_date": co.isoformat(),
                "base_price": 288.0,
            },
        )

        _apply_long_stay_discount(context)
        assert context.metadata["discount_rate"] == 0.10

    def test_calculate_room_price(self):
        """Test the convenience function calculate_room_price."""
        from app.hotel.domain.rules.pricing_rules import calculate_room_price

        # Regular weekday, basic tier, 3 nights
        ci = date(2025, 3, 3)  # Monday
        co = date(2025, 3, 6)
        price, details = calculate_room_price(288.0, ci, co, "basic")
        assert price > 0
        assert "adjustments" in details

    def test_calculate_room_price_vip_long_stay(self):
        """Test calculate_room_price with VIP and long stay."""
        from app.hotel.domain.rules.pricing_rules import calculate_room_price

        ci = date(2025, 3, 3)  # Monday
        co = date(2025, 3, 20)  # 17 nights
        price, details = calculate_room_price(288.0, ci, co, "vip")
        assert price < 288.0  # VIP + long stay discounts applied

    def test_calculate_room_price_weekend(self):
        """Test calculate_room_price on Friday."""
        from app.hotel.domain.rules.pricing_rules import calculate_room_price

        # 2025-01-03 is a Friday
        ci = date(2025, 1, 3)
        co = date(2025, 1, 5)
        price, details = calculate_room_price(288.0, ci, co, "basic")
        assert price > 288.0  # Weekend surcharge

    def test_is_weekend_function(self):
        """Test the is_weekend convenience function."""
        from app.hotel.domain.rules.pricing_rules import is_weekend
        assert is_weekend(date(2025, 1, 3)) is True  # Friday
        assert is_weekend(date(2025, 1, 6)) is False  # Monday

    def test_is_holiday_function(self):
        """Test the is_holiday convenience function."""
        from app.hotel.domain.rules.pricing_rules import is_holiday
        assert is_holiday(date(2025, 1, 1)) is True  # New Year
        assert is_holiday(date(2025, 3, 15)) is False

    def test_weekend_booking_condition_string_date(self):
        """Test _is_weekend_booking with string date."""
        from app.hotel.domain.rules.pricing_rules import _is_weekend_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"check_in_date": "2025-01-03"},  # Friday
        )
        assert _is_weekend_booking(context) is True

    def test_weekend_booking_condition_non_date(self):
        """Test _is_weekend_booking with non-date value."""
        from app.hotel.domain.rules.pricing_rules import _is_weekend_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"check_in_date": 12345},
        )
        assert _is_weekend_booking(context) is False

    def test_holiday_booking_condition_string_date(self):
        """Test _is_holiday_booking with string date."""
        from app.hotel.domain.rules.pricing_rules import _is_holiday_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"check_in_date": "2025-01-01"},  # New Year
        )
        assert _is_holiday_booking(context) is True

    def test_holiday_booking_condition_non_date(self):
        """Test _is_holiday_booking with non-date value."""
        from app.hotel.domain.rules.pricing_rules import _is_holiday_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"check_in_date": 12345},
        )
        assert _is_holiday_booking(context) is False

    def test_member_booking_no_guest(self):
        """Test _is_member_booking with no guest."""
        from app.hotel.domain.rules.pricing_rules import _is_member_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={},
        )
        assert _is_member_booking(context) is False

    def test_member_booking_non_object_guest(self):
        """Test _is_member_booking with non-dict/non-object guest."""
        from app.hotel.domain.rules.pricing_rules import _is_member_booking
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"guest": "just_a_string"},
        )
        assert _is_member_booking(context) is False

    def test_member_discount_no_base_price(self):
        """Test _apply_member_discount with no base_price."""
        from app.hotel.domain.rules.pricing_rules import _apply_member_discount
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={"guest": {"tier": "vip"}},
        )
        _apply_member_discount(context)
        assert "member_discount" not in context.metadata

    def test_long_stay_missing_dates(self):
        """Test _is_long_stay with missing dates."""
        from app.hotel.domain.rules.pricing_rules import _is_long_stay
        from core.engine.rule_engine import RuleContext

        context = RuleContext(
            entity=None, entity_type="Reservation", action="create_reservation",
            parameters={},
        )
        assert _is_long_stay(context) is False


# ============== Business Rules ==============

class TestBusinessRulesExtra:
    """Cover uncovered lines in business_rules.py."""

    def test_init_hotel_business_rules(self, db_session):
        """Cover lines 49-62: init_hotel_business_rules room status aliases."""
        # Need to set up OntologyRegistry first
        from core.ontology.registry import OntologyRegistry
        from app.hotel.hotel_domain_adapter import HotelDomainAdapter

        registry = OntologyRegistry()
        adapter = HotelDomainAdapter()
        adapter.register_ontology(registry)

        from app.hotel.business_rules import init_hotel_business_rules
        # Should not raise
        init_hotel_business_rules()


# ============== Guest Domain Extra ==============

class TestGuestEntityExtra:
    """Cover uncovered lines in guest domain."""

    def test_add_to_blacklist(self, sample_guest):
        """Test add_to_blacklist method."""
        from app.hotel.domain.guest import GuestEntity
        entity = GuestEntity(sample_guest)
        entity.add_to_blacklist("行为不当")
        assert entity.is_blacklisted is True
        assert entity.blacklist_reason == "行为不当"

    def test_remove_from_blacklist(self, sample_guest):
        """Test remove_from_blacklist method."""
        from app.hotel.domain.guest import GuestEntity
        sample_guest.is_blacklisted = True
        sample_guest.blacklist_reason = "test"
        entity = GuestEntity(sample_guest)
        entity.remove_from_blacklist()
        assert entity.is_blacklisted is False
        assert entity.blacklist_reason is None

    def test_update_preferences(self, sample_guest):
        """Test update_preferences method."""
        from app.hotel.domain.guest import GuestEntity
        entity = GuestEntity(sample_guest)
        entity.update_preferences('{"room_floor": "high"}')
        assert entity.preferences == '{"room_floor": "high"}'

    def test_increment_stays(self, sample_guest):
        """Test increment_stays method."""
        from app.hotel.domain.guest import GuestEntity
        entity = GuestEntity(sample_guest)
        original = entity.total_stays
        entity.increment_stays()
        assert entity.total_stays == original + 1

    def test_add_amount(self, sample_guest):
        """Test add_amount method."""
        from app.hotel.domain.guest import GuestEntity
        entity = GuestEntity(sample_guest)
        entity.add_amount(500.0)
        assert entity.total_amount >= 500.0

    def test_can_make_reservation(self, sample_guest):
        """Test can_make_reservation method."""
        from app.hotel.domain.guest import GuestEntity
        entity = GuestEntity(sample_guest)
        assert entity.can_make_reservation() is True
        entity.add_to_blacklist("test")
        assert entity.can_make_reservation() is False

    def test_repository_get_by_phone(self, db_session, sample_guest):
        """Test get_by_phone repository method."""
        from app.hotel.domain.guest import GuestRepository
        repo = GuestRepository(db_session)
        guest = repo.get_by_phone("13800138000")
        assert guest is not None

    def test_repository_get_by_id_number(self, db_session, sample_guest):
        """Test get_by_id_number repository method."""
        from app.hotel.domain.guest import GuestRepository
        repo = GuestRepository(db_session)
        guest = repo.get_by_id_number("110101199001011234")
        assert guest is not None

    def test_repository_find_by_tier(self, db_session, sample_guest):
        """Test find_by_tier repository method."""
        from app.hotel.domain.guest import GuestRepository
        repo = GuestRepository(db_session)
        result = repo.find_by_tier("normal")
        # sample_guest has no explicit tier, so depends on default
        assert isinstance(result, list)

    def test_repository_find_vip_guests(self, db_session, sample_guest):
        """Test find_vip_guests repository method."""
        from app.hotel.domain.guest import GuestRepository
        sample_guest.tier = "gold"
        db_session.commit()
        repo = GuestRepository(db_session)
        vips = repo.find_vip_guests()
        assert len(vips) >= 1

    def test_repository_find_blacklisted(self, db_session, sample_guest):
        """Test find_blacklisted repository method."""
        from app.hotel.domain.guest import GuestRepository
        sample_guest.is_blacklisted = True
        db_session.commit()
        repo = GuestRepository(db_session)
        blacklisted = repo.find_blacklisted()
        assert len(blacklisted) >= 1

    def test_repository_search_by_name(self, db_session, sample_guest):
        """Test search_by_name repository method."""
        from app.hotel.domain.guest import GuestRepository
        repo = GuestRepository(db_session)
        results = repo.search_by_name("测试")
        assert len(results) >= 1

    def test_repository_list_all(self, db_session, sample_guest):
        """Test list_all repository method."""
        from app.hotel.domain.guest import GuestRepository
        repo = GuestRepository(db_session)
        all_guests = repo.list_all()
        assert len(all_guests) >= 1
