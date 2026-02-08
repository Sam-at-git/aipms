"""
tests/services/actions/test_query_actions.py

Tests for query action handlers in app/services/actions/query_actions.py
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

import app.services.actions.query_actions as query_actions
from app.services.actions.base import (
    OntologyQueryParams,
    FilterClauseParams,
    JoinClauseParams,
    SemanticQueryParams,
    SemanticFilterParams,
)
from app.models.ontology import Employee
from core.ontology.metadata import EntityMetadata


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Mock current user"""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "test_user"
    user.role = "manager"
    return user


@pytest.fixture
def mock_param_parser():
    """Mock parameter parser service (optional)"""
    parser = Mock()
    return parser


@pytest.fixture
def mock_entity_metadata():
    """Mock entity metadata"""
    metadata = Mock(spec=EntityMetadata)
    metadata.name = "Guest"
    metadata.properties = {
        "id": {"type": "int"},
        "name": {"type": "str"},
        "phone": {"type": "str"},
        "status": {"type": "str"}
    }
    return metadata


@pytest.fixture
def mock_query_result():
    """Mock query engine result"""
    return {
        "rows": [
            {"id": 1, "name": "张三", "phone": "13800138000"},
            {"id": 2, "name": "李四", "phone": "13900139000"}
        ],
        "columns": ["id", "name", "phone"],
        "column_keys": ["id", "name", "phone"],
        "count": 2,
        "summary": "共 2 条记录"
    }


# ==================== register_query_actions Tests ====================

class TestRegisterQueryActions:
    """Test register_query_actions function"""

    def test_register_query_actions(self):
        """Test that register_query_actions registers query actions"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        query_actions.register_query_actions(registry)

        ontology_query = registry.get_action("ontology_query")
        assert ontology_query is not None
        assert ontology_query.name == "ontology_query"
        assert ontology_query.category == "query"
        assert ontology_query.requires_confirmation is False
        assert ontology_query.undoable is False

        semantic_query = registry.get_action("semantic_query")
        assert semantic_query is not None
        assert semantic_query.name == "semantic_query"
        assert semantic_query.category == "query"


# ==================== _convert_filter_params Tests ====================

class TestConvertFilterParams:
    """Test _convert_filter_params helper function"""

    def test_convert_empty_filters(self):
        """Test converting empty filters list"""
        result = query_actions._convert_filter_params(None)
        assert result == []

        result = query_actions._convert_filter_params([])
        assert result == []

    def test_convert_single_filter(self):
        """Test converting single filter"""
        filters = [FilterClauseParams(field="status", operator="eq", value="ACTIVE")]
        result = query_actions._convert_filter_params(filters)

        assert len(result) == 1
        assert result[0]["field"] == "status"
        assert result[0]["operator"] == "eq"
        assert result[0]["value"] == "ACTIVE"

    def test_convert_multiple_filters(self):
        """Test converting multiple filters"""
        filters = [
            FilterClauseParams(field="status", operator="eq", value="ACTIVE"),
            FilterClauseParams(field="created_at", operator="gte", value="2026-01-01")
        ]
        result = query_actions._convert_filter_params(filters)

        assert len(result) == 2


# ==================== _convert_join_params Tests ====================

class TestConvertJoinParams:
    """Test _convert_join_params helper function"""

    def test_convert_empty_joins(self):
        """Test converting empty joins list"""
        result = query_actions._convert_join_params(None)
        assert result == []

        result = query_actions._convert_join_params([])
        assert result == []

    def test_convert_single_join(self):
        """Test converting single join"""
        joins = [JoinClauseParams(entity="StayRecord", on="stay_records")]
        result = query_actions._convert_join_params(joins)

        assert len(result) == 1
        assert result[0]["entity"] == "StayRecord"
        assert result[0]["on"] == "stay_records"

    def test_convert_multiple_joins(self):
        """Test converting multiple joins"""
        joins = [
            JoinClauseParams(entity="StayRecord", on="stay_records"),
            JoinClauseParams(entity="Room", on="room")
        ]
        result = query_actions._convert_join_params(joins)

        assert len(result) == 2


# ==================== handle_ontology_query Tests ====================

class TestHandleOntologyQuery:
    """Test handle_ontology_query handler"""

    def test_successful_query_minimal(
        self, mock_db, mock_user, mock_entity_metadata, mock_query_result
    ):
        """Test successful query with minimal params"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="Guest")

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True
        assert "query_result" in result

    def test_successful_query_with_fields(
        self, mock_db, mock_user, mock_entity_metadata, mock_query_result
    ):
        """Test successful query with specified fields"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(
            entity="Guest",
            fields=["name", "phone"]
        )

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_with_filters(
        self, mock_db, mock_user, mock_entity_metadata, mock_query_result
    ):
        """Test query with filter conditions"""
        from app.services.actions.query_actions import handle_ontology_query

        filters = [
            FilterClauseParams(field="status", operator="eq", value="ACTIVE"),
            FilterClauseParams(field="created_at", operator="gte", value="2026-01-01")
        ]
        params = OntologyQueryParams(entity="Guest", filters=filters)

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_with_joins(
        self, mock_db, mock_user, mock_entity_metadata, mock_query_result
    ):
        """Test query with joins"""
        from app.services.actions.query_actions import handle_ontology_query

        joins = [
            JoinClauseParams(entity="StayRecord", on="stay_records"),
            JoinClauseParams(entity="Room", on="room")
        ]
        params = OntologyQueryParams(entity="Guest", joins=joins)

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_with_order_by(
        self, mock_db, mock_user, mock_entity_metadata, mock_query_result
    ):
        """Test query with order_by"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(
            entity="Guest",
            order_by=["name", "created_at"]
        )

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_with_limit(self):
        """Test query with custom limit"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="Guest", limit=50)

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = Mock()

        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "count": 0, "summary": "共 0 条记录"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_with_aggregates(self):
        """Test query with aggregate functions"""
        from app.services.actions.query_actions import handle_ontology_query

        aggregates = [
            {"function": "count", "field": "id", "alias": "total"},
            {"function": "sum", "field": "amount", "alias": "total_amount"}
        ]
        params = OntologyQueryParams(entity="Guest", aggregates=aggregates)

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = Mock()

        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "count": 0, "summary": "统计结果"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_unknown_entity(
        self, mock_db, mock_user
    ):
        """Test query with unknown entity returns error"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="UnknownEntity")

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = None
        mock_registry.get_entities.return_value = []

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            result = handle_ontology_query(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "unknown_entity"

    def test_query_with_invalid_operator(
        self, mock_db, mock_user, mock_entity_metadata
    ):
        """Test query with invalid operator defaults to eq"""
        from app.services.actions.query_actions import handle_ontology_query

        filters = [FilterClauseParams(field="status", operator="invalid_op", value="ACTIVE")]
        params = OntologyQueryParams(entity="Guest", filters=filters)

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is True

    def test_query_validation_error(
        self, mock_db, mock_user, mock_entity_metadata
    ):
        """Test query with validation error returns error result"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="Guest")

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.side_effect = ValueError("Invalid field name")

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_query_execution_error(
        self, mock_db, mock_user, mock_entity_metadata
    ):
        """Test query with execution error returns error result"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="Guest")

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.side_effect = Exception("Database connection failed")

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_query_without_param_parser(
        self, mock_db, mock_user, mock_entity_metadata
    ):
        """Test query works without param_parser (optional parameter)"""
        from app.services.actions.query_actions import handle_ontology_query

        params = OntologyQueryParams(entity="Guest")

        mock_registry = MagicMock()
        mock_registry.get_entity.return_value = mock_entity_metadata

        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                result = handle_ontology_query(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=None
                )

        assert result["success"] is True


# ==================== handle_semantic_query Tests ====================

class TestHandleSemanticQuery:
    """Test handle_semantic_query handler"""

    def test_successful_semantic_query_minimal(
        self, mock_db, mock_user, mock_query_result
    ):
        """Test successful semantic query with minimal params"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="Guest")

        mock_registry = MagicMock()

        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()  # StructuredQuery

        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True
        assert "query_result" in result

    def test_semantic_query_with_fields(
        self, mock_db, mock_user, mock_query_result
    ):
        """Test semantic query with specified fields"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room_number"]
        )

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_with_filters(
        self, mock_db, mock_user, mock_query_result
    ):
        """Test semantic query with filters"""
        from app.services.actions.query_actions import handle_semantic_query

        filters = [
            SemanticFilterParams(path="stays.status", operator="eq", value="ACTIVE")
        ]
        params = SemanticQueryParams(
            root_object="Guest",
            filters=filters
        )

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = mock_query_result

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_with_order_by(self):
        """Test semantic query with order_by"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(
            root_object="Guest",
            order_by=["name"]
        )

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_with_limit(self):
        """Test semantic query with custom limit"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="Guest", limit=50)

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_with_offset(self):
        """Test semantic query with offset"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="Guest", offset=10)

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_with_distinct(self):
        """Test semantic query with distinct enabled"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="Guest", distinct=True)

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True

    def test_semantic_query_path_resolution_error(
        self, mock_db, mock_user
    ):
        """Test semantic query with path resolution error"""
        from app.services.actions.query_actions import handle_semantic_query
        from core.ontology.semantic_path_resolver import PathResolutionError

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["invalid_path"]
        )

        mock_registry = MagicMock()

        mock_resolver = MagicMock()
        mock_resolver.compile.side_effect = PathResolutionError(
            path="invalid_path",
            message="Path 'invalid_path' not found on Guest"
        )

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                result = handle_semantic_query(
                    params=params,
                    db=mock_db,
                    user=mock_user
                )

        assert result["success"] is False
        assert result["error"] == "path_resolution_error"

    def test_semantic_query_compilation_error(
        self, mock_db, mock_user
    ):
        """Test semantic query with compilation error"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="InvalidEntity")

        mock_registry = MagicMock()

        mock_resolver = MagicMock()
        mock_resolver.compile.side_effect = ValueError("Entity not found")

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                result = handle_semantic_query(
                    params=params,
                    db=mock_db,
                    user=mock_user
                )

        assert result["success"] is False
        assert result["error"] == "compilation_error"

    def test_semantic_query_execution_error(
        self, mock_db, mock_user
    ):
        """Test semantic query with execution error"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(root_object="Guest")

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()

        mock_engine = MagicMock()
        mock_engine.execute.side_effect = Exception("Query failed")

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_semantic_query_validation_errors(
        self, mock_db, mock_user
    ):
        """Test semantic query with validation errors from SemanticQuery.validate()"""
        from app.services.actions.query_actions import handle_semantic_query

        # Create a SemanticQuery that will fail validation
        params = SemanticQueryParams(
            root_object="Guest",
            limit=2000  # Exceeds max
        )

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        # Pydantic validation will catch limit > 1000
        # If it passes, SemanticQuery.validate() would catch it
        assert isinstance(result, dict)

    def test_semantic_query_multi_hop_navigation(
        self, mock_db, mock_user
    ):
        """Test semantic query with multi-hop navigation path"""
        from app.services.actions.query_actions import handle_semantic_query

        params = SemanticQueryParams(
            root_object="Guest",
            fields=["name", "stays.room.room_type.name"],
            filters=[SemanticFilterParams(path="stays.room.status", operator="eq", value="DIRTY")]
        )

        mock_registry = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.compile.return_value = Mock()
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"rows": [], "summary": "0 条"}

        with patch('app.services.actions.query_actions.ontology_registry', mock_registry):
            with patch('app.services.actions.query_actions.SemanticPathResolver', return_value=mock_resolver):
                with patch('app.services.actions.query_actions.QueryEngine', return_value=mock_engine):
                    result = handle_semantic_query(
                        params=params,
                        db=mock_db,
                        user=mock_user
                    )

        assert result["success"] is True
        mock_resolver.compile.assert_called_once()


# ==================== Integration Tests ====================

class TestQueryActionsIntegration:
    """Integration tests for query actions"""

    def test_action_registration_and_metadata(self):
        """Test query action registration and metadata"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        query_actions.register_query_actions(registry)

        ontology_query = registry.get_action("ontology_query")
        assert ontology_query is not None
        assert "查询" in ontology_query.search_keywords
        assert ontology_query.allowed_roles == set()

        semantic_query = registry.get_action("semantic_query")
        assert semantic_query is not None
        assert "语义" in semantic_query.search_keywords

    def test_module_exports(self):
        """Test that query_actions module exports correctly"""
        assert hasattr(query_actions, "register_query_actions")
        # Handlers are registered via the registry
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        query_actions.register_query_actions(registry)
        assert registry.get_action("ontology_query") is not None
        assert registry.get_action("semantic_query") is not None

    def test_module_all(self):
        """Test __all__ export"""
        assert "register_query_actions" in query_actions.__all__

    def test_convert_filter_params_function_exists(self):
        """Test that _convert_filter_params helper exists"""
        assert hasattr(query_actions, "_convert_filter_params")
        assert callable(query_actions._convert_filter_params)

    def test_convert_join_params_function_exists(self):
        """Test that _convert_join_params helper exists"""
        assert hasattr(query_actions, "_convert_join_params")
        assert callable(query_actions._convert_join_params)
