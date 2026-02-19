"""
tests/services/actions/test_hotel_actions_base.py

Comprehensive tests for app/hotel/actions/base.py - Action parameter models.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pydantic import ValidationError


from app.hotel.models.ontology import TaskType
from app.hotel.actions.base import (
    WalkInCheckInParams,
    UpdateGuestParams,
    SmartUpdateParams,
    UpdateGuestSmartParams,
    CheckoutParams,
    CreateTaskParams,
    DeleteTaskParams,
    BatchDeleteTasksParams,
    CreateReservationParams,
    FilterClauseParams,
    JoinClauseParams,
    OntologyQueryParams,
    SemanticFilterParams,
    SemanticQueryParams,
    ActionResult,
    UpdatePriceParams,
    CreateRatePlanParams,
    SyncOTAParams,
    FetchChannelReservationsParams,
    NotificationParams,
    BookResourceParams,
    AssignTaskParams,
    StartTaskParams,
    CompleteTaskParams,
    CheckinParams,
    ExtendStayParams,
    ChangeRoomParams,
    CancelReservationParams,
    ModifyReservationParams,
    AddPaymentParams,
    AdjustBillParams,
    RefundPaymentParams,
    UpdateRoomStatusParams,
    CreateRoomTypeParams,
    UpdateRoomTypeParams,
    CreateGuestParams,
    CreateEmployeeParams,
    UpdateEmployeeParams,
    DeactivateEmployeeParams,
)


class TestWalkInCheckInParams:
    """Test WalkInCheckInParams validation."""

    def test_valid_params(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        p = WalkInCheckInParams(
            guest_name="张三",
            room_id=101,
            expected_check_out=tomorrow,
        )
        assert p.guest_name == "张三"
        assert p.deposit_amount == Decimal("0")

    def test_deposit_amount_decimal(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        p = WalkInCheckInParams(
            guest_name="张三",
            room_id=101,
            expected_check_out=tomorrow,
            deposit_amount=Decimal("500.00"),
        )
        assert p.deposit_amount == Decimal("500.00")

    def test_deposit_amount_string(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        p = WalkInCheckInParams(
            guest_name="张三",
            room_id=101,
            expected_check_out=tomorrow,
            deposit_amount="300",
        )
        assert p.deposit_amount == Decimal("300")

    def test_deposit_amount_negative_raises(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out=tomorrow,
                deposit_amount="-100",
            )

    def test_deposit_amount_negative_decimal_raises(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out=tomorrow,
                deposit_amount=Decimal("-50"),
            )

    def test_deposit_amount_invalid_string(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out=tomorrow,
                deposit_amount="abc",
            )

    def test_check_out_past_date_raises(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out=yesterday,
            )

    def test_check_out_today_raises(self):
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out=date.today(),
            )

    def test_check_out_invalid_format(self):
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="张三",
                room_id=101,
                expected_check_out="not-a-date",
            )

    def test_check_out_date_object(self):
        tomorrow = date.today() + timedelta(days=1)
        p = WalkInCheckInParams(
            guest_name="张三",
            room_id=101,
            expected_check_out=tomorrow,
        )
        assert p.expected_check_out == tomorrow

    def test_empty_guest_name_raises(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="",
                room_id=101,
                expected_check_out=tomorrow,
            )


class TestCheckoutParams:
    """Test CheckoutParams validation."""

    def test_valid_checkout(self):
        p = CheckoutParams(stay_record_id=1)
        assert p.stay_record_id == 1
        assert p.refund_deposit == Decimal("0")

    def test_refund_negative_raises(self):
        with pytest.raises(ValidationError):
            CheckoutParams(stay_record_id=1, refund_deposit="-100")

    def test_refund_negative_decimal_raises(self):
        with pytest.raises(ValidationError):
            CheckoutParams(stay_record_id=1, refund_deposit=Decimal("-50"))

    def test_refund_string_amount(self):
        p = CheckoutParams(stay_record_id=1, refund_deposit="200")
        assert p.refund_deposit == Decimal("200")

    def test_allow_unsettled(self):
        p = CheckoutParams(
            stay_record_id=1,
            allow_unsettled=True,
            unsettled_reason="VIP guest"
        )
        assert p.allow_unsettled is True


class TestCreateTaskParams:
    """Test CreateTaskParams validation."""

    def test_valid_cleaning(self):
        p = CreateTaskParams(room_id=1, task_type="cleaning")
        assert p.task_type == TaskType.CLEANING

    def test_valid_maintenance(self):
        p = CreateTaskParams(room_id=1, task_type="maintenance")
        assert p.task_type == TaskType.MAINTENANCE

    def test_chinese_alias_cleaning(self):
        p = CreateTaskParams(room_id=1, task_type="清洁")
        assert p.task_type == TaskType.CLEANING

    def test_chinese_alias_maintenance(self):
        p = CreateTaskParams(room_id=1, task_type="维修")
        assert p.task_type == TaskType.MAINTENANCE

    def test_task_type_enum_passthrough(self):
        p = CreateTaskParams(room_id=1, task_type=TaskType.CLEANING)
        assert p.task_type == TaskType.CLEANING

    def test_invalid_task_type_raises(self):
        with pytest.raises(ValidationError):
            CreateTaskParams(room_id=1, task_type="invalid_type")

    def test_alias_clean(self):
        p = CreateTaskParams(room_id=1, task_type="clean")
        assert p.task_type == TaskType.CLEANING

    def test_alias_fix(self):
        p = CreateTaskParams(room_id=1, task_type="fix")
        assert p.task_type == TaskType.MAINTENANCE

    def test_alias_打扫(self):
        p = CreateTaskParams(room_id=1, task_type="打扫")
        assert p.task_type == TaskType.CLEANING


class TestBatchDeleteTasksParams:
    """Test BatchDeleteTasksParams validation."""

    def test_valid_pending_status(self):
        p = BatchDeleteTasksParams(status="pending")
        assert p.status == "pending"

    def test_valid_assigned_status(self):
        p = BatchDeleteTasksParams(status="assigned")
        assert p.status == "assigned"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            BatchDeleteTasksParams(status="completed")

    def test_none_status(self):
        p = BatchDeleteTasksParams(status=None)
        assert p.status is None

    def test_valid_task_type_cleaning(self):
        p = BatchDeleteTasksParams(task_type="cleaning")
        assert p.task_type == "cleaning"

    def test_task_type_chinese(self):
        p = BatchDeleteTasksParams(task_type="清洁")
        assert p.task_type == "cleaning"

    def test_invalid_task_type_raises(self):
        with pytest.raises(ValidationError):
            BatchDeleteTasksParams(task_type="cooking")

    def test_none_task_type(self):
        p = BatchDeleteTasksParams(task_type=None)
        assert p.task_type is None


class TestCreateReservationParams:
    """Test CreateReservationParams validation."""

    def test_valid_reservation(self):
        checkin = (date.today() + timedelta(days=1)).isoformat()
        checkout = (date.today() + timedelta(days=3)).isoformat()
        p = CreateReservationParams(
            guest_name="李四",
            room_type_id=1,
            check_in_date=checkin,
            check_out_date=checkout,
        )
        assert p.guest_name == "李四"

    def test_checkout_before_checkin_raises(self):
        checkin = (date.today() + timedelta(days=3)).isoformat()
        checkout = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError, match="value_error"):
            CreateReservationParams(
                guest_name="李四",
                room_type_id=1,
                check_in_date=checkin,
                check_out_date=checkout,
            )

    def test_invalid_date_format(self):
        with pytest.raises(ValidationError, match="value_error"):
            CreateReservationParams(
                guest_name="李四",
                room_type_id=1,
                check_in_date="not-a-date",
                check_out_date="2025-12-31",
            )

    def test_date_objects(self):
        p = CreateReservationParams(
            guest_name="李四",
            room_type_id=1,
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
        )
        assert isinstance(p.check_in_date, date)


class TestFilterClauseParams:
    """Test FilterClauseParams validation."""

    def test_valid_operator(self):
        p = FilterClauseParams(field="status", operator="eq", value="active")
        assert p.operator == "eq"

    def test_invalid_operator(self):
        with pytest.raises(ValidationError, match="value_error"):
            FilterClauseParams(field="status", operator="invalid", value="x")

    def test_all_valid_operators(self):
        for op in ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'like', 'between']:
            p = FilterClauseParams(field="test", operator=op, value="val")
            assert p.operator == op


class TestSemanticFilterParams:
    """Test SemanticFilterParams validation."""

    def test_valid_operator(self):
        p = SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
        assert p.operator == "eq"

    def test_case_insensitive_operator(self):
        p = SemanticFilterParams(path="stays.status", operator="EQ", value="ACTIVE")
        assert p.operator == "eq"

    def test_invalid_operator(self):
        with pytest.raises(ValidationError, match="value_error"):
            SemanticFilterParams(path="stays.status", operator="bad_op", value="x")

    def test_all_valid_operators(self):
        valid = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in',
                 'like', 'not_like', 'between', 'is_null', 'is_not_null']
        for op in valid:
            p = SemanticFilterParams(path="test", operator=op, value=None)
            assert p.operator == op


class TestSemanticQueryParams:
    """Test SemanticQueryParams validation."""

    def test_alias_resolution(self):
        p = SemanticQueryParams(root_object="guest", fields=["name"])
        assert p.root_object == "Guest"

    def test_alias_rooms(self):
        p = SemanticQueryParams(root_object="rooms", fields=["room_number"])
        assert p.root_object == "Room"

    def test_alias_stays(self):
        p = SemanticQueryParams(root_object="stays", fields=["id"])
        assert p.root_object == "StayRecord"

    def test_alias_tasks(self):
        p = SemanticQueryParams(root_object="tasks", fields=["id"])
        assert p.root_object == "Task"

    def test_unknown_entity_passthrough(self):
        p = SemanticQueryParams(root_object="CustomEntity", fields=["id"])
        assert p.root_object == "CustomEntity"

    def test_defaults(self):
        p = SemanticQueryParams(root_object="Guest")
        assert p.fields == []
        assert p.filters == []
        assert p.order_by == []
        assert p.limit == 100
        assert p.offset == 0
        assert p.distinct is False


class TestSmartUpdateParams:
    """Test SmartUpdateParams validation and alias resolution."""

    def test_empty_instructions_raises(self):
        with pytest.raises(ValidationError, match="value_error"):
            SmartUpdateParams(instructions="")

    def test_whitespace_instructions_raises(self):
        with pytest.raises(ValidationError, match="value_error"):
            SmartUpdateParams(instructions="   ")

    def test_guest_id_alias(self):
        p = SmartUpdateParams(instructions="change phone", guest_id=5)
        assert p.entity_id == 5

    def test_guest_name_alias(self):
        p = SmartUpdateParams(instructions="change phone", guest_name="张三")
        assert p.entity_name == "张三"

    def test_employee_id_alias(self):
        p = SmartUpdateParams(instructions="change role", employee_id=10)
        assert p.entity_id == 10

    def test_employee_name_alias(self):
        p = SmartUpdateParams(instructions="change role", employee_name="李经理")
        assert p.entity_name == "李经理"

    def test_room_type_id_alias(self):
        p = SmartUpdateParams(instructions="change price", room_type_id=2)
        assert p.entity_id == 2

    def test_room_type_name_alias(self):
        p = SmartUpdateParams(instructions="change price", room_type_name="标间")
        assert p.entity_name == "标间"

    def test_entity_id_takes_precedence(self):
        p = SmartUpdateParams(
            instructions="change phone",
            entity_id=1,
            guest_id=5,
        )
        assert p.entity_id == 1

    def test_backward_compat_alias(self):
        """UpdateGuestSmartParams should be an alias for SmartUpdateParams."""
        assert UpdateGuestSmartParams is SmartUpdateParams


class TestUpdatePriceParams:
    """Test UpdatePriceParams validation."""

    def test_valid_base_price(self):
        p = UpdatePriceParams(room_type=1, price=Decimal("300"))
        assert p.update_type == "base_price"

    def test_invalid_update_type(self):
        with pytest.raises(ValidationError, match="value_error"):
            UpdatePriceParams(room_type=1, price=Decimal("300"), update_type="invalid")

    def test_valid_rate_plan_type(self):
        p = UpdatePriceParams(room_type=1, price=Decimal("300"), update_type="rate_plan")
        assert p.update_type == "rate_plan"

    def test_price_type_chinese_weekend(self):
        p = UpdatePriceParams(room_type=1, price=Decimal("300"), price_type="周末")
        assert p.price_type == "weekend"

    def test_price_type_chinese_standard(self):
        p = UpdatePriceParams(room_type=1, price=Decimal("300"), price_type="平日")
        assert p.price_type == "standard"

    def test_invalid_price_type(self):
        with pytest.raises(ValidationError, match="value_error"):
            UpdatePriceParams(room_type=1, price=Decimal("300"), price_type="invalid")


class TestAddPaymentParams:
    """Test AddPaymentParams validation."""

    def test_valid_payment(self):
        p = AddPaymentParams(amount="100", payment_method="cash")
        assert p.amount == Decimal("100")

    def test_zero_amount_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            AddPaymentParams(amount="0", payment_method="cash")

    def test_negative_amount_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            AddPaymentParams(amount="-50", payment_method="cash")

    def test_invalid_amount(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            AddPaymentParams(amount="abc", payment_method="cash")


class TestAdjustBillParams:
    """Test AdjustBillParams validation."""

    def test_valid_adjustment(self):
        p = AdjustBillParams(amount="50", reason="late checkout")
        assert p.amount == Decimal("50")

    def test_negative_adjustment(self):
        p = AdjustBillParams(amount="-50", reason="discount")
        assert p.amount == Decimal("-50")

    def test_invalid_amount(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            AdjustBillParams(amount="xyz", reason="test")


class TestRefundPaymentParams:
    """Test RefundPaymentParams validation."""

    def test_valid_refund(self):
        p = RefundPaymentParams(payment_id=1, amount="100", reason="overcharge")
        assert p.amount == Decimal("100")

    def test_none_amount_full_refund(self):
        p = RefundPaymentParams(payment_id=1, amount=None, reason="cancelled")
        assert p.amount is None

    def test_zero_amount_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            RefundPaymentParams(payment_id=1, amount="0", reason="test")

    def test_negative_refund_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            RefundPaymentParams(payment_id=1, amount="-50", reason="test")


class TestCreateRoomTypeParams:
    """Test CreateRoomTypeParams validation."""

    def test_valid_room_type(self):
        p = CreateRoomTypeParams(name="豪华间", base_price="588")
        assert p.base_price == Decimal("588")

    def test_negative_price_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            CreateRoomTypeParams(name="test", base_price="-100")

    def test_invalid_price(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            CreateRoomTypeParams(name="test", base_price="abc")


class TestUpdateRoomTypeParams:
    """Test UpdateRoomTypeParams validation."""

    def test_valid_update(self):
        p = UpdateRoomTypeParams(room_type_id=1, base_price="300")
        assert p.base_price == Decimal("300")

    def test_none_price(self):
        p = UpdateRoomTypeParams(room_type_id=1, name="New Name")
        assert p.base_price is None

    def test_negative_price_raises(self):
        with pytest.raises((ValidationError, InvalidOperation)):
            UpdateRoomTypeParams(room_type_id=1, base_price="-100")


class TestCreateEmployeeParams:
    """Test CreateEmployeeParams validation."""

    def test_valid_employee(self):
        p = CreateEmployeeParams(
            username="test_user",
            name="测试员工",
            role="receptionist",
        )
        assert p.role == "receptionist"

    def test_invalid_role(self):
        with pytest.raises(ValidationError, match="value_error"):
            CreateEmployeeParams(
                username="test",
                name="test",
                role="invalid_role",
            )

    def test_role_case_insensitive(self):
        p = CreateEmployeeParams(
            username="test",
            name="test",
            role="MANAGER",
        )
        assert p.role == "manager"


class TestUpdateEmployeeParams:
    """Test UpdateEmployeeParams validation."""

    def test_valid_update(self):
        p = UpdateEmployeeParams(employee_id=1, name="新名字")
        assert p.name == "新名字"

    def test_none_role_allowed(self):
        p = UpdateEmployeeParams(employee_id=1, role=None)
        assert p.role is None

    def test_invalid_role(self):
        with pytest.raises(ValidationError, match="value_error"):
            UpdateEmployeeParams(employee_id=1, role="invalid")


class TestExtendStayParams:
    """Test ExtendStayParams validation."""

    def test_valid_date_string(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        p = ExtendStayParams(stay_record_id=1, new_check_out_date=future)
        assert isinstance(p.new_check_out_date, date)

    def test_date_object(self):
        future = date.today() + timedelta(days=5)
        p = ExtendStayParams(stay_record_id=1, new_check_out_date=future)
        assert p.new_check_out_date == future

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError, match="value_error"):
            ExtendStayParams(stay_record_id=1, new_check_out_date="bad-date")


class TestModifyReservationParams:
    """Test ModifyReservationParams validation."""

    def test_valid_modification(self):
        future = (date.today() + timedelta(days=2)).isoformat()
        p = ModifyReservationParams(reservation_id=1, check_in_date=future)
        assert isinstance(p.check_in_date, date)

    def test_none_dates(self):
        p = ModifyReservationParams(reservation_id=1)
        assert p.check_in_date is None
        assert p.check_out_date is None

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError, match="value_error"):
            ModifyReservationParams(reservation_id=1, check_in_date="bad")


class TestActionResult:
    """Test ActionResult model."""

    def test_success_result(self):
        r = ActionResult(success=True, message="Done")
        assert r.success is True
        assert r.requires_confirmation is False

    def test_error_result(self):
        r = ActionResult(success=False, message="Failed", error="validation_error")
        assert r.error == "validation_error"


class TestOntologyQueryParams:
    """Test OntologyQueryParams model."""

    def test_defaults(self):
        p = OntologyQueryParams(entity="Room")
        assert p.fields == []
        assert p.filters is None
        assert p.limit == 100

    def test_with_filters(self):
        p = OntologyQueryParams(
            entity="Room",
            fields=["room_number", "status"],
            filters=[FilterClauseParams(field="status", operator="eq", value="vacant_clean")],
        )
        assert len(p.filters) == 1


class TestMiscParams:
    """Test miscellaneous parameter models."""

    def test_sync_ota_defaults(self):
        p = SyncOTAParams()
        assert p.channel == "all"
        assert p.room_type is None

    def test_notification_defaults(self):
        p = NotificationParams()
        assert p.channel == "system"

    def test_book_resource_defaults(self):
        p = BookResourceParams()
        assert p.resource_type == "Room"

    def test_checkin_params(self):
        p = CheckinParams(reservation_id=1)
        assert p.reservation_id == 1

    def test_change_room_params(self):
        p = ChangeRoomParams(stay_record_id=1, new_room_number="302")
        assert p.new_room_number == "302"

    def test_cancel_reservation_params(self):
        p = CancelReservationParams(reservation_id=1)
        assert p.reason == "客人要求取消"

    def test_deactivate_employee_params(self):
        p = DeactivateEmployeeParams(employee_id=1)
        assert p.employee_id == 1

    def test_create_guest_params(self):
        p = CreateGuestParams(name="测试客人")
        assert p.name == "测试客人"
        assert p.phone is None

    def test_assign_task_params(self):
        p = AssignTaskParams(task_id=1, assignee_id=5)
        assert p.assignee_id == 5

    def test_start_task_params(self):
        p = StartTaskParams(task_id=1)
        assert p.task_id == 1

    def test_complete_task_params(self):
        p = CompleteTaskParams(task_id=1, notes="all done")
        assert p.notes == "all done"

    def test_delete_task_params(self):
        p = DeleteTaskParams(task_id=1)
        assert p.task_id == 1

    def test_update_room_status_params(self):
        p = UpdateRoomStatusParams(room_number="201", status="vacant_clean")
        assert p.room_number == "201"

    def test_join_clause_params(self):
        p = JoinClauseParams(entity="Guest", on="guest_id")
        assert p.entity == "Guest"

    def test_fetch_channel_reservations(self):
        p = FetchChannelReservationsParams(channel="ctrip")
        assert p.channel == "ctrip"
        assert p.date_from is None

    def test_create_rate_plan_params(self):
        p = CreateRatePlanParams(
            room_type=1,
            price=Decimal("300"),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        assert p.priority == 2
        assert p.is_weekend is False

    def test_update_guest_params(self):
        p = UpdateGuestParams(guest_id=1, name="New Name")
        assert p.guest_id == 1
        assert p.name == "New Name"
