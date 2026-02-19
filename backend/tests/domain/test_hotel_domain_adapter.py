"""
tests/domain/test_hotel_domain_adapter.py

Tests for HotelDomainAdapter - verifies entity, relationship, state machine,
constraint, and property registration into OntologyRegistry.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch

from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter


@pytest.fixture
def clean_registry():
    """Provide a clean OntologyRegistry for each test."""
    registry = OntologyRegistry()
    registry.clear()
    yield registry
    registry.clear()


@pytest.fixture
def adapter():
    """Create a HotelDomainAdapter without db."""
    return HotelDomainAdapter()


@pytest.fixture
def adapter_with_registry(adapter, clean_registry):
    """Create adapter and register ontology."""
    adapter.register_ontology(clean_registry)
    return adapter, clean_registry


class TestRegisterOntology:
    """Test register_ontology() registers all expected entities and metadata."""

    def test_register_ontology_populates_entities(self, adapter_with_registry):
        _, registry = adapter_with_registry
        entities = registry.get_entities()
        entity_names = {e.name for e in entities}
        expected = {"Room", "Guest", "Reservation", "StayRecord", "Bill",
                    "Task", "Employee", "Payment", "RoomType", "RatePlan"}
        assert expected.issubset(entity_names), (
            f"Missing entities: {expected - entity_names}"
        )

    def test_register_ontology_registers_models(self, adapter_with_registry):
        _, registry = adapter_with_registry
        for name in ["Room", "Guest", "Reservation", "StayRecord", "Bill",
                      "Task", "Employee", "Payment", "RoomType", "RatePlan"]:
            model = registry.get_model(name)
            assert model is not None, f"Model not registered for {name}"

    def test_register_ontology_returns_none(self, adapter, clean_registry):
        """register_ontology should return None (void method)."""
        result = adapter.register_ontology(clean_registry)
        assert result is None


class TestRegisterEntities:
    """Test entity registration including properties, state machines, constraints."""

    def test_room_entity_has_properties(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        assert room is not None
        assert room.name == "Room"
        assert room.table_name == "rooms"
        # Should have auto-registered properties from ORM columns
        assert "room_number" in room.properties
        assert "floor" in room.properties
        assert "status" in room.properties

    def test_guest_entity_has_properties(self, adapter_with_registry):
        _, registry = adapter_with_registry
        guest = registry.get_entity("Guest")
        assert guest is not None
        assert "name" in guest.properties
        assert "phone" in guest.properties

    def test_guest_phone_has_enhanced_metadata(self, adapter_with_registry):
        _, registry = adapter_with_registry
        guest = registry.get_entity("Guest")
        phone_prop = guest.get_property("phone")
        assert phone_prop is not None
        assert phone_prop.format_regex == r'^1[3-9]\d{9}$'
        assert phone_prop.sensitive is True
        assert len(phone_prop.update_validation_rules) >= 2

    def test_reservation_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        reservation = registry.get_entity("Reservation")
        assert reservation is not None
        assert "guest_id" in reservation.properties
        assert "check_in_date" in reservation.properties

    def test_stay_record_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        stay = registry.get_entity("StayRecord")
        assert stay is not None
        assert stay.table_name == "stay_records"

    def test_bill_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        bill = registry.get_entity("Bill")
        assert bill is not None
        assert "total_amount" in bill.properties

    def test_task_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        task = registry.get_entity("Task")
        assert task is not None
        assert "task_type" in task.properties

    def test_employee_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        employee = registry.get_entity("Employee")
        assert employee is not None
        assert "username" in employee.properties

    def test_room_type_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        rt = registry.get_entity("RoomType")
        assert rt is not None
        assert "base_price" in rt.properties

    def test_rate_plan_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        rp = registry.get_entity("RatePlan")
        assert rp is not None

    def test_payment_entity_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        payment = registry.get_entity("Payment")
        assert payment is not None


class TestAutoRegisterProperties:
    """Test _auto_register_properties assigns correct metadata."""

    def test_property_types_detected(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        # room_number should be string
        rn = room.get_property("room_number")
        assert rn is not None
        assert rn.type == "string"
        # floor should be integer
        fl = room.get_property("floor")
        assert fl is not None
        assert fl.type == "integer"

    def test_foreign_key_detected(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        fk = room.get_property("room_type_id")
        assert fk is not None
        assert fk.is_foreign_key is True

    def test_primary_key_detected(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        pk = room.get_property("id")
        assert pk is not None
        assert pk.is_primary_key is True

    def test_display_names_applied(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        rn = room.get_property("room_number")
        assert rn.display_name == "房间号"

    def test_security_overrides_applied(self, adapter_with_registry):
        _, registry = adapter_with_registry
        employee = registry.get_entity("Employee")
        pw = employee.get_property("password_hash")
        assert pw is not None
        assert pw.security_level == "RESTRICTED"

    def test_confidential_fields(self, adapter_with_registry):
        _, registry = adapter_with_registry
        guest = registry.get_entity("Guest")
        phone = guest.get_property("phone")
        assert phone.security_level == "CONFIDENTIAL"

    def test_enum_detection(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        status_prop = room.get_property("status")
        assert status_prop is not None
        assert status_prop.type == "enum"
        assert status_prop.enum_values is not None
        # Enum values may be uppercase (DB storage convention)
        enum_lower = [v.lower() for v in status_prop.enum_values]
        assert "vacant_clean" in enum_lower

    def test_boolean_detection(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room = registry.get_entity("Room")
        active = room.get_property("is_active")
        assert active is not None
        assert active.type == "boolean"


class TestRegisterRelationships:
    """Test relationship registration."""

    def test_relationships_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        guest_rels = registry.get_relationships("Guest")
        assert len(guest_rels) > 0

    def test_guest_has_stays_relationship(self, adapter_with_registry):
        _, registry = adapter_with_registry
        guest_rels = registry.get_relationships("Guest")
        stays_rel = [r for r in guest_rels if r.name == "stays"]
        assert len(stays_rel) == 1
        assert stays_rel[0].target_entity == "StayRecord"
        assert stays_rel[0].cardinality == "one_to_many"

    def test_room_has_room_type_relationship(self, adapter_with_registry):
        _, registry = adapter_with_registry
        room_rels = registry.get_relationships("Room")
        rt_rel = [r for r in room_rels if r.name == "room_type"]
        assert len(rt_rel) == 1
        assert rt_rel[0].target_entity == "RoomType"

    def test_stay_record_has_bill_relationship(self, adapter_with_registry):
        _, registry = adapter_with_registry
        stay_rels = registry.get_relationships("StayRecord")
        bill_rel = [r for r in stay_rels if r.name == "bill"]
        assert len(bill_rel) == 1
        assert bill_rel[0].target_entity == "Bill"

    def test_task_has_room_relationship(self, adapter_with_registry):
        _, registry = adapter_with_registry
        task_rels = registry.get_relationships("Task")
        room_rel = [r for r in task_rels if r.name == "room"]
        assert len(room_rel) == 1
        assert room_rel[0].target_entity == "Room"


class TestStateMachines:
    """Test state machine registration."""

    def test_room_state_machine_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        sm = registry.get_state_machine("Room")
        assert sm is not None
        assert "vacant_clean" in sm.states
        assert "occupied" in sm.states
        assert sm.initial_state == "vacant_clean"

    def test_task_state_machine_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        sm = registry.get_state_machine("Task")
        assert sm is not None
        assert "pending" in sm.states
        assert "completed" in sm.states

    def test_room_state_transitions(self, adapter_with_registry):
        _, registry = adapter_with_registry
        sm = registry.get_state_machine("Room")
        assert sm.transitions is not None
        triggers = {t.trigger for t in sm.transitions}
        assert "checkin" in triggers
        assert "checkout" in triggers
        assert "clean" in triggers


class TestConstraints:
    """Test constraint registration."""

    def test_room_constraints_registered(self, adapter_with_registry):
        _, registry = adapter_with_registry
        constraints = registry.get_constraints("Room")
        assert len(constraints) > 0

    def test_room_checkin_constraint(self, adapter_with_registry):
        _, registry = adapter_with_registry
        constraints = registry.get_constraints_for_entity_action("Room", "checkin")
        assert any("空闲" in c.name or "vacant" in c.name.lower() for c in constraints)


class TestEvents:
    """Test event registration."""

    def test_room_status_changed_event(self, adapter_with_registry):
        _, registry = adapter_with_registry
        event = registry.get_event("ROOM_STATUS_CHANGED")
        assert event is not None
        assert event.entity == "Room"


class TestDomainAdapterMethods:
    """Test other HotelDomainAdapter methods."""

    def test_get_domain_name(self, adapter):
        assert adapter.get_domain_name() == "Hotel Management System"

    def test_get_current_state(self, adapter):
        state = adapter.get_current_state()
        assert "total_rooms" in state
        assert "occupied_rooms" in state
        assert "occupancy_rate" in state

    def test_get_llm_system_prompt_additions(self, adapter):
        prompt = adapter.get_llm_system_prompt_additions()
        assert "酒店" in prompt
        assert "房间" in prompt

    def test_get_entity_display_name_room(self, adapter):
        assert "房间" in adapter.get_entity_display_name("Room", 101)

    def test_get_entity_display_name_guest(self, adapter):
        assert "客人" in adapter.get_entity_display_name("Guest", 1)

    def test_get_entity_display_name_reservation(self, adapter):
        assert "预订" in adapter.get_entity_display_name("Reservation", 1)

    def test_get_entity_display_name_stay_record(self, adapter):
        assert "住宿记录" in adapter.get_entity_display_name("StayRecord", 1)

    def test_get_entity_display_name_unknown(self, adapter):
        result = adapter.get_entity_display_name("Unknown", 1)
        assert "Unknown" in result

    def test_get_help_text(self, adapter):
        text = adapter.get_help_text()
        assert "查询" in text
        assert "入住" in text

    def test_get_display_names(self, adapter):
        names = adapter.get_display_names()
        assert "guest_name" in names
        assert "room_number" in names
        assert names["guest_name"] == "客人"

    def test_get_admin_roles(self, adapter):
        roles = adapter.get_admin_roles()
        assert "sysadmin" in roles
        assert "manager" in roles

    def test_get_query_examples(self, adapter):
        examples = adapter.get_query_examples()
        assert len(examples) >= 2
        root_objects = {e["query"]["root_object"] for e in examples}
        assert "Guest" in root_objects
        assert "Room" in root_objects

    def test_get_hitl_risk_overrides_returns_empty(self, adapter):
        assert adapter.get_hitl_risk_overrides() == {}

    def test_get_hitl_custom_rules(self, adapter):
        rules = adapter.get_hitl_custom_rules()
        assert len(rules) == 1
        # The rule should be callable
        assert callable(rules[0])

    def test_hitl_custom_rule_high_amount(self, adapter):
        rules = adapter.get_hitl_custom_rules()
        rule_fn = rules[0]
        from core.ontology.metadata import ConfirmationLevel
        # High amount adjustment should return HIGH
        result = rule_fn("adjust_bill", {"adjustment_amount": 1500})
        assert result == ConfirmationLevel.HIGH

    def test_hitl_custom_rule_low_amount(self, adapter):
        rules = adapter.get_hitl_custom_rules()
        rule_fn = rules[0]
        # Low amount should return None
        result = rule_fn("adjust_bill", {"adjustment_amount": 100})
        assert result is None

    def test_hitl_custom_rule_wrong_action(self, adapter):
        rules = adapter.get_hitl_custom_rules()
        rule_fn = rules[0]
        # Wrong action type should return None
        result = rule_fn("create_task", {"adjustment_amount": 5000})
        assert result is None

    def test_hitl_custom_rule_invalid_amount(self, adapter):
        rules = adapter.get_hitl_custom_rules()
        rule_fn = rules[0]
        # Invalid amount should return None
        result = rule_fn("adjust_bill", {"adjustment_amount": "not_a_number"})
        assert result is None


class TestGetContextSummary:
    """Test get_context_summary()."""

    def test_with_room_summary(self, adapter):
        ctx = {"room_summary": {"total": 40, "vacant_clean": 10, "occupied": 25}}
        lines = adapter.get_context_summary(None, ctx)
        assert len(lines) >= 1
        assert "40" in lines[0]

    def test_with_room_types(self, adapter):
        ctx = {
            "room_types": [
                {"name": "标间", "base_price": "288"},
                {"name": "大床房", "base_price": "328"},
            ]
        }
        lines = adapter.get_context_summary(None, ctx)
        assert any("标间" in l for l in lines)

    def test_empty_context(self, adapter):
        lines = adapter.get_context_summary(None, {})
        assert lines == []

    def test_room_types_not_list(self, adapter):
        ctx = {"room_types": "not a list"}
        lines = adapter.get_context_summary(None, ctx)
        assert lines == []


class TestParseRelativeDate:
    """Test _parse_relative_date static method."""

    def test_today(self):
        assert HotelDomainAdapter._parse_relative_date("今天") == date.today()

    def test_today_variants(self):
        assert HotelDomainAdapter._parse_relative_date("今日") == date.today()
        assert HotelDomainAdapter._parse_relative_date("今日内") == date.today()

    def test_tomorrow(self):
        expected = date.today() + timedelta(days=1)
        assert HotelDomainAdapter._parse_relative_date("明天") == expected
        assert HotelDomainAdapter._parse_relative_date("明日") == expected
        assert HotelDomainAdapter._parse_relative_date("明") == expected

    def test_day_after_tomorrow(self):
        expected = date.today() + timedelta(days=2)
        assert HotelDomainAdapter._parse_relative_date("后天") == expected

    def test_three_days_later(self):
        expected = date.today() + timedelta(days=3)
        assert HotelDomainAdapter._parse_relative_date("大后天") == expected

    def test_iso_format(self):
        result = HotelDomainAdapter._parse_relative_date("2025-06-15")
        assert result == date(2025, 6, 15)

    def test_slash_format(self):
        result = HotelDomainAdapter._parse_relative_date("2025/06/15")
        assert result == date(2025, 6, 15)

    def test_dot_format(self):
        result = HotelDomainAdapter._parse_relative_date("2025.06.15")
        assert result == date(2025, 6, 15)

    def test_date_object_passthrough(self):
        d = date(2025, 3, 1)
        assert HotelDomainAdapter._parse_relative_date(d) == d

    def test_invalid_input_returns_none(self):
        assert HotelDomainAdapter._parse_relative_date("invalid") is None

    def test_non_string_returns_none(self):
        assert HotelDomainAdapter._parse_relative_date(12345) is None

    def test_short_month_day_format(self):
        # m/d format - should pick current or next year
        result = HotelDomainAdapter._parse_relative_date("12/25")
        assert result is not None
        assert result.month == 12
        assert result.day == 25


class TestExecuteAction:
    """Test execute_action delegates to ActionRegistry."""

    def test_execute_action_value_error(self, adapter):
        with patch("app.services.actions.get_action_registry") as mock_get:
            mock_reg = Mock()
            mock_reg.dispatch.side_effect = ValueError("bad param")
            mock_get.return_value = mock_reg

            result = adapter.execute_action("test_action", {}, {})
            assert result["success"] is False
            assert "bad param" in result["error"]

    def test_execute_action_generic_error(self, adapter):
        with patch("app.services.actions.get_action_registry") as mock_get:
            mock_reg = Mock()
            mock_reg.dispatch.side_effect = RuntimeError("unexpected")
            mock_get.return_value = mock_reg

            result = adapter.execute_action("test_action", {}, {})
            assert result["success"] is False
            assert "Action execution failed" in result["error"]

    def test_execute_action_success(self, adapter):
        with patch("app.services.actions.get_action_registry") as mock_get:
            mock_reg = Mock()
            mock_reg.dispatch.return_value = {"success": True}
            mock_get.return_value = mock_reg

            result = adapter.execute_action("test_action", {}, {})
            assert result["success"] is True


class TestServiceProperties:
    """Test lazy service initialization."""

    def test_services_are_none_without_db(self, adapter):
        assert adapter.room_service is None
        assert adapter.reservation_service is None
        assert adapter.checkin_service is None
        assert adapter.task_service is None
        assert adapter.param_parser is None
        assert adapter.report_service is None

    def test_ensure_services_no_db(self, adapter):
        """_ensure_services should return early if no db."""
        adapter._ensure_services()
        assert adapter._room_service is None
