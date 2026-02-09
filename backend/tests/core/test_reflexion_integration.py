"""
tests/core/test_reflexion_integration.py

Integration tests for ReflexionLoop + ActionRegistry dispatch_with_reflexion.

Tests:
- dispatch_with_reflexion success on first try
- Auto-correction of date formats
- Auto-correction of enum values
- Auto-correction of number string conversion
- Permission error stops reflexion immediately
- Max retries exhausted
- dispatch without reflexion fallback
- get_attempt_history tracking
- _handle_state_error queries state
- _auto_correct_params rule-based corrections
"""
import pytest
from typing import Any, Dict, List, Optional
from enum import Enum
from unittest.mock import Mock, MagicMock, patch

from pydantic import BaseModel, Field

from core.ai.actions import ActionDefinition, ActionRegistry
from core.ai.reflexion import (
    ErrorType,
    ExecutionError,
    ReflectionResult,
    AttemptRecord,
    ReflexionLoop,
)


# ==================== Test Parameter Models ====================

class RoomStatus(str, Enum):
    VACANT_CLEAN = "vacant_clean"
    VACANT_DIRTY = "vacant_dirty"
    OCCUPIED = "occupied"
    OUT_OF_ORDER = "out_of_order"


class CheckInParams(BaseModel):
    """Check-in action parameters."""
    guest_name: str = Field(..., description="Guest name")
    room_id: int = Field(..., description="Room ID")
    check_in_date: Optional[str] = Field(None, description="Check-in date in YYYY-MM-DD format")
    status: Optional[str] = Field(None, description="Room status")


class QueryParams(BaseModel):
    """Query action parameters."""
    entity: str = Field(..., description="Entity to query")
    limit: int = Field(default=10, description="Max results")


class StatusUpdateParams(BaseModel):
    """Status update parameters with enum field."""
    room_id: int = Field(..., description="Room ID")
    new_status: RoomStatus = Field(..., description="New room status")


# ==================== Fixtures ====================

@pytest.fixture
def registry():
    """Create a fresh ActionRegistry without VectorStore."""
    return ActionRegistry(vector_store=None)


@pytest.fixture
def registry_with_actions(registry):
    """Create a registry with test actions registered."""
    call_count = {"checkin": 0}

    @registry.register(
        name="walkin_checkin",
        entity="Guest",
        description="Handle walk-in guest check-in",
        category="mutation",
        requires_confirmation=True,
    )
    def handle_checkin(params: CheckInParams, **context) -> Dict:
        call_count["checkin"] += 1
        return {
            "success": True,
            "message": f"Checked in {params.guest_name} to room {params.room_id}",
            "guest_name": params.guest_name,
            "room_id": params.room_id,
        }

    @registry.register(
        name="query_rooms",
        entity="Room",
        description="Query available rooms",
        category="query",
    )
    def handle_query(params: QueryParams, **context) -> Dict:
        return {"success": True, "results": [], "limit": params.limit}

    @registry.register(
        name="update_room_status",
        entity="Room",
        description="Update room status",
        category="mutation",
    )
    def handle_status_update(params: StatusUpdateParams, **context) -> Dict:
        return {
            "success": True,
            "room_id": params.room_id,
            "new_status": params.new_status.value,
        }

    registry._call_count = call_count
    return registry


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock()
    client.is_enabled.return_value = True
    return client


@pytest.fixture
def reflexion_loop(mock_llm_client, registry_with_actions):
    """Create a ReflexionLoop with real ActionRegistry."""
    return ReflexionLoop(
        llm_client=mock_llm_client,
        action_registry=registry_with_actions,
        max_retries=2,
    )


# ==================== Tests ====================


class TestDispatchWithReflexion:
    """Tests for ActionRegistry.dispatch_with_reflexion."""

    def test_dispatch_with_reflexion_success_first_try(self, registry_with_actions, mock_llm_client):
        """dispatch_with_reflexion succeeds on first try without needing reflexion."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
        )

        result = registry_with_actions.dispatch_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            {},
            reflexion_loop=loop,
        )

        assert result["result"]["success"] is True
        assert result["result"]["guest_name"] == "Alice"
        assert result["final_attempt"] == 0
        assert result["reflexion_used"] is False
        assert len(result["attempts"]) == 1

    def test_dispatch_without_reflexion_fallback(self, registry_with_actions):
        """dispatch_with_reflexion without loop falls back to regular dispatch."""
        result = registry_with_actions.dispatch_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Bob", "room_id": 202},
            {},
            reflexion_loop=None,
        )

        # Regular dispatch returns the handler result directly
        assert result["success"] is True
        assert result["guest_name"] == "Bob"
        assert result["room_id"] == 202


class TestAutoCorrectParams:
    """Tests for ReflexionLoop._auto_correct_params rule-based correction."""

    def test_auto_correct_params_date_format(self, reflexion_loop):
        """Auto-correct short date format: '2026-2-8' -> '2026-02-08'."""
        error = ExecutionError(
            error_type=ErrorType.VALUE_ERROR,
            message="Invalid date format",
        )

        result = reflexion_loop._auto_correct_params(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101, "check_in_date": "2026-2-8"},
            error,
        )

        assert result is not None
        assert result["check_in_date"] == "2026-02-08"
        # Other params preserved
        assert result["guest_name"] == "Alice"
        assert result["room_id"] == 101

    def test_auto_correct_params_date_already_correct(self, reflexion_loop):
        """No correction when date is already correct."""
        error = ExecutionError(
            error_type=ErrorType.VALUE_ERROR,
            message="Some error",
        )

        result = reflexion_loop._auto_correct_params(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101, "check_in_date": "2026-02-08"},
            error,
        )

        # No correction needed, returns None
        assert result is None

    def test_auto_correct_params_enum_normalization(self, reflexion_loop, registry_with_actions):
        """Auto-correct enum values: 'vacant clean' -> 'vacant_clean'."""
        error = ExecutionError(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid enum value",
        )

        result = reflexion_loop._auto_correct_params(
            "update_room_status",
            {"room_id": 101, "new_status": "vacant clean"},
            error,
        )

        assert result is not None
        assert result["new_status"] == "vacant_clean"

    def test_auto_correct_params_enum_case(self, reflexion_loop, registry_with_actions):
        """Auto-correct enum case: 'OCCUPIED' -> 'occupied'."""
        error = ExecutionError(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid enum value",
        )

        result = reflexion_loop._auto_correct_params(
            "update_room_status",
            {"room_id": 101, "new_status": "OCCUPIED"},
            error,
        )

        assert result is not None
        assert result["new_status"] == "occupied"

    def test_auto_correct_params_number_conversion(self, reflexion_loop):
        """Auto-correct number string: '301' -> 301 for integer fields."""
        error = ExecutionError(
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid type",
        )

        result = reflexion_loop._auto_correct_params(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": "301"},
            error,
        )

        assert result is not None
        assert result["room_id"] == 301
        assert isinstance(result["room_id"], int)

    def test_auto_correct_params_no_correction_needed(self, reflexion_loop):
        """Returns None when no auto-correction is possible."""
        error = ExecutionError(
            error_type=ErrorType.NOT_FOUND,
            message="Room not found",
        )

        result = reflexion_loop._auto_correct_params(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            error,
        )

        assert result is None

    def test_auto_correct_params_unknown_action(self, reflexion_loop):
        """Returns None for unknown action."""
        error = ExecutionError(
            error_type=ErrorType.VALUE_ERROR,
            message="Some error",
        )

        result = reflexion_loop._auto_correct_params(
            "nonexistent_action",
            {"key": "value"},
            error,
        )

        assert result is None


class TestDispatchWithReflexionAutoCorrect:
    """Tests for auto-correction integrated into the reflexion loop dispatch flow."""

    def test_dispatch_with_reflexion_auto_correct_date(self, registry_with_actions, mock_llm_client):
        """Full flow: dispatch fails due to bad date, auto-corrects, succeeds on retry."""
        call_count = [0]

        # Override the handler to fail on first call with bad date
        original_action = registry_with_actions.get_action("walkin_checkin")
        original_handler = original_action.handler

        def date_checking_handler(params: CheckInParams, **context) -> Dict:
            call_count[0] += 1
            if params.check_in_date and params.check_in_date == "2026-2-8":
                raise ValueError("Invalid date format: 2026-2-8")
            return {
                "success": True,
                "guest_name": params.guest_name,
                "room_id": params.room_id,
                "check_in_date": params.check_in_date,
            }

        original_action.handler = date_checking_handler

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
            max_retries=2,
        )

        result = registry_with_actions.dispatch_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101, "check_in_date": "2026-2-8"},
            {},
            reflexion_loop=loop,
        )

        assert result["result"]["success"] is True
        assert result["result"]["check_in_date"] == "2026-02-08"
        assert result["reflexion_used"] is True
        assert call_count[0] == 2  # First attempt failed, second succeeded

        # Restore original handler
        original_action.handler = original_handler

    def test_dispatch_with_reflexion_auto_correct_enum(self, registry_with_actions, mock_llm_client):
        """Full flow: dispatch fails due to bad enum, auto-corrects, succeeds on retry."""
        call_count = [0]

        original_action = registry_with_actions.get_action("update_room_status")
        original_handler = original_action.handler

        def strict_handler(params: StatusUpdateParams, **context) -> Dict:
            call_count[0] += 1
            return {
                "success": True,
                "room_id": params.room_id,
                "new_status": params.new_status.value,
            }

        original_action.handler = strict_handler

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
            max_retries=2,
        )

        # Pydantic validation will fail on "vacant clean" because enum expects "vacant_clean"
        # The auto-corrector normalizes spaces to underscores and case
        result = registry_with_actions.dispatch_with_reflexion(
            "update_room_status",
            {"room_id": 101, "new_status": "vacant clean"},
            {},
            reflexion_loop=loop,
        )

        assert result["result"]["success"] is True
        assert result["result"]["new_status"] == "vacant_clean"
        assert result["reflexion_used"] is True

        # Restore
        original_action.handler = original_handler


class TestDispatchWithReflexionStopConditions:
    """Tests for conditions that stop reflexion."""

    def test_dispatch_with_reflexion_stops_on_permission_error(
        self, registry_with_actions, mock_llm_client
    ):
        """Permission errors immediately stop reflexion without retry."""
        original_action = registry_with_actions.get_action("walkin_checkin")
        original_handler = original_action.handler

        def permission_handler(params: CheckInParams, **context) -> Dict:
            raise PermissionError("User does not have permission")

        original_action.handler = permission_handler

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
            max_retries=2,
        )

        with pytest.raises(ExecutionError) as exc_info:
            registry_with_actions.dispatch_with_reflexion(
                "walkin_checkin",
                {"guest_name": "Alice", "room_id": 101},
                {},
                reflexion_loop=loop,
            )

        assert exc_info.value.error_type == ErrorType.PERMISSION_DENIED
        # LLM should NOT have been called
        assert mock_llm_client.chat.call_count == 0
        # Only 1 attempt
        assert exc_info.value.context["attempts"] == 1

        # Restore
        original_action.handler = original_handler

    def test_dispatch_with_reflexion_max_retries(self, registry_with_actions, mock_llm_client):
        """After max retries, raises ExecutionError."""
        original_action = registry_with_actions.get_action("walkin_checkin")
        original_handler = original_action.handler

        def always_fail_handler(params: CheckInParams, **context) -> Dict:
            raise RuntimeError("Always fails")

        original_action.handler = always_fail_handler

        # Mock LLM to suggest retrying each time
        mock_llm_client.chat.return_value = Mock(
            to_json=lambda: {
                "analysis": "Unknown error",
                "correction": "Try again",
                "corrected_params": {"guest_name": "Alice", "room_id": 101},
                "confidence": 0.8,
                "should_retry": True,
            }
        )

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
            max_retries=2,
        )

        with pytest.raises(ExecutionError) as exc_info:
            registry_with_actions.dispatch_with_reflexion(
                "walkin_checkin",
                {"guest_name": "Alice", "room_id": 101},
                {},
                reflexion_loop=loop,
            )

        error = exc_info.value
        assert "failed after 3 attempts" in error.message  # 0, 1, 2 = 3 attempts
        assert error.context["attempts"] == 3

        # Restore
        original_action.handler = original_handler


class TestHandleStateError:
    """Tests for ReflexionLoop._handle_state_error."""

    def test_handle_state_error_queries_state(self, reflexion_loop):
        """State error handler extracts current state from error context."""
        error = ExecutionError(
            error_type=ErrorType.STATE_ERROR,
            message="Cannot check out: room status is 'vacant_clean'",
            context={"current_state": "vacant_clean"},
            suggestions=["Check the current state of the entity"],
        )

        result = reflexion_loop._handle_state_error(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            error,
            {},
        )

        assert result is not None
        assert result["_entity_current_state"] == "vacant_clean"
        # Original params preserved
        assert result["guest_name"] == "Alice"
        assert result["room_id"] == 101

    def test_handle_state_error_with_alternatives(self, reflexion_loop):
        """State error handler passes valid alternatives."""
        error = ExecutionError(
            error_type=ErrorType.STATE_ERROR,
            message="Invalid state transition",
            context={"valid_alternatives": ["occupied", "out_of_order"]},
            suggestions=["Ensure the state transition is valid"],
        )

        result = reflexion_loop._handle_state_error(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            error,
            {},
        )

        assert result is not None
        assert result["_valid_state_alternatives"] == ["occupied", "out_of_order"]

    def test_handle_state_error_no_state_info(self, reflexion_loop):
        """State error handler returns None when no state info available."""
        error = ExecutionError(
            error_type=ErrorType.STATE_ERROR,
            message="Some state error",
            context={},
            suggestions=[],
        )

        result = reflexion_loop._handle_state_error(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            error,
            {},
        )

        assert result is None

    def test_handle_state_error_unknown_action(self, reflexion_loop):
        """State error handler returns None for unknown action."""
        error = ExecutionError(
            error_type=ErrorType.STATE_ERROR,
            message="State error",
            context={"current_state": "active"},
        )

        result = reflexion_loop._handle_state_error(
            "nonexistent_action",
            {"key": "value"},
            error,
            {},
        )

        assert result is None


class TestGetAttemptHistory:
    """Tests for ReflexionLoop.get_attempt_history."""

    def test_get_attempt_history(self, registry_with_actions, mock_llm_client):
        """get_attempt_history returns records from the most recent execution."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
        )

        # Initially empty
        assert loop.get_attempt_history() == []

        # Execute successfully
        result = loop.execute_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            {},
        )

        history = loop.get_attempt_history()
        assert len(history) == 1
        assert history[0]["attempt_number"] == 0
        assert history[0]["success"] is True
        assert history[0]["params"]["guest_name"] == "Alice"

    def test_get_attempt_history_multiple_attempts(self, registry_with_actions, mock_llm_client):
        """get_attempt_history tracks all attempts including failures."""
        original_action = registry_with_actions.get_action("walkin_checkin")
        original_handler = original_action.handler
        call_count = [0]

        def failing_then_succeeding_handler(params: CheckInParams, **context) -> Dict:
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Invalid date format for check_in_date")
            return {"success": True, "guest_name": params.guest_name, "room_id": params.room_id}

        original_action.handler = failing_then_succeeding_handler

        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
            max_retries=2,
        )

        # First call will fail, auto-correct date should fix it
        result = loop.execute_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101, "check_in_date": "2026-2-8"},
            {},
        )

        history = loop.get_attempt_history()
        assert len(history) == 2
        assert history[0]["success"] is False
        assert history[1]["success"] is True

        # Restore
        original_action.handler = original_handler

    def test_get_attempt_history_resets_on_new_execution(self, registry_with_actions, mock_llm_client):
        """get_attempt_history resets when a new execution starts."""
        loop = ReflexionLoop(
            llm_client=mock_llm_client,
            action_registry=registry_with_actions,
        )

        # First execution
        loop.execute_with_reflexion(
            "walkin_checkin",
            {"guest_name": "Alice", "room_id": 101},
            {},
        )
        assert len(loop.get_attempt_history()) == 1

        # Second execution
        loop.execute_with_reflexion(
            "query_rooms",
            {"entity": "Room", "limit": 5},
            {},
        )
        history = loop.get_attempt_history()
        assert len(history) == 1
        assert history[0]["params"]["entity"] == "Room"
