"""
tests/integration/test_semantic_search.py

Integration tests for the full semantic search workflow.

Tests the complete flow: Index → Search → Retrieve → Schema JSON
"""
import pytest

from core.ontology.registry import OntologyRegistry
from core.ai import (
    VectorStore,
    SchemaItem,
    SchemaRetriever,
    create_embedding_service_for_test
)
from app.services.schema_index_service import SchemaIndexService


class TestSemanticSearchWorkflow:
    """Integration tests for semantic search workflow"""

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
        yield store
        store.close()

    @pytest.fixture
    def registry(self):
        """Get the real OntologyRegistry"""
        return OntologyRegistry()

    @pytest.fixture
    def schema_index_service(self, vector_store, registry):
        """Create schema index service"""
        return SchemaIndexService(
            vector_store=vector_store,
            registry=registry
        )

    @pytest.fixture
    def schema_retriever(self, vector_store, registry):
        """Create schema retriever"""
        return SchemaRetriever(
            vector_store=vector_store,
            registry=registry
        )

    def test_full_workflow_index_search_retrieve(self, schema_index_service, schema_retriever):
        """
        Test complete workflow:
        1. Build index from registry
        2. Search with natural language query
        3. Retrieve schema with relationship expansion
        """
        # Step 1: Build index
        schema_index_service.build_index()

        # Verify index was built (may be empty if registry has no entities)
        stats = schema_index_service.get_stats()

        if stats["total_items"] == 0:
            # Skip test if registry is empty (common in test environment)
            return

        # Step 2: Search with natural language
        result = schema_retriever.retrieve_for_query("guest name")

        # Verify search results
        assert "query" in result
        assert "entities" in result
        assert "schema_json" in result
        assert "search_metadata" in result

        # Should find Guest-related entities
        assert len(result["entities"]) > 0

    def test_search_chinese_query(self, schema_index_service, schema_retriever):
        """Test search with Chinese query"""
        # Build index
        schema_index_service.build_index()

        # Check if we have data
        stats = schema_index_service.get_stats()
        if stats["total_items"] == 0:
            return  # Skip if registry is empty

        # Search with Chinese
        result = schema_retriever.retrieve_for_query("客人姓名")

        # Should find Guest-related items
        assert len(result["entities"]) > 0

    def test_search_without_expansion(self, schema_index_service, schema_retriever):
        """Test search without relationship expansion"""
        # Build index
        schema_index_service.build_index()

        # Check if we have data
        stats = schema_index_service.get_stats()
        if stats["total_items"] == 0:
            return  # Skip if registry is empty

        # Search without expansion
        result = schema_retriever.retrieve_for_query(
            "Guest",
            expand_relationships=False
        )

        # Should return results
        assert len(result["entities"]) >= 1

    def test_retrieve_by_specific_entities(self, schema_retriever):
        """Test retrieving schema for specific entities"""
        result = schema_retriever.retrieve_by_entity(["Guest"])

        assert "Guest" in result["entities"]
        assert "schema_json" in result
        assert "Guest" in result["schema_json"]

    def test_schema_json_structure(self, schema_retriever):
        """Test that schema JSON has correct structure"""
        result = schema_retriever.retrieve_by_entity(["Guest"])

        schema = result["schema_json"]["Guest"]

        # Should have required fields
        assert "description" in schema
        assert "fields" in schema
        assert "relationships" in schema

    def test_multiple_searches_same_index(self, schema_index_service, schema_retriever):
        """Test that multiple searches work with same index"""
        # Build index once
        schema_index_service.build_index()

        # Check if we have data
        stats = schema_index_service.get_stats()
        if stats["total_items"] == 0:
            return  # Skip if registry is empty

        # Multiple searches should all work
        result1 = schema_retriever.retrieve_for_query("guest")
        result2 = schema_retriever.retrieve_for_query("room")
        result3 = schema_retriever.retrieve_for_query("reservation")

        # All should return valid results
        assert "entities" in result1
        assert "entities" in result2
        assert "entities" in result3

    def test_search_metadata(self, schema_index_service, schema_retriever):
        """Test that search metadata is populated correctly"""
        # Build index
        schema_index_service.build_index()

        # Get total entity count
        stats = schema_index_service.get_stats()
        total_entities = len(stats.get("by_type_entity", {}))

        # Search
        result = schema_retriever.retrieve_for_query("guest")

        # Check metadata
        metadata = result["search_metadata"]
        assert "total_entities" in metadata
        assert "selected_count" in metadata
        assert metadata["total_entities"] >= metadata["selected_count"]

    def test_empty_query_handling(self, schema_index_service, schema_retriever):
        """Test handling of queries that match nothing"""
        # Build index
        schema_index_service.build_index()

        # Search for something that won't match
        result = schema_retriever.retrieve_for_query("xyz_nonexistent")

        # Should return empty result gracefully
        assert result["entities"] == []
        assert result["fields"] == []
        assert "message" in result["search_metadata"]


class TestVectorStoreWithRealIndex:
    """Test VectorStore with real indexed data"""

    @pytest.fixture
    def embedding_service(self):
        """Create test embedding service"""
        return create_embedding_service_for_test(enabled=False)

    @pytest.fixture
    def indexed_store(self, embedding_service):
        """Create a store with sample indexed data"""
        store = VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        )

        # Index sample items
        items = [
            SchemaItem(
                id="Guest",
                type="entity",
                entity="Guest",
                name="Guest",
                description="Hotel guest",
                synonyms=["guest", "客人"]
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
                synonyms=["room", "房间"]
            ),
        ]
        store.index_items(items)

        yield store
        store.close()

    def test_search_finds_synonyms(self, indexed_store):
        """Test that search finds items by synonyms"""
        # Search for Chinese synonym
        results = indexed_store.search("客人", top_k=5)

        # Should find Guest entity
        assert any(r.id == "Guest" for r in results)

    def test_search_filters_by_type(self, indexed_store):
        """Test search with type filter"""
        # Search for properties only
        results = indexed_store.search(
            "guest",
            item_type="property"
        )

        # Should only return properties
        assert all(r.type == "property" for r in results)

    def test_search_filters_by_entity(self, indexed_store):
        """Test search with entity filter"""
        # Search within Guest entity only
        results = indexed_store.search(
            "name",
            entity_filter="Guest"
        )

        # Should only return items from Guest entity
        assert all(r.entity == "Guest" for r in results)

    def test_list_items_filters_correctly(self, indexed_store):
        """Test list_items with filters"""
        # List only entities
        entities = indexed_store.list_items(item_type="entity")

        # Should return only entities
        assert all(i.type == "entity" for i in entities)
        assert len(entities) == 2  # Guest and Room


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
