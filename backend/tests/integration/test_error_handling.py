"""
Integration tests for error handling in the Action Registry system.

SPEC-10: Tests comprehensive error scenarios including:
- Parameter validation errors
- Permission errors
- Unknown action errors
- Service unavailability errors
- VectorStore unavailability errors
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError

from app.services.ai_service import AIService
from app.services.actions import reset_action_registry
from app.models.ontology import (
    Employee, EmployeeRole,
    Room, RoomStatus, RoomType,
    Guest, StayRecord, StayRecordStatus,
    Task, TaskStatus, TaskType
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the action registry before and after each test."""
    reset_action_registry()
    yield
    reset_action_registry()


@pytest.fixture
def mock_receptionist(db_session):
    """Create a mock receptionist user."""
    from app.security.auth import get_password_hash
    user = Employee(
        id=1,
        username="test_receptionist",
        password_hash=get_password_hash("password"),
        name="测试前台",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_manager(db_session):
    """Create a mock manager user."""
    from app.security.auth import get_password_hash
    user = Employee(
        id=2,
        username="test_manager",
        password_hash=get_password_hash("password"),
        name="测试经理",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_cleaner(db_session):
    """Create a mock cleaner user (limited permissions)."""
    from app.security.auth import get_password_hash
    user = Employee(
        id=3,
        username="test_cleaner",
        password_hash=get_password_hash("password"),
        name="测试清洁员",
        role=EmployeeRole.CLEANER,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_room_type(db_session):
    """Create a sample room type."""
    room_type = RoomType(
        name="标准间",
        description="Standard Room",
        base_price=Decimal("288.00"),
        max_occupancy=2
    )
    db_session.add(room_type)
    db_session.commit()
    db_session.refresh(room_type)
    return room_type


@pytest.fixture
def available_room(db_session, sample_room_type):
    """Create an available room."""
    room = Room(
        room_number="101",
        floor=1,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


# ============================================================================
# Parameter Validation Error Tests
# ============================================================================

class TestParameterValidationErrors:
    """Test parameter validation error handling."""

    def test_walkin_checkin_missing_required_params(self, db_session, mock_receptionist):
        """Test walkin_checkin with missing required parameters."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三"
                # Missing: guest_phone, room_id
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False
        assert "message" in result
        # Error should indicate validation or missing parameters
        msg_lower = result["message"].lower()
        assert any(keyword in msg_lower for keyword in ["验证", "required", "missing", "请确认", "缺少"])

    def test_walkin_checkin_invalid_date_format(self, db_session, mock_receptionist):
        """Test walkin_checkin with invalid date format."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三",
                "guest_phone": "13800138000",
                "room_id": 1,
                "expected_check_out": "invalid-date"
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_checkout_missing_stay_record_id(self, db_session, mock_receptionist):
        """Test checkout with missing stay_record_id."""
        service = AIService(db_session)

        action = {
            "action_type": "checkout",
            "params": {}  # Missing stay_record_id
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_ontology_query_missing_entity(self, db_session, mock_receptionist):
        """Test ontology_query with missing entity."""
        service = AIService(db_session)

        action = {
            "action_type": "ontology_query",
            "params": {
                "fields": ["name"]
                # Missing: entity
            }
        }

        result = service.execute_action(action, mock_receptionist)

        # Should fail - the legacy path catches KeyError and returns an error message
        # Check for error indicators in the response
        query_result = result.get("query_result", {})
        message = result.get("message", "")

        # Either success=False, or message indicates failure, or query_result has no rows
        has_error = (
            not result.get("success", True) or
            "失败" in message or
            "错误" in message or
            "error" in result.get("error", "") or
            query_result.get("rows") == [] or
            "'entity'" in message  # KeyError message
        )
        assert has_error, f"Expected error indication but got: {result}"

    def test_create_task_missing_room_id(self, db_session, mock_receptionist):
        """Test create_task with missing room_id."""
        service = AIService(db_session)

        action = {
            "action_type": "create_task",
            "params": {
                "task_type": "CLEANING"
                # Missing: room_id
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_create_reservation_missing_required_params(self, db_session, mock_receptionist):
        """Test create_reservation with missing required parameters."""
        service = AIService(db_session)

        action = {
            "action_type": "create_reservation",
            "params": {
                "guest_name": "张三"
                # Missing: guest_phone, room_type_id, dates
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False


# ============================================================================
# Permission Error Tests
# ============================================================================

class TestPermissionErrors:
    """Test permission error handling."""

    def test_walkin_checkin_cleaner_permission_denied(self, db_session, mock_cleaner, available_room):
        """Test that cleaner cannot perform walk-in check-in."""
        service = AIService(db_session)
        registry = service.get_action_registry()

        params = {
            "guest_name": "张三",
            "guest_phone": "13800138000",
            "room_id": available_room.id,
            "expected_check_out": str(date.today() + timedelta(days=1))
        }

        context = {
            "db": db_session,
            "user": mock_cleaner,
            "param_parser": service.param_parser
        }

        # Should raise PermissionError
        with pytest.raises(PermissionError, match=".*not allowed.*"):
            registry.dispatch("walkin_checkin", params, context)

    def test_checkout_cleaner_permission_denied(self, db_session, mock_cleaner):
        """Test that cleaner cannot perform checkout."""
        service = AIService(db_session)
        registry = service.get_action_registry()

        params = {
            "stay_record_id": 1
        }

        context = {
            "db": db_session,
            "user": mock_cleaner,
            "param_parser": service.param_parser
        }

        with pytest.raises(PermissionError, match=".*not allowed.*"):
            registry.dispatch("checkout", params, context)

    def test_create_reservation_cleaner_permission_denied(self, db_session, mock_cleaner):
        """Test that cleaner cannot create reservation."""
        service = AIService(db_session)
        registry = service.get_action_registry()

        params = {
            "guest_name": "张三",
            "guest_phone": "13800138000",
            "room_type_id": 1,
            "check_in_date": str(date.today()),
            "check_out_date": str(date.today() + timedelta(days=1)),
            "adult_count": 1
        }

        context = {
            "db": db_session,
            "user": mock_cleaner,
            "param_parser": service.param_parser
        }

        with pytest.raises(PermissionError, match=".*not allowed.*"):
            registry.dispatch("create_reservation", params, context)

    def test_receptionist_has_permission(self, db_session, mock_receptionist, available_room):
        """Test that receptionist has permission for check-in."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三",
                "guest_phone": "13800138000",
                "room_id": available_room.id,
                "expected_check_out": str(date.today() + timedelta(days=1))
            }
        }

        # Should not raise PermissionError
        try:
            result = service.execute_action(action, mock_receptionist)
            # May fail for other reasons (room occupied, etc.) but not permission
            if not result["success"]:
                assert "permission" not in result["message"].lower()
        except PermissionError:
            pytest.fail("Receptionist should have permission for walkin_checkin")

    def test_manager_has_permission(self, db_session, mock_manager, available_room):
        """Test that manager has permission for all actions."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三",
                "guest_phone": "13800138000",
                "room_id": available_room.id,
                "expected_check_out": str(date.today() + timedelta(days=1))
            }
        }

        # Should not raise PermissionError
        try:
            result = service.execute_action(action, mock_manager)
            if not result["success"]:
                assert "permission" not in result["message"].lower()
        except PermissionError:
            pytest.fail("Manager should have permission for all actions")


# ============================================================================
# Unknown Action Tests
# ============================================================================

class TestUnknownActionErrors:
    """Test unknown action error handling."""

    def test_nonexistent_action_type(self, db_session, mock_receptionist):
        """Test handling of completely unknown action type."""
        service = AIService(db_session)

        action = {
            "action_type": "nonexistent_action_xyz",
            "params": {}
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False
        assert "Unknown action" in result["message"] or "不支持" in result["message"] or "not found" in result["message"].lower()

    def test_malformed_action_no_type(self, db_session, mock_receptionist):
        """Test handling of action without action_type."""
        service = AIService(db_session)

        action = {
            "params": {}  # Missing action_type
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_malformed_action_no_params(self, db_session, mock_receptionist):
        """Test handling of action without params."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin"
            # Missing params
        }

        # Should handle gracefully
        result = service.execute_action(action, mock_receptionist)
        # May fail validation but should not crash


# ============================================================================
# Service Unavailability Tests
# ============================================================================

class TestServiceUnavailability:
    """Test behavior when services are unavailable."""

    def test_registry_not_initialized(self, db_session, mock_receptionist):
        """Test handling when registry is not initialized."""
        service = AIService(db_session)

        # Disable registry
        service._action_registry = False

        # Try to use registry method
        with pytest.raises(ValueError, match=".*not available.*"):
            service.dispatch_via_registry("walkin_checkin", {}, mock_receptionist)

    def test_get_relevant_tools_without_registry(self, db_session):
        """Test get_relevant_tools when registry is unavailable."""
        service = AIService(db_session)

        # Disable registry
        service._action_registry = False

        tools = service.get_relevant_tools("test query", top_k=5)

        assert tools == []

    def test_list_actions_without_registry(self, db_session):
        """Test list_registered_actions when registry is unavailable."""
        service = AIService(db_session)

        # Disable registry
        service._action_registry = False

        actions = service.list_registered_actions()

        assert actions == []


# ============================================================================
# VectorStore Unavailability Tests
# ============================================================================

class TestVectorStoreUnavailability:
    """Test behavior when VectorStore is unavailable."""

    def test_registry_works_without_vectorstore(self, db_session):
        """Test that ActionRegistry works normally when VectorStore is unavailable."""
        # Patch embedding service to return None (VectorStore unavailable)
        with patch('core.ai.get_embedding_service', return_value=None):
            service = AIService(db_session)
            registry = service.get_action_registry()

            # Registry should still be initialized
            assert registry is not None
            assert len(registry.list_actions()) >= 6

            # get_relevant_tools should fall back to all tools
            tools = registry.get_relevant_tools("test query", top_k=3)
            assert len(tools) == 6  # All 6 actions

    def test_get_relevant_tools_falls_back_gracefully(self, db_session):
        """Test that get_relevant_tools falls back when VectorStore fails."""
        # Disable embedding to simulate VectorStore unavailability
        with patch('core.ai.get_embedding_service', return_value=None):
            service = AIService(db_session)

            # Should return all tools as fallback
            tools = service.get_relevant_tools("任意查询", top_k=3)
            tool_names = [t["function"]["name"] for t in tools]

            # Should return all 6 actions
            assert len(tool_names) == 6
            assert "walkin_checkin" in tool_names
            assert "checkout" in tool_names
            assert "create_task" in tool_names


# ============================================================================
# Database Error Tests
# ============================================================================

class TestDatabaseErrors:
    """Test handling of database-related errors."""

    def test_walkin_checkin_room_not_found(self, db_session, mock_receptionist):
        """Test walkin_checkin with non-existent room."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三",
                "guest_phone": "13800138000",
                "room_id": 99999,  # Non-existent room
                "expected_check_out": str(date.today() + timedelta(days=1))
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_checkout_stay_not_found(self, db_session, mock_receptionist):
        """Test checkout with non-existent stay record."""
        service = AIService(db_session)

        action = {
            "action_type": "checkout",
            "params": {
                "stay_record_id": 99999  # Non-existent
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False

    def test_create_task_room_not_found(self, db_session, mock_receptionist):
        """Test create_task with non-existent room."""
        service = AIService(db_session)

        action = {
            "action_type": "create_task",
            "params": {
                "room_id": 99999,
                "task_type": "CLEANING",
                "priority": "normal"
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False


# ============================================================================
# Error Message Format Tests
# ============================================================================

class TestErrorMessageFormat:
    """Test that error messages are properly formatted."""

    def test_error_message_contains_details(self, db_session, mock_receptionist):
        """Test that error messages contain helpful details."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三"
                # Missing required params
            }
        }

        result = service.execute_action(action, mock_receptionist)

        assert result["success"] is False
        assert "message" in result
        # Message should not be empty
        assert len(result["message"]) > 0

    def test_validation_error_is_user_friendly(self, db_session, mock_receptionist):
        """Test that validation errors are user-friendly."""
        service = AIService(db_session)

        action = {
            "action_type": "walkin_checkin",
            "params": {
                "guest_name": "张三"
            }
        }

        result = service.execute_action(action, mock_receptionist)

        # Error should be understandable
        assert result["success"] is False
        # Should mention what's wrong
        msg_lower = result["message"].lower()
        assert any(keyword in msg_lower for keyword in ["required", "missing", "需要", "缺少", "请确认", "room"])

    def test_permission_error_is_clear(self, db_session, mock_cleaner):
        """Test that permission errors are clear."""
        service = AIService(db_session)
        registry = service.get_action_registry()

        params = {
            "guest_name": "张三",
            "guest_phone": "13800138000",
            "room_id": 1,
            "expected_check_out": str(date.today() + timedelta(days=1))
        }

        context = {
            "db": db_session,
            "user": mock_cleaner,
            "param_parser": service.param_parser
        }

        with pytest.raises(PermissionError) as exc_info:
            registry.dispatch("walkin_checkin", params, context)

        # Error message should mention permission
        error_msg = str(exc_info.value).lower()
        assert "permission" in error_msg or "allowed" in error_msg or "role" in error_msg


# ============================================================================
# Recovery Tests
# ============================================================================

class TestErrorRecovery:
    """Test recovery after errors."""

    def test_service_continues_after_validation_error(self, db_session, mock_receptionist):
        """Test that service continues working after a validation error."""
        service = AIService(db_session)

        # First action fails validation
        bad_action = {
            "action_type": "walkin_checkin",
            "params": {"guest_name": "张三"}
        }

        result1 = service.execute_action(bad_action, mock_receptionist)
        assert result1["success"] is False

        # Second action should still work (service not in bad state)
        # Use a simpler action that should work
        registry = service.get_action_registry()
        assert len(registry.list_actions()) >= 6

    def test_registry_not_corrupted_by_errors(self, db_session, mock_receptionist):
        """Test that registry state is not corrupted by errors."""
        service = AIService(db_session)

        # Get initial registry state
        registry = service.get_action_registry()
        initial_count = len(registry.list_actions())

        # Execute failing action
        bad_action = {
            "action_type": "walkin_checkin",
            "params": {"guest_name": "张三"}
        }

        service.execute_action(bad_action, mock_receptionist)

        # Registry should be unchanged
        final_count = len(registry.list_actions())
        assert initial_count == final_count
