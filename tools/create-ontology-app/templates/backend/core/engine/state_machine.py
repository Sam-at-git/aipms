"""
core/engine/state_machine.py

State machine engine - supports state transitions and side effects.
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    """
    State transition definition.

    Attributes:
        from_state: Source state
        to_state: Target state
        trigger: Trigger action
        condition: Optional transition condition
        side_effects: List of side-effect functions
    """

    from_state: str
    to_state: str
    trigger: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    side_effects: List[Callable[[], None]] = field(default_factory=list)

    def is_allowed(self, context: Dict[str, Any]) -> bool:
        """Check whether the transition is allowed."""
        if self.condition is None:
            return True
        try:
            return self.condition(context)
        except Exception as e:
            logger.error(f"Error checking transition condition: {e}")
            return False

    def execute_side_effects(self) -> List[Exception]:
        """Execute side effects and return any errors encountered."""
        errors = []
        for effect in self.side_effects:
            try:
                effect()
            except Exception as e:
                logger.error(f"Side effect failed: {e}", exc_info=True)
                errors.append(e)
        return errors


@dataclass
class StateMachineConfig:
    """
    State machine configuration.

    Attributes:
        name: State machine name
        states: List of all valid states
        transitions: List of transitions
        initial_state: Initial state
    """

    name: str
    states: List[str]
    transitions: List[StateTransition]
    initial_state: str


@dataclass
class StateMachineSnapshot:
    """
    State machine snapshot - used for undo/redo.

    Attributes:
        current_state: Current state
        previous_state: Previous state
        transition: The transition that was triggered
        timestamp: Snapshot timestamp
    """

    current_state: str
    previous_state: str
    transition: Optional[StateTransition]
    timestamp: float


class StateMachine:
    """
    State machine engine.

    Features:
    - State transition validation
    - Side-effect execution
    - History tracking (for audit)
    - Snapshot support

    Example:
        >>> machine = StateMachine(
        ...     config=StateMachineConfig(
        ...         name="Room",
        ...         states=["vacant", "occupied", "dirty"],
        ...         transitions=[...],
        ...         initial_state="vacant"
        ...     )
        ... )
        >>> if machine.can_transition_to("occupied", "checkin"):
        ...     machine.transition_to("occupied", "checkin")
    """

    def __init__(self, config: StateMachineConfig):
        self._config = config
        self._current_state = config.initial_state
        self._history: List[StateMachineSnapshot] = []
        self._transition_map: Dict[str, Dict[str, StateTransition]] = {}

        # Build transition map: (from_state, trigger) -> transition
        for t in config.transitions:
            if t.from_state not in self._transition_map:
                self._transition_map[t.from_state] = {}
            self._transition_map[t.from_state][t.trigger] = t

    @property
    def current_state(self) -> str:
        """Get the current state."""
        return self._current_state

    @property
    def config(self) -> StateMachineConfig:
        """Get the state machine configuration."""
        return self._config

    def can_transition_to(self, target_state: str, trigger: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check whether a transition to the target state is allowed.

        Args:
            target_state: Target state
            trigger: Trigger action
            context: Optional context data

        Returns:
            True if the transition is allowed.
        """
        if target_state not in self._config.states:
            return False

        transitions = self._transition_map.get(self._current_state, {})
        transition = transitions.get(trigger)

        if transition is None or transition.to_state != target_state:
            return False

        if transition.is_allowed(context or {}):
            return True

        return False

    def transition_to(self, target_state: str, trigger: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute a state transition.

        Args:
            target_state: Target state
            trigger: Trigger action
            context: Optional context data

        Returns:
            True if the transition succeeded.
        """
        if not self.can_transition_to(target_state, trigger, context):
            logger.warning(
                f"Invalid transition: {self._current_state} -> {target_state} (trigger: {trigger})"
            )
            return False

        transitions = self._transition_map.get(self._current_state, {})
        transition = transitions.get(trigger)

        # Record snapshot
        snapshot = StateMachineSnapshot(
            current_state=self._current_state,
            previous_state=self._current_state,
            transition=transition,
            timestamp=__import__("time").time(),
        )

        # Execute transition
        previous_state = self._current_state
        self._current_state = target_state

        # Execute side effects
        if transition:
            transition.execute_side_effects()

        # Update snapshot
        snapshot.previous_state = previous_state
        self._history.append(snapshot)

        logger.info(f"State transition: {previous_state} -> {target_state} (trigger: {trigger})")
        return True

    def get_history(self) -> List[StateMachineSnapshot]:
        """Get transition history."""
        return list(self._history)

    def reset(self, state: Optional[str] = None) -> None:
        """
        Reset the state machine.

        Args:
            state: State to reset to; None uses the initial state.
        """
        self._current_state = state if state is not None else self._config.initial_state
        self._history.clear()


class StateMachineEngine:
    """
    State machine engine manager - manages multiple state machine instances.

    Example:
        >>> engine = StateMachineEngine()
        >>> engine.register("Room", room_state_machine)
        >>> room_machine = engine.get("Room")
        >>> room_machine.transition_to("occupied", "checkin")
    """

    def __init__(self):
        self._machines: Dict[str, StateMachine] = {}

    def register(self, entity_type: str, machine: StateMachine) -> None:
        """Register a state machine for an entity type."""
        self._machines[entity_type] = machine
        logger.info(f"StateMachine registered for {entity_type}")

    def get(self, entity_type: str) -> Optional[StateMachine]:
        """Get the state machine for an entity type."""
        return self._machines.get(entity_type)

    def get_all(self) -> Dict[str, StateMachine]:
        """Get all registered state machines."""
        return self._machines.copy()

    def clear(self) -> None:
        """Clear all state machines (for testing)."""
        self._machines.clear()


# Global state machine engine instance
state_machine_engine = StateMachineEngine()


__all__ = [
    "StateTransition",
    "StateMachineConfig",
    "StateMachineSnapshot",
    "StateMachine",
    "StateMachineEngine",
    "state_machine_engine",
]
