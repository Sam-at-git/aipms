"""
tests/domain/test_field_definitions.py

Tests for app/hotel/field_definitions.py - Hotel field definition provider.
"""
import pytest
from unittest.mock import Mock, MagicMock, PropertyMock

from app.hotel.field_definitions import (
    HotelFieldDefinitionProvider,
    _FIELD_BUILDERS,
    _build_room_number,
    _build_guest_name,
    _build_guest_phone,
    _build_check_in_date,
    _build_check_out_date,
    _build_expected_check_out,
    _build_new_room_number,
    _build_room_type_id,
    _build_stay_record_id,
    _build_reservation_id,
    _build_task_type,
)
from app.models.schemas import MissingField


@pytest.fixture
def mock_room_service():
    svc = Mock()
    rt1 = Mock()
    rt1.id = 1
    rt1.name = "标间"
    rt1.base_price = 288
    rt2 = Mock()
    rt2.id = 2
    rt2.name = "大床房"
    rt2.base_price = 328
    svc.get_room_types.return_value = [rt1, rt2]
    return svc


@pytest.fixture
def mock_checkin_service():
    svc = Mock()
    stay = Mock()
    stay.id = 10
    stay.room = Mock()
    stay.room.room_number = "201"
    stay.guest = Mock()
    stay.guest.name = "张三"
    svc.get_active_stays.return_value = [stay]
    return svc


@pytest.fixture
def mock_reservation_service():
    svc = Mock()
    res = Mock()
    res.id = 5
    res.reservation_no = "RES-001"
    res.guest = Mock()
    res.guest.name = "李四"
    res.room_type = Mock()
    res.room_type.name = "大床房"
    svc.get_today_arrivals.return_value = [res]
    return svc


@pytest.fixture
def provider(mock_room_service, mock_checkin_service, mock_reservation_service):
    db = Mock()
    return HotelFieldDefinitionProvider(
        db=db,
        room_service=mock_room_service,
        checkin_service=mock_checkin_service,
        reservation_service=mock_reservation_service,
    )


class TestFieldBuildersRegistry:
    """Test that all expected field builders are registered."""

    def test_all_field_builders_exist(self):
        expected_fields = [
            "room_number", "guest_name", "guest_phone",
            "room_type_id", "check_in_date", "check_out_date",
            "expected_check_out", "new_room_number",
            "stay_record_id", "reservation_id", "task_type",
        ]
        for field_name in expected_fields:
            assert field_name in _FIELD_BUILDERS, (
                f"Missing field builder for: {field_name}"
            )

    def test_field_builders_are_callable(self):
        for name, builder in _FIELD_BUILDERS.items():
            assert callable(builder), f"Builder for {name} is not callable"


class TestStaticFieldBuilders:
    """Test static (non-DB-dependent) field builders."""

    def test_build_room_number(self, provider):
        field = _build_room_number(provider)
        assert isinstance(field, MissingField)
        assert field.field_name == "room_number"
        assert field.display_name == "房间号"
        assert field.field_type == "text"
        assert field.required is True
        assert "201" in field.placeholder

    def test_build_guest_name(self, provider):
        field = _build_guest_name(provider)
        assert field.field_name == "guest_name"
        assert field.display_name == "客人姓名"
        assert field.field_type == "text"
        assert field.required is True

    def test_build_guest_phone(self, provider):
        field = _build_guest_phone(provider)
        assert field.field_name == "guest_phone"
        assert field.display_name == "联系电话"
        assert field.field_type == "text"
        assert field.required is True

    def test_build_check_in_date(self, provider):
        field = _build_check_in_date(provider)
        assert field.field_name == "check_in_date"
        assert field.display_name == "入住日期"
        assert field.field_type == "date"
        assert field.required is True

    def test_build_check_out_date(self, provider):
        field = _build_check_out_date(provider)
        assert field.field_name == "check_out_date"
        assert field.display_name == "离店日期"
        assert field.field_type == "date"
        assert field.required is True

    def test_build_expected_check_out(self, provider):
        field = _build_expected_check_out(provider)
        assert field.field_name == "expected_check_out"
        assert field.display_name == "预计离店日期"
        assert field.field_type == "date"
        assert field.required is True

    def test_build_new_room_number(self, provider):
        field = _build_new_room_number(provider)
        assert field.field_name == "new_room_number"
        assert field.display_name == "新房间号"
        assert field.field_type == "text"
        assert field.required is True

    def test_build_task_type(self, provider):
        field = _build_task_type(provider)
        assert field.field_name == "task_type"
        assert field.display_name == "任务类型"
        assert field.field_type == "select"
        assert field.required is True
        assert field.options is not None
        values = [opt["value"] for opt in field.options]
        assert "cleaning" in values
        assert "maintenance" in values


class TestDynamicFieldBuilders:
    """Test dynamic field builders that query DB for options."""

    def test_build_room_type_id(self, provider):
        field = _build_room_type_id(provider)
        assert field.field_name == "room_type_id"
        assert field.display_name == "房型"
        assert field.field_type == "select"
        assert field.required is True
        assert len(field.options) == 2
        labels = [opt["label"] for opt in field.options]
        assert any("标间" in l for l in labels)
        assert any("大床房" in l for l in labels)

    def test_build_stay_record_id(self, provider):
        field = _build_stay_record_id(provider)
        assert field.field_name == "stay_record_id"
        assert field.display_name == "住宿记录"
        assert field.field_type == "select"
        assert len(field.options) == 1
        assert "201" in field.options[0]["label"]
        assert "张三" in field.options[0]["label"]

    def test_build_reservation_id(self, provider):
        field = _build_reservation_id(provider)
        assert field.field_name == "reservation_id"
        assert field.display_name == "预订记录"
        assert field.field_type == "select"
        assert len(field.options) == 1
        assert "RES-001" in field.options[0]["label"]
        assert "李四" in field.options[0]["label"]


class TestProviderGetFieldDefinition:
    """Test the main get_field_definition method."""

    def test_known_field_returns_definition(self, provider):
        field = provider.get_field_definition("room_number", "create_task", {})
        assert field is not None
        assert isinstance(field, MissingField)
        assert field.field_name == "room_number"

    def test_unknown_field_returns_none(self, provider):
        result = provider.get_field_definition("nonexistent_field", "create_task", {})
        assert result is None

    def test_each_registered_field_returns_definition(self, provider):
        for field_name in _FIELD_BUILDERS:
            result = provider.get_field_definition(field_name)
            assert result is not None, f"get_field_definition returned None for {field_name}"
            assert isinstance(result, MissingField)

    def test_default_params(self, provider):
        """Ensure defaults work for action_type and current_params."""
        field = provider.get_field_definition("guest_name")
        assert field is not None
