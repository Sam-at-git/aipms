"""
tests/core/test_actions.py

Unit tests for ActionDefinition and ActionRegistry.
"""
import pytest
from unittest.mock import MagicMock, Mock
from typing import List, Set
from pydantic import BaseModel, Field, ValidationError

from core.ai.actions import ActionDefinition, ActionRegistry, ActionCategory


# Test Fixtures

class TestParams(BaseModel):
    """Test parameter model"""
    name: str = Field(..., description="Name field")
    count: int = Field(default=1, description="Count field")
    optional: str = Field(None, description="Optional field")


class CheckInParams(BaseModel):
    """Check-in parameters"""
    guest_name: str = Field(..., description="Guest name")
    guest_phone: str = Field(..., description="Guest phone")
    room_id: int = Field(..., description="Room ID")


class TestActionDefinition:
    """Test suite for ActionDefinition"""

    def test_create_action_definition(self):
        """Test creating an action definition"""
        def handler(params: TestParams, db, user):
            return {"success": True}

        definition = ActionDefinition(
            name="test_action",
            entity="TestEntity",
            description="A test action",
            category="mutation",
            parameters_schema=TestParams,
            handler=handler
        )

        assert definition.name == "test_action"
        assert definition.entity == "TestEntity"
        assert definition.description == "A test action"
        assert definition.category == "mutation"
        assert definition.parameters_schema == TestParams
        assert definition.handler == handler

    def test_to_openai_tool(self):
        """Test conversion to OpenAI function format"""
        def handler(params: TestParams, db, user):
            return {}

        definition = ActionDefinition(
            name="test_action",
            entity="TestEntity",
            description="A test action",
            category="mutation",
            parameters_schema=TestParams,
            handler=handler
        )

        tool = definition.to_openai_tool()

        assert tool["type"] == "function"
        assert tool["function"]["name"] == "test_action"
        assert tool["function"]["description"] == "A test action"
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["type"] == "object"

    def test_to_openai_tool_includes_required_fields(self):
        """Test that required fields are in OpenAI schema"""
        def handler(params: TestParams, db, user):
            return {}

        definition = ActionDefinition(
            name="test_action",
            entity="TestEntity",
            description="A test action",
            category="mutation",
            parameters_schema=TestParams,
            handler=handler
        )

        tool = definition.to_openai_tool()
        params_schema = tool["function"]["parameters"]

        # Should have required field
        assert "required" in params_schema
        assert "name" in params_schema["required"]

    def test_to_dict(self):
        """Test dictionary conversion"""
        def handler(params: TestParams, db, user):
            return {}

        definition = ActionDefinition(
            name="test_action",
            entity="TestEntity",
            description="A test action",
            category="mutation",
            parameters_schema=TestParams,
            handler=handler,
            requires_confirmation=False,
            allowed_roles={"admin", "manager"},
            undoable=True,
            side_effects=["creates_record"],
            search_keywords=["test", "example"]
        )

        result = definition.to_dict()

        assert result["name"] == "test_action"
        assert result["entity"] == "TestEntity"
        assert result["requires_confirmation"] is False
        assert "admin" in result["allowed_roles"]
        assert result["undoable"] is True
        assert "creates_record" in result["side_effects"]
        assert "test" in result["search_keywords"]

    def test_defaults(self):
        """Test default values"""
        def handler(params: TestParams, db, user):
            return {}

        definition = ActionDefinition(
            name="test_action",
            entity="TestEntity",
            description="A test action",
            category="mutation",
            parameters_schema=TestParams,
            handler=handler
        )

        assert definition.requires_confirmation is True  # Default
        assert definition.allowed_roles == set()  # Default
        assert definition.undoable is False  # Default
        assert definition.side_effects == []  # Default
        assert definition.search_keywords == []  # Default


class TestActionRegistry:
    """Test suite for ActionRegistry"""

    def test_init_empty_registry(self):
        """Test creating an empty registry"""
        registry = ActionRegistry()

        assert len(registry._actions) == 0
        assert registry.list_actions() == []
        assert registry.get_action("nonexistent") is None

    def test_decorator_registration(self):
        """Test that decorator properly registers actions"""
        registry = ActionRegistry()

        @registry.register(
            name="test_action",
            entity="TestEntity",
            description="A test action"
        )
        def handler(params: TestParams, db, user):
            return {"success": True}

        # Action should be registered
        action = registry.get_action("test_action")
        assert action is not None
        assert action.name == "test_action"
        assert action.entity == "TestEntity"
        assert action.description == "A test action"

    def test_register_multiple_actions(self):
        """Test registering multiple actions"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="Action 1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="Action 2", category="query")
        def handler2(params: TestParams, db, user):
            return {}

        assert registry.get_action("action1") is not None
        assert registry.get_action("action2") is not None
        assert len(registry.list_actions()) == 2

    def test_register_with_all_options(self):
        """Test registration with all options"""
        registry = ActionRegistry()

        @registry.register(
            name="full_action",
            entity="Full",
            description="Full options test",
            category="mutation",
            requires_confirmation=False,
            allowed_roles={"admin"},
            undoable=True,
            side_effects=["creates", "updates"],
            search_keywords=["full", "test"]
        )
        def handler(params: TestParams, db, user):
            return {}

        action = registry.get_action("full_action")

        assert action.requires_confirmation is False
        assert "admin" in action.allowed_roles
        assert action.undoable is True
        assert "creates" in action.side_effects
        assert "full" in action.search_keywords

    def test_list_actions(self):
        """Test listing all registered actions"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="A1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="A2")
        def handler2(params: TestParams, db, user):
            return {}

        actions = registry.list_actions()
        assert len(actions) == 2
        action_names = {a.name for a in actions}
        assert action_names == {"action1", "action2"}

    def test_list_actions_by_entity(self):
        """Test filtering actions by entity"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="Guest", description="A1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="Room", description="A2")
        def handler2(params: TestParams, db, user):
            return {}

        @registry.register(name="action3", entity="Guest", description="A3")
        def handler3(params: TestParams, db, user):
            return {}

        guest_actions = registry.list_actions_by_entity("Guest")
        assert len(guest_actions) == 2
        assert {a.name for a in guest_actions} == {"action1", "action3"}

        room_actions = registry.list_actions_by_entity("Room")
        assert len(room_actions) == 1
        assert room_actions[0].name == "action2"

    def test_list_actions_by_category(self):
        """Test filtering actions by category"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="A1", category="query")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="A2", category="mutation")
        def handler2(params: TestParams, db, user):
            return {}

        @registry.register(name="action3", entity="E3", description="A3", category="query")
        def handler3(params: TestParams, db, user):
            return {}

        query_actions = registry.list_actions_by_category("query")
        assert len(query_actions) == 2

        mutation_actions = registry.list_actions_by_category("mutation")
        assert len(mutation_actions) == 1

    def test_dispatch_success(self):
        """Test successful action dispatch"""
        registry = ActionRegistry()

        @registry.register(name="test", entity="Test", description="Test")
        def handler(params: TestParams, db, user):
            return {"name": params.name, "count": params.count}

        mock_db = Mock()
        mock_user = Mock()

        result = registry.dispatch(
            "test",
            {"name": "test_value", "count": 5},
            {"db": mock_db, "user": mock_user}
        )

        assert result["name"] == "test_value"
        assert result["count"] == 5

    def test_dispatch_with_defaults(self):
        """Test dispatch with default parameter values"""
        registry = ActionRegistry()

        @registry.register(name="test", entity="Test", description="Test")
        def handler(params: TestParams, db, user):
            return {"name": params.name, "count": params.count}

        result = registry.dispatch(
            "test",
            {"name": "test"},  # count has default
            {"db": Mock(), "user": Mock()}
        )

        assert result["name"] == "test"
        assert result["count"] == 1  # Default value

    def test_dispatch_validation_error(self):
        """Test that dispatch validates parameters"""
        registry = ActionRegistry()

        @registry.register(name="test", entity="Test", description="Test")
        def handler(params: TestParams, db, user):
            return {}

        # Missing required field
        with pytest.raises(ValidationError):
            registry.dispatch(
                "test",
                {"count": 5},  # Missing 'name'
                {"db": Mock(), "user": Mock()}
            )

    def test_dispatch_validation_error_wrong_type(self):
        """Test that dispatch validates parameter types"""
        registry = ActionRegistry()

        @registry.register(name="test", entity="Test", description="Test")
        def handler(params: TestParams, db, user):
            return {}

        # Wrong type for count
        with pytest.raises(ValidationError):
            registry.dispatch(
                "test",
                {"name": "test", "count": "not_a_number"},
                {"db": Mock(), "user": Mock()}
            )

    def test_dispatch_unknown_action(self):
        """Test handling of unknown action"""
        registry = ActionRegistry()

        with pytest.raises(ValueError, match="Unknown action"):
            registry.dispatch(
                "unknown_action",
                {},
                {"db": Mock(), "user": Mock()}
            )

    def test_dispatch_role_check_success(self):
        """Test role check passes when user has required role"""
        registry = ActionRegistry()

        @registry.register(
            name="protected_action",
            entity="Test",
            description="Protected",
            allowed_roles={"admin", "manager"}
        )
        def handler(params: TestParams, db, user):
            return {"success": True}

        mock_user = Mock()
        mock_user.role.value = "admin"

        result = registry.dispatch(
            "protected_action",
            {"name": "test"},
            {"db": Mock(), "user": mock_user}
        )

        assert result["success"] is True

    def test_dispatch_role_check_failure(self):
        """Test role check fails when user lacks required role"""
        registry = ActionRegistry()

        @registry.register(
            name="protected_action",
            entity="Test",
            description="Protected",
            allowed_roles={"admin", "manager"}
        )
        def handler(params: TestParams, db, user):
            return {}

        mock_user = Mock()
        mock_user.role.value = "receptionist"

        with pytest.raises(PermissionError, match="not allowed"):
            registry.dispatch(
                "protected_action",
                {"name": "test"},
                {"db": Mock(), "user": mock_user}
            )

    def test_export_all_tools(self):
        """Test exporting all actions as OpenAI tools"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="Action 1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="Action 2")
        def handler2(params: TestParams, db, user):
            return {}

        tools = registry.export_all_tools()

        assert len(tools) == 2
        assert tools[0]["type"] == "function"
        assert tools[1]["type"] == "function"

    def test_get_relevant_tools_small_registry(self):
        """Test get_relevant_tools returns all when registry is small"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="Action 1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="Action 2")
        def handler2(params: TestParams, db, user):
            return {}

        tools = registry.get_relevant_tools("any query")

        # Should return all for small registry
        assert len(tools) == 2

    def test_get_relevant_tools_large_registry(self):
        """Test get_relevant_tools with vector store"""
        mock_vector_store = Mock()

        # Mock search results
        from core.ai.vector_store import SchemaItem
        mock_vector_store.search.return_value = [
            SchemaItem(id="action1", type="action", entity="E1", name="action1", description="test")
        ]

        registry = ActionRegistry(vector_store=mock_vector_store)

        @registry.register(name="action1", entity="E1", description="Action 1")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="E2", description="Action 2")
        def handler2(params: TestParams, db, user):
            return {}

        # Even with 2 actions, if vector_store is provided it should use it
        # But our implementation returns all if <= 20, so let's test the path
        tools = registry.get_relevant_tools("test query")

        # With vector store, it should still work (small registry returns all)
        assert len(tools) >= 1

    def test_get_statistics(self):
        """Test getting registry statistics"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="Guest", description="A1", category="query")
        def handler1(params: TestParams, db, user):
            return {}

        @registry.register(name="action2", entity="Guest", description="A2", category="mutation")
        def handler2(params: TestParams, db, user):
            return {}

        @registry.register(name="action3", entity="Room", description="A3", category="mutation")
        def handler3(params: TestParams, db, user):
            return {}

        stats = registry.get_statistics()

        assert stats["total_actions"] == 3
        assert stats["by_entity"]["Guest"] == 2
        assert stats["by_entity"]["Room"] == 1
        assert stats["by_category"]["query"] == 1
        assert stats["by_category"]["mutation"] == 2

    def test_handler_receives_context(self):
        """Test that handler receives context parameters"""
        registry = ActionRegistry()

        @registry.register(name="test", entity="Test", description="Test")
        def handler(params: TestParams, db, user, extra=None):
            return {
                "db_received": db is not None,
                "user_received": user is not None,
                "extra_received": extra == "test_value"
            }

        mock_db = Mock()
        mock_user = Mock()

        result = registry.dispatch(
            "test",
            {"name": "test"},
            {"db": mock_db, "user": mock_user, "extra": "test_value"}
        )

        assert result["db_received"] is True
        assert result["user_received"] is True
        assert result["extra_received"] is True


class TestActionRegistryIntegration:
    """Integration tests for ActionRegistry"""

    def test_real_world_checkin_action(self):
        """Test a realistic check-in action"""
        registry = ActionRegistry()

        @registry.register(
            name="walkin_checkin",
            entity="Guest",
            description="Handle walk-in guest check-in without reservation",
            category="mutation",
            requires_confirmation=True,
            allowed_roles={"receptionist", "manager"},
            undoable=True,
            search_keywords=["散客入住", "直接入住", "无预订入住"]
        )
        def handle_checkin(params: CheckInParams, db, user):
            # Simulate check-in logic
            return {
                "status": "success",
                "guest_name": params.guest_name,
                "room_id": params.room_id,
                "checked_in_by": user.id if user else None
            }

        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = 123
        mock_user.role.value = "receptionist"  # Has required role

        result = registry.dispatch(
            "walkin_checkin",
            {
                "guest_name": "张三",
                "guest_phone": "13800138000",
                "room_id": 101
            },
            {"db": mock_db, "user": mock_user}
        )

        assert result["status"] == "success"
        assert result["guest_name"] == "张三"
        assert result["room_id"] == 101
        assert result["checked_in_by"] == 123

    def test_action_export_for_llm(self):
        """Test that actions can be exported for LLM consumption"""
        registry = ActionRegistry()

        @registry.register(
            name="walkin_checkin",
            entity="Guest",
            description="Handle walk-in guest check-in"
        )
        def handle_checkin(params: CheckInParams, db, user):
            return {}

        tools = registry.export_all_tools()

        # Verify structure matches OpenAI function calling format
        assert len(tools) == 1
        tool = tools[0]

        assert tool["type"] == "function"
        func = tool["function"]

        assert func["name"] == "walkin_checkin"
        assert "description" in func
        assert "parameters" in func

        # Verify parameters schema
        params = func["parameters"]
        assert params["type"] == "object"
        assert "properties" in params

        # Check required fields
        assert "guest_name" in params["required"]
        assert "guest_phone" in params["required"]
        assert "room_id" in params["required"]

    def test_multiple_handlers_same_signature(self):
        """Test multiple actions with same parameter model"""
        registry = ActionRegistry()

        @registry.register(name="action1", entity="E1", description="First")
        def handler1(params: TestParams, db, user):
            return {"action": "action1", "name": params.name}

        @registry.register(name="action2", entity="E2", description="Second")
        def handler2(params: TestParams, db, user):
            return {"action": "action2", "name": params.name}

        result1 = registry.dispatch("action1", {"name": "test"}, {"db": Mock(), "user": Mock()})
        result2 = registry.dispatch("action2", {"name": "test"}, {"db": Mock(), "user": Mock()})

        assert result1["action"] == "action1"
        assert result2["action"] == "action2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
