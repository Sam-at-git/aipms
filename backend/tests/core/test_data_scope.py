"""
SPEC-20: Core data scope unit tests
Tests for data_scope.py types, EntityMetadata scope fields, and QueryEngine filtering
"""
import pytest
from core.security.data_scope import (
    DataScopeType, DataScopeLevel, DataScopeContext, IDataScopeResolver
)
from core.ontology.metadata import EntityMetadata


class TestDataScopeTypes:
    """Test DataScopeType enum"""

    def test_global_type(self):
        assert DataScopeType.GLOBAL == "global"

    def test_scoped_type(self):
        assert DataScopeType.SCOPED == "scoped"


class TestDataScopeLevel:
    """Test DataScopeLevel enum"""

    def test_all_level(self):
        assert DataScopeLevel.ALL == "all"

    def test_scope_and_below(self):
        assert DataScopeLevel.SCOPE_AND_BELOW == "scope_and_below"

    def test_scope_only(self):
        assert DataScopeLevel.SCOPE_ONLY == "scope_only"

    def test_self_only(self):
        assert DataScopeLevel.SELF_ONLY == "self_only"


class TestDataScopeContext:
    """Test DataScopeContext creation and defaults"""

    def test_default_context(self):
        ctx = DataScopeContext()
        assert ctx.level == DataScopeLevel.ALL
        assert ctx.scope_ids == set()
        assert ctx.user_id is None
        assert ctx.owner_column == "created_by"

    def test_scoped_context(self):
        ctx = DataScopeContext(
            level=DataScopeLevel.SCOPE_ONLY,
            scope_ids={1, 2, 3},
            user_id=42,
        )
        assert ctx.level == DataScopeLevel.SCOPE_ONLY
        assert ctx.scope_ids == {1, 2, 3}
        assert ctx.user_id == 42

    def test_self_only_context(self):
        ctx = DataScopeContext(
            level=DataScopeLevel.SELF_ONLY,
            user_id=99,
            owner_column="assigned_to",
        )
        assert ctx.level == DataScopeLevel.SELF_ONLY
        assert ctx.user_id == 99
        assert ctx.owner_column == "assigned_to"


class TestEntityMetadataScope:
    """Test EntityMetadata data_scope fields"""

    def test_default_scope_is_global(self):
        meta = EntityMetadata(name="TestEntity", description="Test entity", table_name="test_entities")
        assert meta.data_scope_type == "global"
        assert meta.scope_column is None

    def test_scoped_entity_with_column(self):
        meta = EntityMetadata(
            name="Room",
            description="Room entity",
            table_name="rooms",
            data_scope_type="scoped",
            scope_column="branch_id",
        )
        assert meta.data_scope_type == "scoped"
        assert meta.scope_column == "branch_id"

    def test_global_entity_no_column(self):
        meta = EntityMetadata(
            name="Guest",
            description="Guest entity",
            table_name="guests",
            data_scope_type="global",
        )
        assert meta.data_scope_type == "global"
        assert meta.scope_column is None


class TestIDataScopeResolver:
    """Test IDataScopeResolver interface"""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            IDataScopeResolver()

    def test_can_implement(self):
        class MockResolver(IDataScopeResolver):
            def resolve_scope(self, user_id, role_data_scope, **kwargs):
                return DataScopeContext(level=DataScopeLevel.ALL)

            def get_entity_scope_column(self, entity_name):
                return "branch_id" if entity_name == "Room" else None

        resolver = MockResolver()
        ctx = resolver.resolve_scope(1, "ALL")
        assert ctx.level == DataScopeLevel.ALL
        assert resolver.get_entity_scope_column("Room") == "branch_id"
        assert resolver.get_entity_scope_column("Guest") is None
