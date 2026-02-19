"""
tests/domain/test_hotel_domain_adapter_extra.py

Additional coverage tests for HotelDomainAdapter - covers OODA support methods,
enhance_action_params, enhance_single_action_params, get_field_definition,
get_report_data, get_help_text, execute_action error paths, etc.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter


@pytest.fixture
def populated_registry():
    """Create a fresh registry with hotel entities."""
    registry = OntologyRegistry()
    registry.clear()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(registry)
    yield registry
    registry.clear()


@pytest.fixture
def adapter_with_mock_db():
    """Create HotelDomainAdapter with a mock db and mock services."""
    mock_db = Mock()
    adapter = HotelDomainAdapter(db=mock_db)
    return adapter, mock_db


class TestHotelDomainAdapterMethods:
    """Test adapter methods that are uncovered."""

    def test_get_domain_name(self):
        adapter = HotelDomainAdapter()
        assert "Hotel" in adapter.get_domain_name()

    def test_get_current_state(self):
        adapter = HotelDomainAdapter()
        state = adapter.get_current_state()
        assert "total_rooms" in state
        assert "occupancy_rate" in state

    def test_get_llm_system_prompt_additions(self):
        adapter = HotelDomainAdapter()
        prompt = adapter.get_llm_system_prompt_additions()
        assert "房间编号" in prompt

    def test_get_entity_display_name_room(self):
        adapter = HotelDomainAdapter()
        assert adapter.get_entity_display_name("Room", 201) == "房间 201"

    def test_get_entity_display_name_guest(self):
        adapter = HotelDomainAdapter()
        assert adapter.get_entity_display_name("Guest", 1) == "客人 1"

    def test_get_entity_display_name_reservation(self):
        adapter = HotelDomainAdapter()
        assert adapter.get_entity_display_name("Reservation", 5) == "预订 #5"

    def test_get_entity_display_name_stay_record(self):
        adapter = HotelDomainAdapter()
        assert adapter.get_entity_display_name("StayRecord", 10) == "住宿记录 #10"

    def test_get_entity_display_name_unknown(self):
        adapter = HotelDomainAdapter()
        assert adapter.get_entity_display_name("Unknown", 99) == "Unknown:99"

    def test_get_help_text(self):
        adapter = HotelDomainAdapter()
        help_text = adapter.get_help_text()
        assert "查询" in help_text
        assert "操作" in help_text


class TestBuildLLMContext:
    """Cover build_llm_context (lines 361-400)."""

    def test_build_llm_context(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db

        # Inject mock services
        mock_room_service = MagicMock()
        mock_room_service.get_room_status_summary.return_value = {"occupied": 5}
        mock_rt = Mock()
        mock_rt.id = 1
        mock_rt.name = "标间"
        mock_rt.base_price = Decimal("288.00")
        mock_room_service.get_room_types.return_value = [mock_rt]

        mock_checkin_service = MagicMock()
        mock_stay = Mock()
        mock_stay.id = 1
        mock_stay.room = Mock()
        mock_stay.room.room_number = "201"
        mock_stay.guest = Mock()
        mock_stay.guest.name = "张三"
        mock_stay.expected_check_out = date.today() + timedelta(days=1)
        mock_checkin_service.get_active_stays.return_value = [mock_stay]

        mock_task_service = MagicMock()
        mock_task = Mock()
        mock_task.id = 1
        mock_task.room = Mock()
        mock_task.room.room_number = "202"
        mock_task.task_type = Mock()
        mock_task.task_type.value = "cleaning"
        mock_task_service.get_pending_tasks.return_value = [mock_task]

        adapter._room_service = mock_room_service
        adapter._checkin_service = mock_checkin_service
        adapter._task_service = mock_task_service

        context = adapter.build_llm_context(mock_db)
        assert "room_summary" in context
        assert "room_types" in context
        assert "active_stays" in context
        assert "pending_tasks" in context
        assert context["room_types"][0]["name"] == "标间"


class TestEnhanceActionParams:
    """Cover enhance_action_params (lines 409-491)."""

    def test_enhance_room_type_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db

        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room_type.return_value = ParseResult(
            value=1, confidence=1.0, matched_by='direct', raw_input='标间'
        )

        mock_room_svc = MagicMock()
        mock_rt = Mock()
        mock_rt.name = "标间"
        mock_room_svc.get_room_type.return_value = mock_rt

        adapter._param_parser = mock_pp
        adapter._room_service = mock_room_svc
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"room_type_name": "标间"}
        result = adapter.enhance_action_params("create_reservation", params, "test", mock_db)
        assert result["room_type_id"] == 1

    def test_enhance_room_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room.return_value = ParseResult(
            value=5, confidence=1.0, matched_by='direct', raw_input='201'
        )
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"room_number": "201"}
        result = adapter.enhance_action_params("checkin", params, "test", mock_db)
        assert result["room_id"] == 5

    def test_enhance_new_room_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room.return_value = ParseResult(
            value=10, confidence=1.0, matched_by='direct', raw_input='301'
        )
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"new_room_number": "301"}
        result = adapter.enhance_action_params("change_room", params, "test", mock_db)
        assert result["new_room_id"] == 10

    def test_enhance_assignee_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_employee.return_value = ParseResult(
            value=3, confidence=1.0, matched_by='direct', raw_input='刘阿姨'
        )
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"assignee_name": "刘阿姨"}
        result = adapter.enhance_action_params("assign_task", params, "test", mock_db)
        assert result["assignee_id"] == 3

    def test_enhance_status_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room_status.return_value = ParseResult(
            value="vacant_clean", confidence=1.0, matched_by='direct', raw_input='净房'
        )
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"status": "净房"}
        result = adapter.enhance_action_params("update_room_status", params, "test", mock_db)
        assert result["status"] == "vacant_clean"

    def test_enhance_task_type_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_result = ParseResult(
            value=Mock(value="cleaning"), confidence=1.0, matched_by='direct', raw_input='清洁'
        )
        mock_pp.parse_task_type.return_value = mock_result
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"task_type": "清洁"}
        result = adapter.enhance_action_params("create_task", params, "test", mock_db)
        assert result["task_type"] == "cleaning"

    def test_enhance_price_type_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"price_type": "周末"}
        result = adapter.enhance_action_params("update_price", params, "test", mock_db)
        assert result["price_type"] == "weekend"

    def test_enhance_reservation_no_fallback(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()

        mock_res_svc = MagicMock()
        mock_res = Mock()
        mock_res.id = 42
        mock_res_svc.get_reservation_by_no.return_value = mock_res
        adapter._reservation_service = mock_res_svc

        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"reservation_no": "RES001"}
        result = adapter.enhance_action_params("cancel_reservation", params, "test", mock_db)
        assert result["reservation_id"] == 42

    def test_enhance_date_parsing(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_date.return_value = ParseResult(
            value=date(2025, 3, 1), confidence=1.0, matched_by='direct', raw_input='2025-03-01'
        )
        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"check_in_date": "2025-03-01"}
        result = adapter.enhance_action_params("create_reservation", params, "test", mock_db)
        assert result["check_in_date"] == "2025-03-01"


class TestEnhanceSingleActionParams:
    """Cover enhance_single_action_params (lines 493-517)."""

    def test_enhance_single_room_type(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room_type.return_value = ParseResult(
            value=2, confidence=1.0, matched_by='direct', raw_input='大床房'
        )
        mock_room_svc = MagicMock()
        mock_rt = Mock()
        mock_rt.name = "大床房"
        mock_room_svc.get_room_type.return_value = mock_rt

        adapter._param_parser = mock_pp
        adapter._room_service = mock_room_svc
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"room_type": "大床房"}
        result = adapter.enhance_single_action_params("create_reservation", params, mock_db)
        assert result["room_type_id"] == 2
        assert result["room_type_name"] == "大床房"

    def test_enhance_single_room_number(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room.return_value = ParseResult(
            value=5, confidence=1.0, matched_by='direct', raw_input='301'
        )

        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"room_number": "301"}
        result = adapter.enhance_single_action_params("checkin", params, mock_db)
        assert result["room_id"] == 5

    def test_enhance_single_new_room_number(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_pp = MagicMock()
        from app.hotel.services.param_parser_service import ParseResult
        mock_pp.parse_room.return_value = ParseResult(
            value=8, confidence=1.0, matched_by='direct', raw_input='401'
        )

        adapter._param_parser = mock_pp
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()

        params = {"new_room_number": "401"}
        result = adapter.enhance_single_action_params("change_room", params, mock_db)
        assert result["new_room_id"] == 8


class TestGetFieldDefinition:
    """Cover get_field_definition (lines 519-530)."""

    def test_get_field_definition(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._report_service = MagicMock()
        adapter._task_service = MagicMock()
        adapter._param_parser = MagicMock()

        with patch('app.hotel.field_definitions.HotelFieldDefinitionProvider') as MockProvider:
            mock_provider = MagicMock()
            mock_provider.get_field_definition.return_value = {"type": "text", "label": "Phone"}
            MockProvider.return_value = mock_provider

            result = adapter.get_field_definition("phone", "update_guest", {}, mock_db)
            assert result is not None


class TestGetReportData:
    """Cover get_report_data (lines 532-541)."""

    def test_get_report_data(self, adapter_with_mock_db):
        adapter, mock_db = adapter_with_mock_db
        mock_report_svc = MagicMock()
        mock_report_svc.get_dashboard_stats.return_value = {
            "occupancy_rate": 65,
            "today_checkins": 3,
            "today_checkouts": 2,
            "today_revenue": 5000,
        }
        adapter._report_service = mock_report_svc
        adapter._room_service = MagicMock()
        adapter._reservation_service = MagicMock()
        adapter._checkin_service = MagicMock()
        adapter._billing_service = MagicMock()
        adapter._checkout_service = MagicMock()
        adapter._task_service = MagicMock()
        adapter._param_parser = MagicMock()

        result = adapter.get_report_data(mock_db)
        assert "message" in result
        assert "stats" in result
        assert "入住率" in result["message"]


class TestExecuteActionErrors:
    """Cover execute_action error handling paths (lines 305-332)."""

    def test_execute_action_value_error(self):
        adapter = HotelDomainAdapter()
        with patch('app.services.actions.get_action_registry') as mock_get_reg:
            mock_get_reg.return_value.dispatch.side_effect = ValueError("不支持")
            result = adapter.execute_action("invalid_action", {}, {})
        assert result["success"] is False
        assert "不支持" in result["error"]

    def test_execute_action_generic_exception(self):
        adapter = HotelDomainAdapter()
        with patch('app.services.actions.get_action_registry') as mock_get_reg:
            mock_get_reg.return_value.dispatch.side_effect = RuntimeError("crash")
            result = adapter.execute_action("test", {}, {})
        assert result["success"] is False
        assert "Action execution failed" in result["error"]


class TestAutoRegisterProperties:
    """Cover _auto_register_properties (lines 182-239)."""

    def test_auto_register_all_column_types(self, populated_registry):
        """Verify that all column types are properly auto-registered."""
        room_meta = populated_registry.get_entity("Room")
        assert room_meta is not None

        # Should have auto-registered common properties
        assert "room_number" in room_meta.properties
        assert "floor" in room_meta.properties
        assert "status" in room_meta.properties

        # Check types
        assert room_meta.properties["room_number"].type == "string"
        assert room_meta.properties["floor"].type == "integer"

    def test_display_names_applied(self, populated_registry):
        """Verify that display names from _DISPLAY_NAMES are applied."""
        room_meta = populated_registry.get_entity("Room")
        room_number_prop = room_meta.properties["room_number"]
        assert room_number_prop.display_name == "房间号"

    def test_security_overrides_applied(self, populated_registry):
        """Verify security overrides from _SECURITY_OVERRIDES are applied."""
        guest_meta = populated_registry.get_entity("Guest")
        phone_prop = guest_meta.properties["phone"]
        assert phone_prop.security_level == "CONFIDENTIAL"

        id_number_prop = guest_meta.properties["id_number"]
        assert id_number_prop.security_level == "RESTRICTED"

    def test_enum_columns_detected(self, populated_registry):
        """Verify enum columns are properly detected."""
        room_meta = populated_registry.get_entity("Room")
        status_prop = room_meta.properties["status"]
        assert status_prop.type == "enum"
        assert status_prop.enum_values is not None

    def test_foreign_keys_detected(self, populated_registry):
        """Verify foreign key columns are detected."""
        room_meta = populated_registry.get_entity("Room")
        room_type_prop = room_meta.properties["room_type_id"]
        assert room_type_prop.is_foreign_key is True
