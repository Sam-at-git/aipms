"""
core/ooda/intent.py

意图识别服务接口 - OODA 循环的 Orient 阶段
定义可插拔的意图识别策略，支持 LLM 和规则两种实现方式
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class IntentResult:
    """
    意图识别结果

    Attributes:
        action_type: 动作类型（如 "checkin", "checkout", "create_reservation"）
        confidence: 置信度（0-1）
        entities: 提取的实体映射（如 {"room_id": 1, "guest_name": "张三"}）
        requires_confirmation: 是否需要用户确认
        raw_response: LLM 原始响应（用于调试）
        missing_fields: 缺失字段列表（用于 Follow-up 模式）
    """

    action_type: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    raw_response: str = ""
    missing_fields: List[Dict[str, Any]] = field(default_factory=list)

    def is_valid(self) -> bool:
        """检查意图是否有效（置信度超过阈值）"""
        return self.confidence >= 0.5


@dataclass
class MissingField:
    """
    缺失字段定义

    Attributes:
        field_name: 字段名称
        display_name: 显示名称
        field_type: 字段类型（string, integer, date, enum 等）
        options: 枚举选项（如果 field_type 是 enum）
        required: 是否必填
    """

    field_name: str
    display_name: str
    field_type: str
    options: Optional[List[str]] = None
    required: bool = True


class IntentRecognitionStrategy(ABC):
    """
    意图识别策略接口 - 抽象基类

    定义了意图识别的策略接口，支持多种实现方式：
    - LLMIntentStrategy: 使用大语言模型进行意图识别
    - RuleIntentStrategy: 使用规则匹配进行意图识别

    Example:
        >>> class CustomStrategy(IntentRecognitionStrategy):
        ...     def recognize(self, input: str) -> IntentResult:
        ...         # 自定义意图识别逻辑
        ...         return IntentResult(action_type="test", confidence=1.0)
    """

    @abstractmethod
    def recognize(self, input: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        识别输入的意图

        Args:
            input: 用户输入（自然语言文本）
            context: 上下文信息（可选）

        Returns:
            IntentResult 对象，包含识别出的意图和实体

        Raises:
            Exception: 当意图识别失败时
        """
        raise NotImplementedError("Subclasses must implement recognize()")


class IntentRecognitionService:
    """
    意图识别服务 - OODA 循环 Orient 阶段的核心

    使用策略模式，支持可插拔的意图识别实现。

    Example:
        >>> llm_strategy = LLMIntentStrategy(llm_client)
        >>> service = IntentRecognitionService(llm_strategy)
        >>> result = service.recognize("帮客人办理入住，房间号101")
        >>> print(result.action_type)  # "checkin"
        >>> print(result.entities)  # {"room_id": 101}
    """

    def __init__(self, strategy: IntentRecognitionStrategy):
        """
        初始化意图识别服务

        Args:
            strategy: 意图识别策略
        """
        self._strategy = strategy

    def recognize(self, input: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        识别用户输入的意图

        Args:
            input: 用户输入（自然语言文本）
            context: 上下文信息（可选）

        Returns:
            IntentResult 对象

        Example:
            >>> result = service.recognize("将客人张三安排到201房间")
            >>> if result.action_type == "change_room":
            ...     room_id = result.entities.get("room_id")
            ...     guest_name = result.entities.get("guest_name")
        """
        return self._strategy.recognize(input, context)

    def set_strategy(self, strategy: IntentRecognitionStrategy) -> None:
        """
        更换意图识别策略

        Args:
            strategy: 新的意图识别策略
        """
        self._strategy = strategy


# 导出
__all__ = [
    "IntentResult",
    "MissingField",
    "IntentRecognitionStrategy",
    "IntentRecognitionService",
]
