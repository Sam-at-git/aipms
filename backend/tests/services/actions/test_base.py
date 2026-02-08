"""
tests/services/actions/test_base.py

Tests for action parameter models in app/services/actions/base.py
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.services.actions.base import (
    WalkInCheckInParams,
    CheckoutParams,
    CreateTaskParams,
    CreateReservationParams,
    FilterClauseParams,
    JoinClauseParams,
    OntologyQueryParams,
    SemanticFilterParams,
    SemanticQueryParams,
    ActionResult,
)
from app.models.ontology import TaskType


# ==================== WalkInCheckInParams Tests ====================

class TestWalkInCheckInParams:
    """Test WalkInCheckInParams validation"""

    def test_valid_params_with_defaults(self):
        """Test valid params with default values"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="张三",
            room_id=101,
            expected_check_out=tomorrow
        )
        assert params.guest_name == "张三"
        assert params.guest_phone == ""
        assert params.guest_id_type == "身份证"
        assert params.guest_id_number == ""
        assert params.deposit_amount == Decimal("0")

    def test_valid_params_all_fields(self):
        """Test valid params with all fields specified"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="李四",
            guest_phone="13800138000",
            guest_id_type="护照",
            guest_id_number="A12345678",
            room_id=201,
            expected_check_out=tomorrow,
            deposit_amount=Decimal("100.50")
        )
        assert params.guest_name == "李四"
        assert params.guest_phone == "13800138000"
        assert params.guest_id_type == "护照"
        assert params.guest_id_number == "A12345678"
        assert params.deposit_amount == Decimal("100.50")

    def test_deposit_amount_parsing_string(self):
        """Test deposit amount parsing from string"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="王五",
            room_id=101,
            expected_check_out=tomorrow,
            deposit_amount="200.75"
        )
        assert params.deposit_amount == Decimal("200.75")

    def test_deposit_amount_parsing_int(self):
        """Test deposit amount parsing from int"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="王五",
            room_id=101,
            expected_check_out=tomorrow,
            deposit_amount=300
        )
        assert params.deposit_amount == Decimal("300")

    def test_deposit_amount_parsing_float(self):
        """Test deposit amount parsing from float"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="王五",
            room_id=101,
            expected_check_out=tomorrow,
            deposit_amount=150.25
        )
        assert params.deposit_amount == Decimal("150.25")

    def test_deposit_amount_negative_rejected(self):
        """Test negative deposit amount is rejected"""
        tomorrow = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="王五",
                room_id=101,
                expected_check_out=tomorrow,
                deposit_amount=-50
            )
        # Error message may be either "押金金额不能为负数" or "无效的押金金额"
        assert "不能为负数" in str(exc_info.value) or "无效的押金金额" in str(exc_info.value)

    def test_deposit_amount_invalid_string_rejected(self):
        """Test invalid deposit amount string is rejected"""
        tomorrow = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError):
            WalkInCheckInParams(
                guest_name="王五",
                room_id=101,
                expected_check_out=tomorrow,
                deposit_amount="abc"
            )

    def test_check_out_date_parsing_string(self):
        """Test check out date parsing from string"""
        params = WalkInCheckInParams(
            guest_name="赵六",
            room_id=101,
            expected_check_out="2026-12-31"
        )
        assert params.expected_check_out == date(2026, 12, 31)

    def test_check_out_date_today_rejected(self):
        """Test check out date cannot be today"""
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="赵六",
                room_id=101,
                expected_check_out=date.today()
            )
        assert "退房日期必须晚于今天" in str(exc_info.value)

    def test_check_out_date_past_rejected(self):
        """Test check out date cannot be in the past"""
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="赵六",
                room_id=101,
                expected_check_out="2020-01-01"
            )
        # Should fail validation
        assert exc_info.value is not None

    def test_check_out_date_invalid_format_rejected(self):
        """Test invalid date format is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="赵六",
                room_id=101,
                expected_check_out="01/01/2026"
            )
        assert "无效的日期格式" in str(exc_info.value)

    def test_guest_name_too_short(self):
        """Test guest name minimum length"""
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="",
                room_id=101,
                expected_check_out="2026-12-31"
            )
        assert "guest_name" in str(exc_info.value).lower()

    def test_guest_name_too_long(self):
        """Test guest name maximum length"""
        with pytest.raises(ValidationError) as exc_info:
            WalkInCheckInParams(
                guest_name="a" * 101,
                room_id=101,
                expected_check_out="2026-12-31"
            )
        assert "guest_name" in str(exc_info.value).lower()

    def test_room_id_can_be_string(self):
        """Test room_id can be a string (room number)"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="孙七",
            room_id="301",
            expected_check_out=tomorrow
        )
        assert params.room_id == "301"

    def test_room_id_can_be_int(self):
        """Test room_id can be an integer"""
        tomorrow = date.today() + timedelta(days=1)
        params = WalkInCheckInParams(
            guest_name="孙七",
            room_id=301,
            expected_check_out=tomorrow
        )
        assert params.room_id == 301


# ==================== CheckoutParams Tests ====================

class TestCheckoutParams:
    """Test CheckoutParams validation"""

    def test_valid_params_with_defaults(self):
        """Test valid params with default values"""
        params = CheckoutParams(stay_record_id=1)
        assert params.stay_record_id == 1
        assert params.refund_deposit == Decimal("0")
        assert params.allow_unsettled is False
        assert params.unsettled_reason is None

    def test_valid_params_all_fields(self):
        """Test valid params with all fields specified"""
        params = CheckoutParams(
            stay_record_id=123,
            refund_deposit=Decimal("50.25"),
            allow_unsettled=True,
            unsettled_reason="客人承诺稍后支付"
        )
        assert params.stay_record_id == 123
        assert params.refund_deposit == Decimal("50.25")
        assert params.allow_unsettled is True
        assert params.unsettled_reason == "客人承诺稍后支付"

    def test_refund_deposit_parsing(self):
        """Test refund deposit parsing from various types"""
        params1 = CheckoutParams(stay_record_id=1, refund_deposit="100")
        assert params1.refund_deposit == Decimal("100")

        params2 = CheckoutParams(stay_record_id=1, refund_deposit=50.5)
        assert params2.refund_deposit == Decimal("50.5")

        params3 = CheckoutParams(stay_record_id=1, refund_deposit=Decimal("75.25"))
        assert params3.refund_deposit == Decimal("75.25")

    def test_refund_deposit_negative_rejected(self):
        """Test negative refund deposit is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            CheckoutParams(
                stay_record_id=1,
                refund_deposit=-10
            )
        # Error message may be either "退还金额不能为负数" or "无效的金额"
        assert "不能为负数" in str(exc_info.value) or "无效的金额" in str(exc_info.value)

    def test_stay_record_id_must_be_positive(self):
        """Test stay_record_id must be greater than 0"""
        with pytest.raises(ValidationError) as exc_info:
            CheckoutParams(stay_record_id=0)
        assert "stay_record_id" in str(exc_info.value).lower()

    def test_stay_record_id_cannot_be_negative(self):
        """Test stay_record_id cannot be negative"""
        with pytest.raises(ValidationError) as exc_info:
            CheckoutParams(stay_record_id=-1)
        assert "stay_record_id" in str(exc_info.value).lower()


# ==================== CreateTaskParams Tests ====================

class TestCreateTaskParams:
    """Test CreateTaskParams validation"""

    def test_valid_params_with_defaults(self):
        """Test valid params with default values"""
        params = CreateTaskParams(room_id=101)
        assert params.room_id == 101
        assert params.task_type == TaskType.CLEANING

    def test_valid_params_with_maintenance(self):
        """Test valid params with maintenance task type"""
        params = CreateTaskParams(
            room_id=201,
            task_type=TaskType.MAINTENANCE
        )
        assert params.room_id == 201
        assert params.task_type == TaskType.MAINTENANCE

    def test_task_type_normalization_string_cleaning(self):
        """Test task type normalization from string - cleaning"""
        params = CreateTaskParams(room_id=101, task_type="cleaning")
        assert params.task_type == TaskType.CLEANING

    def test_task_type_normalization_chinese_cleaning(self):
        """Test task type normalization from Chinese - 清洁"""
        params = CreateTaskParams(room_id=101, task_type="清洁")
        assert params.task_type == TaskType.CLEANING

    def test_task_type_normalization_string_maintenance(self):
        """Test task type normalization from string - maintenance"""
        params = CreateTaskParams(room_id=101, task_type="maintenance")
        assert params.task_type == TaskType.MAINTENANCE

    def test_task_type_normalization_chinese_maintenance(self):
        """Test task type normalization from Chinese - 维修"""
        params = CreateTaskParams(room_id=101, task_type="维修")
        assert params.task_type == TaskType.MAINTENANCE

    def test_task_type_normalization_case_insensitive(self):
        """Test task type normalization is case insensitive"""
        params = CreateTaskParams(room_id=101, task_type="CLEANING")
        assert params.task_type == TaskType.CLEANING

    def test_task_type_normalization_trims_whitespace(self):
        """Test task type normalization trims whitespace"""
        params = CreateTaskParams(room_id=101, task_type="  cleaning  ")
        assert params.task_type == TaskType.CLEANING

    def test_task_type_invalid_rejected(self):
        """Test invalid task type is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            CreateTaskParams(room_id=101, task_type="invalid_type")
        assert "无效的任务类型" in str(exc_info.value)

    def test_room_id_can_be_string(self):
        """Test room_id can be a string"""
        params = CreateTaskParams(room_id="301")
        assert params.room_id == "301"

    def test_room_id_can_be_int(self):
        """Test room_id can be an int"""
        params = CreateTaskParams(room_id=301)
        assert params.room_id == 301


# ==================== CreateReservationParams Tests ====================

class TestCreateReservationParams:
    """Test CreateReservationParams validation"""

    def test_valid_params_minimal(self):
        """Test valid params with minimal required fields"""
        params = CreateReservationParams(
            guest_name="张三",
            room_type_id=1,
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )
        assert params.guest_name == "张三"
        assert params.guest_phone == ""
        assert params.adult_count == 1
        assert params.child_count == 0
        assert params.room_count == 1

    def test_valid_params_all_fields(self):
        """Test valid params with all fields specified"""
        params = CreateReservationParams(
            guest_name="李四",
            guest_phone="13800138000",
            guest_id_number="A12345678",
            room_type_id=2,
            check_in_date="2026-06-01",
            check_out_date="2026-06-05",
            adult_count=2,
            child_count=1,
            room_count=2,
            special_requests="高层房间，无烟"
        )
        assert params.special_requests == "高层房间，无烟"

    def test_date_parsing_from_string(self):
        """Test date parsing from ISO format strings"""
        params = CreateReservationParams(
            guest_name="王五",
            room_type_id=1,
            check_in_date="2026-07-01",
            check_out_date="2026-07-03"
        )
        assert params.check_in_date == date(2026, 7, 1)
        assert params.check_out_date == date(2026, 7, 3)

    def test_date_parsing_from_date_objects(self):
        """Test date parsing from date objects"""
        check_in = date(2026, 8, 1)
        check_out = date(2026, 8, 5)
        params = CreateReservationParams(
            guest_name="赵六",
            room_type_id=1,
            check_in_date=check_in,
            check_out_date=check_out
        )
        assert params.check_in_date == check_in
        assert params.check_out_date == check_out

    def test_check_out_after_check_in_validation(self):
        """Test check_out must be after check_in"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="孙七",
                room_type_id=1,
                check_in_date="2026-06-05",
                check_out_date="2026-06-01"
            )
        assert "退房日期必须晚于入住日期" in str(exc_info.value)

    def test_check_out_equal_check_in_rejected(self):
        """Test check_out cannot equal check_in"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="孙七",
                room_type_id=1,
                check_in_date="2026-06-05",
                check_out_date="2026-06-05"
            )
        assert "退房日期必须晚于入住日期" in str(exc_info.value)

    def test_invalid_date_format_rejected(self):
        """Test invalid date format is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="周八",
                room_type_id=1,
                check_in_date="01/06/2026",
                check_out_date="05/06/2026"
            )
        assert "无效的日期格式" in str(exc_info.value)

    def test_adult_count_minimum(self):
        """Test adult_count minimum is 1"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="吴九",
                room_type_id=1,
                check_in_date="2026-06-01",
                check_out_date="2026-06-03",
                adult_count=0
            )
        assert "adult_count" in str(exc_info.value).lower()

    def test_adult_count_maximum(self):
        """Test adult_count maximum is 10"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="郑十",
                room_type_id=1,
                check_in_date="2026-06-01",
                check_out_date="2026-06-03",
                adult_count=11
            )
        assert "adult_count" in str(exc_info.value).lower()

    def test_child_count_minimum(self):
        """Test child_count minimum is 0"""
        params = CreateReservationParams(
            guest_name="刘一",
            room_type_id=1,
            check_in_date="2026-06-01",
            check_out_date="2026-06-03",
            child_count=0
        )
        assert params.child_count == 0

    def test_child_count_maximum(self):
        """Test child_count maximum is 10"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="陈二",
                room_type_id=1,
                check_in_date="2026-06-01",
                check_out_date="2026-06-03",
                child_count=11
            )
        assert "child_count" in str(exc_info.value).lower()

    def test_room_count_minimum(self):
        """Test room_count minimum is 1"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="杨三",
                room_type_id=1,
                check_in_date="2026-06-01",
                check_out_date="2026-06-03",
                room_count=0
            )
        assert "room_count" in str(exc_info.value).lower()

    def test_guest_name_too_long(self):
        """Test guest name maximum length"""
        with pytest.raises(ValidationError) as exc_info:
            CreateReservationParams(
                guest_name="a" * 101,
                room_type_id=1,
                check_in_date="2026-06-01",
                check_out_date="2026-06-03"
            )
        assert "guest_name" in str(exc_info.value).lower()

    def test_room_type_id_can_be_string(self):
        """Test room_type_id can be a string"""
        params = CreateReservationParams(
            guest_name="黄四",
            room_type_id="豪华大床房",
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )
        assert params.room_type_id == "豪华大床房"


# ==================== FilterClauseParams Tests ====================

class TestFilterClauseParams:
    """Test FilterClauseParams validation"""

    def test_valid_params_default_operator(self):
        """Test valid params with default operator"""
        params = FilterClauseParams(field="status", value="ACTIVE")
        assert params.field == "status"
        assert params.operator == "eq"
        assert params.value == "ACTIVE"

    def test_valid_params_all_operators(self):
        """Test all valid operators"""
        valid_operators = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'like', 'between']
        for op in valid_operators:
            params = FilterClauseParams(field="test", operator=op, value="value")
            assert params.operator == op

    def test_invalid_operator_rejected(self):
        """Test invalid operator is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            FilterClauseParams(field="test", operator="invalid_op", value="value")
        assert "无效的操作符" in str(exc_info.value)

    def test_value_can_be_any_type(self):
        """Test value can be various types"""
        params1 = FilterClauseParams(field="id", value=123)
        assert params1.value == 123

        params2 = FilterClauseParams(field="status", value="ACTIVE")
        assert params2.value == "ACTIVE"

        params3 = FilterClauseParams(field="tags", value=["tag1", "tag2"])
        assert params3.value == ["tag1", "tag2"]

        params4 = FilterClauseParams(field="active", value=True)
        assert params4.value is True


# ==================== JoinClauseParams Tests ====================

class TestJoinClauseParams:
    """Test JoinClauseParams validation"""

    def test_valid_params(self):
        """Test valid params"""
        params = JoinClauseParams(entity="Room", on="room_id")
        assert params.entity == "Room"
        assert params.on == "room_id"


# ==================== OntologyQueryParams Tests ====================

class TestOntologyQueryParams:
    """Test OntologyQueryParams validation"""

    def test_valid_params_minimal(self):
        """Test valid params with minimal required fields"""
        params = OntologyQueryParams(entity="Guest")
        assert params.entity == "Guest"
        assert params.fields == []
        assert params.filters is None
        assert params.joins is None
        assert params.limit == 100

    def test_valid_params_with_fields(self):
        """Test valid params with fields specified"""
        params = OntologyQueryParams(
            entity="Guest",
            fields=["name", "phone", "status"]
        )
        assert params.fields == ["name", "phone", "status"]

    def test_valid_params_with_filters(self):
        """Test valid params with filters"""
        filters = [
            FilterClauseParams(field="status", operator="eq", value="ACTIVE"),
            FilterClauseParams(field="created_at", operator="gte", value="2026-01-01")
        ]
        params = OntologyQueryParams(entity="Guest", filters=filters)
        assert len(params.filters) == 2
        assert params.filters[0].field == "status"

    def test_valid_params_with_joins(self):
        """Test valid params with joins"""
        joins = [
            JoinClauseParams(entity="StayRecord", on="stay_records"),
            JoinClauseParams(entity="Room", on="room")
        ]
        params = OntologyQueryParams(entity="Guest", joins=joins)
        assert len(params.joins) == 2
        assert params.joins[0].entity == "StayRecord"

    def test_valid_params_with_order_by(self):
        """Test valid params with order_by"""
        params = OntologyQueryParams(
            entity="Guest",
            order_by=["name", "created_at"]
        )
        assert params.order_by == ["name", "created_at"]

    def test_limit_minimum(self):
        """Test limit minimum is 1"""
        with pytest.raises(ValidationError) as exc_info:
            OntologyQueryParams(entity="Guest", limit=0)
        assert "limit" in str(exc_info.value).lower()

    def test_limit_maximum(self):
        """Test limit maximum is 1000"""
        with pytest.raises(ValidationError) as exc_info:
            OntologyQueryParams(entity="Guest", limit=1001)
        assert "limit" in str(exc_info.value).lower()

    def test_limit_at_boundary(self):
        """Test limit at boundary values"""
        params1 = OntologyQueryParams(entity="Guest", limit=1)
        assert params1.limit == 1

        params2 = OntologyQueryParams(entity="Guest", limit=1000)
        assert params2.limit == 1000

    def test_aggregates_can_be_list(self):
        """Test aggregates can be a list of dicts"""
        aggregates = [
            {"function": "count", "field": "id", "alias": "total"},
            {"function": "sum", "field": "amount", "alias": "total_amount"}
        ]
        params = OntologyQueryParams(entity="Guest", aggregates=aggregates)
        assert len(params.aggregates) == 2
        assert params.aggregates[0]["function"] == "count"


# ==================== SemanticFilterParams Tests ====================

class TestSemanticFilterParams:
    """Test SemanticFilterParams validation"""

    def test_valid_params_defaults(self):
        """Test valid params with default operator"""
        params = SemanticFilterParams(path="status", value="ACTIVE")
        assert params.path == "status"
        assert params.operator == "eq"
        assert params.value == "ACTIVE"

    def test_valid_params_all_operators(self):
        """Test all valid operators for semantic filter"""
        valid_operators = [
            'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
            'in', 'not_in', 'like', 'not_like',
            'between', 'is_null', 'is_not_null'
        ]
        for op in valid_operators:
            params = SemanticFilterParams(path="test", operator=op, value="value")
            assert params.operator == op

    def test_operator_normalization_to_lowercase(self):
        """Test operator is normalized to lowercase"""
        params1 = SemanticFilterParams(path="test", operator="EQ", value="value")
        assert params1.operator == "eq"

        params2 = SemanticFilterParams(path="test", operator="LIKE", value="value")
        assert params2.operator == "like"

    def test_invalid_operator_rejected(self):
        """Test invalid operator is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            SemanticFilterParams(path="test", operator="invalid_op", value="value")
        assert "无效的操作符" in str(exc_info.value)

    def test_path_can_be_dotted(self):
        """Test path can be dotted notation"""
        params = SemanticFilterParams(path="stays.room.status", value="DIRTY")
        assert params.path == "stays.room.status"

    def test_value_can_be_none(self):
        """Test value can be None for some operators"""
        params = SemanticFilterParams(path="deleted_at", operator="is_null", value=None)
        assert params.value is None

    def test_value_can_be_list(self):
        """Test value can be a list for 'in' operator"""
        params = SemanticFilterParams(
            path="status",
            operator="in",
            value=["ACTIVE", "PENDING"]
        )
        assert params.value == ["ACTIVE", "PENDING"]


# ==================== SemanticQueryParams Tests ====================

class TestSemanticQueryParams:
    """Test SemanticQueryParams validation"""

    def test_valid_params_minimal(self):
        """Test valid params with minimal required fields"""
        params = SemanticQueryParams(root_object="Guest")
        assert params.root_object == "Guest"
        assert params.fields == []
        assert params.filters == []
        assert params.order_by == []
        assert params.limit == 100
        assert params.offset == 0
        assert params.distinct is False

    def test_valid_params_all_fields(self):
        """Test valid params with all fields specified"""
        filters = [
            SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
        ]
        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=filters,
            order_by=["name"],
            limit=50,
            offset=10,
            distinct=True
        )
        assert params.root_object == "Guest"
        assert params.fields == ["name", "stays.room_number"]
        assert len(params.filters) == 1
        assert params.limit == 50
        assert params.offset == 10
        assert params.distinct is True

    def test_fields_can_be_dotted_notation(self):
        """Test fields support dotted notation"""
        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room_number", "stays.room.room_type.name"]
        )
        assert "stays.room.room_type.name" in params.fields

    def test_filters_default_to_empty_list(self):
        """Test filters defaults to empty list"""
        params = SemanticQueryParams(root_object="Guest")
        assert params.filters == []

    def test_order_by_default_to_empty_list(self):
        """Test order_by defaults to empty list"""
        params = SemanticQueryParams(root_object="Guest")
        assert params.order_by == []

    def test_offset_minimum(self):
        """Test offset minimum is 0"""
        params = SemanticQueryParams(root_object="Guest", offset=0)
        assert params.offset == 0

    def test_offset_cannot_be_negative(self):
        """Test offset cannot be negative"""
        with pytest.raises(ValidationError) as exc_info:
            SemanticQueryParams(root_object="Guest", offset=-1)
        assert "offset" in str(exc_info.value).lower()

    def test_limit_minimum(self):
        """Test limit minimum is 1"""
        with pytest.raises(ValidationError) as exc_info:
            SemanticQueryParams(root_object="Guest", limit=0)
        assert "limit" in str(exc_info.value).lower()

    def test_limit_maximum(self):
        """Test limit maximum is 1000"""
        with pytest.raises(ValidationError) as exc_info:
            SemanticQueryParams(root_object="Guest", limit=1001)
        assert "limit" in str(exc_info.value).lower()

    def test_root_object_alias_normalization(self):
        """Test root_object alias normalization"""
        # Guest aliases
        params1 = SemanticQueryParams(root_object="guest")
        assert params1.root_object == "Guest"

        params2 = SemanticQueryParams(root_object="guests")
        assert params2.root_object == "Guest"

        # Room aliases
        params3 = SemanticQueryParams(root_object="room")
        assert params3.root_object == "Room"

        params4 = SemanticQueryParams(root_object="rooms")
        assert params4.root_object == "Room"

        # StayRecord aliases
        params5 = SemanticQueryParams(root_object="stay")
        assert params5.root_object == "StayRecord"

        params6 = SemanticQueryParams(root_object="stays")
        assert params6.root_object == "StayRecord"

    def test_root_object_case_insensitive(self):
        """Test root_object normalization is case insensitive"""
        params1 = SemanticQueryParams(root_object="GUEST")
        assert params1.root_object == "Guest"

        params2 = SemanticQueryParams(root_object="Room")
        assert params2.root_object == "Room"

    def test_distinct_default_is_false(self):
        """Test distinct defaults to False"""
        params = SemanticQueryParams(root_object="Guest")
        assert params.distinct is False

    def test_distinct_can_be_true(self):
        """Test distinct can be set to True"""
        params = SemanticQueryParams(root_object="Guest", distinct=True)
        assert params.distinct is True


# ==================== ActionResult Tests ====================

class TestActionResult:
    """Test ActionResult model"""

    def test_success_result(self):
        """Test success result"""
        result = ActionResult(success=True, message="操作成功")
        assert result.success is True
        assert result.message == "操作成功"
        assert result.data is None
        assert result.requires_confirmation is False
        assert result.error is None

    def test_success_result_with_data(self):
        """Test success result with data"""
        result = ActionResult(
            success=True,
            message="查询成功",
            data={"rows": [{"id": 1, "name": "张三"}]}
        )
        assert result.data["rows"][0]["name"] == "张三"

    def test_error_result(self):
        """Test error result"""
        result = ActionResult(
            success=False,
            message="操作失败",
            error="validation_error"
        )
        assert result.success is False
        assert result.error == "validation_error"

    def test_result_with_confirmation_required(self):
        """Test result with confirmation required"""
        result = ActionResult(
            success=True,
            message="需要确认",
            requires_confirmation=True
        )
        assert result.requires_confirmation is True

    def test_all_fields(self):
        """Test result with all fields"""
        result = ActionResult(
            success=True,
            message="完整结果",
            data={"id": 123},
            requires_confirmation=False,
            error=None
        )
        assert result.success is True
        assert result.data["id"] == 123


# ==================== __all__ Export Tests ====================

class TestModuleExports:
    """Test that all models are properly exported"""

    def test_base_module_exports(self):
        """Test that base module exports all expected models"""
        from app.services.actions import base

        expected_exports = [
            "WalkInCheckInParams",
            "CheckoutParams",
            "CreateTaskParams",
            "CreateReservationParams",
            "FilterClauseParams",
            "JoinClauseParams",
            "OntologyQueryParams",
            "SemanticFilterParams",
            "SemanticQueryParams",
            "ActionResult",
        ]

        for export in expected_exports:
            assert hasattr(base, export), f"{export} should be exported from base module"
