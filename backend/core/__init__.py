"""
core - 本体运行时框架

Palantir 式架构的核心框架层，提供通用的业务概念抽象。

该框架独立于具体领域，包含：
- ontology: 本体抽象层（BaseEntity, ObjectProxy, 元数据, 注册中心）
- security: 安全模块（访问控制, 加密脱敏）
- ooda: OODA 循环引擎（Observe, Orient, Decide, Act）
- engine: 核心引擎（事件总线, 规则引擎, 状态机）
- ai: AI 抽象层（LLM 客户端, 提示词构建, HITL）

使用方式:
    >>> from core.ontology import BaseEntity, ObjectProxy
    >>> from core.ontology.metadata import EntityMetadata
    >>> from core.ontology.registry import registry
    >>> from core.ooda import IntentRecognitionService

架构原则:
    - 语义驱动 (Ontology-Driven)
    - 安全内嵌 (Security-Embedded)
    - OODA 循环运行时
    - 人类在环 (Human-in-the-Loop)
"""

# 本体抽象层
from core.ontology.base import BaseEntity, ObjectProxy
from core.ontology.metadata import (
    ParamType,
    ActionParam,
    BusinessRule,
    StateTransition,
    StateMachine,
    ActionMetadata,
    PropertyMetadata,
    EntityMetadata,
)
from core.ontology.registry import OntologyRegistry, registry
from core.ontology.security import SecurityLevel
from core.ontology.link import Link, LinkCollection

# OODA 循环
from core.ooda.intent import (
    IntentResult,
    MissingField,
    IntentRecognitionStrategy,
    IntentRecognitionService,
)

# AI 抽象层
from core.ai.llm_client import (
    LLMClient,
    OpenAICompatibleClient,
    LLMResponse,
    extract_json_from_text,
    create_llm_client,
)
from core.ai.prompt_builder import (
    PromptBuilder,
    PromptContext,
    build_system_prompt,
)
from core.ai.hitl import (
    HITLStrategy,
    ConfirmAlwaysStrategy,
    ConfirmByRiskStrategy,
    ConfirmByPolicyStrategy,
    ConfirmByThresholdStrategy,
    CompositeHITLStrategy,
    ConfirmationLevel,
    ActionRisk,
    create_default_hitl_strategy,
    create_safe_hitl_strategy,
)

__version__ = "0.1.0"

__all__ = [
    # 本体抽象层
    "BaseEntity",
    "ObjectProxy",
    "ParamType",
    "ActionParam",
    "BusinessRule",
    "StateTransition",
    "StateMachine",
    "ActionMetadata",
    "PropertyMetadata",
    "EntityMetadata",
    "OntologyRegistry",
    "registry",
    "SecurityLevel",
    "Link",
    "LinkCollection",
    # OODA 循环
    "IntentResult",
    "MissingField",
    "IntentRecognitionStrategy",
    "IntentRecognitionService",
    # AI 抽象层
    "LLMClient",
    "OpenAICompatibleClient",
    "LLMResponse",
    "extract_json_from_text",
    "create_llm_client",
    "PromptBuilder",
    "PromptContext",
    "build_system_prompt",
    "HITLStrategy",
    "ConfirmAlwaysStrategy",
    "ConfirmByRiskStrategy",
    "ConfirmByPolicyStrategy",
    "ConfirmByThresholdStrategy",
    "CompositeHITLStrategy",
    "ConfirmationLevel",
    "ActionRisk",
    "create_default_hitl_strategy",
    "create_safe_hitl_strategy",
]
