"""
tests/services/test_ai_service_registry.py

Integration tests for AIService with ActionRegistry.

SPEC-08: Test the integration of ActionRegistry into AIService.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from app.services.ai_service import AIService
from app.services.actions import reset_action_registry
from app.models.ontology import Employee, EmployeeRole
from datetime import date


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "test_user"
    user.name = "Test User"
    # Create a proper mock role with value attribute
    role_mock = Mock()
    role_mock.value = "receptionist"
    user.role = role_mock
    return user


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the action registry before each test."""
    reset_action_registry()
    yield
    reset_action_registry()


class TestActionRegistryIntegration:
    """Test ActionRegistry integration with AIService."""

    def test_get_action_registry_returns_singleton(self, db_session):
        """Test that get_action_registry returns a singleton instance."""
        service = AIService(db_session)
        registry1 = service.get_action_registry()
        registry2 = service.get_action_registry()

        assert registry1 is registry2

    def test_get_action_registry_initializes_on_first_call(self, db_session):
        """Test that ActionRegistry is initialized on first call."""
        service = AIService(db_session)

        # Reset to ensure fresh state
        service._action_registry = None

        registry = service.get_action_registry()

        assert registry is not None
        # Should have actions registered (all domain action handlers)
        assert len(registry.list_actions()) >= 6

    def test_use_action_registry_returns_true_when_available(self, db_session):
        """Test that use_action_registry returns True when registry is available."""
        service = AIService(db_session)

        assert service.use_action_registry() is True

    def test_use_action_registry_returns_false_when_unavailable(self, db_session):
        """Test that use_action_registry returns False when registry fails."""
        service = AIService(db_session)

        # Simulate registry initialization failure
        service._action_registry = False

        assert service.use_action_registry() is False

    def test_list_registered_actions(self, db_session):
        """Test listing all registered actions."""
        service = AIService(db_session)

        actions = service.list_registered_actions()

        assert len(actions) >= 6

        # Check structure of returned actions
        for action in actions:
            assert "name" in action
            assert "entity" in action
            assert "description" in action
            assert "category" in action
            assert "parameters" in action

        # Check for specific migrated actions
        action_names = [a["name"] for a in actions]
        assert "walkin_checkin" in action_names
        assert "checkout" in action_names
        assert "create_task" in action_names
        assert "create_reservation" in action_names
        assert "ontology_query" in action_names
        assert "semantic_query" in action_names


class TestDispatchViaRegistry:
    """Test dispatch_via_registry method."""

    def test_dispatch_via_registry_success(self, db_session, mock_user):
        """Test successful dispatch via registry."""
        service = AIService(db_session)

        # Mock the registry dispatch to avoid DB operations
        with patch.object(service.get_action_registry(), 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = {
                "success": True,
                "message": "Action executed successfully",
                "stay_record_id": 123
            }

            result = service.dispatch_via_registry(
                "walkin_checkin",
                {"guest_name": "张三", "room_id": 101, "expected_check_out": "2026-02-10"},
                mock_user
            )

            assert result["success"] is True
            assert result["message"] == "Action executed successfully"
            assert result["data"]["stay_record_id"] == 123

    def test_dispatch_via_registry_no_registry(self, db_session, mock_user):
        """Test dispatch_via_registry when registry is unavailable."""
        service = AIService(db_session)
        service._action_registry = False

        with pytest.raises(ValueError, match="ActionRegistry is not available"):
            service.dispatch_via_registry("walkin_checkin", {}, mock_user)


class TestExecuteActionWithRegistry:
    """Test execute_action method with ActionRegistry integration."""

    def test_execute_action_uses_registry_for_migrated_actions(self, db_session, mock_user):
        """Test that execute_action uses registry for migrated actions."""
        service = AIService(db_session)

        # Mock the dispatch_via_registry to avoid DB operations
        with patch.object(service, 'dispatch_via_registry') as mock_dispatch:
            mock_dispatch.return_value = {
                "success": True,
                "message": "Checkin successful",
                "data": {"stay_record_id": 456}
            }

            action = {
                "action_type": "walkin_checkin",
                "params": {
                    "guest_name": "张三",
                    "room_id": 101,
                    "expected_check_out": "2026-02-10"
                }
            }

            result = service.execute_action(action, mock_user)

            assert result["success"] is True
            mock_dispatch.assert_called_once()

    def test_execute_action_returns_error_on_registry_dispatch_failure(self, db_session, mock_user):
        """Test that registered action dispatch failure returns error directly (no legacy fallback)."""
        service = AIService(db_session)

        # Mock dispatch_via_registry to raise an error
        with patch.object(service, 'dispatch_via_registry') as mock_dispatch:
            mock_dispatch.side_effect = Exception("Registry error")

            action = {
                "action_type": "checkout",
                "params": {"stay_record_id": 1}
            }

            result = service.execute_action(action, mock_user)

            # Should return error directly, NOT fall through to legacy
            assert result["success"] is False
            assert "Registry error" in result["message"]

    def test_execute_action_registry_unavailable(self, db_session, mock_user):
        """Test execute_action when registry is not available returns error."""
        service = AIService(db_session)
        service._action_registry = False

        # With no registry, action should fail gracefully
        action = {
            "action_type": "checkout",
            "params": {"stay_record_id": 1}
        }

        result = service.execute_action(action, mock_user)

        assert result["success"] is False
        assert "不支持" in result["message"]


class TestGetRelevantTools:
    """Test get_relevant_tools method."""

    def test_get_relevant_tools_returns_openai_format(self, db_session):
        """Test that get_relevant_tools returns OpenAI tool format."""
        service = AIService(db_session)

        tools = service.get_relevant_tools("办理入住", top_k=5)

        assert len(tools) > 0

        # Check OpenAI tool format
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_get_relevant_tools_no_registry(self, db_session):
        """Test get_relevant_tools when registry is unavailable."""
        service = AIService(db_session)
        service._action_registry = False

        tools = service.get_relevant_tools("test", top_k=5)

        assert tools == []

    def test_get_relevant_tools_includes_all_actions(self, db_session):
        """Test that get_relevant_tools includes all registered actions."""
        service = AIService(db_session)

        tools = service.get_relevant_tools("all actions", top_k=20)

        # With 6 registered actions, should return all (small registry)
        tool_names = [t["function"]["name"] for t in tools]
        assert "walkin_checkin" in tool_names
        assert "checkout" in tool_names
        assert "create_task" in tool_names
        assert "create_reservation" in tool_names
        assert "ontology_query" in tool_names
        assert "semantic_query" in tool_names


class TestBackwardCompatibility:
    """Test backward compatibility with legacy actions."""

    def test_registered_actions_use_registry(self, db_session, mock_user):
        """Test that registered actions dispatch via registry, not legacy path."""
        service = AIService(db_session)

        # start_task is in registry, so it uses registry dispatch
        with patch.object(service, 'dispatch_via_registry') as mock_registry:
            mock_registry.return_value = {
                "success": True,
                "message": "Registry action",
                "data": {}
            }

            result = service.execute_action({
                "action_type": "start_task",
                "params": {"task_id": 1}
            }, mock_user)

            assert result["success"] is True
            mock_registry.assert_called_once()

    def test_registry_and_legacy_coexist(self, db_session, mock_user):
        """Test that registry handles registered actions and legacy handles unknown ones."""
        service = AIService(db_session)

        # Registry action (walkin_checkin is in registry)
        with patch.object(service, 'dispatch_via_registry') as mock_registry:
            mock_registry.return_value = {
                "success": True,
                "message": "Registry action",
                "data": {}
            }

            registry_result = service.execute_action({
                "action_type": "walkin_checkin",
                "params": {}
            }, mock_user)

            assert registry_result["success"] is True

        # Unregistered action falls through to legacy chain
        # Use a fake action_type that isn't registered anywhere
        legacy_result = service.execute_action({
            "action_type": "some_nonexistent_action",
            "params": {}
        }, mock_user)

        # Legacy chain doesn't handle this either, returns error
        assert legacy_result["success"] is False
