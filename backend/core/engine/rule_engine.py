"""
core/engine/rule_engine.py

规则引擎 - 装饰器注册的业务规则执行
支持运行时规则定义、条件评估和副作用触发
"""
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


@dataclass
class RuleContext:
    """
    规则执行上下文

    Attributes:
        entity: 当前实体对象
        entity_type: 实体类型名称
        action: 正在执行的动作
        parameters: 动作参数
        metadata: 额外的元数据
    """

    entity: Any
    entity_type: str
    action: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """获取参数值"""
        return self.parameters.get(name, default)

    def has_parameter(self, name: str) -> bool:
        """检查参数是否存在"""
        return name in self.parameters


class RuleCondition(ABC):
    """规则条件接口"""

    @abstractmethod
    def evaluate(self, context: RuleContext) -> bool:
        """
        评估条件是否满足

        Args:
            context: 规则执行上下文

        Returns:
            True 如果条件满足
        """
        raise NotImplementedError


class FunctionCondition(RuleCondition):
    """函数条件 - 使用可调用对象评估"""

    def __init__(self, func: Callable[[RuleContext], bool], description: str = ""):
        self._func = func
        self._description = description

    def evaluate(self, context: RuleContext) -> bool:
        return self._func(context)

    def __repr__(self) -> str:
        return f"FunctionCondition({self._description or self._func.__name__})"


class ExpressionCondition(RuleCondition):
    """表达式条件 - 使用字符串表达式评估（简化版，不使用 eval）"""

    def __init__(self, expression: str):
        self._expression = expression

    def evaluate(self, context: RuleContext) -> bool:
        # 简化的表达式解析：只支持简单的 == 检查
        # 例如: "status == 'active'" 或 "count > 5"
        # 完整实现应该使用安全的表达式解析器

        # 获取属性值的辅助函数（支持 dict 和对象）
        def get_attr_value(entity, attr_name):
            if isinstance(entity, dict):
                return entity.get(attr_name)
            return getattr(entity, attr_name, None)

        # 对于当前实现，我们只支持简单的属性检查
        if " == " in self._expression:
            attr, value = self._expression.split(" == ", 1)
            attr_value = get_attr_value(context.entity, attr.strip())
            expected = value.strip().strip("'\"")
            return str(attr_value) == expected

        if " != " in self._expression:
            attr, value = self._expression.split(" != ", 1)
            attr_value = get_attr_value(context.entity, attr.strip())
            expected = value.strip().strip("'\"")
            return str(attr_value) != expected

        logger.warning(f"Unsupported expression: {self._expression}")
        return False

    def __repr__(self) -> str:
        return f"ExpressionCondition({self._expression})"


@dataclass
class Rule:
    """
    业务规则定义

    Attributes:
        rule_id: 规则唯一标识
        name: 规则名称
        description: 规则描述
        condition: 规则条件
        action: 触发的动作（函数或描述）
        priority: 优先级（数字越大优先级越高）
        enabled: 是否启用
    """

    rule_id: str
    name: str
    description: str
    condition: RuleCondition
    action: Callable[[RuleContext], None]
    priority: int = 0
    enabled: bool = True


class RuleEngine:
    """
    规则引擎 - 管理和执行业务规则

    特性：
    - 规则注册和注销
    - 条件评估
    - 动作执行
    - 优先级排序

    Example:
        >>> engine = RuleEngine()
        >>> def check_status(ctx):
        ...     return ctx.entity.status == "active"
        >>> def log_action(ctx):
        ...     logger.info(f"Action on {ctx.entity}")
        >>> engine.register_rule(Rule(
        ...     rule_id="r1",
        ...     name="Active Entity Rule",
        ...     description="Log when entity is active",
        ...     condition=FunctionCondition(check_status),
        ...     action=log_action
        ... ))
        >>> engine.evaluate(RuleContext(...))
    """

    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._entity_rules: Dict[str, List[str]] = {}  # entity_type -> rule_ids

    def register_rule(self, rule: Rule) -> None:
        """
        注册规则

        Args:
            rule: 要注册的规则

        Raises:
            ValueError: 如果 rule_id 已存在
        """
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule {rule.rule_id} already exists")

        self._rules[rule.rule_id] = rule

        # 按实体类型索引规则（从 rule_id 提取）
        entity_type = rule.rule_id.split("_")[0] if "_" in rule.rule_id else None
        if entity_type:
            if entity_type not in self._entity_rules:
                self._entity_rules[entity_type] = []
            self._entity_rules[entity_type].append(rule.rule_id)

        logger.info(f"Rule {rule.rule_id} registered")

    def unregister_rule(self, rule_id: str) -> None:
        """
        注销规则

        Args:
            rule_id: 规则ID
        """
        if rule_id in self._rules:
            rule = self._rules[rule_id]

            # 从实体索引中移除
            for entity_type, rule_ids in self._entity_rules.items():
                if rule_id in rule_ids:
                    rule_ids.remove(rule_id)

            del self._rules[rule_id]
            logger.info(f"Rule {rule_id} unregistered")

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取规则"""
        return self._rules.get(rule_id)

    def get_rules_for_entity(self, entity_type: str) -> List[Rule]:
        """
        获取实体的所有规则

        Args:
            entity_type: 实体类型

        Returns:
            规则列表（按优先级排序）
        """
        rule_ids = self._entity_rules.get(entity_type, [])
        rules = [self._rules[rid] for rid in rule_ids if rid in self._rules and self._rules[rid].enabled]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: RuleContext) -> List[Rule]:
        """
        评估规则并执行匹配的规则动作

        Args:
            context: 规则执行上下文

        Returns:
            触发的规则列表
        """
        triggered = []

        for rule in self.get_rules_for_entity(context.entity_type):
            try:
                if rule.condition.evaluate(context):
                    rule.action(context)
                    triggered.append(rule)
                    logger.info(f"Rule {rule.rule_id} triggered for {context.entity_type}")
            except Exception as e:
                logger.error(f"Error executing rule {rule.rule_id}: {e}", exc_info=True)

        return triggered

    def enable_rule(self, rule_id: str) -> None:
        """启用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str) -> None:
        """禁用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False

    def clear(self) -> None:
        """清空所有规则（用于测试）"""
        self._rules.clear()
        self._entity_rules.clear()


# 全局规则引擎实例
rule_engine = RuleEngine()


# 导出
__all__ = [
    "RuleContext",
    "RuleCondition",
    "FunctionCondition",
    "ExpressionCondition",
    "Rule",
    "RuleEngine",
    "rule_engine",
]
