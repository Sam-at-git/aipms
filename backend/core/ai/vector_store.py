"""
core/ai/vector_store.py

SQLite-based vector storage for semantic search.

Uses pure Python implementation for compatibility (no external extension required).
Supports indexing schema items (entities, properties, actions) with semantic search.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional, Set, Literal
from dataclasses import dataclass, field, asdict
from functools import lru_cache
import math

from core.ai.embedding import EmbeddingService


@dataclass
class SchemaItem:
    """
    Schema item that can be vector-indexed

    Represents entities, properties, or actions that can be semantically searched.

    Attributes:
        id: Unique identifier (e.g., "Guest.name", "walkin_checkin")
        type: Item type - entity, property, action, or relationship
        entity: Associated entity name (e.g., "Guest")
        name: Display name (e.g., "name")
        description: Semantic description used for embedding generation
        synonyms: Alternative names/aliases for fuzzy matching
        metadata: Additional metadata as JSON dict

    Example:
        >>> item = SchemaItem(
        ...     id="Guest.name",
        ...     type="property",
        ...     entity="Guest",
        ...     name="name",
        ...     description="Guest's full name as shown on ID"
        ... )
    """
    id: str
    type: Literal["entity", "property", "action", "relationship"]
    entity: str
    name: str
    description: str
    synonyms: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_searchable_text(self) -> str:
        """
        Generate text for embedding

        Combines name, description, and synonyms for rich semantic search.
        """
        parts = [self.name, self.description]
        if self.synonyms:
            parts.extend(self.synonyms)
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "type": self.type,
            "entity": self.entity,
            "name": self.name,
            "description": self.description,
            "synonyms": self.synonyms,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaItem":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            type=data["type"],
            entity=data["entity"],
            name=data["name"],
            description=data["description"],
            synonyms=data.get("synonyms", []),
            metadata=data.get("metadata", {})
        )


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors

    Args:
        a: First vector
        b: Second vector

    Returns:
        Similarity score between -1 and 1, where 1 is identical
    """
    if len(a) != len(b):
        raise ValueError("Vectors must have the same length")

    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


class VectorStore:
    """
    SQLite-based vector storage with semantic search

    Uses pure Python cosine similarity for vector search (no external dependencies).
    Stores schema items with their embeddings for semantic retrieval.

    Features:
        - SQLite-based (no external service needed)
        - Pure Python vector similarity (cosine similarity)
        - Supports filtering by type, entity
        - Automatic embedding generation
        - In-memory option for testing

    Example:
        >>> store = VectorStore(":memory:")
        >>> store.index_items([
        ...     SchemaItem(id="Guest.name", type="property", ...),
        ... ])
        >>> results = store.search("guest name", top_k=5)
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        embedding_service: Optional[EmbeddingService] = None,
        embedding_dim: int = 1536
    ):
        """
        Initialize vector store

        Args:
            db_path: SQLite database path (":memory:" for in-memory)
            embedding_service: EmbeddingService instance (creates default if None)
            embedding_dim: Embedding vector dimension
        """
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        self.embedding_service = embedding_service or EmbeddingService(enabled=False)

        # In-memory cache of embeddings for faster search
        self._embeddings_cache: Dict[str, List[float]] = {}

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Create schema_items table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_items (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                entity TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                synonyms TEXT,
                metadata TEXT,
                embedding BLOB
            )
        """)

        # Create index for filtering
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_schema_items_type
            ON schema_items(type)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_schema_items_entity
            ON schema_items(entity)
        """)

        self.conn.commit()

        # Rebuild cache on init
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        """Rebuild in-memory embeddings cache from database"""
        self._embeddings_cache.clear()

        cursor = self.conn.execute("""
            SELECT id, embedding FROM schema_items
            WHERE embedding IS NOT NULL
        """)

        for row in cursor.fetchall():
            item_id = row["id"]
            embedding_blob = row["embedding"]
            if embedding_blob:
                self._embeddings_cache[item_id] = self._bytes_to_float_array(embedding_blob)

    def index_items(self, items: List[SchemaItem]) -> None:
        """
        Index schema items with embeddings

        Args:
            items: List of SchemaItem objects to index

        Note:
            Updates existing items if ID already exists.
        """
        if not items:
            return

        # Generate embeddings for all items
        texts = [item.to_searchable_text() for item in items]
        embeddings = self.embedding_service.batch_embed(texts)

        for item, embedding in zip(items, embeddings):
            # Insert or replace schema item
            self.conn.execute("""
                INSERT OR REPLACE INTO schema_items
                (id, type, entity, name, description, synonyms, metadata, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id,
                item.type,
                item.entity,
                item.name,
                item.description,
                json.dumps(item.synonyms, ensure_ascii=False),
                json.dumps(item.metadata, ensure_ascii=False),
                self._float_array_to_bytes(embedding)
            ))

            # Update cache
            self._embeddings_cache[item.id] = embedding

        self.conn.commit()

    def search(
        self,
        query: str,
        top_k: int = 5,
        item_type: Optional[str] = None,
        entity_filter: Optional[str] = None
    ) -> List[SchemaItem]:
        """
        Semantic search for similar schema items

        Args:
            query: Search query text
            top_k: Maximum number of results to return
            item_type: Filter by item type (entity, property, action, relationship)
            entity_filter: Filter by entity name

        Returns:
            List of SchemaItem objects ranked by similarity
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed(query)

        # Build WHERE clause for filters
        where_conditions = []
        params = []

        if item_type:
            where_conditions.append("type = ?")
            params.append(item_type)

        if entity_filter:
            where_conditions.append("entity = ?")
            params.append(entity_filter)

        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        # Get candidate items from database
        cursor = self.conn.execute(f"""
            SELECT id, type, entity, name, description, synonyms, metadata
            FROM schema_items
            {where_clause}
        """, params)

        # Calculate similarity for each item
        results_with_scores = []
        for row in cursor.fetchall():
            item_id = row["id"]

            # Get embedding from cache
            item_embedding = self._embeddings_cache.get(item_id)
            if not item_embedding:
                # If not in cache, try to get from database
                emb_cursor = self.conn.execute(
                    "SELECT embedding FROM schema_items WHERE id = ?",
                    (item_id,)
                )
                emb_row = emb_cursor.fetchone()
                if emb_row and emb_row["embedding"]:
                    item_embedding = self._bytes_to_float_array(emb_row["embedding"])
                    self._embeddings_cache[item_id] = item_embedding
                else:
                    continue

            # Calculate cosine similarity
            similarity = cosine_similarity(query_embedding, item_embedding)

            item = SchemaItem(
                id=row["id"],
                type=row["type"],
                entity=row["entity"],
                name=row["name"],
                description=row["description"],
                synonyms=json.loads(row["synonyms"]) if row["synonyms"] else [],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {}
            )

            results_with_scores.append((similarity, item))

        # Sort by similarity (descending) and return top_k
        results_with_scores.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results_with_scores[:top_k]]

    def get_item(self, item_id: str) -> Optional[SchemaItem]:
        """
        Retrieve a specific item by ID

        Args:
            item_id: Item ID to retrieve

        Returns:
            SchemaItem if found, None otherwise
        """
        cursor = self.conn.execute("""
            SELECT id, type, entity, name, description, synonyms, metadata
            FROM schema_items
            WHERE id = ?
        """, (item_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return SchemaItem(
            id=row["id"],
            type=row["type"],
            entity=row["entity"],
            name=row["name"],
            description=row["description"],
            synonyms=json.loads(row["synonyms"]) if row["synonyms"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )

    def list_items(
        self,
        item_type: Optional[str] = None,
        entity_filter: Optional[str] = None
    ) -> List[SchemaItem]:
        """
        List all indexed items with optional filtering

        Args:
            item_type: Filter by item type
            entity_filter: Filter by entity name

        Returns:
            List of all matching SchemaItem objects
        """
        conditions = []
        params = []

        if item_type:
            conditions.append("type = ?")
            params.append(item_type)

        if entity_filter:
            conditions.append("entity = ?")
            params.append(entity_filter)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor = self.conn.execute(f"""
            SELECT id, type, entity, name, description, synonyms, metadata
            FROM schema_items
            {where_clause}
            ORDER BY entity, type, name
        """, params)

        results = []
        for row in cursor.fetchall():
            item = SchemaItem(
                id=row["id"],
                type=row["type"],
                entity=row["entity"],
                name=row["name"],
                description=row["description"],
                synonyms=json.loads(row["synonyms"]) if row["synonyms"] else [],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {}
            )
            results.append(item)

        return results

    def delete_item(self, item_id: str) -> bool:
        """
        Delete an item from the index

        Args:
            item_id: ID of item to delete

        Returns:
            True if item was deleted, False if not found
        """
        cursor = self.conn.execute("""
            DELETE FROM schema_items WHERE id = ?
        """, (item_id,))

        # Remove from cache
        if item_id in self._embeddings_cache:
            del self._embeddings_cache[item_id]

        self.conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Clear all indexed items (useful for testing)"""
        self.conn.execute("DELETE FROM schema_items")
        self._embeddings_cache.clear()
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics

        Returns:
            Dict with index size, breakdown by type/entity, etc.
        """
        cursor = self.conn.execute("""
            SELECT
                type,
                entity,
                COUNT(*) as count
            FROM schema_items
            GROUP BY type, entity
            ORDER BY type, entity
        """)

        by_type_entity = {}
        total = 0
        for row in cursor.fetchall():
            type_name, entity, count = row["type"], row["entity"], row["count"]
            key = f"{type_name}.{entity}"
            by_type_entity[key] = count
            total += count

        cursor = self.conn.execute("SELECT COUNT(*) as count FROM schema_items")
        total_items = cursor.fetchone()["count"]

        return {
            "total_items": total_items,
            "by_type_entity": by_type_entity,
            "embedding_dim": self.embedding_dim,
            "cache_size": len(self._embeddings_cache),
            "db_path": self.db_path
        }

    @staticmethod
    def _float_array_to_bytes(arr: List[float]) -> bytes:
        """Convert float array to bytes for storage"""
        import struct
        return struct.pack(f"{len(arr)}f", *arr)

    @staticmethod
    def _bytes_to_float_array(data: bytes) -> List[float]:
        """Convert bytes back to float array"""
        import struct
        fmt = f"{len(data) // 4}f"
        return list(struct.unpack(fmt, data))


__all__ = [
    "VectorStore",
    "SchemaItem",
    "cosine_similarity",
]
