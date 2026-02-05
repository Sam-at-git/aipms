"""
core/ooda/orient.py

Orient 阶段 - OODA Loop 第二步
负责上下文注入、意图识别和实体提取
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import logging

from core.ooda.observe import Observation
from core.ooda.intent import IntentResult, IntentRecognitionService
from core.security.context import security_context_manager, SecurityContext

logger = logging.getLogger(__name__)


@dataclass
class Orientation:
    """
    导向结果 - Orient 阶段的输出

    Attributes:
        observation: Observe 阶段的结果
        intent: 意图识别结果
        context: 注入的完整上下文
        extracted_entities: 提取的实体
        confidence: 综合置信度
        metadata: 额外元数据
        timestamp: 导向时间戳
        is_valid: 导向是否有效
        errors: 错误列表
    """

    observation: Observation
    intent: Optional[IntentResult]
    context: Dict[str, Any] = field(default_factory=dict)
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "observation": self.observation.to_dict(),
            "intent": {
                "action_type": self.intent.action_type,
                "confidence": self.intent.confidence,
                "entities": self.intent.entities,
                "requires_confirmation": self.intent.requires_confirmation,
            } if self.intent else None,
            "context": self.context,
            "extracted_entities": self.extracted_entities,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "is_valid": self.is_valid,
            "errors": self.errors,
        }


class ContextProvider(ABC):
    """上下文提供者接口"""

    @abstractmethod
    def provide(self) -> Dict[str, Any]:
        """
        提供上下文数据

        Returns:
            上下文字典
        """
        raise NotImplementedError("Subclasses must implement provide()")


class SecurityContextProvider(ContextProvider):
    """安全上下文提供者"""

    def provide(self) -> Dict[str, Any]:
        """提供当前安全上下文"""
        context = security_context_manager.get_context()
        if context is None:
            return {}

        return {
            "user_id": context.user_id,
            "username": context.username,
            "role": context.role,
            "security_level": context.security_level.value if context.security_level else None,
            "is_admin": context.is_admin(),
        }


class StaticContextProvider(ContextProvider):
    """静态上下文提供者"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def provide(self) -> Dict[str, Any]:
        """提供静态上下文数据"""
        return self._data.copy()


class CompositeContextProvider(ContextProvider):
    """组合上下文提供者"""

    def __init__(self, providers: List[ContextProvider]):
        self._providers = providers

    def provide(self) -> Dict[str, Any]:
        """合并所有提供者的上下文"""
        result = {}
        for provider in self._providers:
            result.update(provider.provide())
        return result


class OrientPhase:
    """
    Orient 阶段 - OODA Loop 第二步

    特性：
    - 上下文注入（可扩展的提供者链）
    - 意图识别（通过 IntentRecognitionService）
    - 实体提取
    - 置信度计算

    Example:
        >>> intent_service = IntentRecognitionService(strategy)
        >>> orient = OrientPhase(intent_service)
        >>> observation = Observation(raw_input="...", normalized_input="...")
        >>> orientation = orient.orient(observation)
        >>> print(orientation.intent.action_type)
    """

    def __init__(self, intent_service: IntentRecognitionService):
        """
        初始化 Orient 阶段

        Args:
            intent_service: 意图识别服务
        """
        self._intent_service = intent_service
        self._context_providers: List[ContextProvider] = []

        # 默认上下文提供者
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """设置默认上下文提供者"""
        # 默认添加安全上下文提供者
        self.add_context_provider(SecurityContextProvider())

    def add_context_provider(self, provider: ContextProvider) -> None:
        """
        添加上下文提供者

        Args:
            provider: 上下文提供者
        """
        self._context_providers.append(provider)
        logger.debug(f"Added context provider: {provider.__class__.__name__}")

    def remove_context_provider(self, provider: ContextProvider) -> None:
        """
        移除上下文提供者

        Args:
            provider: 要移除的上下文提供者
        """
        if provider in self._context_providers:
            self._context_providers.remove(provider)
            logger.debug(f"Removed context provider: {provider.__class__.__name__}")

    def clear_context_providers(self) -> None:
        """清空所有上下文提供者"""
        self._context_providers.clear()
        logger.debug("Cleared all context providers")

    def orient(self, observation: Observation) -> Orientation:
        """
        执行导向阶段

        Args:
            observation: Observe 阶段的观察结果

        Returns:
            导向结果
        """
        logger.debug(f"Orienting observation: {observation.normalized_input[:50]}...")

        errors = []
        is_valid = True

        # 1. 收集上下文
        context = {}
        for provider in self._context_providers:
            try:
                provider_context = provider.provide()
                context.update(provider_context)
            except Exception as e:
                logger.warning(f"Context provider {provider.__class__.__name__} failed: {e}")
                errors.append(f"Context provider failed: {e}")

        # 2. 意图识别
        intent = None
        confidence = 0.0

        if observation.is_valid:
            try:
                intent = self._intent_service.recognize(
                    observation.normalized_input,
                    context=context,
                )
                confidence = intent.confidence
            except Exception as e:
                logger.error(f"Intent recognition failed: {e}")
                errors.append(f"Intent recognition failed: {e}")
                is_valid = False
        else:
            errors.extend(observation.validation_errors)
            is_valid = False

        # 3. 提取实体
        extracted_entities = {}
        if intent:
            extracted_entities = intent.entities.copy()

        # 4. 创建导向结果
        orientation = Orientation(
            observation=observation,
            intent=intent,
            context=context,
            extracted_entities=extracted_entities,
            confidence=confidence,
            metadata=observation.metadata.copy(),
            is_valid=is_valid,
            errors=errors,
        )

        logger.info(
            f"Orient phase completed: valid={orientation.is_valid}, "
            f"action={orientation.intent.action_type if orientation.intent else 'N/A'}, "
            f"confidence={confidence:.2f}"
        )

        return orientation


# 全局 Orient 阶段实例（延迟初始化，需要传入 intent_service）
_orient_phase_instance: Optional[OrientPhase] = None


def get_orient_phase(intent_service: Optional[IntentRecognitionService] = None) -> OrientPhase:
    """
    获取全局 Orient 阶段实例

    Args:
        intent_service: 意图识别服务（首次调用时必须提供）

    Returns:
        OrientPhase 单例
    """
    global _orient_phase_instance

    if _orient_phase_instance is None:
        if intent_service is None:
            raise ValueError("intent_service must be provided on first call")
        _orient_phase_instance = OrientPhase(intent_service)

    return _orient_phase_instance


def set_orient_phase(orient_phase: OrientPhase) -> None:
    """
    设置全局 Orient 阶段实例（用于测试）

    Args:
        orient_phase: OrientPhase 实例
    """
    global _orient_phase_instance
    _orient_phase_instance = orient_phase


# 导出
__all__ = [
    "Orientation",
    "ContextProvider",
    "SecurityContextProvider",
    "StaticContextProvider",
    "CompositeContextProvider",
    "OrientPhase",
    "get_orient_phase",
    "set_orient_phase",
]
