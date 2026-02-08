"""
tests/core/test_vector_store.py

Unit tests for VectorStore and SchemaItem
"""
import pytest
import sqlite3

from core.ai.vector_store import SchemaItem, VectorStore
from core.ai.embedding import EmbeddingService


class TestSchemaItem:
    """Test suite for SchemaItem dataclass"""

    def test_create_schema_item(self):
        """Test creating a SchemaItem"""
        item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Guest's full name"
        )

        assert item.id == "Guest.name"
        assert item.type == "property"
        assert item.entity == "Guest"
        assert item.name == "name"
        assert item.description == "Guest's full name"

    def test_schema_item_with_synonyms(self):
        """Test SchemaItem with synonyms"""
        item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Guest's full name",
            synonyms=["guest_name", "visitor_name"]
        )

        assert item.synonyms == ["guest_name", "visitor_name"]

    def test_to_searchable_text(self):
        """Test generating searchable text from SchemaItem"""
        item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Guest's full name",
            synonyms=["guest_name"]
        )

        text = item.to_searchable_text()

        assert "name" in text
        assert "Guest's full name" in text
        assert "guest_name" in text

    def test_to_dict(self):
        """Test converting SchemaItem to dictionary"""
        item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Guest's full name",
            synonyms=["guest_name"],
            metadata={"key": "value"}
        )

        result = item.to_dict()

        assert result["id"] == "Guest.name"
        assert result["type"] == "property"
        assert result["synonyms"] == ["guest_name"]
        assert result["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """Test creating SchemaItem from dictionary"""
        data = {
            "id": "Guest.name",
            "type": "property",
            "entity": "Guest",
            "name": "name",
            "description": "Guest's full name",
            "synonyms": ["guest_name"],
            "metadata": {"key": "value"}
        }

        item = SchemaItem.from_dict(data)

        assert item.id == "Guest.name"
        assert item.synonyms == ["guest_name"]
        assert item.metadata == {"key": "value"}

    def test_from_dict_with_missing_optional_fields(self):
        """Test from_dict with missing optional fields"""
        data = {
            "id": "Guest.name",
            "type": "property",
            "entity": "Guest",
            "name": "name",
            "description": "Guest's full name"
        }

        item = SchemaItem.from_dict(data)

        assert item.synonyms == []
        assert item.metadata == {}


class TestVectorStore:
    """Test suite for VectorStore"""

    @pytest.fixture
    def embedding_service(self):
        """Create a mock embedding service for testing"""
        service = EmbeddingService(enabled=False)

        # Override embed to return predictable values
        def mock_embed(text):
            # Create deterministic embeddings based on text hash
            import hashlib
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            return [(hash_val % 100) / 100.0] * 1536

        service.embed = mock_embed
        return service

    @pytest.fixture
    def vector_store(self, embedding_service):
        """Create an in-memory vector store for testing"""
        store = VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        )
        yield store
        store.close()

    @pytest.fixture
    def sample_items(self):
        """Create sample SchemaItem objects for testing"""
        return [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest's full name",
                synonyms=["guest_name"]
            ),
            SchemaItem(
                id="Guest.phone",
                type="property",
                entity="Guest",
                name="phone",
                description="Guest's phone number"
            ),
            SchemaItem(
                id="Room.status",
                type="property",
                entity="Room",
                name="status",
                description="Current room status"
            ),
            SchemaItem(
                id="walkin_checkin",
                type="action",
                entity="Guest",
                name="walkin_checkin",
                description="Direct check-in without reservation"
            ),
        ]

    def test_vector_store_init(self, embedding_service):
        """Test VectorStore initialization"""
        store = VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        )

        assert store.db_path == ":memory:"
        assert store.embedding_dim == 1536
        assert store.conn is not None

        store.close()

    def test_index_items(self, vector_store, sample_items):
        """Test indexing schema items"""
        vector_store.index_items(sample_items)

        stats = vector_store.get_stats()
        assert stats["total_items"] == 4

    def test_index_empty_list(self, vector_store):
        """Test indexing empty list"""
        vector_store.index_items([])

        stats = vector_store.get_stats()
        assert stats["total_items"] == 0

    def test_get_item(self, vector_store, sample_items):
        """Test retrieving a specific item"""
        vector_store.index_items(sample_items)

        item = vector_store.get_item("Guest.name")

        assert item is not None
        assert item.id == "Guest.name"
        assert item.type == "property"

    def test_get_item_not_found(self, vector_store):
        """Test retrieving non-existent item"""
        item = vector_store.get_item("NonExistent")

        assert item is None

    def test_list_items_all(self, vector_store, sample_items):
        """Test listing all items"""
        vector_store.index_items(sample_items)

        items = vector_store.list_items()

        assert len(items) == 4

    def test_list_items_filtered_by_type(self, vector_store, sample_items):
        """Test listing items filtered by type"""
        vector_store.index_items(sample_items)

        items = vector_store.list_items(item_type="property")

        assert len(items) == 3
        for item in items:
            assert item.type == "property"

    def test_list_items_filtered_by_entity(self, vector_store, sample_items):
        """Test listing items filtered by entity"""
        vector_store.index_items(sample_items)

        items = vector_store.list_items(entity_filter="Guest")

        assert len(items) == 3
        for item in items:
            assert item.entity == "Guest"

    def test_list_items_filtered_by_type_and_entity(self, vector_store, sample_items):
        """Test listing items filtered by both type and entity"""
        vector_store.index_items(sample_items)

        items = vector_store.list_items(item_type="property", entity_filter="Guest")

        assert len(items) == 2
        for item in items:
            assert item.type == "property"
            assert item.entity == "Guest"

    def test_delete_item(self, vector_store, sample_items):
        """Test deleting an item"""
        vector_store.index_items(sample_items)

        result = vector_store.delete_item("Guest.name")

        assert result is True
        assert vector_store.get_item("Guest.name") is None

    def test_delete_item_not_found(self, vector_store):
        """Test deleting non-existent item"""
        result = vector_store.delete_item("NonExistent")

        assert result is False

    def test_clear(self, vector_store, sample_items):
        """Test clearing all items"""
        vector_store.index_items(sample_items)
        assert vector_store.get_stats()["total_items"] == 4

        vector_store.clear()

        assert vector_store.get_stats()["total_items"] == 0

    def test_get_stats(self, vector_store, sample_items):
        """Test getting index statistics"""
        vector_store.index_items(sample_items)

        stats = vector_store.get_stats()

        assert stats["total_items"] == 4
        assert stats["embedding_dim"] == 1536
        assert "property.Guest" in stats["by_type_entity"]
        assert "property.Room" in stats["by_type_entity"]
        assert "action.Guest" in stats["by_type_entity"]

    def test_context_manager(self, embedding_service):
        """Test using VectorStore as context manager"""
        with VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        ) as store:
            assert store.conn is not None

        # Connection should be closed after exiting context
        # (can't directly test conn.closed, but this ensures __exit__ was called)

    def test_float_array_to_bytes(self):
        """Test converting float array to bytes"""
        arr = [0.1, 0.2, 0.3, 0.4]
        result = VectorStore._float_array_to_bytes(arr)

        assert isinstance(result, bytes)
        assert len(result) == 4 * 4  # 4 floats * 4 bytes each

    def test_bytes_to_float_array(self):
        """Test converting bytes back to float array"""
        arr = [0.1, 0.2, 0.3, 0.4]
        bytes_data = VectorStore._float_array_to_bytes(arr)
        result = VectorStore._bytes_to_float_array(bytes_data)

        # Values might have small floating point differences
        assert len(result) == len(arr)
        for i, val in enumerate(result):
            assert abs(val - arr[i]) < 0.0001


class TestVectorStoreIntegration:
    """Integration tests for VectorStore with real operations"""

    @pytest.fixture
    def embedding_service(self):
        """Create embedding service with mock embeddings"""
        service = EmbeddingService(enabled=False)

        def mock_embed(text):
            # Create embeddings based on character codes for variety
            import hashlib
            hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            base = [(hash_val % 100) / 100.0] * 1536
            return base

        service.embed = mock_embed

        def mock_batch_embed(texts):
            return [mock_embed(text) for text in texts]

        service.batch_embed = mock_batch_embed

        return service

    @pytest.fixture
    def vector_store(self, embedding_service):
        """Create vector store"""
        store = VectorStore(
            db_path=":memory:",
            embedding_service=embedding_service
        )
        yield store
        store.close()

    def test_search_returns_items(self, vector_store):
        """Test that search returns indexed items"""
        items = [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest's full name"
            ),
            SchemaItem(
                id="Room.status",
                type="property",
                entity="Room",
                name="status",
                description="Current room status"
            ),
        ]

        vector_store.index_items(items)
        results = vector_store.search("guest name", top_k=5)

        # Should return at least one result
        assert len(results) >= 1

    def test_search_with_type_filter(self, vector_store):
        """Test search with type filter"""
        items = [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest's full name"
            ),
            SchemaItem(
                id="checkin",
                type="action",
                entity="Guest",
                name="checkin",
                description="Check in a guest"
            ),
        ]

        vector_store.index_items(items)

        results = vector_store.search("guest", item_type="property")
        assert all(r.type == "property" for r in results)

    def test_search_with_entity_filter(self, vector_store):
        """Test search with entity filter"""
        items = [
            SchemaItem(
                id="Guest.name",
                type="property",
                entity="Guest",
                name="name",
                description="Guest's full name"
            ),
            SchemaItem(
                id="Room.status",
                type="property",
                entity="Room",
                name="status",
                description="Current room status"
            ),
        ]

        vector_store.index_items(items)

        results = vector_store.search("name", entity_filter="Guest")
        assert all(r.entity == "Guest" for r in results)

    def test_update_existing_item(self, vector_store):
        """Test that indexing an existing item updates it"""
        item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Original description"
        )

        vector_store.index_items([item])

        # Update with new description
        updated_item = SchemaItem(
            id="Guest.name",
            type="property",
            entity="Guest",
            name="name",
            description="Updated description"
        )

        vector_store.index_items([updated_item])

        retrieved = vector_store.get_item("Guest.name")
        assert retrieved.description == "Updated description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
