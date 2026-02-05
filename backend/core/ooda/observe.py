"""
core/ooda/observe.py

Observe 阶段 - OODA Loop 第一步
负责输入规范化、验证和预处理
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import logging
import re
import threading

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """
    观察结果 - Observe 阶段的输出

    Attributes:
        raw_input: 原始输入
        normalized_input: 规范化后的输入
        metadata: 额外元数据
        timestamp: 观察时间戳
        extracted_entities: 提取的实体
        confidence: 置信度 (0.0 - 1.0)
        is_valid: 输入是否有效
        validation_errors: 验证错误列表
    """

    raw_input: str
    normalized_input: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    extracted_entities: List[str] = field(default_factory=list)
    confidence: float = 1.0
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "raw_input": self.raw_input,
            "normalized_input": self.normalized_input,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "extracted_entities": self.extracted_entities,
            "confidence": self.confidence,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


class ValidationResult:
    """验证结果"""

    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def add_error(self, error: str) -> None:
        """添加错误"""
        self.errors.append(error)
        self.is_valid = False


class InputValidator(ABC):
    """输入验证器接口"""

    @abstractmethod
    def validate(self, input_data: str) -> ValidationResult:
        """
        验证输入

        Args:
            input_data: 输入数据

        Returns:
            验证结果
        """
        raise NotImplementedError

    def __and__(self, other: "InputValidator") -> "CompositeValidator":
        """组合验证器"""
        return CompositeValidator([self, other])


class CompositeValidator(InputValidator):
    """组合验证器 - 按顺序执行多个验证器"""

    def __init__(self, validators: List[InputValidator]):
        self._validators = validators

    def validate(self, input_data: str) -> ValidationResult:
        """执行所有验证器"""
        result = ValidationResult(True)
        for validator in self._validators:
            vr = validator.validate(input_data)
            if not vr.is_valid:
                result.is_valid = False
                result.errors.extend(vr.errors)
        return result


class InputNormalizer(ABC):
    """输入规范化器接口"""

    @abstractmethod
    def normalize(self, input_data: str) -> str:
        """
        规范化输入

        Args:
            input_data: 输入数据

        Returns:
            规范化后的数据
        """
        raise NotImplementedError

    def __and__(self, other: "InputNormalizer") -> "PipelineNormalizer":
        """管道规范化器"""
        return PipelineNormalizer([self, other])


class PipelineNormalizer(InputNormalizer):
    """管道规范化器 - 按顺序执行多个规范化器"""

    def __init__(self, normalizers: List[InputNormalizer]):
        self._normalizers = normalizers

    def normalize(self, input_data: str) -> str:
        """按顺序执行所有规范化器"""
        result = input_data
        for normalizer in self._normalizers:
            result = normalizer.normalize(result)
        return result


# ============== 内置验证器 ==============

class NotEmptyValidator(InputValidator):
    """非空验证器"""

    def validate(self, input_data: str) -> ValidationResult:
        if not input_data or not input_data.strip():
            return ValidationResult(False, ["Input cannot be empty"])
        return ValidationResult(True)


class MinLengthValidator(InputValidator):
    """最小长度验证器"""

    def __init__(self, min_length: int):
        self.min_length = min_length

    def validate(self, input_data: str) -> ValidationResult:
        if len(input_data) < self.min_length:
            return ValidationResult(
                False, [f"Input must be at least {self.min_length} characters"]
            )
        return ValidationResult(True)


class MaxLengthValidator(InputValidator):
    """最大长度验证器"""

    def __init__(self, max_length: int):
        self.max_length = max_length

    def validate(self, input_data: str) -> ValidationResult:
        if len(input_data) > self.max_length:
            return ValidationResult(
                False, [f"Input must be at most {self.max_length} characters"]
            )
        return ValidationResult(True)


class PatternValidator(InputValidator):
    """正则表达式验证器"""

    def __init__(self, pattern: str, error_message: str = "Input format invalid"):
        self.pattern = re.compile(pattern)
        self.error_message = error_message

    def validate(self, input_data: str) -> ValidationResult:
        if not self.pattern.match(input_data):
            return ValidationResult(False, [self.error_message])
        return ValidationResult(True)


# ============== 内置规范化器 ==============

class TrimNormalizer(InputNormalizer):
    """去除首尾空白"""

    def normalize(self, input_data: str) -> str:
        return input_data.strip()


class LowercaseNormalizer(InputNormalizer):
    """转小写"""

    def normalize(self, input_data: str) -> str:
        return input_data.lower()


class UppercaseNormalizer(InputNormalizer):
    """转大写"""

    def normalize(self, input_data: str) -> str:
        return input_data.upper()


class CollapseWhitespaceNormalizer(InputNormalizer):
    """合并多余空白"""

    def normalize(self, input_data: str) -> str:
        return re.sub(r"\s+", " ", input_data.strip())


class RemoveSpecialCharsNormalizer(InputNormalizer):
    """移除特殊字符（只保留中文、字母、数字、空白）"""

    def normalize(self, input_data: str) -> str:
        # 保留中文字符、字母、数字、空白
        return re.sub(r"[^\u4e00-\u9fff\w\s]", "", input_data)


# ============== Observe Phase ==============

class ObservePhase:
    """
    Observe 阶段 - OODA Loop 第一步

    特性：
    - 输入验证（链式）
    - 输入规范化（管道）
    - 元数据提取
    - 时间戳记录

    Example:
        >>> observe = ObservePhase()
        >>> observe.add_validator(NotEmptyValidator())
        >>> observe.add_normalizer(TrimNormalizer())
        >>> result = observe.observe("  Hello World  ")
        >>> assert result.normalized_input == "Hello World"
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "ObservePhase":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # 单例只初始化一次
        if self._initialized:
            return

        self._validators: List[InputValidator] = []
        self._normalizers: List[InputNormalizer] = []

        # 默认验证器和规范化器
        self._setup_defaults()

        self._initialized = True

    def _setup_defaults(self) -> None:
        """设置默认验证器和规范化器"""
        # 默认验证：非空
        self.add_validator(NotEmptyValidator())

        # 默认规范化：去空白、合并空白
        self.add_normalizer(TrimNormalizer())
        self.add_normalizer(CollapseWhitespaceNormalizer())

    def add_validator(self, validator: InputValidator) -> None:
        """
        添加验证器

        Args:
            validator: 验证器
        """
        self._validators.append(validator)
        logger.debug(f"Added validator: {validator.__class__.__name__}")

    def add_normalizer(self, normalizer: InputNormalizer) -> None:
        """
        添加规范化器

        Args:
            normalizer: 规范化器
        """
        self._normalizers.append(normalizer)
        logger.debug(f"Added normalizer: {normalizer.__class__.__name__}")

    def clear_validators(self) -> None:
        """清空所有验证器"""
        self._validators.clear()

    def clear_normalizers(self) -> None:
        """清空所有规范化器"""
        self._normalizers.clear()

    def observe(
        self, input_data: str, context: Optional[Dict[str, Any]] = None
    ) -> Observation:
        """
        执行观察阶段

        Args:
            input_data: 原始输入
            context: 额外上下文信息

        Returns:
            观察结果
        """
        logger.debug(f"Observing input: {input_data[:50]}...")

        # 执行验证
        validation_result = ValidationResult(True)
        for validator in self._validators:
            vr = validator.validate(input_data)
            if not vr.is_valid:
                validation_result.is_valid = False
                validation_result.errors.extend(vr.errors)

        # 执行规范化（即使验证失败也规范化，用于错误消息）
        normalized = input_data
        for normalizer in self._normalizers:
            normalized = normalizer.normalize(normalized)

        # 创建观察结果
        observation = Observation(
            raw_input=input_data,
            normalized_input=normalized,
            is_valid=validation_result.is_valid,
            validation_errors=validation_result.errors,
        )

        # 添加上下文到元数据
        if context:
            observation.metadata.update(context)

        logger.info(
            f"Observe phase completed: valid={observation.is_valid}, "
            f"input_len={len(input_data)}, normalized_len={len(normalized)}"
        )

        return observation


# 全局观察阶段实例
observe_phase = ObservePhase()


# 导出
__all__ = [
    "Observation",
    "ValidationResult",
    "InputValidator",
    "CompositeValidator",
    "InputNormalizer",
    "PipelineNormalizer",
    # 内置验证器
    "NotEmptyValidator",
    "MinLengthValidator",
    "MaxLengthValidator",
    "PatternValidator",
    # 内置规范化器
    "TrimNormalizer",
    "LowercaseNormalizer",
    "UppercaseNormalizer",
    "CollapseWhitespaceNormalizer",
    "RemoveSpecialCharsNormalizer",
    # 主类
    "ObservePhase",
    "observe_phase",
]
