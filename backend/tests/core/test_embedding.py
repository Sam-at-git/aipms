"""
tests/core/test_embedding.py

Unit tests for EmbeddingService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from core.ai.embedding import (
    EmbeddingService,
    EmbeddingResult,
    create_embedding_service
)


class TestEmbeddingService:
    """Test suite for EmbeddingService"""

    def test_init_with_default_params(self):
        """Test initialization with default parameters"""
        service = EmbeddingService(enabled=False)

        assert service.model == "text-embedding-3-small"
        assert service.dimension == 1536
        assert service.enabled is False
        assert service.is_available() is False

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters"""
        service = EmbeddingService(
            model="text-embedding-3-large",
            cache_size=500,
            enabled=False
        )

        assert service.model == "text-embedding-3-large"
        assert service.dimension == 3072
        assert service._cache_size == 500

    def test_dimension_property(self):
        """Test dimension property for different models"""
        assert EmbeddingService(model="text-embedding-3-small", enabled=False).dimension == 1536
        assert EmbeddingService(model="text-embedding-3-large", enabled=False).dimension == 3072
        assert EmbeddingService(model="text-embedding-ada-002", enabled=False).dimension == 1536

    def test_embed_returns_zero_vector_when_disabled(self):
        """Test that embed returns zero vector when service is disabled"""
        service = EmbeddingService(enabled=False)

        result = service.embed("test text")

        assert len(result) == 1536
        assert all(x == 0.0 for x in result)

    def test_embed_caches_results(self):
        """Test that embeddings are cached"""
        service = EmbeddingService(enabled=False)

        # First call
        result1 = service.embed("test text")
        # Second call (should hit cache)
        result2 = service.embed("test text")

        assert len(service._cache) == 1
        assert "test text" in service._cache_order

    def test_embed_cache_lru_eviction(self):
        """Test LRU cache eviction when cache is full"""
        service = EmbeddingService(cache_size=3, enabled=False)

        service.embed("first")
        service.embed("second")
        service.embed("third")
        assert len(service._cache) == 3

        # This should evict "first"
        service.embed("fourth")

        assert len(service._cache) == 3
        assert "first" not in service._cache
        assert "fourth" in service._cache

    def test_batch_embed_with_all_cached(self):
        """Test batch_embed when all texts are cached"""
        service = EmbeddingService(enabled=False)

        # Pre-cache
        service.embed("first")
        service.embed("second")

        results = service.batch_embed(["first", "second"])

        assert len(results) == 2
        assert len(results[0]) == 1536
        assert len(results[1]) == 1536

    def test_batch_embed_with_none_cached(self):
        """Test batch_embed when no texts are cached"""
        service = EmbeddingService(enabled=False)

        results = service.batch_embed(["first", "second", "third"])

        assert len(results) == 3
        for result in results:
            assert len(result) == 1536

    def test_batch_embed_mixed_cached_and_uncached(self):
        """Test batch_embed with some cached and some uncached"""
        service = EmbeddingService(enabled=False)

        # Pre-cache one
        service.embed("first")

        results = service.batch_embed(["first", "second"])

        assert len(results) == 2
        assert len(service._cache) == 2

    def test_clear_cache(self):
        """Test clearing the cache"""
        service = EmbeddingService(enabled=False)

        service.embed("first")
        service.embed("second")
        assert len(service._cache) == 2

        service.clear_cache()
        assert len(service._cache) == 0
        assert len(service._cache_order) == 0

    def test_get_cache_stats(self):
        """Test getting cache statistics"""
        service = EmbeddingService(
            model="text-embedding-3-small",
            cache_size=100,
            enabled=False
        )

        service.embed("test")

        stats = service.get_cache_stats()

        assert stats["cache_size"] == 100
        assert stats["cache_entries"] == 1
        assert stats["model"] == "text-embedding-3-small"
        assert stats["dimension"] == 1536
        assert stats["enabled"] is False

    def test_is_available(self):
        """Test is_available method"""
        service_disabled = EmbeddingService(enabled=False)
        assert service_disabled.is_available() is False

    @patch('core.ai.embedding.OPENAI_AVAILABLE', True)
    def test_embed_with_real_client(self):
        """Test embed with mocked real API client"""
        mock_response = MagicMock()
        mock_response.data[0].embedding = [0.1] * 1536

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(EmbeddingService, '__init__', lambda self, api_key=None, model="text-embedding-3-small", base_url="https://api.openai.com", cache_size=1000, enabled=True: None):
            service = EmbeddingService.__new__(EmbeddingService)
            service.model = "text-embedding-3-small"
            service.base_url = "https://api.openai.com"
            service.enabled = True
            service._client = mock_client
            service._cache = {}
            service._cache_order = []
            service._cache_size = 1000

            result = service.embed("test")

            assert len(result) == 1536
            mock_client.embeddings.create.assert_called_once()


class TestCreateEmbeddingService:
    """Test factory function"""

    def test_create_embedding_service_openai(self):
        """Test creating OpenAI embedding service"""
        service = create_embedding_service(
            provider="openai",
            enabled=False
        )

        assert isinstance(service, EmbeddingService)

    def test_create_embedding_service_unsupported_provider(self):
        """Test error for unsupported provider"""
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            create_embedding_service(provider="unknown")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
