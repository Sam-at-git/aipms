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

    def test_execute_action_falls_back_to_legacy_on_error(self, db_session, mock_user):
        """Test that execute_action falls back to legacy path on registry error."""
        service = AIService(db_session)

        # Mock dispatch_via_registry to raise an error
        with patch.object(service, 'dispatch_via_registry') as mock_dispatch:
            mock_dispatch.side_effect = Exception("Registry error")

            # Mock the legacy path to succeed
            with patch.object(service, 'checkout_service') as mock_checkout:
                mock_stay = Mock()
                mock_stay.room.room_number = "201"
                mock_checkout.check_out.return_value = mock_stay

                action = {
                    "action_type": "checkout",
                    "params": {"stay_record_id": 1}
                }

                result = service.execute_action(action, mock_user)

                # Should succeed via legacy path
                assert result["success"] is True

    def test_execute_action_registry_unavailable(self, db_session, mock_user):
        """Test execute_action when registry is not available."""
        service = AIService(db_session)
        service._action_registry = False

        # Should use legacy path
        with patch.object(service, 'checkout_service') as mock_checkout:
            mock_stay = Mock()
            mock_stay.room.room_number = "201"
            mock_checkout.check_out.return_value = mock_stay

            action = {
                "action_type": "checkout",
                "params": {"stay_record_id": 1}
            }

            result = service.execute_action(action, mock_user)

            assert result["success"] is True


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

    def test_legacy_actions_still_work(self, db_session, mock_user):
        """Test that non-migrated actions still work via legacy path."""
        service = AIService(db_session)

        # Use an action that hasn't been migrated yet
        # For example: assign_task, start_task, complete_task, etc.

        # Mock the legacy path
        with patch.object(service, 'task_service') as mock_task:
            mock_task.start_task.return_value = Mock(id=1)

            action = {
                "action_type": "start_task",
                "params": {"task_id": 1}
            }

            result = service.execute_action(action, mock_user)

            # Should succeed via legacy path
            assert result["success"] is True

    def test_registry_and_legacy_coexist(self, db_session, mock_user):
        """Test that both registry and legacy paths can coexist."""
        service = AIService(db_session)

        # Since registry is now enabled, we need to disable it to test legacy path
        # Or we should patch the registry dispatch to simulate both paths

        # Registry action (using create_task which is in registry)
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

        # Legacy action (unmigrated action like start_task)
        # Since start_task is not in registry, it should use legacy path
        # But we need to mock task_service since we don't have real data
        with patch.object(service, 'task_service') as mock_task_service:
            mock_task = Mock()
            mock_task.status = "in_progress"
            mock_task_service.start_task.return_value = mock_task

            legacy_result = service.execute_action({
                "action_type": "start_task",
                "params": {"task_id": 1}
            }, mock_user)

            # start_task is not in registry, so it uses legacy path
            assert legacy_result["success"] is True
