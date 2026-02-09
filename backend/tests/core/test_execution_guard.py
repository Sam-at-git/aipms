"""
Tests for SPEC-12: OAG Execution Guard in ActionRegistry.dispatch()
"""
import pytest
from pydantic import BaseModel, Field
from core.ai.actions import ActionRegistry
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import (
    StateMachine, StateTransition,
    ConstraintMetadata, ConstraintType, ConstraintSeverity,
)
from core.ontology.state_machine_executor import StateMachineExecutor
from core.reasoning.constraint_engine import ConstraintEngine


class CheckinParams(BaseModel):
    room_id: int = Field(..., description="Room ID")
    guest_name: str = Field(default="", description="Guest name")


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def guarded_registry(clean_registry):
    """Set up registry with state machine and constraints"""
    # Room state machine
    clean_registry.register_state_machine(StateMachine(
        entity="Room",
        states=["VACANT_CLEAN", "OCCUPIED", "VACANT_DIRTY"],
        initial_state="VACANT_CLEAN",
        transitions=[
            StateTransition(from_state="VACANT_CLEAN", to_state="OCCUPIED", trigger="checkin"),
            StateTransition(from_state="OCCUPIED", to_state="VACANT_DIRTY", trigger="checkout"),
        ]
    ))
    # Constraint: room must be vacant
    clean_registry.register_constraint(ConstraintMetadata(
        id="room_vacant",
        name="Room must be vacant",
        description="Room must be VACANT_CLEAN",
        constraint_type=ConstraintType.STATE,
        severity=ConstraintSeverity.ERROR,
        entity="Room",
        action="test_checkin",
        condition_text="state.status == 'VACANT_CLEAN'",
        condition_code="state.status == 'VACANT_CLEAN'",
        error_message="Room not vacant",
        suggestion_message="Choose a vacant room",
    ))

    sm_executor = StateMachineExecutor(clean_registry)
    constraint_engine = ConstraintEngine(clean_registry)

    action_registry = ActionRegistry(
        vector_store=None,
        ontology_registry=clean_registry,
        state_machine_executor=sm_executor,
        constraint_engine=constraint_engine,
    )

    @action_registry.register(
        name="test_checkin",
        entity="Room",
        description="Test check-in",
        category="mutation",
        requires_confirmation=False,
    )
    def handle_checkin(params: CheckinParams, **ctx):
        return {"success": True, "room_id": params.room_id}

    return action_registry


class TestGuardPassthrough:
    """Guards pass when no state/constraint context provided"""

    def test_dispatch_without_guards(self, guarded_registry):
        result = guarded_registry.dispatch(
            "test_checkin",
            {"room_id": 1, "guest_name": "Test"},
            {},
        )
        assert result["success"] is True

    def test_dispatch_with_valid_state(self, guarded_registry):
        result = guarded_registry.dispatch(
            "test_checkin",
            {"room_id": 1},
            {"current_state": "VACANT_CLEAN", "target_state": "OCCUPIED"},
        )
        assert result["success"] is True


class TestStateMachineGuard:
    """Guard 2: State machine validation"""

    def test_invalid_state_transition_blocked(self, guarded_registry):
        result = guarded_registry.dispatch(
            "test_checkin",
            {"room_id": 1},
            {"current_state": "VACANT_DIRTY", "target_state": "OCCUPIED"},
        )
        assert result["success"] is False
        assert result["error_code"] == "state_error"
        assert "valid_alternatives" in result


class TestConstraintGuard:
    """Guard 3: Constraint validation"""

    def test_constraint_violation_blocked(self, guarded_registry):
        result = guarded_registry.dispatch(
            "test_checkin",
            {"room_id": 1},
            {"entity_state": {"status": "OCCUPIED"}, "user_context": {}},
        )
        assert result["success"] is False
        assert result["error_code"] == "constraint_violation"
        assert "suggestions" in result

    def test_constraint_passes_with_valid_state(self, guarded_registry):
        result = guarded_registry.dispatch(
            "test_checkin",
            {"room_id": 1},
            {"entity_state": {"status": "VACANT_CLEAN"}, "user_context": {}},
        )
        assert result["success"] is True


class TestNoGuardsConfigured:
    """When no guards configured, dispatch works normally"""

    def test_dispatch_without_any_guards(self, clean_registry):
        reg = ActionRegistry(vector_store=None)

        @reg.register(
            name="simple_action",
            entity="Test",
            description="Simple",
            category="mutation",
            requires_confirmation=False,
        )
        def handle(params: CheckinParams, **ctx):
            return {"done": True}

        result = reg.dispatch("simple_action", {"room_id": 1}, {})
        assert result["done"] is True
