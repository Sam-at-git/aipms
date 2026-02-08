"""
core/ai/ - AI 抽象层

提供统一的 LLM 调用接口、提示词构建、人类在环确认策略和向量检索。
"""
from typing import Optional

from core.ai.llm_client import LLMClient, OpenAICompatibleClient
from core.ai.prompt_builder import PromptBuilder
from core.ai.hitl import HITLStrategy, ConfirmAlwaysStrategy, ConfirmByRiskStrategy, ConfirmByPolicyStrategy
from core.ai.query_keywords import QUERY_KEYWORDS, ACTION_KEYWORDS, HELP_KEYWORDS
from core.ai.embedding import EmbeddingService, EmbeddingResult, create_embedding_service
from core.ai.vector_store import VectorStore, SchemaItem
from core.ai.schema_retriever import SchemaRetriever
from core.ai.actions import ActionDefinition, ActionRegistry, ActionCategory
from core.ai.reflexion import (
    ReflexionLoop,
    ExecutionError,
    ReflectionResult,
    AttemptRecord,
    ErrorType
)
from core.ai.debug_logger import (
    DebugLogger,
    DebugSession,
    AttemptLog,
)
from core.ai.replay import (
    ReplayEngine,
    ReplayOverrides,
    ReplayConfig,
    ReplayResult,
    ReplayDiff,
    SessionDiff,
    AttemptDiff,
    PerformanceDiff,
)

# Global singleton instance (lazy initialized)
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the global EmbeddingService singleton

    Creates the instance on first call with configuration from app.config.settings.
    Subsequent calls return the same instance.

    Returns:
        The global EmbeddingService instance

    Example:
        >>> from core.ai import get_embedding_service
        >>> service = get_embedding_service()
        >>> embedding = service.embed("客人姓名")
    """
    global _embedding_service
    if _embedding_service is None:
        # Import here to avoid circular dependency
        from app.config import settings

        # Use EMBEDDING_API_KEY if set, otherwise fall back to OPENAI_API_KEY
        api_key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY

        # Service is only enabled if both ENABLE_LLM and EMBEDDING_ENABLED are true
        # AND we have a valid API key
        enabled = (
            settings.ENABLE_LLM and
            settings.EMBEDDING_ENABLED and
            bool(api_key)
        )

        _embedding_service = EmbeddingService(
            api_key=api_key,
            base_url=settings.EMBEDDING_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            cache_size=settings.EMBEDDING_CACHE_SIZE,
            enabled=enabled
        )
    return _embedding_service


def create_embedding_service_for_test(**kwargs) -> EmbeddingService:
    """
    Create a fresh EmbeddingService instance for testing

    Bypasses the singleton and allows custom configuration.

    Args:
        **kwargs: Arguments passed to EmbeddingService constructor

    Returns:
        A new EmbeddingService instance

    Example:
        >>> service = create_embedding_service_for_test(enabled=False)
        >>> result = service.embed("test")
    """
    return EmbeddingService(**kwargs)


def reset_embedding_service() -> None:
    """
    Reset the global EmbeddingService singleton

    Should be called in tests to ensure test isolation.
    After calling this, the next get_embedding_service() call
    will create a new instance.

    Example:
        >>> reset_embedding_service()
        >>> service = get_embedding_service()  # Fresh instance
    """
    global _embedding_service
    _embedding_service = None


__all__ = [
    "LLMClient",
    "OpenAICompatibleClient",
    "PromptBuilder",
    "HITLStrategy",
    "ConfirmAlwaysStrategy",
    "ConfirmByRiskStrategy",
    "ConfirmByPolicyStrategy",
    "QUERY_KEYWORDS",
    "ACTION_KEYWORDS",
    "HELP_KEYWORDS",
    "EmbeddingService",
    "EmbeddingResult",
    "create_embedding_service",
    "get_embedding_service",
    "create_embedding_service_for_test",
    "reset_embedding_service",
    "VectorStore",
    "SchemaItem",
    "SchemaRetriever",
    "ActionDefinition",
    "ActionRegistry",
    "ActionCategory",
    "ReflexionLoop",
    "ExecutionError",
    "ReflectionResult",
    "AttemptRecord",
    "ErrorType",
    "DebugLogger",
    "DebugSession",
    "AttemptLog",
    "ReplayEngine",
    "ReplayOverrides",
    "ReplayConfig",
    "ReplayResult",
    "ReplayDiff",
    "SessionDiff",
    "AttemptDiff",
    "PerformanceDiff",
]
