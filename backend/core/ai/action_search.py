"""
core/ai/action_search.py

Hybrid search engine for action discovery: keyword-first, embedding fallback.

Core-layer component with zero domain knowledge. Actions register their
keywords at startup, and this engine provides fast keyword matching with
optional vector similarity fallback when keyword results are sparse.

Key components:
- ActionSearchResult: Typed result container with provenance tracking
- ActionSearchEngine: Hybrid keyword + embedding search
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class ActionSearchResult:
    """A single action search result with score and provenance."""
    name: str
    entity: str
    description: str
    score: float
    source: str  # "keyword" | "embedding"


class ActionSearchEngine:
    """Hybrid search: keyword-first, embedding fallback.

    Core-layer component, zero domain knowledge.

    Usage:
        engine = ActionSearchEngine()
        engine.register_keywords("checkin", ["入住", "check-in"], entity="StayRecord", description="办理入住")
        results = engine.search("办理入住")
    """

    def __init__(self, action_registry=None, embedding_service=None):
        self._action_registry = action_registry
        self._embedding_service = embedding_service
        self._keyword_index: Dict[str, List[str]] = {}  # keyword_lower -> [action_names]
        self._action_meta: Dict[str, Dict] = {}  # action_name -> {entity, description}
        self._embeddings: Dict[str, List[float]] = {}  # action_name -> vector
        self._action_texts: Dict[str, str] = {}  # action_name -> searchable text

    def register_keywords(self, action_name: str, keywords: List[str],
                          entity: str = "", description: str = ""):
        """Register keywords for an action. Called by domain at action registration time."""
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in self._keyword_index:
                self._keyword_index[kw_lower] = []
            if action_name not in self._keyword_index[kw_lower]:
                self._keyword_index[kw_lower].append(action_name)

        self._action_meta[action_name] = {"entity": entity, "description": description}
        self._action_texts[action_name] = f"{action_name} {description} {' '.join(keywords)}"

    async def build_embeddings(self):
        """Build embedding index asynchronously at startup."""
        if not self._embedding_service:
            return
        for name, text in self._action_texts.items():
            try:
                vec = await self._embedding_service.embed(text)
                self._embeddings[name] = vec
            except Exception:
                logger.debug(f"Failed to build embedding for action '{name}'")

    def search(self, query: str, user_role: str = "", top_k: int = 5) -> List[ActionSearchResult]:
        """Hybrid search: keyword first, embedding supplement if keyword results < 2."""
        keyword_results = self._keyword_search(query, top_k)

        if len(keyword_results) >= 2 or not self._embeddings:
            return keyword_results[:top_k]

        embedding_results = self._embedding_search(query, top_k)

        # Merge: keyword results first, then embedding supplements
        seen = {r.name for r in keyword_results}
        combined = list(keyword_results)
        for r in embedding_results:
            if r.name not in seen:
                combined.append(r)
                seen.add(r.name)

        return combined[:top_k]

    def _keyword_search(self, query: str, top_k: int) -> List[ActionSearchResult]:
        """Keyword matching against the index."""
        query_lower = query.lower()
        scores: Dict[str, float] = {}

        for kw, action_names in self._keyword_index.items():
            if kw in query_lower:
                for name in action_names:
                    scores[name] = scores.get(name, 0) + 1.0

        results = []
        for name, score in sorted(scores.items(), key=lambda x: -x[1]):
            meta = self._action_meta.get(name, {})
            results.append(ActionSearchResult(
                name=name,
                entity=meta.get("entity", ""),
                description=meta.get("description", ""),
                score=score,
                source="keyword"
            ))
        return results[:top_k]

    def _embedding_search(self, query: str, top_k: int) -> List[ActionSearchResult]:
        """Vector similarity search (requires embedding service)."""
        if not self._embedding_service or not self._embeddings:
            return []

        try:
            query_vec = self._embedding_service.embed_sync(query)
        except Exception:
            return []

        similarities = []
        for name, vec in self._embeddings.items():
            sim = self._cosine_similarity(query_vec, vec)
            similarities.append((name, sim))

        similarities.sort(key=lambda x: -x[1])

        results = []
        for name, sim in similarities[:top_k]:
            if sim < 0.3:
                break
            meta = self._action_meta.get(name, {})
            results.append(ActionSearchResult(
                name=name,
                entity=meta.get("entity", ""),
                description=meta.get("description", ""),
                score=sim,
                source="embedding"
            ))
        return results

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


__all__ = [
    "ActionSearchResult",
    "ActionSearchEngine",
]
