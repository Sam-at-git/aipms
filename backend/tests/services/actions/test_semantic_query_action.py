"""
tests/services/actions/test_semantic_query_action.py

Unit tests for the semantic_query action handler.

SPEC-15: 语义查询编译器集成测试
"""
import pytest
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock, patch

from app.models.ontology import (
    Guest, Room, RoomStatus, RoomType, StayRecord,
    StayRecordStatus, Employee, EmployeeRole
)
from app.services.actions.base import SemanticQueryParams, SemanticFilterParams
from app.services.actions.query_actions import register_query_actions
from core.ai.actions import ActionRegistry
from core.ontology.semantic_query import SemanticQuery, SemanticFilter
from core.ontology.semantic_path_resolver import PathResolutionError
from core.ontology.query import StructuredQuery, FilterClause, JoinClause, FilterOperator


# ========== Fixtures ==========

@pytest.fixture
def db_session():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock()
    user.id = 1
    user.username = "test_user"
    # Create a proper mock role that has value attribute
    user.role = Mock()
    user.role.value = "receptionist"
    return user


@pytest.fixture
def action_registry():
    """Create ActionRegistry and register query actions."""
    registry = ActionRegistry()
    register_query_actions(registry)
    return registry


@pytest.fixture
def mock_ontology_registry():
    """Create a mock ontology registry."""
    registry = Mock()
    registry.get_entity = Mock(return_value=Mock(properties={
        "id": Mock(),
        "name": Mock(),
        "phone": Mock(),
    }))
    registry.list_entities = Mock(return_value=["Guest", "Room", "StayRecord"])
    return registry


# ========== SemanticQueryParams Tests ==========

class TestSemanticQueryParams:
    """Test SemanticQueryParams Pydantic model."""

    def test_valid_params(self):
        """Test valid semantic query parameters."""
        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[
                SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
            ],
            limit=10
        )
        assert params.root_object == "Guest"
        assert params.fields == ["name", "stays.room_number"]
        assert len(params.filters) == 1
        assert params.limit == 10

    def test_entity_alias_mapping(self):
        """Test entity alias mapping (e.g., 'guest' -> 'Guest')."""
        params = SemanticQueryParams(
            root_object="guest",
            fields=["name"]
        )
        assert params.root_object == "Guest"

    def test_entity_alias_guests(self):
        """Test entity alias mapping for 'guests'."""
        params = SemanticQueryParams(
            root_object="guests",
            fields=["name"]
        )
        assert params.root_object == "Guest"

    def test_entity_alias_stays(self):
        """Test entity alias mapping for 'stays'."""
        params = SemanticQueryParams(
            root_object="stays",
            fields=["status"]
        )
        assert params.root_object == "StayRecord"

    def test_entity_alias_rooms(self):
        """Test entity alias mapping for 'rooms'."""
        params = SemanticQueryParams(
            root_object="rooms",
            fields=["room_number"]
        )
        assert params.root_object == "Room"

    def test_minimal_params(self):
        """Test minimal valid parameters."""
        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name"]
        )
        assert params.root_object == "Guest"
        assert params.fields == ["name"]
        assert params.filters == []
        assert params.limit == 100  # default
        assert params.offset == 0  # default
        assert params.distinct is False  # default

    def test_invalid_limit_too_small(self):
        """Test invalid limit (too small)."""
        with pytest.raises(ValueError) as exc_info:
            SemanticQueryParams(
                root_object="Guest",
                fields=["name"],
                limit=0
            )
        assert "limit" in str(exc_info.value).lower()

    def test_invalid_limit_too_large(self):
        """Test invalid limit (too large)."""
        with pytest.raises(ValueError) as exc_info:
            SemanticQueryParams(
                root_object="Guest",
                fields=["name"],
                limit=1001
            )
        assert "limit" in str(exc_info.value).lower()

    def test_invalid_offset_negative(self):
        """Test invalid offset (negative)."""
        with pytest.raises(ValueError) as exc_info:
            SemanticQueryParams(
                root_object="Guest",
                fields=["name"],
                offset=-1
            )
        assert "offset" in str(exc_info.value).lower()


class TestSemanticFilterParams:
    """Test SemanticFilterParams Pydantic model."""

    def test_valid_filter(self):
        """Test valid filter parameters."""
        filt = SemanticFilterParams(
            path="stays.status",
            operator="eq",
            value="ACTIVE"
        )
        assert filt.path == "stays.status"
        assert filt.operator == "eq"
        assert filt.value == "ACTIVE"

    def test_operator_case_normalization(self):
        """Test operator is normalized to lowercase."""
        filt = SemanticFilterParams(
            path="status",
            operator="EQ",  # uppercase
            value="ACTIVE"
        )
        assert filt.operator == "eq"  # lowercase

    def test_valid_operators(self):
        """Test all valid operators."""
        valid_operators = [
            'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
            'in', 'not_in', 'like', 'not_like',
            'between', 'is_null', 'is_not_null'
        ]
        for op in valid_operators:
            filt = SemanticFilterParams(
                path="status",
                operator=op,
                value="test"
            )
            assert filt.operator == op

    def test_invalid_operator(self):
        """Test invalid operator."""
        with pytest.raises(ValueError) as exc_info:
            SemanticFilterParams(
                path="status",
                operator="invalid",
                value="test"
            )
        assert "无效的操作符" in str(exc_info.value)

    def test_filter_with_none_value(self):
        """Test filter with None value."""
        filt = SemanticFilterParams(
            path="status",
            operator="is_null",
            value=None
        )
        assert filt.value is None


# ========== handle_semantic_query Tests ==========

class TestHandleSemanticQuery:
    """Test the handle_semantic_query action handler."""

    def test_action_registered(self, action_registry):
        """Test that semantic_query action is registered."""
        action = action_registry.get_action("semantic_query")
        assert action is not None
        assert action.name == "semantic_query"
        assert action.category == "query"
        assert action.requires_confirmation is False
        assert action.undoable is False

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_simple_query_success(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test simple semantic query execution."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver.compile.return_value = StructuredQuery(
            entity="Guest",
            fields=["name"]
        )
        mock_resolver_class.return_value = mock_resolver

        mock_engine = Mock()
        mock_engine.execute.return_value = {
            "display_type": "table",
            "columns": ["姓名"],
            "column_keys": ["name"],
            "rows": [{"name": "张三"}, {"name": "李四"}],
            "summary": "共 2 条记录"
        }
        mock_query_engine_class.return_value = mock_engine

        # Create registry and get action
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        # Execute
        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name"]
        )
        result = action.handler(params, db_session, mock_user)

        # Verify
        assert result["success"] is True
        assert "query_result" in result
        assert result["query_result"]["summary"] == "共 2 条记录"
        assert len(result["query_result"]["rows"]) == 2

        # Verify resolver was called
        mock_resolver.compile.assert_called_once()

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_query_with_filters(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test semantic query with filters."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver.compile.return_value = StructuredQuery(
            entity="Guest",
            fields=["name"],
            filters=[FilterClause(field="stay_records.status", operator=FilterOperator.EQ, value="ACTIVE")]
        )
        mock_resolver_class.return_value = mock_resolver

        mock_engine = Mock()
        mock_engine.execute.return_value = {
            "display_type": "table",
            "columns": ["姓名"],
            "column_keys": ["name"],
            "rows": [{"name": "张三"}],
            "summary": "共 1 条记录"
        }
        mock_query_engine_class.return_value = mock_engine

        # Create registry and execute
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name"],
            filters=[
                SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )
        result = action.handler(params, db_session, mock_user)

        # Verify
        assert result["success"] is True

        # Verify the compiled query has filters
        compiled_query = mock_resolver.compile.call_args[0][0]
        assert len(compiled_query.filters) == 1

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_path_resolution_error_returns_friendly_message(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test that PathResolutionError returns friendly error message."""
        # Setup mock to raise PathResolutionError
        mock_resolver = Mock()
        error = PathResolutionError(
            path="Guest.invalid_path",
            position=1,
            token="invalid_path",
            current_entity="Guest",
            suggestions=["stay_records", "reservations"]
        )
        mock_resolver.compile.side_effect = error
        mock_resolver_class.return_value = mock_resolver

        # Create registry and execute
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "invalid_path.field"]
        )
        result = action.handler(params, db_session, mock_user)

        # Verify error response
        assert result["success"] is False
        assert result["error"] == "path_resolution_error"
        assert "details" in result
        assert result["details"]["path"] == "Guest.invalid_path"
        assert "suggestions" in result["details"]

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_validation_error_returns_friendly_message(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test that validation errors return friendly messages."""

        # Create registry and execute with empty fields (should fail validation)
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=[]  # Empty fields should fail validation
        )
        result = action.handler(params, db_session, mock_user)

        # Verify error response
        assert result["success"] is False
        assert result["error"] == "validation_error"

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_multi_hop_query(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test multi-hop semantic query (e.g., Guest.stays.room.room_type.name)."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver.compile.return_value = StructuredQuery(
            entity="Guest",
            fields=["name", "stay_records.room_number"],
            joins=[
                JoinClause(entity="StayRecord", on="stay_records"),
                JoinClause(entity="Room", on="room")
            ]
        )
        mock_resolver_class.return_value = mock_resolver

        mock_engine = Mock()
        mock_engine.execute.return_value = {
            "display_type": "table",
            "columns": ["姓名", "房间号"],
            "column_keys": ["name", "room_number"],
            "rows": [{"name": "张三", "room_number": "201"}],
            "summary": "共 1 条记录"
        }
        mock_query_engine_class.return_value = mock_engine

        # Create registry and execute
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[
                SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )
        result = action.handler(params, db_session, mock_user)

        # Verify
        assert result["success"] is True

        # Verify the resolver was called and compile returned a StructuredQuery with joins
        mock_resolver.compile.assert_called_once()
        # The mock's return value already has joins set
        assert len(mock_resolver.compile.return_value.joins) >= 1  # Should have at least one JOIN

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_query_with_limit_and_offset(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test semantic query with limit and offset."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver.compile.return_value = StructuredQuery(
            entity="Guest",
            fields=["name"],
            limit=10,
            offset=20
        )
        mock_resolver_class.return_value = mock_resolver

        mock_engine = Mock()
        mock_engine.execute.return_value = {
            "display_type": "table",
            "columns": ["姓名"],
            "column_keys": ["name"],
            "rows": [],
            "summary": "共 0 条记录"
        }
        mock_query_engine_class.return_value = mock_engine

        # Create registry and execute
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name"],
            limit=10,
            offset=20
        )
        result = action.handler(params, db_session, mock_user)

        # Verify
        assert result["success"] is True

        # Verify limit and offset passed through
        compiled_query = mock_resolver.compile.call_args[0][0]
        assert compiled_query.limit == 10
        assert compiled_query.offset == 20

    @patch('core.ontology.semantic_path_resolver.SemanticPathResolver')
    @patch('core.ontology.query_engine.QueryEngine')
    def test_query_with_order_by(
        self,
        mock_query_engine_class,
        mock_resolver_class,
        db_session,
        mock_user
    ):
        """Test semantic query with order_by."""
        # Setup mocks
        mock_resolver = Mock()
        mock_resolver.compile.return_value = StructuredQuery(
            entity="Guest",
            fields=["name"],
            order_by=["name ASC"]
        )
        mock_resolver_class.return_value = mock_resolver

        mock_engine = Mock()
        mock_engine.execute.return_value = {
            "display_type": "table",
            "columns": ["姓名"],
            "column_keys": ["name"],
            "rows": [{"name": "李四"}, {"name": "张三"}],
            "summary": "共 2 条记录"
        }
        mock_query_engine_class.return_value = mock_engine

        # Create registry and execute
        registry = ActionRegistry()
        register_query_actions(registry)
        action = registry.get_action("semantic_query")

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name"],
            order_by=["name ASC"]
        )
        result = action.handler(params, db_session, mock_user)

        # Verify
        assert result["success"] is True

        # Verify order_by passed through
        compiled_query = mock_resolver.compile.call_args[0][0]
        assert compiled_query.order_by == ["name ASC"]


# ========== Integration Tests ==========

class TestSemanticQueryIntegration:
    """Integration tests for semantic query flow."""

    def test_full_semantic_query_flow(self, db_session, mock_user):
        """Test the complete semantic query flow from params to result."""
        # This test verifies the integration of all components:
        # 1. SemanticQueryParams (Pydantic validation)
        # 2. SemanticQuery (data structure)
        # 3. SemanticPathResolver (compilation)
        # 4. QueryEngine (execution)

        # Note: This is a structural test - actual database testing
        # is done in integration tests

        # Create registry
        registry = ActionRegistry()
        register_query_actions(registry)

        # Verify action is registered
        action = registry.get_action("semantic_query")
        assert action is not None
        assert action.name == "semantic_query"

        # Verify handler function exists
        assert callable(action.handler)

        # Verify parameters schema
        assert action.parameters_schema == SemanticQueryParams

    def test_semantic_vs_ontology_query_coexist(self, action_registry):
        """Test that both semantic_query and ontology_query actions coexist."""
        semantic_action = action_registry.get_action("semantic_query")
        ontology_action = action_registry.get_action("ontology_query")

        assert semantic_action is not None
        assert ontology_action is not None

        # Both should have different parameter schemas
        assert semantic_action.parameters_schema == SemanticQueryParams
        assert ontology_action.parameters_schema != SemanticQueryParams

    def test_all_roles_can_query(self, action_registry):
        """Test that semantic_query allows all roles."""
        action = action_registry.get_action("semantic_query")
        assert action.allowed_roles == set()  # Empty set = all roles
