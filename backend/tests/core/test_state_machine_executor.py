"""
tests/core/test_state_machine_executor.py

Tests for StateMachineExecutor - validates state transitions
against OntologyRegistry StateMachine definitions.
"""
import pytest

from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import StateMachine, StateTransition
from core.ontology.state_machine_executor import StateMachineExecutor, TransitionResult


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before and after each test."""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def room_state_machine():
    """Create a Room state machine with 4 states."""
    return StateMachine(
        entity="Room",
        states=["VACANT_CLEAN", "OCCUPIED", "VACANT_DIRTY", "OUT_OF_ORDER"],
        initial_state="VACANT_CLEAN",
        transitions=[
            StateTransition(
                from_state="VACANT_CLEAN",
                to_state="OCCUPIED",
                trigger="check_in",
                side_effects=["notify_housekeeping"],
            ),
            StateTransition(
                from_state="OCCUPIED",
                to_state="VACANT_DIRTY",
                trigger="check_out",
                side_effects=["create_cleaning_task"],
            ),
            StateTransition(
                from_state="VACANT_DIRTY",
                to_state="VACANT_CLEAN",
                trigger="clean_room",
                side_effects=["update_room_status"],
            ),
            StateTransition(
                from_state="VACANT_CLEAN",
                to_state="OUT_OF_ORDER",
                trigger="mark_out_of_order",
            ),
            StateTransition(
                from_state="VACANT_DIRTY",
                to_state="OUT_OF_ORDER",
                trigger="mark_out_of_order",
            ),
            StateTransition(
                from_state="OUT_OF_ORDER",
                to_state="VACANT_DIRTY",
                trigger="mark_available",
                side_effects=["create_cleaning_task"],
            ),
        ],
    )


@pytest.fixture
def registry_with_room(clean_registry, room_state_machine):
    """Register the Room state machine in the registry."""
    clean_registry.register_state_machine(room_state_machine)
    return clean_registry


class TestTransitionResult:
    """Tests for the TransitionResult dataclass."""

    def test_transition_result_defaults(self):
        """TransitionResult has sensible defaults."""
        result = TransitionResult(allowed=True, reason="ok")
        assert result.allowed is True
        assert result.reason == "ok"
        assert result.side_effects == []
        assert result.valid_alternatives == []

    def test_transition_result_with_all_fields(self):
        """TransitionResult can be constructed with all fields."""
        result = TransitionResult(
            allowed=False,
            reason="not allowed",
            side_effects=["effect1"],
            valid_alternatives=["STATE_A", "STATE_B"],
        )
        assert result.allowed is False
        assert result.reason == "not allowed"
        assert result.side_effects == ["effect1"]
        assert result.valid_alternatives == ["STATE_A", "STATE_B"]


class TestStateMachineExecutorInit:
    """Tests for StateMachineExecutor initialization."""

    def test_default_registry(self):
        """Executor uses the singleton OntologyRegistry by default."""
        executor = StateMachineExecutor()
        assert executor._registry is not None

    def test_custom_registry(self, clean_registry):
        """Executor can accept a custom registry."""
        executor = StateMachineExecutor(registry=clean_registry)
        assert executor._registry is clean_registry


class TestValidTransitions:
    """Tests for valid state transitions."""

    def test_valid_transition_vacant_clean_to_occupied(self, registry_with_room):
        """VACANT_CLEAN -> OCCUPIED is a valid transition."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_CLEAN", "OCCUPIED")

        assert result.allowed is True
        assert "VACANT_CLEAN" in result.reason
        assert "OCCUPIED" in result.reason
        assert "check_in" in result.reason
        assert result.side_effects == ["notify_housekeeping"]
        assert result.valid_alternatives == []

    def test_valid_transition_occupied_to_vacant_dirty(self, registry_with_room):
        """OCCUPIED -> VACANT_DIRTY is a valid transition."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "OCCUPIED", "VACANT_DIRTY")

        assert result.allowed is True
        assert result.side_effects == ["create_cleaning_task"]

    def test_valid_transition_vacant_dirty_to_vacant_clean(self, registry_with_room):
        """VACANT_DIRTY -> VACANT_CLEAN is a valid transition."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_DIRTY", "VACANT_CLEAN")

        assert result.allowed is True
        assert result.side_effects == ["update_room_status"]

    def test_valid_transition_to_out_of_order(self, registry_with_room):
        """VACANT_CLEAN -> OUT_OF_ORDER is a valid transition."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_CLEAN", "OUT_OF_ORDER")

        assert result.allowed is True
        assert result.side_effects == []

    def test_valid_transition_out_of_order_to_vacant_dirty(self, registry_with_room):
        """OUT_OF_ORDER -> VACANT_DIRTY is a valid transition."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "OUT_OF_ORDER", "VACANT_DIRTY")

        assert result.allowed is True
        assert result.side_effects == ["create_cleaning_task"]


class TestInvalidTransitions:
    """Tests for invalid state transitions."""

    def test_invalid_transition_vacant_dirty_to_occupied(self, registry_with_room):
        """VACANT_DIRTY -> OCCUPIED is not allowed (must clean first)."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_DIRTY", "OCCUPIED")

        assert result.allowed is False
        assert "not allowed" in result.reason
        # valid_alternatives should list reachable states from VACANT_DIRTY
        assert "VACANT_CLEAN" in result.valid_alternatives
        assert "OUT_OF_ORDER" in result.valid_alternatives
        assert "OCCUPIED" not in result.valid_alternatives

    def test_invalid_transition_occupied_to_vacant_clean(self, registry_with_room):
        """OCCUPIED -> VACANT_CLEAN is not allowed (must go through VACANT_DIRTY)."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "OCCUPIED", "VACANT_CLEAN")

        assert result.allowed is False
        assert "VACANT_DIRTY" in result.valid_alternatives

    def test_invalid_transition_occupied_to_out_of_order(self, registry_with_room):
        """OCCUPIED -> OUT_OF_ORDER has no direct transition defined."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "OCCUPIED", "OUT_OF_ORDER")

        assert result.allowed is False
        assert "VACANT_DIRTY" in result.valid_alternatives

    def test_invalid_same_state_transition(self, registry_with_room):
        """OCCUPIED -> OCCUPIED is not defined and should be invalid."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "OCCUPIED", "OCCUPIED")

        assert result.allowed is False


class TestNonexistentEntityType:
    """Tests for entity types without a registered state machine."""

    def test_nonexistent_entity_type(self, clean_registry):
        """A nonexistent entity type returns not allowed."""
        executor = StateMachineExecutor(registry=clean_registry)
        result = executor.validate_transition("NonExistent", "A", "B")

        assert result.allowed is False
        assert "No state machine" in result.reason
        assert "NonExistent" in result.reason
        assert result.side_effects == []
        assert result.valid_alternatives == []

    def test_entity_without_state_machine(self, clean_registry):
        """An entity with no state machine registered returns not allowed."""
        executor = StateMachineExecutor(registry=clean_registry)
        result = executor.validate_transition("Guest", "active", "inactive")

        assert result.allowed is False
        assert "No state machine" in result.reason


class TestUnknownStates:
    """Tests for unknown state values."""

    def test_unknown_current_state(self, registry_with_room):
        """An unknown current state returns not allowed."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "NONEXISTENT_STATE", "OCCUPIED")

        assert result.allowed is False
        assert "Unknown state" in result.reason
        assert "NONEXISTENT_STATE" in result.reason

    def test_unknown_target_state(self, registry_with_room):
        """An unknown target state returns not allowed with valid alternatives."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_CLEAN", "NONEXISTENT_STATE")

        assert result.allowed is False
        assert "Unknown state" in result.reason
        assert "NONEXISTENT_STATE" in result.reason
        # Should still provide valid alternatives from current state
        assert "OCCUPIED" in result.valid_alternatives
        assert "OUT_OF_ORDER" in result.valid_alternatives


class TestRoleBasedPermissions:
    """Tests for role-based permission checking."""

    def test_allowed_role(self, registry_with_room):
        """User with an allowed role can perform the transition."""
        registry_with_room.register_permission("check_in", {"manager", "receptionist"})
        executor = StateMachineExecutor(registry=registry_with_room)

        result = executor.validate_transition(
            "Room", "VACANT_CLEAN", "OCCUPIED", user_role="receptionist"
        )
        assert result.allowed is True

    def test_denied_role(self, registry_with_room):
        """User with a non-allowed role is denied the transition."""
        registry_with_room.register_permission("check_in", {"manager", "receptionist"})
        executor = StateMachineExecutor(registry=registry_with_room)

        result = executor.validate_transition(
            "Room", "VACANT_CLEAN", "OCCUPIED", user_role="cleaner"
        )
        assert result.allowed is False
        assert "cleaner" in result.reason
        assert "not permitted" in result.reason

    def test_no_permission_registered_allows_all(self, registry_with_room):
        """When no permission is registered for the trigger, any role is allowed."""
        executor = StateMachineExecutor(registry=registry_with_room)

        result = executor.validate_transition(
            "Room", "VACANT_CLEAN", "OCCUPIED", user_role="anyone"
        )
        assert result.allowed is True

    def test_no_role_provided_skips_permission_check(self, registry_with_room):
        """When user_role is None, permission check is skipped."""
        registry_with_room.register_permission("check_in", {"manager"})
        executor = StateMachineExecutor(registry=registry_with_room)

        result = executor.validate_transition("Room", "VACANT_CLEAN", "OCCUPIED")
        assert result.allowed is True

    def test_denied_role_provides_valid_alternatives(self, registry_with_room):
        """Denied role result still includes valid alternatives."""
        registry_with_room.register_permission("check_in", {"manager"})
        executor = StateMachineExecutor(registry=registry_with_room)

        result = executor.validate_transition(
            "Room", "VACANT_CLEAN", "OCCUPIED", user_role="cleaner"
        )
        assert result.allowed is False
        assert "OCCUPIED" in result.valid_alternatives or "OUT_OF_ORDER" in result.valid_alternatives


class TestSideEffects:
    """Tests for side effects in transition results."""

    def test_transition_with_multiple_side_effects(self, clean_registry):
        """Transition with multiple side effects returns all of them."""
        sm = StateMachine(
            entity="Task",
            states=["PENDING", "COMPLETED"],
            initial_state="PENDING",
            transitions=[
                StateTransition(
                    from_state="PENDING",
                    to_state="COMPLETED",
                    trigger="complete_task",
                    side_effects=["send_notification", "update_room_status", "log_event"],
                ),
            ],
        )
        clean_registry.register_state_machine(sm)
        executor = StateMachineExecutor(registry=clean_registry)

        result = executor.validate_transition("Task", "PENDING", "COMPLETED")
        assert result.allowed is True
        assert result.side_effects == ["send_notification", "update_room_status", "log_event"]

    def test_transition_without_side_effects(self, registry_with_room):
        """Transition without side effects returns empty list."""
        executor = StateMachineExecutor(registry=registry_with_room)
        result = executor.validate_transition("Room", "VACANT_CLEAN", "OUT_OF_ORDER")

        assert result.allowed is True
        assert result.side_effects == []


class TestMultipleStateMachines:
    """Tests with multiple entity types registered."""

    def test_independent_state_machines(self, clean_registry):
        """Different entity types have independent state machines."""
        room_sm = StateMachine(
            entity="Room",
            states=["VACANT_CLEAN", "OCCUPIED"],
            initial_state="VACANT_CLEAN",
            transitions=[
                StateTransition(
                    from_state="VACANT_CLEAN",
                    to_state="OCCUPIED",
                    trigger="check_in",
                ),
            ],
        )
        task_sm = StateMachine(
            entity="Task",
            states=["PENDING", "IN_PROGRESS", "COMPLETED"],
            initial_state="PENDING",
            transitions=[
                StateTransition(
                    from_state="PENDING",
                    to_state="IN_PROGRESS",
                    trigger="start_task",
                ),
                StateTransition(
                    from_state="IN_PROGRESS",
                    to_state="COMPLETED",
                    trigger="complete_task",
                ),
            ],
        )
        clean_registry.register_state_machine(room_sm)
        clean_registry.register_state_machine(task_sm)

        executor = StateMachineExecutor(registry=clean_registry)

        # Room transitions
        room_result = executor.validate_transition("Room", "VACANT_CLEAN", "OCCUPIED")
        assert room_result.allowed is True

        # Task transitions
        task_result = executor.validate_transition("Task", "PENDING", "IN_PROGRESS")
        assert task_result.allowed is True

        # Cross-entity states don't interfere
        cross_result = executor.validate_transition("Room", "PENDING", "IN_PROGRESS")
        assert cross_result.allowed is False
