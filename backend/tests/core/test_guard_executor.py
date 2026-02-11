"""
tests/core/test_guard_executor.py

SPEC-2: Tests for GuardExecutor - unified pre-dispatch guard.
"""
import pytest
from unittest.mock import Mock, MagicMock
from core.ontology.guard_executor import GuardExecutor, GuardResult, GuardViolation
from core.ontology.metadata import (
    ConstraintMetadata, ConstraintType, ConstraintSeverity
)
from core.ontology.registry import OntologyRegistry


@pytest.fixture
def registry():
    """Create a clean OntologyRegistry for testing."""
    reg = OntologyRegistry()
    reg._constraints.clear()
    yield reg
    reg._constraints.clear()


class TestGuardResult:
    """Test GuardResult data class."""

    def test_allowed_result(self):
        result = GuardResult(allowed=True)
        assert result.allowed
        assert not result.has_errors
        assert not result.has_warnings
        assert result.violations == []

    def test_result_with_violation(self):
        result = GuardResult(
            allowed=False,
            violations=[GuardViolation(
                constraint_id="test", constraint_name="Test",
                message="failed", severity="ERROR"
            )]
        )
        assert not result.allowed
        assert result.has_errors

    def test_result_with_warning(self):
        result = GuardResult(
            allowed=True,
            warnings=[GuardViolation(
                constraint_id="test", constraint_name="Test",
                message="caution", severity="WARNING"
            )]
        )
        assert result.allowed
        assert result.has_warnings

    def test_to_dict(self):
        result = GuardResult(
            allowed=False,
            violations=[GuardViolation(
                constraint_id="c1", constraint_name="Constraint 1",
                message="error", severity="ERROR"
            )],
            suggestions=["Fix it"]
        )
        d = result.to_dict()
        assert d["allowed"] is False
        assert len(d["violations"]) == 1
        assert d["violations"][0]["id"] == "c1"
        assert d["suggestions"] == ["Fix it"]


class TestGuardExecutorConstraints:
    """Test constraint evaluation in GuardExecutor."""

    def test_passes_when_no_constraints(self, registry):
        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Room", "checkin", {}, {})
        assert result.allowed

    def test_passes_when_condition_code_satisfied(self, registry):
        registry.register_constraint(ConstraintMetadata(
            id="room_vacant",
            name="Room must be vacant",
            description="Room must be VACANT_CLEAN for checkin",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="room.status == 'VACANT_CLEAN'",
            condition_code="state.status == 'VACANT_CLEAN'",
            error_message="Room not vacant",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Room", "checkin", {}, {
            "entity_state": {"status": "VACANT_CLEAN"}
        })
        assert result.allowed
        assert len(result.violations) == 0

    def test_fails_when_condition_code_violated(self, registry):
        registry.register_constraint(ConstraintMetadata(
            id="room_vacant",
            name="Room must be vacant",
            description="Room must be VACANT_CLEAN for checkin",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="room.status == 'VACANT_CLEAN'",
            condition_code="state.status == 'VACANT_CLEAN'",
            error_message="Room not vacant",
            suggestion_message="Choose a clean room",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Room", "checkin", {}, {
            "entity_state": {"status": "OCCUPIED"}
        })
        assert not result.allowed
        assert len(result.violations) == 1
        assert result.violations[0].constraint_id == "room_vacant"
        assert result.violations[0].message == "Room not vacant"
        assert "Choose a clean room" in result.suggestions

    def test_warning_does_not_block(self, registry):
        registry.register_constraint(ConstraintMetadata(
            id="deposit_warning",
            name="Deposit recommended",
            description="Deposit is recommended",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.WARNING,
            entity="Reservation",
            action="create_reservation",
            condition_text="prepaid > 0",
            condition_code="param.prepaid_amount > 0",
            error_message="No deposit",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Reservation", "create_reservation",
                             {"prepaid_amount": 0}, {})
        assert result.allowed  # WARNING doesn't block
        assert len(result.warnings) == 1

    def test_short_circuit_on_error(self, registry):
        """ERROR constraint should short-circuit, skipping remaining constraints."""
        registry.register_constraint(ConstraintMetadata(
            id="error_first",
            name="First Error",
            description="This fails",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="fails",
            condition_code="state.status == 'VACANT_CLEAN'",
            error_message="First error",
        ))
        registry.register_constraint(ConstraintMetadata(
            id="error_second",
            name="Second Error",
            description="This also fails",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="also fails",
            condition_code="state.floor > 0",
            error_message="Second error",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Room", "checkin", {}, {
            "entity_state": {"status": "OCCUPIED", "floor": 0}
        })
        assert not result.allowed
        # Only first ERROR violation due to short-circuit
        assert len(result.violations) == 1
        assert result.violations[0].constraint_id == "error_first"

    def test_user_context_in_expression(self, registry):
        registry.register_constraint(ConstraintMetadata(
            id="manager_only",
            name="Manager only",
            description="Requires manager role",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Bill",
            action="adjust_bill",
            condition_text="user.role in ('manager', 'sysadmin')",
            condition_code="user.role in ('manager', 'sysadmin')",
            error_message="Manager approval needed",
        ))

        guard = GuardExecutor(ontology_registry=registry)

        # Manager should pass
        result = guard.check("Bill", "adjust_bill", {}, {
            "user_context": {"role": "manager"}
        })
        assert result.allowed

        # Receptionist should fail
        result = guard.check("Bill", "adjust_bill", {}, {
            "user_context": {"role": "receptionist"}
        })
        assert not result.allowed

    def test_param_in_expression(self, registry):
        registry.register_constraint(ConstraintMetadata(
            id="payment_limit",
            name="Payment limit",
            description="Payment must not exceed balance",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Bill",
            action="add_payment",
            condition_text="amount <= outstanding",
            condition_code="param.amount <= state.outstanding_amount",
            error_message="Payment exceeds balance",
        ))

        guard = GuardExecutor(ontology_registry=registry)

        # Valid payment
        result = guard.check("Bill", "add_payment",
                             {"amount": 100},
                             {"entity_state": {"outstanding_amount": 200}})
        assert result.allowed

        # Excess payment
        result = guard.check("Bill", "add_payment",
                             {"amount": 300},
                             {"entity_state": {"outstanding_amount": 200}})
        assert not result.allowed

    def test_constraints_only_match_entity_action(self, registry):
        """Constraints for other entities/actions should not be evaluated."""
        registry.register_constraint(ConstraintMetadata(
            id="room_constraint",
            name="Room only",
            description="Only for Room checkin",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="room check",
            condition_code="False",  # Always fails
            error_message="Should not see this",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        # Different entity
        result = guard.check("Guest", "create_guest", {}, {})
        assert result.allowed

    def test_skips_constraints_without_condition_code(self, registry):
        """Constraints without condition_code should be skipped."""
        registry.register_constraint(ConstraintMetadata(
            id="no_code",
            name="No code",
            description="Only natural language",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="some natural language rule",
            error_message="Should not block",
        ))

        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check("Room", "checkin", {}, {})
        assert result.allowed


class TestGuardExecutorStateMachine:
    """Test state machine integration in GuardExecutor."""

    def test_state_machine_blocks_invalid_transition(self):
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.allowed = False
        mock_result.reason = "Cannot go from occupied to occupied"
        mock_result.valid_alternatives = ["vacant_dirty"]
        mock_executor.validate_transition.return_value = mock_result

        guard = GuardExecutor(state_machine_executor=mock_executor)
        result = guard.check("Room", "checkin", {}, {
            "current_state": "occupied",
            "target_state": "occupied"
        })

        assert not result.allowed
        assert "occupied" in result.violations[0].message

    def test_state_machine_allows_valid_transition(self):
        mock_executor = Mock()
        mock_result = Mock()
        mock_result.allowed = True
        mock_executor.validate_transition.return_value = mock_result

        guard = GuardExecutor(state_machine_executor=mock_executor)
        result = guard.check("Room", "checkin", {}, {
            "current_state": "vacant_clean",
            "target_state": "occupied"
        })

        assert result.allowed

    def test_no_state_machine_check_without_states(self):
        mock_executor = Mock()
        guard = GuardExecutor(state_machine_executor=mock_executor)
        result = guard.check("Room", "checkin", {}, {})

        assert result.allowed
        mock_executor.validate_transition.assert_not_called()


class TestGuardExecutorIntegration:
    """Integration tests combining state machine + constraints."""

    def test_state_machine_short_circuits_before_constraints(self, registry):
        """State machine failure should prevent constraint evaluation."""
        registry.register_constraint(ConstraintMetadata(
            id="would_also_fail",
            name="Would also fail",
            description="But should never be reached",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="unreachable",
            condition_code="False",
            error_message="Should not see this",
        ))

        mock_executor = Mock()
        mock_result = Mock()
        mock_result.allowed = False
        mock_result.reason = "Invalid transition"
        mock_result.valid_alternatives = []
        mock_executor.validate_transition.return_value = mock_result

        guard = GuardExecutor(
            ontology_registry=registry,
            state_machine_executor=mock_executor
        )
        result = guard.check("Room", "checkin", {}, {
            "current_state": "occupied",
            "target_state": "occupied"
        })

        assert not result.allowed
        # Only state machine violation, not constraint
        assert result.violations[0].constraint_id.startswith("state_machine_")
