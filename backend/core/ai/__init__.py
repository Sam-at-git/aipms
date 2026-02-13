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
from core.ai.response_generator import (
    OntologyResult,
    ResponseGenerator,
    VALID_RESULT_TYPES,
)

# Global singleton instance (lazy initialized)
_embedding_service: Optional[EmbeddingService] = None

# Module-level configuration (injected by app layer at startup)
_embedding_config: Optional[dict] = None


def configure_embedding_service(
    api_key: str = None,
    base_url: str = None,
    model: str = None,
    cache_size: int = 1000,
    enabled: bool = True,
) -> None:
    """
    Configure the embedding service. Called by app layer at startup.

    Args:
        api_key: API key for embedding service
        base_url: Base URL for embedding API
        model: Model name for embeddings
        cache_size: Cache size for embedding results
        enabled: Whether embedding is enabled
    """
    global _embedding_config, _embedding_service
    _embedding_config = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "cache_size": cache_size,
        "enabled": enabled,
    }
    _embedding_service = None  # Reset singleton so next call uses new config


def get_embedding_service() -> EmbeddingService:
    """
    Get the global EmbeddingService singleton

    Creates the instance on first call with injected configuration.
    If not configured, falls back to trying app.config.settings.

    Returns:
        The global EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        if _embedding_config is not None:
            _embedding_service = EmbeddingService(**_embedding_config)
        else:
            # Not configured - create disabled service
            import logging
            logging.getLogger(__name__).warning(
                "EmbeddingService not configured. Call configure_embedding_service() at startup."
            )
            _embedding_service = EmbeddingService(enabled=False)
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
    "configure_embedding_service",
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
    "OntologyResult",
    "ResponseGenerator",
    "VALID_RESULT_TYPES",
]
