"""
core/ontology/state_machine_executor.py

State Machine Executor - validates state transitions against OntologyRegistry.

Reads StateMachine definitions from the registry and determines whether a
given transition is allowed, optionally checking role-based permissions
via the registry's permission matrix.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from core.ontology.registry import OntologyRegistry


@dataclass
class TransitionResult:
    """Result of a state transition validation."""
    allowed: bool
    reason: str
    side_effects: List[str] = field(default_factory=list)
    valid_alternatives: List[str] = field(default_factory=list)


class StateMachineExecutor:
    """
    Validates state transitions using StateMachine definitions
    registered in the OntologyRegistry.

    Example:
        >>> executor = StateMachineExecutor()
        >>> result = executor.validate_transition("Room", "VACANT_CLEAN", "OCCUPIED")
        >>> assert result.allowed is True
    """

    def __init__(self, registry: Optional[OntologyRegistry] = None):
        self._registry = registry or OntologyRegistry()

    def validate_transition(
        self,
        entity_type: str,
        current_state: str,
        target_state: str,
        user_role: Optional[str] = None,
    ) -> TransitionResult:
        """
        Validate whether a state transition is allowed.

        Args:
            entity_type: The entity type name (e.g. "Room").
            current_state: The current state of the entity.
            target_state: The desired target state.
            user_role: Optional role of the user attempting the transition.
                       If provided, checks against the permission matrix.

        Returns:
            TransitionResult with allowed flag, reason, side_effects,
            and valid_alternatives (reachable states from current_state).
        """
        state_machine = self._registry.get_state_machine(entity_type)

        if state_machine is None:
            return TransitionResult(
                allowed=False,
                reason=f"No state machine registered for entity type '{entity_type}'",
            )

        # Check if current_state is a known state
        if current_state not in state_machine.states:
            return TransitionResult(
                allowed=False,
                reason=f"Unknown state '{current_state}' for entity type '{entity_type}'",
            )

        # Check if target_state is a known state
        if target_state not in state_machine.states:
            valid_targets = [
                t.to_state for t in state_machine.get_valid_transitions(current_state)
            ]
            return TransitionResult(
                allowed=False,
                reason=f"Unknown state '{target_state}' for entity type '{entity_type}'",
                valid_alternatives=valid_targets,
            )

        # Find the matching transition
        matching_transition = None
        for transition in state_machine.transitions:
            if transition.from_state == current_state and transition.to_state == target_state:
                matching_transition = transition
                break

        if matching_transition is None:
            # Transition not defined - collect valid alternatives
            valid_targets = [
                t.to_state for t in state_machine.get_valid_transitions(current_state)
            ]
            return TransitionResult(
                allowed=False,
                reason=(
                    f"Transition from '{current_state}' to '{target_state}' "
                    f"is not allowed for entity type '{entity_type}'"
                ),
                valid_alternatives=valid_targets,
            )

        # Check role-based permission if user_role is provided
        if user_role is not None:
            trigger = matching_transition.trigger
            permissions = self._registry.get_permissions()
            if trigger in permissions:
                allowed_roles = permissions[trigger]
                if user_role not in allowed_roles:
                    valid_targets = [
                        t.to_state
                        for t in state_machine.get_valid_transitions(current_state)
                    ]
                    return TransitionResult(
                        allowed=False,
                        reason=(
                            f"Role '{user_role}' is not permitted to perform "
                            f"'{trigger}' on entity type '{entity_type}'"
                        ),
                        valid_alternatives=valid_targets,
                    )

        # Transition is allowed
        return TransitionResult(
            allowed=True,
            reason=(
                f"Transition from '{current_state}' to '{target_state}' "
                f"is allowed (trigger: '{matching_transition.trigger}')"
            ),
            side_effects=list(matching_transition.side_effects),
        )
