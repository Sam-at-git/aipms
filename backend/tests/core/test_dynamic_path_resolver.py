"""
Tests for SPEC-14: Dynamic semantic_path_resolver (no hardcoded imports)
"""
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import RelationshipMetadata, EntityMetadata
from core.ontology.semantic_path_resolver import SemanticPathResolver


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestDynamicPathResolver:
    """Test SemanticPathResolver uses OntologyRegistry dynamically"""

    def test_resolver_uses_registry_relationships(self, clean_registry):
        """Resolver's relationship_map should come from registry"""
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        resolver = SemanticPathResolver(registry=clean_registry)
        rmap = resolver.relationship_map
        assert "Guest" in rmap
        assert "StayRecord" in rmap["Guest"]
        assert rmap["Guest"]["StayRecord"] == ("stays", "guest_id")

    def test_resolver_uses_registry_models(self, clean_registry):
        """Resolver's model_map should come from registry"""
        class FakeModel:
            pass
        clean_registry.register_model("TestEntity", FakeModel)
        resolver = SemanticPathResolver(registry=clean_registry)
        assert "TestEntity" in resolver.model_map
        assert resolver.model_map["TestEntity"] is FakeModel

    def test_resolver_empty_registry_returns_empty(self, clean_registry):
        """SPEC-R04: With empty registry, resolver returns empty map (no fallback)."""
        resolver = SemanticPathResolver(registry=clean_registry)
        assert len(resolver.relationship_map) == 0

    def test_resolver_uses_registry_relationships(self, clean_registry):
        """When registry has data, resolver uses it."""
        clean_registry.register_relationship("TestEntity", RelationshipMetadata(
            name="items",
            target_entity="TestItem",
            cardinality="one_to_many",
            foreign_key="entity_id",
            foreign_key_entity="TestItem",
        ))
        resolver = SemanticPathResolver(registry=clean_registry)
        rmap = resolver.relationship_map
        assert "TestEntity" in rmap
        assert rmap["TestEntity"]["TestItem"] == ("items", "entity_id")

    def test_resolver_no_import_of_hardcoded_maps(self):
        """Verify the module doesn't import MODEL_MAP or RELATIONSHIP_MAP directly"""
        import inspect
        import core.ontology.semantic_path_resolver as mod
        source = inspect.getsource(mod)
        assert "import MODEL_MAP" not in source
        assert "import RELATIONSHIP_MAP" not in source

    def test_resolver_accepts_none_registry(self):
        """With None registry, should use singleton"""
        resolver = SemanticPathResolver(registry=None)
        assert resolver.registry is not None
