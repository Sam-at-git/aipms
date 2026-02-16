"""
tests/core/test_schema_retriever.py

Unit tests for SchemaRetriever.
"""
import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import Optional

from core.ai.schema_retriever import SchemaRetriever
from core.ai import VectorStore, SchemaItem, create_embedding_service_for_test
from core.ontology.metadata import EntityMetadata, PropertyMetadata, ActionMetadata


@dataclass
class _MockRelationshipMetadata:
    """Mock RelationshipMetadata for tests."""
    name: str
    target_entity: str
    cardinality: str
    foreign_key: str = ""
    foreign_key_entity: str = ""
    inverse_name: Optional[str] = None
    description: str = ""


class TestSchemaRetriever:
    """Test suite for SchemaRetriever"""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock OntologyRegistry"""
        registry = MagicMock()

        # Mock entities
        guest_entity = EntityMetadata(
            name="Guest",
            description="Hotel guest",
            table_name="guests",
            is_aggregate_root=True,
            properties={
                "name": PropertyMetadata(
                    name="name",
                    type="string",
                    python_type="str",
                    is_required=True
                ),
                "phone": PropertyMetadata(
                    name="phone",
                    type="string",
                    python_type="str",
                    is_required=True
                )
            }
        )

        room_entity = EntityMetadata(
            name="Room",
            description="Hotel room",
            table_name="rooms",
            is_aggregate_root=False,
            properties={
                "room_number": PropertyMetadata(
                    name="room_number",
                    type="string",
                    python_type="str",
                    is_required=True
                ),
                "status": PropertyMetadata(
                    name="status",
                    type="string",
                    python_type="str",
                    is_required=True
                )
            }
        )

        stay_entity = EntityMetadata(
            name="StayRecord",
            description="Stay record",
            table_name="stay_records",
        )

        registry.get_entities.return_value = [guest_entity, room_entity, stay_entity]
        registry.get_entity.side_effect = lambda name: {
            "Guest": guest_entity,
            "Room": room_entity,
            "StayRecord": stay_entity,
        }.get(name)
        registry.get_actions.return_value = []

        # Mock relationships (replaces hardcoded _RELATIONSHIP_MAP)
        _relationships = {
            "Guest": [
                _MockRelationshipMetadata("stay_records", "StayRecord", "one_to_many"),
            ],
            "StayRecord": [
                _MockRelationshipMetadata("guest", "Guest", "many_to_one"),
                _MockRelationshipMetadata("room", "Room", "many_to_one"),
            ],
        }
        registry.get_relationships.side_effect = lambda name: _relationships.get(name, [])

        return registry

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore"""
        store = MagicMock(spec=VectorStore)
        store.get_stats.return_value = {
            "total_items": 10,
            "by_type_entity": {"entity.Guest": 1, "property.Guest": 2}
        }
        return store

    @pytest.fixture
    def schema_retriever(self, mock_vector_store, mock_registry):
        """Create SchemaRetriever with mocked dependencies"""
        retriever = SchemaRetriever(
            vector_store=mock_vector_store,
            registry=mock_registry
        )
        return retriever

    def test_init_with_defaults(self):
        """Test initialization with default parameters"""
        # This will create real VectorStore with in-memory db
        retriever = SchemaRetriever(vector_store=VectorStore(db_path=":memory:"))
        assert retriever.vector_store is not None
        assert retriever.registry is not None

    def test_retrieve_for_query_returns_schema(self, schema_retriever, mock_vector_store):
        """Test retrieve_for_query returns schema structure"""
        # Mock search results
        mock_vector_store.search.return_value = [
            SchemaItem(
                id="Guest",
                type="entity",
                entity="Guest",
                name="Guest",
                description="Hotel guest"
            )
        ]

        result = schema_retriever.retrieve_for_query("guest name")

        assert "query" in result
        assert "entities" in result
        assert "fields" in result
        assert "schema_json" in result
        assert "search_metadata" in result

    def test_retrieve_for_query_expands_relationships(self, schema_retriever, mock_vector_store):
        """Test that relationships are automatically expanded"""
        # Mock search results for Guest
        mock_vector_store.search.return_value = [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest name"
            )
        ]

        result = schema_retriever.retrieve_for_query("guest name")

        # Should include Guest and its related entity StayRecord
        assert "Guest" in result["entities"]
        assert "StayRecord" in result["entities"]

    def test_retrieve_for_query_without_expansion(self, schema_retriever, mock_vector_store):
        """Test retrieval without relationship expansion"""
        mock_vector_store.search.return_value = [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest name"
            )
        ]

        result = schema_retriever.retrieve_for_query(
            "guest name",
            expand_relationships=False
        )

        # Should only include Guest, not StayRecord
        assert "Guest" in result["entities"]
        assert "StayRecord" not in result["entities"]

    def test_retrieve_by_entity(self, schema_retriever):
        """Test retrieving schema for specific entities"""
        result = schema_retriever.retrieve_by_entity(["Guest", "Room"])

        assert "Guest" in result["entities"]
        assert "Room" in result["entities"]
        assert "schema_json" in result
        assert "Guest" in result["schema_json"]
        assert "Room" in result["schema_json"]

    def test_extract_entities_from_results(self, schema_retriever):
        """Test extracting entities from search results"""
        results = [
            SchemaItem(id="Guest", type="entity", entity="Guest", name="Guest", description=""),
            SchemaItem(id="Guest.name", type="property", entity="Guest", name="name", description=""),
            SchemaItem(id="checkin", type="action", entity="Guest", name="checkin", description=""),
        ]

        entities = schema_retriever._extract_entities(results)

        assert entities == {"Guest"}

    def test_extract_fields_from_results(self, schema_retriever):
        """Test extracting fields from search results"""
        results = [
            SchemaItem(id="Guest.name", type="property", entity="Guest", name="name", description=""),
            SchemaItem(id="Guest.phone", type="property", entity="Guest", name="phone", description=""),
            SchemaItem(id="checkin", type="action", entity="Guest", name="checkin", description=""),
        ]

        fields = schema_retriever._extract_fields(results)

        assert fields == ["Guest.name", "Guest.phone"]

    def test_expand_relationships(self, schema_retriever):
        """Test relationship expansion"""
        entities = {"Guest"}
        expanded, reasons = schema_retriever._expand_relationships(entities)

        # Guest should expand to include StayRecord
        assert "StayRecord" in expanded
        assert len(reasons) > 0
        assert any("Guest -> StayRecord" in r for r in reasons)

    def test_expand_relationships_prevents_circular(self, schema_retriever):
        """Test that expansion prevents infinite loops"""
        # Start with entities that have circular relationships
        entities = {"Guest", "StayRecord"}
        expanded, _ = schema_retriever._expand_relationships(entities)

        # Should not add duplicates
        assert len(expanded) == len(set(expanded))

    def test_build_schema_json(self, schema_retriever):
        """Test building schema JSON for entities"""
        entities = {"Guest"}
        schema = schema_retriever._build_schema_json(entities)

        assert "Guest" in schema
        assert "fields" in schema["Guest"]
        assert "relationships" in schema["Guest"]
        assert "name" in schema["Guest"]["fields"]
        assert "phone" in schema["Guest"]["fields"]

    def test_build_schema_json_with_unknown_entity(self, schema_retriever):
        """Test building schema for entity not in registry"""
        entities = {"UnknownEntity"}
        schema = schema_retriever._build_schema_json(entities)

        # Should return minimal schema
        assert "UnknownEntity" in schema
        assert "fields" in schema["UnknownEntity"]

    def test_empty_result_when_no_matches(self, schema_retriever, mock_vector_store):
        """Test empty result when search returns nothing"""
        mock_vector_store.search.return_value = []

        result = schema_retriever.retrieve_for_query("xyz")

        assert result["entities"] == []
        assert result["fields"] == []
        assert result["schema_json"] == {}
        assert "message" in result["search_metadata"]

    def test_search_metadata_includes_expansion_info(self, schema_retriever, mock_vector_store):
        """Test that search metadata includes expansion reasons"""
        mock_vector_store.search.return_value = [
            SchemaItem(id="Guest", type="entity", entity="Guest", name="Guest", description="")
        ]

        result = schema_retriever.retrieve_for_query("guest")

        metadata = result["search_metadata"]
        assert "expansion_reasons" in metadata
        assert len(metadata["expansion_reasons"]) > 0

    def test_get_index_stats(self, schema_retriever, mock_vector_store):
        """Test getting index statistics"""
        stats = schema_retriever.get_index_stats()

        assert stats == mock_vector_store.get_stats.return_value


class TestSchemaRetrieverIntegration:
    """Integration tests for SchemaRetriever with real components"""

    @pytest.fixture
    def embedding_service(self):
        """Create test embedding service"""
        return create_embedding_service_for_test(enabled=False)

    @pytest.fixture
    def vector_store(self, embedding_service):
        """Create in-memory vector store"""
        store = VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        )

        # Index some sample items
        items = [
            SchemaItem(
                id="Guest",
                type="entity",
                entity="Guest",
                name="Guest",
                description="Hotel guest",
                synonyms=["客人", "住客"]
            ),
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest name"
            ),
            SchemaItem(
                id="Room",
                type="entity",
                entity="Room",
                name="Room",
                description="Hotel room",
                synonyms=["房间", "客房"]
            ),
        ]
        store.index_items(items)

        yield store
        store.close()

    def test_retrieve_for_query_integration(self, vector_store):
        """Test retrieve_for_query with real VectorStore"""
        from core.ontology.registry import OntologyRegistry

        retriever = SchemaRetriever(
            vector_store=vector_store,
            registry=OntologyRegistry()
        )

        result = retriever.retrieve_for_query("客人姓名")

        # Should find Guest-related items
        assert "Guest" in result["entities"]
        assert result["search_metadata"]["selected_count"] >= 1

    def test_retrieve_by_entity_integration(self, vector_store):
        """Test retrieve_by_entity with real registry"""
        from core.ontology.registry import OntologyRegistry

        retriever = SchemaRetriever(
            vector_store=vector_store,
            registry=OntologyRegistry()
        )

        result = retriever.retrieve_by_entity(["Guest"])

        assert "Guest" in result["entities"]
        assert "schema_json" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
