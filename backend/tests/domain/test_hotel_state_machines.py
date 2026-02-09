"""
Tests for SPEC-08: HotelDomainAdapter state machine + enum registration
"""
import pytest
from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter


@pytest.fixture
def hotel_registry():
    reg = OntologyRegistry()
    reg.clear()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(reg)
    yield reg
    reg.clear()


class TestRoomStateMachine:
    def test_room_state_machine_exists(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Room")
        assert sm is not None
        assert sm.entity == "Room"

    def test_room_states(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Room")
        assert "vacant_clean" in sm.states
        assert "occupied" in sm.states
        assert "vacant_dirty" in sm.states
        assert "out_of_order" in sm.states

    def test_room_valid_transition_checkin(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Room")
        assert sm.is_valid_transition("vacant_clean", "occupied")

    def test_room_invalid_transition(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Room")
        assert not sm.is_valid_transition("vacant_dirty", "occupied")


class TestReservationStateMachine:
    def test_reservation_sm_exists(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Reservation")
        assert sm is not None

    def test_reservation_transitions(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Reservation")
        assert sm.is_valid_transition("confirmed", "checked_in")
        assert sm.is_valid_transition("confirmed", "cancelled")
        assert sm.is_valid_transition("confirmed", "no_show")
        assert not sm.is_valid_transition("cancelled", "confirmed")

    def test_reservation_final_states(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Reservation")
        assert "completed" in sm.final_states
        assert "cancelled" in sm.final_states


class TestStayRecordStateMachine:
    def test_stay_record_sm(self, hotel_registry):
        sm = hotel_registry.get_state_machine("StayRecord")
        assert sm is not None
        assert sm.is_valid_transition("active", "checked_out")
        assert not sm.is_valid_transition("checked_out", "active")


class TestTaskStateMachine:
    def test_task_sm(self, hotel_registry):
        sm = hotel_registry.get_state_machine("Task")
        assert sm is not None
        assert sm.is_valid_transition("pending", "in_progress")
        assert sm.is_valid_transition("pending", "assigned")
        assert sm.is_valid_transition("assigned", "in_progress")
        assert sm.is_valid_transition("assigned", "completed")
        assert sm.is_valid_transition("in_progress", "completed")
        assert not sm.is_valid_transition("completed", "pending")


class TestEnumValues:
    def test_room_status_enum(self, hotel_registry):
        room = hotel_registry.get_entity("Room")
        status = room.properties.get("status")
        assert status is not None
        assert status.enum_values is not None
        assert "OCCUPIED" in status.enum_values

    def test_task_type_enum(self, hotel_registry):
        task = hotel_registry.get_entity("Task")
        task_type = task.properties.get("task_type")
        assert task_type is not None
        assert task_type.enum_values is not None

    def test_payment_method_enum(self, hotel_registry):
        payment = hotel_registry.get_entity("Payment")
        method = payment.properties.get("method")
        assert method is not None
        assert method.enum_values is not None
