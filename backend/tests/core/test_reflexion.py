"""
tests/core/test_reflexion.py

Comprehensive tests for ReflexionLoop self-healing mechanism.

Tests:
- ExecutionError normalization and classification
- ReflectionResult creation and serialization
- ReflexionLoop retry logic
- LLM-based reflection generation
- Fallback behavior
- Error history tracking
"""
import json
import pytest
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock, patch

from pydantic import BaseModel, ValidationError
from core.ai.reflexion import (
    ErrorType,
    ExecutionError,
    ReflectionResult,
    AttemptRecord,
    ReflexionLoop,
)
from core.ai.actions import ActionDefinition, ActionRegistry, ActionCategory


# ==================== Test Fixtures ====================

class DummyParams(BaseModel):
    """Dummy parameter model for testing."""
    name: str
    room_id: int
    check_in_date: Optional[str] = None


class TestParams(BaseModel):
    """Test parameter model."""
    value: str
    count: int = 1


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock()
    client.is_enabled.return_value = True
    return client


@pytest.fixture
def mock_action_registry():
    """Create a mock action registry."""
    registry = Mock(spec=ActionRegistry)

    # Mock get_action
    mock_action = ActionDefinition(
        name="test_action",
        entity="TestEntity",
        description="A test action",
        category="mutation",
        parameters_schema=TestParams,
        handler=lambda p, **kw: {"status": "ok", "value": p.value}
    )
    registry.get_action.return_value = mock_action

    return registry


@pytest.fixture
def mock_rule_engine():
    """Create a mock rule engine."""
    engine = Mock()
    engine.fallback.return_value = {"status": "ok", "fallback": True}
    return engine


@pytest.fixture
def reflexion_loop(mock_llm_client, mock_action_registry):
    """Create a ReflexionLoop instance for testing."""
    return ReflexionLoop(
        llm_client=mock_llm_client,
        action_registry=mock_action_registry,
        max_retries=2
    )


@pytest.fixture
def reflexion_loop_with_fallback(mock_llm_client, mock_action_registry, mock_rule_engine):
    """Create a ReflexionLoop with rule engine fallback."""
    return ReflexionLoop(
        llm_client=mock_llm_client,
        action_registry=mock_action_registry,
        rule_engine=mock_rule_engine,
        max_retries=2
    )


# ==================== Test ExecutionError ====================

class TestExecutionError:
    """Tests for ExecutionError dataclass."""

    def test_creation(self):
        """Test creating an ExecutionError."""
        error = ExecutionError(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid parameter",
            suggestions=["Check the parameter type"],
            context={"param": "value"}
        )

        assert error.error_type == ErrorType.VALIDATION_ERROR
        assert error.message == "Invalid parameter"
        assert len(error.suggestions) == 1
        assert error.context["param"] == "value"

    def test_to_dict(self):
        """Test converting ExecutionError to dictionary."""
        error = ExecutionError(
            error_type=ErrorType.NOT_FOUND,
            message="Entity not found",
            suggestions=["Verify the ID"],
            context={"id": 999}
        )

        result = error.to_dict()

        assert result["error_type"] == ErrorType.NOT_FOUND
        assert result["message"] == "Entity not found"
        assert result["suggestions"] == ["Verify the ID"]
        assert result["context"]["id"] == 999
        assert "original_error" not in result  # Should not be in dict

    def test_to_prompt_string(self):
        """Test formatting ExecutionError as prompt string."""
        error = ExecutionError(
            error_type=ErrorType.VALUE_ERROR,
            message="Invalid date format",
            suggestions=["Use ISO format (YYYY-MM-DD)"],
            context={"date": "01/01/2026"}
        )

        result = error.to_prompt_string()

        assert "**Type:**" in result
        assert ErrorType.VALUE_ERROR in result
        assert "Invalid date format" in result
        assert "Use ISO format" in result

    def test_from_exception_validation_error(self):
        """Test creating ExecutionError from ValidationError."""
        # Create a ValidationError
        try:
            TestParams(value=123)  # Invalid type
        except ValidationError as e:
            error = ExecutionError.from_exception(e)

            assert error.error_type == ErrorType.VALIDATION_ERROR
            assert error.original_error == e
            assert len(error.suggestions) > 0

    def test_from_exception_permission_error(self):
        """Test creating ExecutionError from PermissionError."""
        exc = PermissionError("User does not have permission")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.PERMISSION_DENIED
        assert "permission" in error.message.lower()
        assert len(error.suggestions) > 0

    def test_from_exception_value_error(self):
        """Test creating ExecutionError from ValueError."""
        exc = ValueError("invalid literal for int()")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.VALUE_ERROR
        assert error.original_error == exc

    def test_from_exception_not_found(self):
        """Test creating ExecutionError from 'not found' error."""
        exc = ValueError("Room 999 not found")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.NOT_FOUND
        assert "not found" in error.message.lower()

    def test_from_exception_unknown(self):
        """Test creating ExecutionError from unknown exception."""
        exc = RuntimeError("Something went wrong")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.UNKNOWN
        assert error.original_error == exc

    def test_from_exception_with_context(self):
        """Test creating ExecutionError with context."""
        exc = ValueError("Invalid value")
        error = ExecutionError.from_exception(exc, context={"attempt": 1})

        assert error.context["attempt"] == 1

    def test_error_classification_date_errors(self):
        """Test that date-related errors get appropriate suggestions."""
        exc = ValueError("Invalid date format")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.VALUE_ERROR
        assert any("ISO" in s for s in error.suggestions)

    def test_error_classification_number_errors(self):
        """Test that number-related errors get appropriate suggestions."""
        exc = ValueError("invalid literal for int() with base 10: 'abc'")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.VALUE_ERROR

    def test_error_classification_enum_errors(self):
        """Test that enum errors get appropriate suggestions."""
        exc = ValueError("'INVALID' is not a valid RoomStatus")
        error = ExecutionError.from_exception(exc)

        assert error.error_type == ErrorType.VALUE_ERROR
        assert any("enum" in s.lower() or "option" in s.lower() for s in error.suggestions)


# ==================== Test ReflectionResult ====================

class TestReflectionResult:
    """Tests for ReflectionResult dataclass."""

    def test_creation(self):
        """Test creating a ReflectionResult."""
        result = ReflectionResult(
            analysis="Parameter type was wrong",
            correction="Change room_id to integer",
            corrected_params={"room_id": 101},
            confidence=0.9,
            should_retry=True
        )

        assert result.analysis == "Parameter type was wrong"
        assert result.correction == "Change room_id to integer"
        assert result.corrected_params == {"room_id": 101}
        assert result.confidence == 0.9
        assert result.should_retry is True

    def test_to_dict(self):
        """Test converting ReflectionResult to dictionary."""
        result = ReflectionResult(
            analysis="Test analysis",
            correction="Test correction",
            corrected_params={"test": "value"},
            confidence=0.8,
            should_retry=True
        )

        dict_result = result.to_dict()

        assert dict_result["analysis"] == "Test analysis"
        assert dict_result["correction"] == "Test correction"
        assert dict_result["corrected_params"] == {"test": "value"}
        assert dict_result["confidence"] == 0.8
        assert dict_result["should_retry"] is True

    def test_from_dict(self):
        """Test creating ReflectionResult from dictionary."""
        data = {
            "analysis": "Wrong field name",
            "correction": "Use 'room_number' instead",
            "corrected_params": {"room_number": "201"},
            "confidence": 0.7,
            "should_retry": True
        }

        result = ReflectionResult.from_dict(data)

        assert result.analysis == "Wrong field name"
        assert result.correction == "Use 'room_number' instead"
        assert result.corrected_params == {"room_number": "201"}
        assert result.confidence == 0.7

    def test_from_dict_with_null_params(self):
        """Test ReflectionResult.from_dict with null corrected_params."""
        data = {
            "analysis": "Cannot fix",
            "correction": "No correction possible",
            "corrected_params": None,
            "confidence": 0.2,
            "should_retry": False
        }

        result = ReflectionResult.from_dict(data)

        assert result.corrected_params is None
        assert result.should_retry is False

    def test_from_dict_defaults(self):
        """Test ReflectionResult.from_dict with default values."""
        data = {
            "analysis": "Test"
        }

        result = ReflectionResult.from_dict(data)

        assert result.analysis == "Test"
        assert result.correction == ""
        assert result.corrected_params is None
        assert result.confidence == 0.5
        assert result.should_retry is True  # Default


# ==================== Test AttemptRecord ====================

class TestAttemptRecord:
    """Tests for AttemptRecord dataclass."""

    def test_success_record(self):
        """Test creating a successful attempt record."""
        record = AttemptRecord(
            attempt_number=0,
            params={"test": "value"},
            success=True,
            result={"status": "ok"}
        )

        assert record.attempt_number == 0
        assert record.params == {"test": "value"}
        assert record.success is True
        assert record.result == {"status": "ok"}
        assert record.error is None

    def test_failure_record(self):
        """Test creating a failed attempt record."""
        error = ExecutionError(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid params"
        )
        record = AttemptRecord(
            attempt_number=1,
            params={"test": "value"},
            success=False,
            error=error
        )

        assert record.attempt_number == 1
        assert record.success is False
        assert record.error == error
        assert record.result is None

    def test_to_dict_success(self):
        """Test converting successful attempt to dictionary."""
        record = AttemptRecord(
            attempt_number=0,
            params={"test": "value"},
            success=True,
            result={"status": "ok"}
        )

        dict_result = record.to_dict()

        assert dict_result["attempt_number"] == 0
        assert dict_result["params"] == {"test": "value"}
        assert dict_result["success"] is True
        assert dict_result["result"] == {"status": "ok"}
        assert dict_result["error"] is None

    def test_to_dict_failure(self):
        """Test converting failed attempt to dictionary."""
        error = ExecutionError(
            error_type=ErrorType.NOT_FOUND,
            message="Not found"
        )
        record = AttemptRecord(
            attempt_number=1,
            params={"test": "value"},
            success=False,
            error=error
        )

        dict_result = record.to_dict()

        assert dict_result["success"] is False
        assert dict_result["error"]["error_type"] == ErrorType.NOT_FOUND
        assert dict_result["result"] is None


# ==================== Test ReflexionLoop ====================

class TestReflexionLoopInit:
    """Tests for ReflexionLoop initialization."""

    def test_init_default(self, mock_llm_client, mock_action_registry):
        """Test initialization with defaults."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry
        )

        assert loop.llm_client == mock_llm_client
        assert loop.action_registry == mock_action_registry
        assert loop.rule_engine is None
        assert loop.max_retries == 2

    def test_init_with_max_retries(self, mock_llm_client, mock_action_registry):
        """Test initialization with custom max_retries."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry,
            max_retries=3
        )

        assert loop.max_retries == 3

    def test_init_with_rule_engine(self, mock_llm_client, mock_action_registry, mock_rule_engine):
        """Test initialization with rule engine."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry,
            rule_engine=mock_rule_engine
        )

        assert loop.rule_engine == mock_rule_engine


class TestReflexionLoopExecute:
    """Tests for ReflexionLoop.execute_with_reflexion."""

    def test_success_on_first_attempt(self, reflexion_loop, mock_action_registry):
        """Test successful execution on first attempt (no retry needed)."""
        mock_action_registry.dispatch.return_value = {"status": "ok"}

        result = reflexion_loop.execute_with_reflexion(
            "test_action",
            {"value": "test", "count": 1},
            {}
        )

        assert result["result"]["status"] == "ok"
        assert result["final_attempt"] == 0
        assert result["reflexion_used"] is False
        assert len(result["attempts"]) == 1
        assert result["attempts"][0]["success"] is True

        # Verify dispatch was called once
        assert mock_action_registry.dispatch.call_count == 1

    def test_success_after_one_retry(self, reflexion_loop, mock_action_registry, mock_llm_client):
        """Test successful execution after one retry."""
        # First attempt fails, second succeeds
        mock_action_registry.dispatch.side_effect = [
            ValueError("Invalid value"),
            {"status": "ok"}
        ]

        # Mock LLM reflection response
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Parameter was wrong",
                "correction": "Fixed the parameter",
                "corrected_params": {"value": "corrected", "count": 1},
                "confidence": 0.9,
                "should_retry": True
            }
        )

        result = reflexion_loop.execute_with_reflexion(
            "test_action",
            {"value": "wrong", "count": 1},
            {}
        )

        assert result["result"]["status"] == "ok"
        assert result["final_attempt"] == 1
        assert result["reflexion_used"] is True
        assert len(result["attempts"]) == 2

    def test_max_retries_exceeded(self, reflexion_loop, mock_action_registry, mock_llm_client):
        """Test behavior when max retries is exceeded."""
        # All attempts fail
        mock_action_registry.dispatch.side_effect = ValueError("Always fails")

        # Mock LLM reflection response with sufficient confidence to keep retrying
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Cannot fix",
                "correction": "No correction possible",
                "corrected_params": None,
                "confidence": 0.5,  # Above MIN_CONFIDENCE_FOR_RETRY (0.3)
                "should_retry": True
            }
        )

        with pytest.raises(ExecutionError) as exc_info:
            reflexion_loop.execute_with_reflexion(
                "test_action",
                {"value": "wrong"},
                {}
            )

        error = exc_info.value
        # The error type is preserved from the last error (ValueError -> value_error)
        assert error.error_type == ErrorType.VALUE_ERROR
        assert "failed after 3 attempts" in error.message
        # With max_retries=2, we have attempts 0, 1, 2 = 3 total attempts
        assert error.context["attempts"] == 3

    def test_permission_error_no_reflexion(self, reflexion_loop, mock_action_registry):
        """Test that permission errors don't trigger reflection."""
        mock_action_registry.dispatch.side_effect = PermissionError("Access denied")

        with pytest.raises(ExecutionError) as exc_info:
            reflexion_loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

        error = exc_info.value
        assert error.error_type == ErrorType.PERMISSION_DENIED
        # Should not have called LLM
        assert reflexion_loop.llm_client.chat.call_count == 0

    def test_llm_not_available(self, mock_action_registry):
        """Test behavior when LLM is not available."""
        # Create loop with disabled LLM
        disabled_llm = Mock()
        disabled_llm.is_enabled.return_value = False

        loop = ReflexionLoop(
            llm_client=disabled_llm,
            action_registry=mock_action_registry
        )

        mock_action_registry.dispatch.side_effect = ValueError("Error")

        with pytest.raises(ExecutionError):
            loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

    def test_fallback_to_rule_engine(self, reflexion_loop_with_fallback, mock_action_registry, mock_rule_engine):
        """Test fallback to rule engine when retries exhausted."""
        # All attempts fail
        mock_action_registry.dispatch.side_effect = ValueError("Always fails")

        # Mock LLM response
        mock_llm = reflexion_loop_with_fallback.llm_client
        mock_llm.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Cannot fix",
                "correction": "No correction",
                "corrected_params": None,
                "confidence": 0.1,
                "should_retry": False
            }
        )

        result = reflexion_loop_with_fallback.execute_with_reflexion(
            "test_action",
            {"value": "test"},
            {}
        )

        assert result["result"]["status"] == "ok"
        assert result["fallback_used"] is True
        assert mock_rule_engine.fallback.call_count == 1

    def test_fallback_also_fails(self, reflexion_loop_with_fallback, mock_action_registry, mock_rule_engine):
        """Test when both reflexion and fallback fail."""
        mock_action_registry.dispatch.side_effect = ValueError("Always fails")
        mock_rule_engine.fallback.side_effect = RuntimeError("Fallback failed")

        mock_llm = reflexion_loop_with_fallback.llm_client
        mock_llm.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Cannot fix",
                "correction": "No correction",
                "corrected_params": None,
                "confidence": 0.1,
                "should_retry": False
            }
        )

        with pytest.raises(ExecutionError):
            reflexion_loop_with_fallback.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )


class TestReflexionLoopShouldAttemptReflexion:
    """Tests for ReflexionLoop._should_attempt_reflexion."""

    def test_reflectable_errors(self, reflexion_loop):
        """Test that most errors are reflectable."""
        reflectable_errors = [
            ExecutionError(error_type=ErrorType.VALIDATION_ERROR, message="Test"),
            ExecutionError(error_type=ErrorType.NOT_FOUND, message="Test"),
            ExecutionError(error_type=ErrorType.VALUE_ERROR, message="Test"),
            ExecutionError(error_type=ErrorType.STATE_ERROR, message="Test"),
            ExecutionError(error_type=ErrorType.UNKNOWN, message="Test"),
        ]

        for error in reflectable_errors:
            assert reflexion_loop._should_attempt_reflexion(error) is True, \
                f"Error type {error.error_type} should be reflectable"

    def test_non_reflectable_errors(self, reflexion_loop):
        """Test that permission errors are not reflectable."""
        error = ExecutionError(
            error_type=ErrorType.PERMISSION_DENIED,
            message="Access denied"
        )

        assert reflexion_loop._should_attempt_reflexion(error) is False


class TestReflexionLoopBuildPrompt:
    """Tests for ReflexionLoop._build_reflection_prompt."""

    def test_prompt_structure(self, reflexion_loop, mock_action_registry):
        """Test that reflection prompt has correct structure."""
        action_def = mock_action_registry.get_action("test_action")

        prompt = reflexion_loop._build_reflection_prompt(
            action_def=action_def,
            original_params={"value": "original"},
            current_params={"value": "current"},
            error=ExecutionError(
                error_type=ErrorType.VALIDATION_ERROR,
                message="Invalid value"
            ),
            error_history=[]
        )

        # Check key sections
        assert "Action Definition" in prompt
        assert "test_action" in prompt
        assert "Parameter Schema" in prompt
        assert "Original Parameters" in prompt
        assert "Current Parameters" in prompt
        assert "Error Information" in prompt
        assert "Your Task" in prompt
        assert "Response Format" in prompt

    def test_prompt_with_error_history(self, reflexion_loop, mock_action_registry):
        """Test that error history is included in prompt."""
        action_def = mock_action_registry.get_action("test_action")

        # Need at least 2 historical errors (the current error is excluded from history display)
        error_history = [
            ExecutionError(error_type=ErrorType.VALUE_ERROR, message="Error 1"),
            ExecutionError(error_type=ErrorType.VALIDATION_ERROR, message="Error 2"),
            ExecutionError(error_type=ErrorType.NOT_FOUND, message="Error 3")  # This will be excluded as current
        ]

        prompt = reflexion_loop._build_reflection_prompt(
            action_def=action_def,
            original_params={},
            current_params={},
            error=error_history[-1],  # The last one is current
            error_history=error_history
        )

        assert "Error History" in prompt
        assert "Error 1" in prompt
        assert "Error 2" in prompt
        # Error 3 is excluded as it's the current error


# ==================== Integration Tests ====================

class TestReflexionLoopIntegration:
    """Integration tests for ReflexionLoop."""

    def test_end_to_end_recovery_scenario(self, mock_llm_client, mock_action_registry):
        """Test a complete error recovery scenario."""
        # Scenario: First attempt fails with validation error,
        # LLM suggests correction, second attempt succeeds

        call_count = [0]

        def side_effect_fn(action_name, params, context):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: fail with validation error
                raise ValidationError.from_exception_data(
                    TestParams.__name__,
                    [{"loc": ("value",), "msg": "field required", "type": "value_error"}]
                )
            else:
                # Second call: succeed
                return {"status": "ok", "value": params.get("value")}

        mock_action_registry.dispatch.side_effect = side_effect_fn

        # Mock LLM to provide correction
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "The 'value' field was missing",
                "correction": "Add the required 'value' field",
                "corrected_params": {"value": "corrected_value", "count": 1},
                "confidence": 0.95,
                "should_retry": True
            }
        )

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry
        )

        result = loop.execute_with_reflexion(
            "test_action",
            {"count": 1},  # Missing 'value'
            {}
        )

        assert result["result"]["status"] == "ok"
        assert result["result"]["value"] == "corrected_value"
        assert result["final_attempt"] == 1
        assert result["reflexion_used"] is True
        assert call_count[0] == 2

    def test_no_recovery_scenario(self, mock_llm_client, mock_action_registry):
        """Test scenario where recovery is not possible."""
        mock_action_registry.dispatch.side_effect = ValueError("Unrecoverable error")

        # LLM says don't retry
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "This error cannot be fixed by changing parameters",
                "correction": "External action required",
                "corrected_params": None,
                "confidence": 0.9,
                "should_retry": False
            }
        )

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry
        )

        with pytest.raises(ExecutionError) as exc_info:
            loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

        # Should have stopped early due to should_retry=False
        assert exc_info.value.context["attempts"] == 1
        assert mock_action_registry.dispatch.call_count == 1

    def test_low_confidence_stops_retry(self, mock_llm_client, mock_action_registry):
        """Test that low confidence LLM response stops retry."""
        mock_action_registry.dispatch.side_effect = ValueError("Error")

        # LLM has low confidence
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Not sure what to do",
                "correction": "Maybe try this?",
                "corrected_params": {"value": "uncertain"},
                "confidence": 0.2,  # Below MIN_CONFIDENCE_FOR_RETRY
                "should_retry": True
            }
        )

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry
        )

        with pytest.raises(ExecutionError):
            loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

        # Should have stopped after first reflection due to low confidence
        assert mock_action_registry.dispatch.call_count == 1


# ==================== Edge Cases ====================

class TestReflexionLoopEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_unknown_action(self, reflexion_loop, mock_action_registry):
        """Test behavior when action is unknown."""
        mock_action_registry.get_action.return_value = None
        mock_action_registry.dispatch.side_effect = ValueError("Unknown action")

        mock_llm = reflexion_loop.llm_client
        mock_llm.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Unknown action",
                "correction": "No correction",
                "corrected_params": None,
                "confidence": 0.0,
                "should_retry": False
            }
        )

        # Should raise ExecutionError after all attempts fail
        with pytest.raises(ExecutionError):
            reflexion_loop.execute_with_reflexion(
                "unknown_action",
                {"value": "test"},
                {}
            )

    def test_llm_returns_invalid_json(self, reflexion_loop, mock_action_registry, mock_llm_client):
        """Test handling of invalid LLM response."""
        mock_action_registry.dispatch.side_effect = ValueError("Error")

        # LLM returns unparsable response
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: None  # Returns None (unparsable)
        )

        # Should stop retrying when reflection fails
        with pytest.raises(ExecutionError):
            reflexion_loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

    def test_reflection_generation_fails(self, reflexion_loop, mock_action_registry, mock_llm_client):
        """Test handling of reflection generation failure."""
        mock_action_registry.dispatch.side_effect = ValueError("Error")

        # LLM call raises exception
        mock_llm_client.chat.side_effect = RuntimeError("LLM failed")

        # Should handle gracefully and stop retrying
        with pytest.raises(ExecutionError):
            reflexion_loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

    def test_no_rule_engine_available(self, reflexion_loop, mock_action_registry, mock_llm_client):
        """Test fallback when no rule engine is available."""
        mock_action_registry.dispatch.side_effect = ValueError("Error")

        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Cannot fix",
                "correction": "No correction",
                "corrected_params": None,
                "confidence": 0.1,
                "should_retry": False
            }
        )

        # Should raise ExecutionError (not crash)
        with pytest.raises(ExecutionError):
            reflexion_loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

    def test_zero_max_retries(self, mock_llm_client, mock_action_registry):
        """Test behavior with max_retries=0 (no retries)."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=mock_action_registry,
            max_retries=0
        )

        mock_action_registry.dispatch.side_effect = ValueError("Error")

        with pytest.raises(ExecutionError) as exc_info:
            loop.execute_with_reflexion(
                "test_action",
                {"value": "test"},
                {}
            )

        # Should fail immediately without retry
        assert exc_info.value.context["attempts"] == 1

    def test_params_immutability(self, reflexion_loop, mock_action_registry):
        """Test that original params are not modified."""
        original_params = {"value": "test", "count": 1}
        params_copy = original_params.copy()

        mock_action_registry.dispatch.return_value = {"status": "ok"}

        reflexion_loop.execute_with_reflexion(
            "test_action",
            original_params,
            {}
        )

        # Original params should not be modified
        assert original_params == params_copy
