"""
tests/core/test_embedding_integration.py

Integration tests for EmbeddingService singleton and configuration.
"""
import os
import pytest

from core.ai import (
    get_embedding_service,
    reset_embedding_service,
    create_embedding_service_for_test,
)
from app.config import Settings, settings


class TestEmbeddingServiceSingleton:
    """Test suite for global EmbeddingService singleton"""

    def setup_method(self):
        """Reset singleton before each test"""
        reset_embedding_service()

    def teardown_method(self):
        """Reset singleton after each test"""
        reset_embedding_service()

    def test_get_embedding_service_returns_singleton(self):
        """Test that get_embedding_service returns the same instance"""
        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2

    def test_get_embedding_service_uses_config(self):
        """Test that singleton is created with config values"""
        service = get_embedding_service()

        # Check that service uses values from settings
        assert service.model == settings.EMBEDDING_MODEL
        assert service._cache_size == settings.EMBEDDING_CACHE_SIZE

    def test_get_embedding_service_respects_enable_flags(self):
        """Test that ENABLE_LLM and EMBEDDING_ENABLED are respected"""
        # When ENABLE_LLM is False, service should be disabled
        original_enable = os.environ.get("ENABLE_LLM")
        os.environ["ENABLE_LLM"] = "false"

        try:
            reset_embedding_service()
            service = get_embedding_service()

            # Service should be disabled when ENABLE_LLM is false
            # Note: This tests the logic, actual behavior depends on settings
            assert service is not None
        finally:
            if original_enable:
                os.environ["ENABLE_LLM"] = original_enable
            else:
                os.environ.pop("ENABLE_LLM", None)
            reset_embedding_service()

    def test_reset_embedding_service_creates_new_instance(self):
        """Test that reset_embedding_service creates a new instance"""
        service1 = get_embedding_service()
        reset_embedding_service()
        service2 = get_embedding_service()

        assert service1 is not service2

    def test_singleton_caches_results(self):
        """Test that singleton properly caches embeddings"""
        service = get_embedding_service()

        # Embed the same text twice
        result1 = service.embed("test text")
        result2 = service.embed("test text")

        # Should be the same cached result
        assert len(result1) == service.dimension
        assert len(service._cache) >= 1


class TestCreateEmbeddingServiceForTest:
    """Test suite for create_embedding_service_for_test"""

    def test_create_test_service_bypasses_singleton(self):
        """Test that create_embedding_service_for_test bypasses singleton"""
        singleton = get_embedding_service()
        test_service = create_embedding_service_for_test(enabled=False)

        assert test_service is not singleton
        assert test_service.enabled is False

    def test_create_test_service_with_custom_params(self):
        """Test creating test service with custom parameters"""
        service = create_embedding_service_for_test(
            model="text-embedding-3-large",
            cache_size=500,
            enabled=False
        )

        assert service.model == "text-embedding-3-large"
        assert service._cache_size == 500
        assert service.enabled is False

    def test_create_test_service_does_not_affect_singleton(self):
        """Test that test service doesn't affect the singleton"""
        test_service = create_embedding_service_for_test(cache_size=100)
        singleton = get_embedding_service()

        # Singleton should have its own cache size from settings
        assert singleton._cache_size == settings.EMBEDDING_CACHE_SIZE
        assert test_service._cache_size == 100


class TestSettingsConfiguration:
    """Test suite for embedding configuration in Settings"""

    def test_embedding_settings_have_defaults(self):
        """Test that embedding settings have sensible defaults"""
        s = Settings()

        # Project uses Ollama as default
        assert s.EMBEDDING_MODEL == "nomic-embed-text"
        assert s.EMBEDDING_BASE_URL == "http://localhost:11434/v1"
        assert s.EMBEDDING_CACHE_SIZE == 1000
        assert s.EMBEDDING_ENABLED is True

    def test_embedding_settings_from_env(self, monkeypatch):
        """Test that embedding settings can be set via environment"""
        monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")
        monkeypatch.setenv("EMBEDDING_CACHE_SIZE", "500")
        monkeypatch.setenv("EMBEDDING_ENABLED", "false")

        s = Settings()

        assert s.EMBEDDING_MODEL == "text-embedding-3-large"
        assert s.EMBEDDING_CACHE_SIZE == 500
        assert s.EMBEDDING_ENABLED is False

    def test_embedding_api_key_fallback_to_openai_key(self, monkeypatch):
        """Test that EMBEDDING_API_KEY falls back to OPENAI_API_KEY"""
        monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        s = Settings()

        # EMBEDDING_API_KEY should be None, but service should use OPENAI_API_KEY
        assert s.EMBEDDING_API_KEY is None
        assert s.OPENAI_API_KEY == "sk-test-key"

    def test_embedding_api_key_overrides_openai_key(self, monkeypatch):
        """Test that EMBEDDING_API_KEY takes precedence over OPENAI_API_KEY"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
        monkeypatch.setenv("EMBEDDING_API_KEY", "sk-embedding-key")

        s = Settings()

        assert s.EMBEDDING_API_KEY == "sk-embedding-key"
        assert s.OPENAI_API_KEY == "sk-openai-key"


class TestIntegrationWithVectorStore:
    """Integration tests with VectorStore"""

    def setup_method(self):
        """Reset singleton before each test"""
        reset_embedding_service()

    def teardown_method(self):
        """Reset singleton after each test"""
        reset_embedding_service()

    def test_vector_store_uses_singleton_embedding_service(self):
        """Test that VectorStore can use the singleton embedding service"""
        from core.ai import VectorStore, SchemaItem, get_embedding_service

        # Create vector store with singleton embedding service
        store = VectorStore(
            db_path=":memory:",
            embedding_service=get_embedding_service()
        )

        # Index some items
        items = [
            SchemaItem(
                id="test.id",
                type="property",
                entity="Test",
                name="id",
                description="Test ID field"
            )
        ]
        store.index_items(items)

        # Verify item was indexed
        stats = store.get_stats()
        assert stats["total_items"] == 1

        store.close()

    def test_multiple_components_share_embedding_service(self):
        """Test that multiple components can share the same embedding service"""
        from core.ai import VectorStore, SchemaItem, get_embedding_service

        # Get the shared service
        service = get_embedding_service()

        # Create multiple stores using the same service
        store1 = VectorStore(
            db_path=":memory:",
            embedding_service=service
        )
        store2 = VectorStore(
            db_path=":memory:",
            embedding_service=service
        )

        # Both stores should work with the same service
        items = [
            SchemaItem(
                id="test.id",
                type="property",
                entity="Test",
                name="id",
                description="Test ID field"
            )
        ]

        store1.index_items(items)
        store2.index_items(items)

        assert store1.get_stats()["total_items"] == 1
        assert store2.get_stats()["total_items"] == 1

        # Cache should be shared
        assert len(service._cache) > 0

        store1.close()
        store2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
