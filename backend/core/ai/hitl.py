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
    """

    # 默认风险配置
    DEFAULT_RISK_MAPPING: Dict[str, ConfirmationLevel] = {
        # 查询类 - 不需要确认
        "view": ConfirmationLevel.NONE,
        "query_rooms": ConfirmationLevel.NONE,
        "query_reservations": ConfirmationLevel.NONE,
        "query_guests": ConfirmationLevel.NONE,
        "query_tasks": ConfirmationLevel.NONE,
        "query_reports": ConfirmationLevel.NONE,

        # 低风险操作 - 不需要确认
        "start_task": ConfirmationLevel.NONE,

        # 中风险操作 - 需要确认
        "create_task": ConfirmationLevel.LOW,
        "assign_task": ConfirmationLevel.LOW,
        "complete_task": ConfirmationLevel.LOW,
        "checkin": ConfirmationLevel.MEDIUM,
        "walkin_checkin": ConfirmationLevel.MEDIUM,
        "create_reservation": ConfirmationLevel.MEDIUM,

        # 高风险操作 - 需要确认
        "extend_stay": ConfirmationLevel.HIGH,
        "change_room": ConfirmationLevel.HIGH,
        "checkout": ConfirmationLevel.MEDIUM,
        "cancel_reservation": ConfirmationLevel.HIGH,

        # 关键操作 - 需要确认
        "add_payment": ConfirmationLevel.HIGH,
        "adjust_bill": ConfirmationLevel.CRITICAL,
        "update_room_status": ConfirmationLevel.MEDIUM,
    }

    def __init__(self, risk_mapping: Optional[Dict[str, ConfirmationLevel]] = None):
        """
        初始化基于风险的确认策略

        Args:
            risk_mapping: 自定义风险映射，默认使用 DEFAULT_RISK_MAPPING
        """
        self.risk_mapping = risk_mapping or self.DEFAULT_RISK_MAPPING.copy()

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
        """获取操作的风险等级"""
        # 先检查映射表
        if action_type in self.risk_mapping:
            base_risk = self.risk_mapping[action_type]
        else:
            # 未定义的操作默认为 MEDIUM
            base_risk = ConfirmationLevel.MEDIUM

        # 特殊情况调整
        # 调整账单金额过大时提升风险
        if action_type == "adjust_bill":
            amount = params.get("adjustment_amount", 0)
            if abs(float(amount)) > 1000:
                return ConfirmationLevel.CRITICAL

        # 取消预订根据原因判断
        if action_type == "cancel_reservation":
            reason = params.get("cancel_reason", "")
            if "系统" in reason or "强制" in reason:
                return ConfirmationLevel.CRITICAL

        return base_risk


class ConfirmByPolicyStrategy(HITLStrategy):
    """
    基于配置策略的确认策略

    从配置文件读取确认策略，支持动态配置。
    """

    # 默认策略配置
    DEFAULT_POLICIES: Dict[str, Dict[str, Any]] = {
        "high_risk_actions": {
            "actions": ["adjust_bill", "delete_guest"],
            "confirm": True,
            "require_reason": True
        },
        "medium_risk_actions": {
            "actions": ["change_room", "extend_stay", "cancel_reservation"],
            "confirm": True,
            "require_reason": False
        },
        "low_risk_actions": {
            "actions": ["create_task", "assign_task", "complete_task"],
            "confirm": False,
            "require_reason": False
        },
        "role_based": {
            "manager": {
                "skip_confirmation": ["add_payment", "create_reservation", "checkout"]
            },
            "receptionist": {
                "skip_confirmation": ["query_rooms", "query_reservations"]
            }
        }
    }

    def __init__(self, policies: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        初始化基于策略的确认

        Args:
            policies: 策略配置，默认使用 DEFAULT_POLICIES
        """
        self.policies = policies or self.DEFAULT_POLICIES.copy()

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
    """

    def __init__(
        self,
        payment_threshold: float = 1000.0,
        adjustment_threshold: float = 500.0,
        quantity_threshold: int = 10
    ):
        """
        初始化基于阈值的确认策略

        Args:
            payment_threshold: 支付金额阈值
            adjustment_threshold: 调整金额阈值
            quantity_threshold: 数量阈值
        """
        self.payment_threshold = payment_threshold
        self.adjustment_threshold = adjustment_threshold
        self.quantity_threshold = quantity_threshold

    def requires_confirmation(
        self,
        action_type: str,
        params: Dict[str, Any],
        user_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """根据阈值判断是否需要确认"""
        # 支付金额阈值
        if action_type == "add_payment":
            amount = float(params.get("amount", 0))
            return amount >= self.payment_threshold

        # 账单调整阈值
        if action_type == "adjust_bill":
            amount = abs(float(params.get("adjustment_amount", 0)))
            return amount >= self.adjustment_threshold

        # 批量操作阈值
        if action_type in ["create_task", "assign_task"]:
            # 检查是否批量操作
            if "room_ids" in params or "task_ids" in params:
                count = len(params.get("room_ids", params.get("task_ids", [])))
                return count >= self.quantity_threshold

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

def create_default_hitl_strategy() -> HITLStrategy:
    """
    创建默认的 HITL 策略

    组合基于风险和基于策略的确认方式。
    """
    return CompositeHITLStrategy([
        ConfirmByRiskStrategy(),
        ConfirmByPolicyStrategy(),
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
