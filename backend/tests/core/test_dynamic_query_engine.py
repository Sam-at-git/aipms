"""
Tests for SPEC-13: Dynamic query engine (no hardcoded maps)
"""
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import RelationshipMetadata, EntityMetadata, PropertyMetadata
from core.ontology.query_engine import get_model_class, get_relationship_info, get_display_name


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestDynamicModelMap:
    """Test get_model_class uses Registry first"""

    def test_get_model_from_registry(self, clean_registry):
        class FakeRoom:
            __tablename__ = "rooms"
        clean_registry.register_model("FakeRoom", FakeRoom)
        result = get_model_class("FakeRoom")
        assert result is FakeRoom

    def test_get_model_fallback_to_import(self, clean_registry):
        """Unregistered entities should raise ValueError (fallback removed)"""
        # After decoupling, get_model_class no longer falls back to app.models
        with pytest.raises(ValueError, match="Unknown entity"):
            get_model_class("Room")


class TestDynamicRelationshipMap:
    """Test get_relationship_info uses Registry"""

    def test_get_relationship_from_registry(self, clean_registry):
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        result = get_relationship_info("Guest", "StayRecord")
        assert result is not None
        assert result == ("stays", "guest_id")

    def test_get_relationship_not_found(self, clean_registry):
        result = get_relationship_info("X", "Y")
        assert result is None


class TestDynamicDisplayName:
    """Test get_display_name uses PropertyMetadata"""

    def test_display_name_from_registry(self, clean_registry):
        entity = EntityMetadata(name="Room", description="Room", table_name="rooms")
        entity.add_property(PropertyMetadata(
            name="room_number", type="string", python_type="str",
            display_name="房号"
        ))
        clean_registry.register_entity(entity)
        assert get_display_name("room_number") == "房号"

    def test_display_name_fallback(self, clean_registry):
        assert get_display_name("unknown_field") == "unknown_field"

    def test_display_name_with_default(self, clean_registry):
        assert get_display_name("unknown", "默认") == "默认"


class TestBackwardCompatibility:
    """Ensure backward compat aliases exist"""

    def test_relationship_map_alias_exists(self):
        from core.ontology.query_engine import RELATIONSHIP_MAP
        # SPEC-R04: RELATIONSHIP_MAP is now a callable returning a dict
        assert callable(RELATIONSHIP_MAP)
        result = RELATIONSHIP_MAP()
        assert isinstance(result, dict)
