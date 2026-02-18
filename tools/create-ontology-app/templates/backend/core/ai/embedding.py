"""
core/ai/embedding.py

Embedding service with caching for semantic search.

Provides OpenAI-compatible text embedding generation with in-memory caching
to reduce API calls and improve performance.
"""
import os
from collections import OrderedDict
from typing import List, Dict, Any, Optional
from dataclasses import field

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class EmbeddingService:
    """
    Embedding service with caching

    Generates text embeddings using OpenAI-compatible API (text-embedding-3-small).
    Caches results in memory to reduce redundant API calls.

    Configuration:
        - api_key: OpenAI API key (from env or parameter)
        - model: Model name (default: text-embedding-3-small, 1536 dimensions)
        - base_url: API base URL (default: https://api.openai.com)
        - cache_size: Maximum number of cached embeddings

    Example:
        >>> service = EmbeddingService(api_key="sk-...")
        >>> result = service.embed("客人姓名")
        >>> print(result.dimension)  # 1536
    """

    # Model dimensions
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        "nomic-embed-text": 768,
        "nomic-embed-text:latest": 768,
        "mxbai-embed-large": 1024,
        "mxbai-embed-large:latest": 1024,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com",
        cache_size: int = 1000,
        enabled: bool = True
    ):
        """
        Initialize embedding service

        Args:
            api_key: OpenAI API key, reads from OPENAI_API_KEY env if None
            model: Embedding model name
            base_url: API base URL for OpenAI-compatible services
            cache_size: Maximum cache entries (LRU eviction when exceeded)
            enabled: Whether to use real API (False for testing)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: uv add openai")

        self.model = model
        self.base_url = base_url
        self.enabled = enabled
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._cache_size = cache_size

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if self.api_key and enabled:
            self._client = OpenAI(api_key=self.api_key, base_url=base_url, timeout=10.0)
        else:
            self._client = None

    @property
    def dimension(self) -> int:
        """Get embedding dimension for current model"""
        return self.MODEL_DIMENSIONS.get(
            self.model,
            1536  # Default for text-embedding-3-small
        )

    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text

        Caches results to avoid redundant API calls.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector, or None on failure
        """
        # Check cache
        if text in self._cache:
            self._cache.move_to_end(text)  # O(1) LRU touch
            return self._cache[text].copy()

        # Generate new embedding
        if not self._client or not self.enabled:
            # Return zero vector for testing, but still cache it
            embedding = [0.0] * self.dimension
            self._cache_put(text, embedding)
            return embedding.copy()

        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            self._cache_put(text, embedding)
            return embedding.copy()

        except Exception as e:
            import logging
            logging.warning(f"Failed to generate embedding for text '{text[:50]}...': {e}")
            return None

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently

        Uses batch API call when possible for better performance.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        results = []

        # Filter out cached texts
        uncached_texts = []
        uncached_indices = []
        cached_embeddings = [None] * len(texts)

        for i, text in enumerate(texts):
            if text in self._cache:
                self._cache.move_to_end(text)  # O(1) LRU touch
                cached_embeddings[i] = self._cache[text].copy()
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Generate embeddings for uncached texts
        if uncached_texts and self._client and self.enabled:
            try:
                response = self._client.embeddings.create(
                    model=self.model,
                    input=uncached_texts
                )

                for i, embedding_result in enumerate(response.data):
                    idx = uncached_indices[i]
                    text = uncached_texts[i]
                    embedding = embedding_result.embedding

                    cached_embeddings[idx] = embedding
                    results.append(embedding)
                    self._cache_put(text, embedding)

            except Exception as e:
                import logging
                logging.warning(f"Batch embedding failed: {e}")
                # Fill remaining with None to signal failure
                for idx in uncached_indices[len(results):]:
                    cached_embeddings[idx] = None

        elif uncached_texts and (not self.enabled or not self._client):
            # Zero vectors for testing or when client is unavailable, but still cache them
            for i, idx in enumerate(uncached_indices):
                text = uncached_texts[i]
                embedding = [0.0] * self.dimension
                cached_embeddings[idx] = embedding
                self._cache_put(text, embedding)

        return cached_embeddings

    def _cache_put(self, key: str, value: List[float]) -> None:
        """Insert into LRU cache with O(1) eviction."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)  # evict oldest
        self._cache[key] = value

    def clear_cache(self) -> None:
        """Clear the embedding cache"""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with cache_size, cache_entries, and hit_rate (if tracked)
        """
        return {
            "cache_size": self._cache_size,
            "cache_entries": len(self._cache),
            "model": self.model,
            "dimension": self.dimension,
            "enabled": self.enabled
        }

    def is_available(self) -> bool:
        """Check if the embedding service is available"""
        return self._client is not None and self.enabled


# Factory function
def create_embedding_service(
    provider: str = "openai",
    **kwargs
) -> EmbeddingService:
    """
    Create an embedding service instance

    Args:
        provider: Provider name (currently only "openai" supported)
        **kwargs: Additional arguments for EmbeddingService

    Returns:
        EmbeddingService instance
    """
    if provider != "openai":
        raise ValueError(f"Unsupported embedding provider: {provider}")

    return EmbeddingService(**kwargs)


__all__ = [
    "EmbeddingService",
    "create_embedding_service",
]
