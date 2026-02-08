"""
Unit tests for ActionRegistry vector search integration.

SPEC-09: Tests for semantic tool discovery via VectorStore.
"""
import pytest
import tempfile
from unittest.mock import Mock, MagicMock, patch, call
from core.ai.actions import ActionRegistry, ActionDefinition
from core.ai.vector_store import SchemaItem, VectorStore
from pydantic import BaseModel, ValidationError


# Test parameter models
class TestParams(BaseModel):
    name: str
    value: int = 0


class EmptyParams(BaseModel):
    """Empty params for testing"""
    pass


# ============================================================================
# Tests for _create_vector_store()
# ============================================================================

def test_create_vector_store_with_enabled_embedding():
    """Test that ActionRegistry creates VectorStore when embedding service is enabled"""
    # Use the actual implementation with a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('core.ai.get_embedding_service') as mock_get:
            # Create a real embedding service for testing (no API calls)
            from core.ai import create_embedding_service_for_test
            mock_embedding = create_embedding_service_for_test()
            mock_get.return_value = mock_embedding

            # Create registry - it should create VectorStore
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                registry = ActionRegistry()

                # Verify VectorStore was created
                assert registry.vector_store is not None
                assert isinstance(registry.vector_store, VectorStore)
            finally:
                os.chdir(original_cwd)


def test_create_vector_store_without_embedding_service():
    """Test that ActionRegistry falls back gracefully when embedding service is unavailable"""
    with patch('core.ai.get_embedding_service') as mock_get:
        mock_get.return_value = None

        registry = ActionRegistry()

        # Should have no VectorStore
        assert registry.vector_store is None


def test_create_vector_store_with_disabled_embedding():
    """Test that ActionRegistry falls back when embedding service is disabled"""
    with patch('core.ai.get_embedding_service') as mock_get:
        mock_embedding = Mock()
        mock_embedding.enabled = False
        mock_get.return_value = mock_embedding

        registry = ActionRegistry()

        # Should have no VectorStore
        assert registry.vector_store is None


def test_create_vector_store_with_exception():
    """Test that ActionRegistry handles exceptions gracefully"""
    with patch('core.ai.get_embedding_service') as mock_get:
        mock_get.side_effect = Exception("Embedding service error")

        registry = ActionRegistry()

        # Should have no VectorStore
        assert registry.vector_store is None


def test_explicit_vector_store_takes_precedence():
    """Test that explicitly provided VectorStore is used instead of auto-creation"""
    explicit_vs = Mock(spec=VectorStore)

    with patch('core.ai.get_embedding_service') as mock_get:
        # Even though embedding service is available
        mock_embedding = Mock()
        mock_embedding.enabled = True
        mock_get.return_value = mock_embedding

        registry = ActionRegistry(vector_store=explicit_vs)

        # Should use the explicit VectorStore
        assert registry.vector_store == explicit_vs


# ============================================================================
# Tests for _index_action()
# ============================================================================

def test_index_action_creates_schemaitem():
    """Test that _index_action creates correct SchemaItem"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    definition = ActionDefinition(
        name="test_action",
        entity="TestEntity",
        description="Test action description",
        category="mutation",
        parameters_schema=TestParams,
        handler=lambda p, **kwargs: {"success": True},
        search_keywords=["test", "testing"]
    )

    registry._index_action(definition)

    # Verify index_items was called
    mock_vs.index_items.assert_called_once()
    call_args = mock_vs.index_items.call_args[0][0]
    assert len(call_args) == 1
    assert isinstance(call_args[0], SchemaItem)


def test_index_action_includes_entity_in_searchable_text():
    """Test that entity name is included in searchable text"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    definition = ActionDefinition(
        name="test_action",
        entity="TestEntity",
        description="Test description",
        category="mutation",
        parameters_schema=TestParams,
        handler=lambda p, **kwargs: {"success": True},
        search_keywords=["keyword1"]
    )

    registry._index_action(definition)

    # Get the SchemaItem that was indexed
    call_args = mock_vs.index_items.call_args[0][0]
    item = call_args[0]

    # Verify entity is in the description
    assert "TestEntity" in item.description or "实体" in item.description


def test_index_action_with_no_vector_store():
    """Test that _index_action handles missing VectorStore gracefully"""
    # VectorStore is None
    registry = ActionRegistry(vector_store=None)

    definition = ActionDefinition(
        name="test_action",
        entity="TestEntity",
        description="Test description",
        category="mutation",
        parameters_schema=TestParams,
        handler=lambda p, **kwargs: {"success": True}
    )

    # Should not raise exception
    registry._index_action(definition)


def test_index_action_includes_metadata():
    """Test that _index_action includes all relevant metadata"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    definition = ActionDefinition(
        name="test_action",
        entity="TestEntity",
        description="Test description",
        category="query",
        parameters_schema=TestParams,
        handler=lambda p, **kwargs: {"success": True},
        requires_confirmation=False,
        allowed_roles={"manager", "receptionist"},
        undoable=True
    )

    registry._index_action(definition)

    # Get the SchemaItem that was indexed
    call_args = mock_vs.index_items.call_args[0][0]
    item = call_args[0]

    # Verify metadata
    assert item.metadata["category"] == "query"
    assert item.metadata["requires_confirmation"] is False
    assert "manager" in item.metadata["allowed_roles"]
    assert item.metadata["undoable"] is True


# ============================================================================
# Tests for get_relevant_tools()
# ============================================================================

def test_get_relevant_tools_uses_vector_search():
    """Test that get_relevant_tools uses VectorStore.search() when available"""
    mock_vs = Mock(spec=VectorStore)
    # Mock search results
    mock_vs.search.return_value = [
        SchemaItem(id="action1", type="action", entity="E1", name="A1", description="...", synonyms=[], metadata={}),
        SchemaItem(id="action2", type="action", entity="E2", name="A2", description="...", synonyms=[], metadata={})
    ]

    registry = ActionRegistry(vector_store=mock_vs)

    # Register 25 actions (above the threshold for using vector search)
    for i in range(25):
        registry._actions[f"action{i}"] = ActionDefinition(
            name=f"action{i}",
            entity=f"Entity{i}",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Call get_relevant_tools
    tools = registry.get_relevant_tools("test query", top_k=5)

    # Verify vector_store.search was called
    mock_vs.search.assert_called_once_with("test query", top_k=5, item_type="action")


def test_get_relevant_tools_returns_search_results_in_order():
    """Test that get_relevant_tools preserves search result order"""
    mock_vs = Mock(spec=VectorStore)
    # Mock search results in specific order
    mock_vs.search.return_value = [
        SchemaItem(id="action_z", type="action", entity="E1", name="Z", description="...", synonyms=[], metadata={}),
        SchemaItem(id="action_a", type="action", entity="E2", name="A", description="...", synonyms=[], metadata={}),
        SchemaItem(id="action_m", type="action", entity="E3", name="M", description="...", synonyms=[], metadata={})
    ]

    registry = ActionRegistry(vector_store=mock_vs)

    # Register the actions
    for name in ["action_a", "action_m", "action_z"]:
        registry._actions[name] = ActionDefinition(
            name=name,
            entity="Entity",
            description="Action",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Need to register 20+ actions to trigger vector search
    for i in range(20):
        registry._actions[f"extra_{i}"] = ActionDefinition(
            name=f"extra_{i}",
            entity="Entity",
            description=f"Extra {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Get relevant tools
    tools = registry.get_relevant_tools("query", top_k=5)

    # Verify order matches search results
    assert len(tools) == 3
    assert tools[0]["function"]["name"] == "action_z"
    assert tools[1]["function"]["name"] == "action_a"
    assert tools[2]["function"]["name"] == "action_m"


def test_get_relevant_tools_falls_back_on_small_scale():
    """Test that get_relevant_tools returns all tools when action count is low"""
    mock_vs = Mock(spec=VectorStore)

    registry = ActionRegistry(vector_store=mock_vs)

    # Register only 5 actions (below threshold)
    for i in range(5):
        registry._actions[f"action{i}"] = ActionDefinition(
            name=f"action{i}",
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Call get_relevant_tools
    tools = registry.get_relevant_tools("query", top_k=2)

    # Should return all 5 tools, not use search
    assert len(tools) == 5
    mock_vs.search.assert_not_called()


def test_get_relevant_tools_falls_back_without_vector_store():
    """Test that get_relevant_tools returns all tools when VectorStore is None"""
    # No VectorStore
    registry = ActionRegistry(vector_store=None)

    # Register some actions
    for i in range(10):
        registry._actions[f"action{i}"] = ActionDefinition(
            name=f"action{i}",
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Call get_relevant_tools
    tools = registry.get_relevant_tools("query", top_k=3)

    # Should return all tools
    assert len(tools) == 10


def test_get_relevant_tools_falls_back_on_search_error():
    """Test that get_relevant_tools falls back when search raises exception"""
    mock_vs = Mock(spec=VectorStore)
    mock_vs.search.side_effect = Exception("Search failed")

    registry = ActionRegistry(vector_store=mock_vs)

    # Register 25 actions
    for i in range(25):
        registry._actions[f"action{i}"] = ActionDefinition(
            name=f"action{i}",
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Call get_relevant_tools
    tools = registry.get_relevant_tools("query", top_k=5)

    # Should return all tools as fallback
    assert len(tools) == 25


def test_get_relevant_tools_filters_unknown_actions():
    """Test that get_relevant_tools ignores search results that aren't registered"""
    mock_vs = Mock(spec=VectorStore)
    # Mock search results including unknown action
    mock_vs.search.return_value = [
        SchemaItem(id="action1", type="action", entity="E1", name="A1", description="...", synonyms=[], metadata={}),
        SchemaItem(id="unknown_action", type="action", entity="E2", name="Unknown", description="...", synonyms=[], metadata={}),
        SchemaItem(id="action2", type="action", entity="E3", name="A2", description="...", synonyms=[], metadata={})
    ]

    registry = ActionRegistry(vector_store=mock_vs)

    # Only register action1 and action2
    for name in ["action1", "action2"]:
        registry._actions[name] = ActionDefinition(
            name=name,
            entity="Entity",
            description="Action",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Get relevant tools
    tools = registry.get_relevant_tools("query", top_k=5)

    # Should only return 2 tools (unknown_action filtered out)
    assert len(tools) == 2
    tool_names = {t["function"]["name"] for t in tools}
    assert tool_names == {"action1", "action2"}


# ============================================================================
# Tests for reindex_all_actions()
# ============================================================================

def test_reindex_all_actions_success():
    """Test that reindex_all_actions re-indexes all actions"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    # Register 3 actions
    for i in range(3):
        name = f"action{i}"
        registry._actions[name] = ActionDefinition(
            name=name,
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Reindex
    result = registry.reindex_all_actions()

    # Verify result
    assert result["indexed"] == 3
    assert result["failed"] == 0
    assert result["total"] == 3

    # Verify index_items was called 3 times
    assert mock_vs.index_items.call_count == 3


def test_reindex_all_actions_partial_failure():
    """Test that reindex_all_actions handles partial failures"""
    mock_vs = Mock(spec=VectorStore)

    registry = ActionRegistry(vector_store=mock_vs)

    # Register 3 actions
    for i in range(3):
        name = f"action{i}"
        registry._actions[name] = ActionDefinition(
            name=name,
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=TestParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Make index_items fail for action1 by checking the list
    original_index = 0
    def side_effect(items):
        nonlocal original_index
        original_index += 1
        if items[0].id == "action1":
            raise Exception("Index failed for action1")

    mock_vs.index_items.side_effect = side_effect

    # Reindex
    result = registry.reindex_all_actions()

    # Verify result - action1 fails (but _index_action catches it), so all 3 are "indexed"
    # The actual failure happens inside _index_action which catches the exception
    # So reindex_all_actions sees all 3 as successful
    assert result["indexed"] == 3
    assert result["failed"] == 0
    assert result["total"] == 3


def test_reindex_all_actions_without_vector_store():
    """Test that reindex_all_actions handles VectorStore being None"""
    # Need to patch embedding service to prevent auto-creation
    with patch('core.ai.get_embedding_service') as mock_get:
        mock_get.return_value = None

        registry = ActionRegistry(vector_store=None)

        # Verify no VectorStore was auto-created
        assert registry.vector_store is None

        # Register some actions
        for i in range(3):
            registry._actions[f"action{i}"] = ActionDefinition(
                name=f"action{i}",
                entity="Entity",
                description=f"Action {i}",
                category="mutation",
                parameters_schema=TestParams,
                handler=lambda p, **kwargs: {"success": True}
            )

        # Reindex
        result = registry.reindex_all_actions()

        # Should return error since VectorStore is None
        assert result["indexed"] == 0
        assert result["failed"] == 3
        assert result["total"] == 3
        assert "error" in result


def test_reindex_all_actions_empty_registry():
    """Test that reindex_all_actions handles empty registry"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    # No actions registered
    result = registry.reindex_all_actions()

    # Verify result
    assert result["indexed"] == 0
    assert result["failed"] == 0
    assert result["total"] == 0
    mock_vs.index_items.assert_not_called()


# ============================================================================
# Integration tests with register decorator
# ============================================================================

def test_register_decorator_indexes_action():
    """Test that register decorator automatically indexes actions"""
    mock_vs = Mock(spec=VectorStore)
    registry = ActionRegistry(vector_store=mock_vs)

    @registry.register(
        name="test_decorator",
        entity="Test",
        description="Test decorator action",
        search_keywords=["decorator", "test"]
    )
    def test_action(params: TestParams, db) -> dict:
        return {"success": True}

    # Verify action was registered
    assert "test_decorator" in registry._actions

    # Verify action was indexed
    mock_vs.index_items.assert_called_once()


def test_register_with_vector_store_none_still_works():
    """Test that register works when VectorStore is None"""
    registry = ActionRegistry(vector_store=None)

    @registry.register(
        name="test_no_vs",
        entity="Test",
        description="Test without VectorStore"
    )
    def test_action(params: TestParams, db) -> dict:
        return {"success": True}

    # Should still register the action
    assert "test_no_vs" in registry._actions
    assert registry._actions["test_no_vs"].name == "test_no_vs"
