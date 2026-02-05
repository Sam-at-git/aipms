"""
core/security/masking.py

敏感数据脱敏 - 根据安全级别和用户权限自动脱敏敏感数据
支持多种数据类型的脱敏规则
"""
from typing import Dict, Any, Optional, Callable, Pattern
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

from core.security.context import SecurityContext, security_context_manager
from core.ontology.security import SecurityLevel

logger = logging.getLogger(__name__)


class MaskingStrategy(str, Enum):
    """脱敏策略"""

    FULL = "full"  # 完全脱敏: ******
    PARTIAL = "partial"  # 部分脱敏: 138****1234
    EMAIL = "email"  # 邮箱脱敏: a***@example.com
    NAME = "name"  # 姓名脱敏: 张**
    CUSTOM = "custom"  # 自定义规则


@dataclass
class MaskingRule:
    """
    脱敏规则定义

    Attributes:
        field_name: 字段名
        data_type: 数据类型（phone, id_card, email, name 等）
        strategy: 脱敏策略
        security_level: 需要脱敏的安全级别
        custom_pattern: 自定义模式（如 "{first3}****{last4}"）
        preserve_chars: 保留字符数（部分脱敏时）
    """

    field_name: str
    data_type: str
    strategy: MaskingStrategy
    security_level: SecurityLevel
    custom_pattern: Optional[str] = None
    preserve_chars: int = 0


class DataMasker:
    """
    数据脱敏器 - 单例模式

    特性：
    - 多类型数据脱敏
    - 基于安全级别的自动脱敏
    - 可配置脱敏规则
    - 字典批量脱敏

    Example:
        >>> masker = DataMasker()
        >>> masker.mask("phone", "13800138000", context)  # 有权限
        '13800138000'
        >>> masker.mask("phone", "13800138000", low_context)  # 无权限
        '138****8000'
    """

    _instance: Optional["DataMasker"] = None
    _lock = object()

    def __new__(cls) -> "DataMasker":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._rules: Dict[str, MaskingRule] = {}
        self._patterns: Dict[str, Callable[[str], str]] = {}
        self._initialized = True

        # 注册预定义规则
        self._register_predefined_rules()

        logger.debug("DataMasker initialized")

    def _register_predefined_rules(self) -> None:
        """注册预定义的脱敏规则"""
        rules = [
            # 电话号码
            MaskingRule(
                field_name="phone",
                data_type="phone",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.CONFIDENTIAL,
                preserve_chars=3,
            ),
            # 手机号码（别名）
            MaskingRule(
                field_name="mobile",
                data_type="phone",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.CONFIDENTIAL,
                preserve_chars=3,
            ),
            # 身份证
            MaskingRule(
                field_name="id_card",
                data_type="id_card",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.RESTRICTED,
                preserve_chars=6,
            ),
            # 邮箱
            MaskingRule(
                field_name="email",
                data_type="email",
                strategy=MaskingStrategy.EMAIL,
                security_level=SecurityLevel.INTERNAL,
            ),
            # 姓名中文
            MaskingRule(
                field_name="name",
                data_type="name",
                strategy=MaskingStrategy.NAME,
                security_level=SecurityLevel.INTERNAL,
            ),
            # 真实姓名
            MaskingRule(
                field_name="real_name",
                data_type="name",
                strategy=MaskingStrategy.NAME,
                security_level=SecurityLevel.INTERNAL,
            ),
            # 地址
            MaskingRule(
                field_name="address",
                data_type="address",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.CONFIDENTIAL,
                preserve_chars=6,
            ),
            # 银行卡号
            MaskingRule(
                field_name="bank_card",
                data_type="bank_card",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.RESTRICTED,
                preserve_chars=4,
            ),
        ]

        for rule in rules:
            self.register_rule(rule)

    def register_rule(self, rule: MaskingRule) -> None:
        """
        注册脱敏规则

        Args:
            rule: 脱敏规则
        """
        self._rules[rule.field_name] = rule
        logger.debug(f"Registered masking rule for: {rule.field_name}")

    def get_rule(self, field_name: str) -> Optional[MaskingRule]:
        """获取字段脱敏规则"""
        return self._rules.get(field_name)

    def mask(
        self, field_name: str, value: Any, context: Optional[SecurityContext] = None
    ) -> Any:
        """
        脱敏数据

        Args:
            field_name: 字段名
            value: 原始值
            context: 安全上下文

        Returns:
            脱敏后的值（如果需要脱敏），否则返回原值
        """
        # None 值直接返回
        if value is None:
            return None

        # 只处理字符串类型
        if not isinstance(value, str):
            return value

        rule = self.get_rule(field_name)
        if rule is None:
            return value

        # 检查是否需要脱敏
        if context is None:
            context = security_context_manager.get_context()

        if context is None:
            # 没有上下文时，PUBLIC 级别不脱敏
            if rule.security_level == SecurityLevel.PUBLIC:
                return value
            # 其他级别需要脱敏
        elif not context.has_clearance(rule.security_level):
            # 级别不足，需要脱敏
            pass
        else:
            # 级别足够，不需要脱敏
            return value

        # 执行脱敏
        return self._apply_masking(value, rule)

    def _apply_masking(self, value: str, rule: MaskingRule) -> str:
        """应用脱敏规则"""
        strategy = rule.strategy

        if strategy == MaskingStrategy.FULL:
            return "*" * len(value)

        if strategy == MaskingStrategy.PARTIAL:
            return self._mask_partial(value, rule.preserve_chars)

        if strategy == MaskingStrategy.EMAIL:
            return self._mask_email(value)

        if strategy == MaskingStrategy.NAME:
            return self._mask_name(value)

        if strategy == MaskingStrategy.CUSTOM and rule.custom_pattern:
            return self._mask_custom(value, rule.custom_pattern)

        # 默认完全脱敏
        return "*" * len(value)

    def _mask_partial(self, value: str, preserve_chars: int) -> str:
        """部分脱敏"""
        if len(value) <= preserve_chars * 2:
            return "*" * len(value)

        preserved = value[:preserve_chars]
        masked_length = len(value) - preserve_chars
        return f"{preserved}{'*' * masked_length}"

    def _mask_email(self, value: str) -> str:
        """邮箱脱敏"""
        if "@" not in value:
            return "*" * len(value)

        local, domain = value.split("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 1)

        return f"{masked_local}@{domain}"

    def _mask_name(self, value: str) -> str:
        """姓名脱敏"""
        # 简单处理：保留第一个字符，其余用*代替
        if len(value) <= 1:
            return value
        return value[0] + "*" * (len(value) - 1)

    def _mask_custom(self, value: str, pattern: str) -> str:
        """自定义模式脱敏"""
        # 简化实现：支持 {firstN} 和 {lastN} 占位符
        result = pattern
        if "{first" in pattern:
            match = re.search(r"\{first(\d+)\}", pattern)
            if match:
                n = int(match.group(1))
                result = result.replace(match.group(0), value[:n])
        if "{last" in pattern:
            match = re.search(r"\{last(\d+)\}", pattern)
            if match:
                n = int(match.group(1))
                result = result.replace(match.group(0), value[-n:])
        # 替换剩余的 * 为实际数量的星号
        star_count = result.count("*")
        if star_count > 0:
            needed_stars = len(value) - len(re.sub(r"\*", "", result))
            result = result.replace("*", "*" * needed_stars)
        return result

    def mask_dict(
        self,
        data: Dict[str, Any],
        context: Optional[SecurityContext] = None,
        field_prefix: str = "",
    ) -> Dict[str, Any]:
        """
        脱敏字典数据

        Args:
            data: 原始字典
            context: 安全上下文
            field_prefix: 字段前缀（用于嵌套对象）

        Returns:
            脱敏后的字典
        """
        masked = {}
        for key, value in data.items():
            full_key = f"{field_prefix}.{key}" if field_prefix else key
            if isinstance(value, dict):
                # 递归处理嵌套字典
                masked[key] = self.mask_dict(value, context, full_key)
            elif isinstance(value, list):
                # 处理列表
                masked[key] = [
                    self.mask_dict(item, context, full_key) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = self.mask(full_key, value, context)
        return masked


# 全局脱敏器实例
data_masker = DataMasker()


# 导出
__all__ = [
    "MaskingStrategy",
    "MaskingRule",
    "DataMasker",
    "data_masker",
]
