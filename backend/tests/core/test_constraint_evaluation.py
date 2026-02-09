"""
Tests for SPEC-10: ConstraintEngine expression evaluation
"""
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import (
    ConstraintMetadata, ConstraintType, ConstraintSeverity,
)
from core.reasoning.constraint_engine import ConstraintEngine, ConstraintValidationResult


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def engine_with_constraints(clean_registry):
    # Room must be vacant_clean for checkin
    clean_registry.register_constraint(ConstraintMetadata(
        id="room_vacant_for_checkin",
        name="Room must be vacant clean",
        description="Room must be VACANT_CLEAN for check-in",
        constraint_type=ConstraintType.STATE,
        severity=ConstraintSeverity.ERROR,
        entity="Room",
        action="checkin",
        condition_text="state.status == 'VACANT_CLEAN'",
        condition_code="state.status == 'VACANT_CLEAN'",
        error_message="Room is not vacant clean",
        suggestion_message="Choose a VACANT_CLEAN room",
    ))
    # Blacklist constraint
    clean_registry.register_constraint(ConstraintMetadata(
        id="guest_not_blacklisted",
        name="Guest not blacklisted",
        description="Blacklisted guests cannot check in",
        constraint_type=ConstraintType.BUSINESS_RULE,
        severity=ConstraintSeverity.ERROR,
        entity="Room",
        action="checkin",
        condition_text="state.guest_blacklisted != True",
        condition_code="state.guest_blacklisted != True",
        error_message="Guest is blacklisted",
    ))
    # Warning constraint
    clean_registry.register_constraint(ConstraintMetadata(
        id="bill_outstanding_warning",
        name="Outstanding balance warning",
        description="Guest has outstanding balance",
        constraint_type=ConstraintType.BUSINESS_RULE,
        severity=ConstraintSeverity.WARNING,
        entity="StayRecord",
        action="checkout",
        condition_text="state.outstanding <= 0",
        condition_code="state.outstanding <= 0",
        error_message="Outstanding balance exists",
    ))
    return ConstraintEngine(clean_registry)


class TestExpressionEvaluation:
    """Test constraint expression evaluation"""

    def test_valid_state_passes(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="Room",
            action_type="checkin",
            params={"room_id": 1},
            current_state={"status": "VACANT_CLEAN", "guest_blacklisted": False},
            user_context={},
        )
        assert result.is_valid

    def test_invalid_state_fails(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="Room",
            action_type="checkin",
            params={"room_id": 1},
            current_state={"status": "OCCUPIED", "guest_blacklisted": False},
            user_context={},
        )
        assert not result.is_valid
        assert len(result.violated_constraints) >= 1
        assert any("vacant" in v["message"].lower() for v in result.violated_constraints)

    def test_blacklist_constraint(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="Room",
            action_type="checkin",
            params={},
            current_state={"status": "VACANT_CLEAN", "guest_blacklisted": True},
            user_context={},
        )
        assert not result.is_valid
        assert any("blacklisted" in v["message"].lower() for v in result.violated_constraints)

    def test_warning_constraint(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="StayRecord",
            action_type="checkout",
            params={},
            current_state={"outstanding": 500},
            user_context={},
        )
        # Outstanding > 0, so warning should fire
        assert len(result.warnings) >= 1

    def test_suggestions_populated(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="Room",
            action_type="checkin",
            params={},
            current_state={"status": "OCCUPIED", "guest_blacklisted": False},
            user_context={},
        )
        assert len(result.suggestions) >= 1

    def test_no_constraints_for_entity(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="NonExistent",
            action_type="something",
            params={},
            current_state={},
            user_context={},
        )
        assert result.is_valid

    def test_to_llm_feedback(self, engine_with_constraints):
        result = engine_with_constraints.validate_action(
            entity_type="Room",
            action_type="checkin",
            params={},
            current_state={"status": "OCCUPIED", "guest_blacklisted": False},
            user_context={},
        )
        feedback = result.to_llm_feedback()
        assert feedback is not None
        assert "约束违规" in feedback


class TestCustomValidator:
    """Test custom validator registration"""

    def test_custom_validator(self, clean_registry):
        from core.ontology.metadata import IConstraintValidator, ConstraintEvaluationContext

        class AlwaysFailValidator(IConstraintValidator):
            def validate(self, context):
                return (False, "Always fails")

        clean_registry.register_constraint(ConstraintMetadata(
            id="custom_test",
            name="Custom test",
            description="Test",
            constraint_type=ConstraintType.CUSTOM,
            severity=ConstraintSeverity.ERROR,
            entity="Test",
            action="test",
            condition_text="",
        ))
        engine = ConstraintEngine(clean_registry)
        engine.register_validator("custom_test", AlwaysFailValidator())

        result = engine.validate_action("Test", "test", {}, {}, {})
        assert not result.is_valid
