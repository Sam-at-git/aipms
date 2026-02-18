"""
core/ontology/guard_executor.py

GuardExecutor - Unified pre-dispatch guard for action execution.

Orchestrates state machine validation and constraint evaluation with:
- Severity-based priority ordering (ERROR > WARNING > INFO)
- Short-circuit on ERROR violations
- Structured result with violations and suggestions

SPEC-2: Constraint Auto-Execution Engine
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging

from core.ontology.metadata import ConstraintSeverity

logger = logging.getLogger(__name__)


@dataclass
class GuardViolation:
    """A single constraint violation."""
    constraint_id: str
    constraint_name: str
    message: str
    severity: str  # "ERROR", "WARNING", "INFO"
    suggestion: str = ""


@dataclass
class GuardResult:
    """Result of guard evaluation."""
    allowed: bool
    violations: List[GuardViolation] = field(default_factory=list)
    warnings: List[GuardViolation] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "ERROR" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "violations": [
                {"id": v.constraint_id, "name": v.constraint_name,
                 "message": v.message, "severity": v.severity}
                for v in self.violations
            ],
            "warnings": [
                {"id": w.constraint_id, "name": w.constraint_name,
                 "message": w.message, "severity": w.severity}
                for w in self.warnings
            ],
            "suggestions": self.suggestions,
        }


class _DotDict:
    """Dict wrapper supporting dot-notation access for expression evaluation."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            return super().__getattribute__(name)
        val = self._data.get(name)
        if isinstance(val, dict):
            return _DotDict(val)
        return val

    def __eq__(self, other):
        return self._data == other

    def __bool__(self):
        return bool(self._data)


class GuardExecutor:
    """
    Unified pre-dispatch guard for action execution.

    Evaluates state machine transitions and constraints before
    allowing an action to proceed.

    Usage:
        guard = GuardExecutor(registry, state_machine_executor)
        result = guard.check("Room", "checkin", params, context)
        if not result.allowed:
            return result.violations
    """

    def __init__(
        self,
        ontology_registry=None,
        state_machine_executor=None,
    ):
        self._registry = ontology_registry
        self._state_machine_executor = state_machine_executor

    def check(
        self,
        entity: str,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> GuardResult:
        """
        Run all guards for an entity+action combination.

        Args:
            entity: Entity type (e.g., "Room", "StayRecord")
            action: Action name (e.g., "checkout", "checkin")
            params: Action parameters
            context: Execution context with keys:
                - current_state: str (for state machine)
                - target_state: str (for state machine)
                - entity_state: dict (for constraint evaluation)
                - user_context: dict (for permission constraints)
                - user: Employee object

        Returns:
            GuardResult with allowed flag, violations, and suggestions
        """
        result = GuardResult(allowed=True)

        # Guard 1: State machine validation
        self._check_state_machine(entity, action, context, result)
        if not result.allowed:
            return result  # Short-circuit on state machine failure

        # Guard 2: Constraint validation (sorted by severity)
        self._check_constraints(entity, action, params, context, result)

        return result

    def _check_state_machine(
        self,
        entity: str,
        action: str,
        context: Dict[str, Any],
        result: GuardResult
    ) -> None:
        """Validate state machine transition if applicable."""
        if not self._state_machine_executor:
            return

        current_state = context.get("current_state")
        target_state = context.get("target_state")
        if not current_state or not target_state:
            return

        user_role = None
        user = context.get("user")
        if user:
            role = getattr(user, "role", None)
            user_role = role.value if hasattr(role, "value") else str(role) if role else None

        sm_result = self._state_machine_executor.validate_transition(
            entity, current_state, target_state, user_role
        )
        if not sm_result.allowed:
            result.allowed = False
            result.violations.append(GuardViolation(
                constraint_id=f"state_machine_{entity}",
                constraint_name=f"{entity} state transition",
                message=sm_result.reason or f"Invalid transition: {current_state} → {target_state}",
                severity="ERROR",
                suggestion=f"Valid transitions from {current_state}: {', '.join(sm_result.valid_alternatives or [])}"
            ))
            if sm_result.valid_alternatives:
                result.suggestions.extend(
                    [f"Can transition to: {alt}" for alt in sm_result.valid_alternatives]
                )

    def _check_constraints(
        self,
        entity: str,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        result: GuardResult
    ) -> None:
        """Evaluate constraints sorted by severity with short-circuit on ERROR."""
        if not self._registry:
            return

        constraints = self._registry.get_constraints_for_entity_action(entity, action)
        if not constraints:
            return

        # Sort by severity: ERROR first for short-circuit
        severity_order = {
            ConstraintSeverity.ERROR: 0,
            ConstraintSeverity.CRITICAL: 0,
            ConstraintSeverity.WARNING: 1,
            ConstraintSeverity.INFO: 2,
        }
        sorted_constraints = sorted(
            constraints,
            key=lambda c: severity_order.get(c.severity, 3)
        )

        # Build evaluation namespace
        entity_state = context.get("entity_state", {})
        user_context = context.get("user_context", {})
        namespace = {
            "state": _DotDict(entity_state),
            "param": _DotDict(params),
            "user": _DotDict(user_context),
            "True": True,
            "False": False,
            "None": None,
        }

        for constraint in sorted_constraints:
            if not constraint.condition_code:
                # No executable code — skip (logged as debug)
                logger.debug(
                    f"Constraint {constraint.id} has no condition_code, skipping auto-evaluation"
                )
                continue

            try:
                is_valid = bool(eval(
                    constraint.condition_code,
                    {"__builtins__": {}},
                    namespace
                ))
            except Exception as e:
                logger.warning(
                    f"Failed to evaluate constraint {constraint.id}: {e}"
                )
                continue

            if not is_valid:
                violation = GuardViolation(
                    constraint_id=constraint.id,
                    constraint_name=constraint.name,
                    message=constraint.error_message or constraint.description,
                    severity=constraint.severity.value if hasattr(constraint.severity, 'value') else str(constraint.severity),
                    suggestion=constraint.suggestion_message or ""
                )

                if constraint.severity in (ConstraintSeverity.ERROR, ConstraintSeverity.CRITICAL):
                    result.allowed = False
                    result.violations.append(violation)
                    if constraint.suggestion_message:
                        result.suggestions.append(constraint.suggestion_message)
                    # Short-circuit: stop evaluating after first ERROR
                    return
                else:
                    result.warnings.append(violation)


__all__ = ["GuardExecutor", "GuardResult", "GuardViolation"]
