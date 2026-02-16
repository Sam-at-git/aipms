"""
core/ai/hitl.py

HITL (Human-in-the-Loop) 策略 - 人类在环确认策略

定义多种确认策略，控制哪些操作需要用户确认。
支持基于风险等级、配置策略等多种确认模式。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum


class ConfirmationLevel(Enum):
    """确认级别"""
    NONE = "none"           # 不需要确认
    LOW = "low"             # 低级别确认
    MEDIUM = "medium"       # 中级别确认
    HIGH = "high"           # 高级别确认
    CRITICAL = "critical"   # 关键操作确认


@dataclass
class ActionRisk:
    """操作风险评估"""
    action_type: str
    risk_level: ConfirmationLevel
    reason: str = ""


class HITLStrategy(ABC):
    """
    人类在环策略抽象基类

    定义了所有 HITL 策略必须实现的接口。
    """

    @abstractmethod
    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        判断操作是否需要确认

        Args:
            action_type: 操作类型
            params: 操作参数
            user_role: 用户角色
            context: 额外上下文

        Returns:
            是否需要确认
        """
        pass

    @abstractmethod
    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """
        获取操作的风险等级

        Args:
            action_type: 操作类型
            params: 操作参数

        Returns:
            风险等级
        """
        pass


class ConfirmAlwaysStrategy(HITLStrategy):
    """
    总是确认策略

    所有操作都需要用户确认，最安全的策略。
    适合对安全性要求极高的场景。
    """

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """所有操作都需要确认"""
        return True

    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """返回 MEDIUM 级别"""
        return ConfirmationLevel.MEDIUM


class ConfirmByRiskStrategy(HITLStrategy):
    """
    基于风险等级的确认策略

    根据操作类型和参数评估风险等级，决定是否需要确认。
    Risk levels are resolved in order: override mapping → custom rules → registry → default.
    """

    # Risk level string → ConfirmationLevel mapping
    _RISK_LEVEL_MAP: Dict[str, ConfirmationLevel] = {
        "none": ConfirmationLevel.NONE,
        "low": ConfirmationLevel.LOW,
        "medium": ConfirmationLevel.MEDIUM,
        "high": ConfirmationLevel.HIGH,
        "critical": ConfirmationLevel.CRITICAL,
    }

    def __init__(
        self,
        risk_mapping: Optional[Dict[str, ConfirmationLevel]] = None,
        registry=None,
        custom_rules: Optional[List] = None,
    ):
        """
        初始化基于风险的确认策略

        Args:
            risk_mapping: Override mapping of action_type → ConfirmationLevel
            registry: OntologyRegistry instance for action metadata lookups
            custom_rules: List of callables (action_type, params) → Optional[ConfirmationLevel]
        """
        self.risk_mapping = risk_mapping or {}
        self._registry = registry
        self._custom_rules = custom_rules or []

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        根据风险等级判断是否需要确认

        - NONE: 不需要确认
        - LOW: 不需要确认
        - MEDIUM及以上: 需要确认
        """
        risk_level = self.get_risk_level(action_type, params)

        # NONE 和 LOW 级别不需要确认
        return risk_level in (
            ConfirmationLevel.MEDIUM,
            ConfirmationLevel.HIGH,
            ConfirmationLevel.CRITICAL
        )

    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """获取操作的风险等级 (override → custom_rules → registry → default)"""
        # 1. Check override mapping
        if action_type in self.risk_mapping:
            return self.risk_mapping[action_type]

        # 2. Check custom rules (injected by domain adapter)
        for rule in self._custom_rules:
            result = rule(action_type, params)
            if result is not None:
                return result

        # 3. Check registry metadata
        if self._registry:
            action = self._registry.get_action_by_name(action_type)
            if action and action.risk_level:
                return self._RISK_LEVEL_MAP.get(
                    action.risk_level, ConfirmationLevel.MEDIUM
                )

        # 4. Default
        return ConfirmationLevel.MEDIUM


class ConfirmByPolicyStrategy(HITLStrategy):
    """
    基于配置策略的确认策略

    从配置或域适配器注入确认策略，支持动态配置。
    Policies are fully injected via constructor; no domain-specific defaults.
    """

    def __init__(self, policies: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        初始化基于策略的确认

        Args:
            policies: 策略配置 (action tiers + role-based exemptions)
        """
        self.policies = policies or {}

        # 构建动作到策略的映射
        self._action_policy_map: Dict[str, str] = {}
        self._build_policy_map()

    def _build_policy_map(self):
        """构建动作到策略级别的映射"""
        for level, config in self.policies.items():
            if level.endswith("_actions") and "actions" in config:
                for action in config["actions"]:
                    self._action_policy_map[action] = level

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """根据策略判断是否需要确认"""
        # 检查角色豁免
        if self._check_role_exemption(action_type, user_role):
            return False

        # 检查动作级别策略
        policy_level = self._action_policy_map.get(action_type)

        if policy_level == "high_risk_actions":
            return True
        elif policy_level == "medium_risk_actions":
            return True
        elif policy_level == "low_risk_actions":
            return False

        # 未定义的操作默认需要确认
        return True

    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """获取操作的风险等级"""
        policy_level = self._action_policy_map.get(action_type)

        if policy_level == "high_risk_actions":
            return ConfirmationLevel.CRITICAL
        elif policy_level == "medium_risk_actions":
            return ConfirmationLevel.HIGH
        elif policy_level == "low_risk_actions":
            return ConfirmationLevel.LOW

        return ConfirmationLevel.MEDIUM

    def _check_role_exemption(self, action_type: str, user_role: str) -> bool:
        """检查角色是否可以跳过确认"""
        role_based = self.policies.get("role_based", {})
        skip_list = role_based.get(user_role, {}).get("skip_confirmation", [])
        return action_type in skip_list

    def add_policy(
        self,
        level: str,
        actions: List[str],
        confirm: bool = True,
        require_reason: bool = False
    ):
        """
        动态添加策略

        Args:
            level: 策略级别 (high_risk_actions, medium_risk_actions, low_risk_actions)
            actions: 操作列表
            confirm: 是否需要确认
            require_reason: 是否需要原因
        """
        policy_key = f"{level}_actions"
        if policy_key not in self.policies:
            self.policies[policy_key] = {
                "actions": [],
                "confirm": confirm,
                "require_reason": require_reason
            }

        self.policies[policy_key]["actions"].extend(actions)

        # 更新映射
        for action in actions:
            self._action_policy_map[action] = policy_key


class ConfirmByThresholdStrategy(HITLStrategy):
    """
    基于阈值的确认策略

    根据操作参数的值（如金额、数量）判断是否需要确认。
    Uses is_financial from registry instead of hardcoded action names.
    """

    def __init__(
        self,
        amount_threshold: float = 1000.0,
        adjustment_threshold: float = 500.0,
        quantity_threshold: int = 10,
        registry=None,
    ):
        """
        初始化基于阈值的确认策略

        Args:
            amount_threshold: 金额阈值 (for financial actions with 'amount' param)
            adjustment_threshold: 调整金额阈值 (for financial actions with 'adjustment_amount' param)
            quantity_threshold: 批量操作数量阈值
            registry: OntologyRegistry instance for is_financial lookups
        """
        self.amount_threshold = amount_threshold
        self.adjustment_threshold = adjustment_threshold
        self.quantity_threshold = quantity_threshold
        self._registry = registry

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """根据阈值判断是否需要确认"""
        # Check if financial action via registry
        is_financial = False
        if self._registry:
            action = self._registry.get_action_by_name(action_type)
            if action:
                is_financial = action.is_financial

        if is_financial:
            # Check amount-related params against thresholds
            if "amount" in params:
                amount = float(params.get("amount", 0))
                if amount >= self.amount_threshold:
                    return True
            if "adjustment_amount" in params:
                amount = abs(float(params.get("adjustment_amount", 0)))
                if amount >= self.adjustment_threshold:
                    return True

        # Batch operation quantity threshold (generic)
        for batch_key in ("room_ids", "task_ids"):
            if batch_key in params:
                count = len(params[batch_key])
                if count >= self.quantity_threshold:
                    return True

        return False

    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """获取操作的风险等级"""
        if self.requires_confirmation(action_type, params, ""):
            return ConfirmationLevel.HIGH
        return ConfirmationLevel.LOW


class CompositeHITLStrategy(HITLStrategy):
    """
    组合确认策略

    组合多个策略，任一策略要求确认即返回 True。
    """

    def __init__(self, strategies: List[HITLStrategy]):
        """
        初始化组合策略

        Args:
            strategies: 策略列表
        """
        self.strategies = strategies

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """任一策略要求确认即返回 True"""
        for strategy in self.strategies:
            if strategy.requires_confirmation(action_type, params, user_role, context):
                return True
        return False

    def get_risk_level(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> ConfirmationLevel:
        """返回最高的风险等级"""
        levels = [
            strategy.get_risk_level(action_type, params)
            for strategy in self.strategies
        ]

        # 按优先级排序
        priority = {
            ConfirmationLevel.CRITICAL: 4,
            ConfirmationLevel.HIGH: 3,
            ConfirmationLevel.MEDIUM: 2,
            ConfirmationLevel.LOW: 1,
            ConfirmationLevel.NONE: 0,
        }

        return max(levels, key=lambda l: priority.get(l, 0))


# ==================== 便捷函数 ====================

def create_default_hitl_strategy(registry=None, custom_rules=None, policies=None) -> HITLStrategy:
    """
    创建默认的 HITL 策略

    组合基于风险和基于策略的确认方式。

    Args:
        registry: OntologyRegistry instance for action metadata lookups
        custom_rules: List of custom rule callables for ConfirmByRiskStrategy
        policies: Policy configuration for ConfirmByPolicyStrategy
    """
    return CompositeHITLStrategy([
        ConfirmByRiskStrategy(registry=registry, custom_rules=custom_rules),
        ConfirmByPolicyStrategy(policies=policies),
    ])


def create_safe_hitl_strategy() -> HITLStrategy:
    """创建最安全的确认策略（所有操作都确认）"""
    return ConfirmAlwaysStrategy()


__all__ = [
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
