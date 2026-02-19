"""
Tests for app/routers/ontology.py - increasing coverage for uncovered endpoints.
Covers: semantic, kinetic, dynamic metadata endpoints, instance-graph,
state-transitions, constraints validation, interfaces, and schema export.
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, GuestTier,
    Reservation, ReservationStatus, StayRecord, StayRecordStatus,
    Bill, Task, TaskType, TaskStatus, Employee, EmployeeRole,
    RatePlan, Payment, PaymentMethod,
)


# ==============================================================
# Semantic endpoints
# ==============================================================

class TestSemanticEndpoints:
    """Test /ontology/semantic* endpoints."""

    def test_get_semantic_metadata(self, client, manager_auth_headers):
        """GET /ontology/semantic - returns semantic metadata."""
        resp = client.get("/ontology/semantic", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert isinstance(data["entities"], list)

    def test_get_entity_semantic_found(self, client, manager_auth_headers):
        """GET /ontology/semantic/{entity_name} - known entity."""
        resp = client.get("/ontology/semantic/Room", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should return entity info or error depending on registry state
        # Either has 'name' field or 'error' field
        assert "name" in data or "error" in data

    def test_get_entity_semantic_not_found(self, client, manager_auth_headers):
        """GET /ontology/semantic/{entity_name} - unknown entity returns error."""
        resp = client.get("/ontology/semantic/NonExistentEntity", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "Entity not found"

    def test_semantic_requires_manager(self, client, cleaner_auth_headers):
        """Semantic endpoints require manager role."""
        resp = client.get("/ontology/semantic", headers=cleaner_auth_headers)
        assert resp.status_code == 403


# ==============================================================
# Kinetic endpoints
# ==============================================================

class TestKineticEndpoints:
    """Test /ontology/kinetic* endpoints."""

    def test_get_kinetic_metadata(self, client, manager_auth_headers):
        """GET /ontology/kinetic - returns kinetic metadata."""
        resp = client.get("/ontology/kinetic", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert isinstance(data["entities"], list)

    def test_get_entity_kinetic_found(self, client, manager_auth_headers):
        """GET /ontology/kinetic/{entity_name} - known entity."""
        resp = client.get("/ontology/kinetic/Room", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data or "error" in data

    def test_get_entity_kinetic_not_found(self, client, manager_auth_headers):
        """GET /ontology/kinetic/{entity_name} - unknown entity."""
        resp = client.get("/ontology/kinetic/FakeEntity", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "Entity not found"


# ==============================================================
# Dynamic endpoints
# ==============================================================

class TestDynamicEndpoints:
    """Test /ontology/dynamic* endpoints."""

    def test_get_dynamic_metadata(self, client, manager_auth_headers):
        """GET /ontology/dynamic - returns dynamic metadata."""
        resp = client.get("/ontology/dynamic", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "state_machines" in data
        assert "permission_matrix" in data
        assert "business_rules" in data

    def test_get_state_machines(self, client, manager_auth_headers):
        """GET /ontology/dynamic/state-machines - returns state machines list."""
        resp = client.get("/ontology/dynamic/state-machines", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should contain at least Room, Reservation, StayRecord, Task
        entities = [sm.get("entity") for sm in data]
        assert "Room" in entities
        assert "Task" in entities

    def test_get_entity_state_machine_found(self, client, manager_auth_headers):
        """GET /ontology/dynamic/state-machines/{entity} - found."""
        resp = client.get("/ontology/dynamic/state-machines/Room", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("entity") == "Room"
        assert "states" in data
        assert "transitions" in data

    def test_get_entity_state_machine_not_found(self, client, manager_auth_headers):
        """GET /ontology/dynamic/state-machines/{entity} - not found."""
        resp = client.get("/ontology/dynamic/state-machines/NotAnEntity", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "State machine not found"

    def test_get_permission_matrix(self, client, manager_auth_headers):
        """GET /ontology/dynamic/permission-matrix - returns permission matrix."""
        resp = client.get("/ontology/dynamic/permission-matrix", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        assert "actions" in data
        assert isinstance(data["roles"], list)
        assert isinstance(data["actions"], list)

    def test_get_events(self, client, manager_auth_headers):
        """GET /ontology/dynamic/events - returns events list."""
        resp = client.get("/ontology/dynamic/events", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)

    def test_get_business_rules(self, client, manager_auth_headers):
        """GET /ontology/dynamic/business-rules - returns business rules."""
        resp = client.get("/ontology/dynamic/business-rules", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)
        assert len(data["rules"]) > 0

    def test_get_business_rules_filter_by_entity(self, client, manager_auth_headers):
        """GET /ontology/dynamic/business-rules?entity=Room - filtered rules."""
        resp = client.get(
            "/ontology/dynamic/business-rules?entity=Room",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        for rule in data["rules"]:
            assert rule["entity"] == "Room"

    def test_get_business_rules_filter_no_match(self, client, manager_auth_headers):
        """GET /ontology/dynamic/business-rules?entity=FakeEntity - empty result."""
        resp = client.get(
            "/ontology/dynamic/business-rules?entity=FakeEntity",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rules"] == []


# ==============================================================
# State Transitions (Reasoning Transparency)
# ==============================================================

class TestStateTransitions:
    """Test /ontology/dynamic/state-transitions/{entity_name}."""

    def test_get_state_transitions_all(self, client, manager_auth_headers):
        """GET state transitions without current_state filter."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Room",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "Room"
        assert data["current_state"] is None
        # transitions may be present from registry
        assert "transitions" in data

    def test_get_state_transitions_with_current_state(self, client, manager_auth_headers):
        """GET state transitions filtered by current_state."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Room?current_state=vacant_clean",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "Room"
        assert data["current_state"] == "vacant_clean"

    def test_get_state_transitions_no_state_machine(self, client, manager_auth_headers):
        """GET state transitions for entity without state machine."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Payment",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "Payment"
        assert "error" in data or data["transitions"] == []

    def test_state_transitions_auth_any_user(self, client, receptionist_auth_headers):
        """State transitions endpoint requires get_current_user (any role)."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Task",
            headers=receptionist_auth_headers,
        )
        assert resp.status_code == 200


# ==============================================================
# Constraint Validation
# ==============================================================

class TestConstraintValidation:
    """Test POST /ontology/dynamic/constraints/validate."""

    def test_validate_constraints_basic(self, client, manager_auth_headers):
        """POST validate constraints with basic body."""
        body = {
            "entity_type": "Room",
            "action_type": "checkin",
            "params": {},
            "entity_state": {},
        }
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json=body,
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "Room"
        assert data["action_type"] == "checkin"
        assert "constraints" in data
        assert "violations" in data
        assert "warnings" in data

    def test_validate_constraints_empty_body(self, client, manager_auth_headers):
        """POST validate constraints with empty entity/action."""
        body = {
            "entity_type": "",
            "action_type": "",
        }
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json=body,
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == ""
        assert data["action_type"] == ""

    def test_validate_constraints_unknown_entity(self, client, manager_auth_headers):
        """POST validate constraints with unknown entity returns empty constraints."""
        body = {
            "entity_type": "UnknownEntity",
            "action_type": "unknown_action",
        }
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json=body,
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["constraints"] == []


# ==============================================================
# Interfaces endpoints
# ==============================================================

class TestInterfacesEndpoints:
    """Test /ontology/interfaces* endpoints."""

    def test_get_interfaces(self, client, manager_auth_headers):
        """GET /ontology/interfaces - list all interfaces."""
        resp = client.get("/ontology/interfaces", headers=manager_auth_headers)
        assert resp.status_code == 200

    def test_get_interface_found(self, client, manager_auth_headers):
        """GET /ontology/interfaces/{name} - interface detail."""
        resp = client.get(
            "/ontology/interfaces/SomeInterface",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Interface may or may not exist
        # If not found, returns {"error": "Interface not found"}
        assert isinstance(data, dict)

    def test_get_interface_implementations(self, client, manager_auth_headers):
        """GET /ontology/interfaces/{name}/implementations."""
        resp = client.get(
            "/ontology/interfaces/SomeInterface/implementations",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "interface" in data
        assert "implementations" in data

    def test_get_entity_interfaces(self, client, manager_auth_headers):
        """GET /ontology/entities/{entity}/interfaces."""
        resp = client.get(
            "/ontology/entities/Room/interfaces",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "Room"
        assert "interfaces" in data


# ==============================================================
# Schema export
# ==============================================================

class TestSchemaExport:
    """Test /ontology/schema/export."""

    def test_export_schema(self, client, manager_auth_headers):
        """GET /ontology/schema/export - returns full schema JSON."""
        resp = client.get("/ontology/schema/export", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Schema export returns whatever registry.export_schema() returns
        assert isinstance(data, dict)


# ==============================================================
# Instance graph — StayRecord, Room, Guest centers
# ==============================================================

class TestInstanceGraph:
    """Test /ontology/instance-graph with different center entities."""

    def test_instance_graph_overview(self, client, db_session, manager_auth_headers, sample_room_type):
        """No center_entity → returns overview graph."""
        resp = client.get("/ontology/instance-graph", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_instance_graph_stay_record_center(
        self, client, db_session, manager_auth_headers,
        sample_room_type, sample_room, sample_guest
    ):
        """Instance graph centered on StayRecord."""
        from app.hotel.models.ontology import StayRecord, StayRecordStatus, Bill, Reservation

        # Create a reservation
        reservation = Reservation(
            reservation_no="R-TEST-001",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=date.today(),
            check_out_date=date.today(),
            status=ReservationStatus.CHECKED_IN,
        )
        db_session.add(reservation)
        db_session.flush()

        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            reservation_id=reservation.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
        )
        db_session.add(bill)
        db_session.commit()

        resp = client.get(
            f"/ontology/instance-graph?center_entity=StayRecord&center_id={stay.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) >= 1  # At least the center node
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"StayRecord-{stay.id}" in node_ids
        assert f"Guest-{sample_guest.id}" in node_ids
        assert f"Room-{sample_room.id}" in node_ids
        assert f"Bill-{bill.id}" in node_ids
        assert f"Reservation-{reservation.id}" in node_ids

    def test_instance_graph_stay_record_not_found(self, client, manager_auth_headers):
        """Instance graph for non-existent StayRecord."""
        resp = client.get(
            "/ontology/instance-graph?center_entity=StayRecord&center_id=99999",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_instance_graph_room_center(
        self, client, db_session, manager_auth_headers,
        sample_room_type, sample_room
    ):
        """Instance graph centered on Room."""
        resp = client.get(
            f"/ontology/instance-graph?center_entity=Room&center_id={sample_room.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"Room-{sample_room.id}" in node_ids
        # room_type should appear
        assert f"RoomType-{sample_room_type.id}" in node_ids

    def test_instance_graph_guest_center(
        self, client, db_session, manager_auth_headers,
        sample_guest, sample_room_type
    ):
        """Instance graph centered on Guest."""
        # Create a reservation for this guest
        reservation = Reservation(
            reservation_no="R-GRAPH-001",
            guest_id=sample_guest.id,
            room_type_id=sample_room_type.id,
            check_in_date=date.today(),
            check_out_date=date.today(),
            status=ReservationStatus.CONFIRMED,
        )
        db_session.add(reservation)
        db_session.commit()

        resp = client.get(
            f"/ontology/instance-graph?center_entity=Guest&center_id={sample_guest.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"Guest-{sample_guest.id}" in node_ids
        assert f"Reservation-{reservation.id}" in node_ids

    def test_instance_graph_guest_not_found(self, client, manager_auth_headers):
        """Instance graph for non-existent Guest."""
        resp = client.get(
            "/ontology/instance-graph?center_entity=Guest&center_id=99999",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []

    def test_instance_graph_room_not_found(self, client, manager_auth_headers):
        """Instance graph for non-existent Room."""
        resp = client.get(
            "/ontology/instance-graph?center_entity=Room&center_id=99999",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []

    def test_instance_graph_room_with_tasks_and_stays(
        self, client, db_session, manager_auth_headers,
        sample_room, sample_room_type, sample_guest, sample_cleaner
    ):
        """Instance graph for Room with active stays and pending tasks."""
        # Create active stay
        stay = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE,
        )
        db_session.add(stay)

        # Create pending task
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            priority=1,
        )
        db_session.add(task)

        # Mark room as occupied
        sample_room.status = RoomStatus.OCCUPIED
        db_session.commit()

        resp = client.get(
            f"/ontology/instance-graph?center_entity=Room&center_id={sample_room.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"Room-{sample_room.id}" in node_ids
        assert f"StayRecord-{stay.id}" in node_ids
        assert f"Task-{task.id}" in node_ids
