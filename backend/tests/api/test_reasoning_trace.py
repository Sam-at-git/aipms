"""
tests/api/test_reasoning_trace.py

SPEC-6: Tests for reasoning trace in AI responses and new ontology APIs.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestReasoningTraceSchema:
    """Test AIResponse and AIAction schema changes."""

    def test_ai_response_has_reasoning_trace(self):
        from app.models.schemas import AIResponse
        resp = AIResponse(message="test", reasoning_trace={"intent_source": "llm"})
        assert resp.reasoning_trace == {"intent_source": "llm"}

    def test_ai_response_reasoning_trace_optional(self):
        from app.models.schemas import AIResponse
        resp = AIResponse(message="test")
        assert resp.reasoning_trace is None

    def test_ai_action_has_side_effects(self):
        from app.models.schemas import AIAction
        action = AIAction(
            action_type="checkout",
            entity_type="StayRecord",
            description="退房",
            side_effects=["Auto-create cleaning task", "Generate invoice"],
        )
        assert len(action.side_effects) == 2

    def test_ai_action_side_effects_optional(self):
        from app.models.schemas import AIAction
        action = AIAction(
            action_type="checkout",
            entity_type="StayRecord",
            description="退房",
        )
        assert action.side_effects is None


class TestReasoningTraceInService:
    """Test reasoning trace generation in AIService."""

    def test_build_reasoning_trace_basic(self):
        """Test _build_reasoning_trace helper."""
        from app.services.ai_service import AIService
        # AIService needs db, but _build_reasoning_trace is a simple dict builder
        # Use a minimal mock
        service = MagicMock(spec=AIService)
        service._build_reasoning_trace = AIService._build_reasoning_trace.__get__(service)

        trace = service._build_reasoning_trace(
            intent_source="llm",
            action_type="checkout",
        )
        assert trace["intent_source"] == "llm"
        assert trace["action_type"] == "checkout"

    def test_build_reasoning_trace_with_constraints(self):
        from app.services.ai_service import AIService
        service = MagicMock(spec=AIService)
        service._build_reasoning_trace = AIService._build_reasoning_trace.__get__(service)

        trace = service._build_reasoning_trace(
            intent_source="llm",
            constraints_checked=["room_vacant", "bill_settled"],
            guard_summary="all passed",
        )
        assert trace["constraints_checked"] == ["room_vacant", "bill_settled"]
        assert trace["guard_summary"] == "all passed"

    def test_build_reasoning_trace_omits_empty(self):
        from app.services.ai_service import AIService
        service = MagicMock(spec=AIService)
        service._build_reasoning_trace = AIService._build_reasoning_trace.__get__(service)

        trace = service._build_reasoning_trace(intent_source="rule_based")
        assert "action_type" not in trace
        assert "constraints_checked" not in trace
        assert trace["intent_source"] == "rule_based"


class TestStateTransitionsAPI:
    """Test state transitions endpoint."""

    def test_get_state_transitions_no_machine(self, client, manager_token):
        """Entity without state machine returns empty transitions."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/NonExistentEntity",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transitions"] == []
        assert "error" in data

    def test_get_state_transitions_room(self, client, manager_token):
        """Room entity should have state transitions."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Room",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "Room"
        # Room has a state machine registered by HotelDomainAdapter
        assert isinstance(data["transitions"], list)

    def test_get_state_transitions_with_filter(self, client, manager_token):
        """Filter transitions by current_state."""
        resp = client.get(
            "/ontology/dynamic/state-transitions/Room?current_state=occupied",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_state"] == "occupied"
        # All returned transitions should have from_state == occupied
        for t in data["transitions"]:
            assert t["from_state"].lower() == "occupied"

    def test_get_state_transitions_requires_auth(self, client):
        """Endpoint requires authentication."""
        resp = client.get("/ontology/dynamic/state-transitions/Room")
        assert resp.status_code in [401, 403]


class TestConstraintValidationAPI:
    """Test constraint validation endpoint."""

    def test_validate_constraints_basic(self, client, manager_token):
        """Basic constraint validation returns structure."""
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json={
                "entity_type": "Room",
                "action_type": "checkin",
                "params": {},
                "entity_state": {},
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "Room"
        assert data["action_type"] == "checkin"
        assert "constraints" in data
        assert "violations" in data
        assert "warnings" in data

    def test_validate_constraints_returns_registered(self, client, manager_token):
        """Should return constraints registered by HotelDomainAdapter."""
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json={
                "entity_type": "Room",
                "action_type": "checkin",
                "params": {},
                "entity_state": {"status": "OCCUPIED"},
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Room checkin has "room_must_be_vacant_for_checkin" constraint
        constraint_ids = [c["id"] for c in data["constraints"]]
        assert "room_must_be_vacant_for_checkin" in constraint_ids

    def test_validate_constraints_detects_violation(self, client, manager_token):
        """Occupied room should violate checkin constraint."""
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json={
                "entity_type": "Room",
                "action_type": "checkin",
                "params": {},
                "entity_state": {"status": "OCCUPIED"},
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["violations"]) > 0

    def test_validate_constraints_passes_valid_state(self, client, manager_token):
        """Vacant clean room should pass checkin constraint."""
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json={
                "entity_type": "Room",
                "action_type": "checkin",
                "params": {},
                "entity_state": {"status": "VACANT_CLEAN"},
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["violations"]) == 0

    def test_validate_constraints_requires_auth(self, client):
        """Endpoint requires authentication."""
        resp = client.post(
            "/ontology/dynamic/constraints/validate",
            json={"entity_type": "Room", "action_type": "checkin"},
        )
        assert resp.status_code in [401, 403]
