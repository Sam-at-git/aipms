"""
core/ooda/decide.py

Decide 阶段 - OODA Loop 第三步
负责决策生成和动作选择
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import logging

from core.ooda.orient import Orientation
from core.ooda.intent import IntentResult
from core.security.checker import permission_checker, Permission

logger = logging.getLogger(__name__)


# 高风险操作类型（需要确认）
HIGH_RISK_ACTIONS = {
    "checkout",
    "cancel_reservation",
    "adjust_bill",
    "delete_guest",
    "delete_room",
    "delete_task",
}

# 涉及金额的操作类型（需要确认）
FINANCIAL_ACTIONS = {
    "adjust_bill",
    "add_payment",
}

# 所有动作类型及其必需参数
ACTION_REQUIRED_PARAMS = {
    "walkin_checkin": ["room_id", "guest_name", "guest_phone", "expected_check_out"],
    "checkin": ["reservation_id", "room_id"],
    "checkout": ["stay_record_id"],
    "update_room_status": ["room_id", "status"],
    "create_reservation": ["guest_name", "guest_phone", "room_type_id", "check_in_date", "check_out_date", "adult_count"],
    "cancel_reservation": ["reservation_id", "cancel_reason"],
    "create_task": ["room_id", "task_type"],
    "assign_task": ["task_id", "assignee_id"],
    "start_task": ["task_id"],
    "complete_task": ["task_id"],
    "add_payment": ["bill_id", "amount", "method"],
    "adjust_bill": ["bill_id", "adjustment_amount", "reason"],
    "extend_stay": ["stay_record_id", "new_check_out_date"],
    "change_room": ["stay_record_id", "new_room_id"],
}


@dataclass
class Decision:
    """
    决策结果 - Decide 阶段的输出

    Attributes:
        orientation: Orient 阶段的结果
        action_type: 动作类型
        action_params: 动作参数
        requires_confirmation: 是否需要确认
        confidence: 决策置信度
        metadata: 额外元数据
        timestamp: 决策时间戳
        is_valid: 决策是否有效
        errors: 错误列表
        missing_fields: 缺失字段列表（用于 Follow-up 模式）
    """

    orientation: Orientation
    action_type: str
    action_params: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    missing_fields: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "action_type": self.action_type,
            "action_params": self.action_params,
            "requires_confirmation": self.requires_confirmation,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "is_valid": self.is_valid,
            "errors": self.errors,
            "missing_fields": self.missing_fields,
        }


class DecisionRule(ABC):
    """决策规则接口"""

    @abstractmethod
    def evaluate(self, orientation: Orientation) -> Optional[Decision]:
        """
        评估导向并生成决策

        Args:
            orientation: Orient 阶段的结果

        Returns:
            Decision 对象，如果规则不匹配则返回 None
        """
        raise NotImplementedError("Subclasses must implement evaluate()")

    @abstractmethod
    def can_handle(self, orientation: Orientation) -> bool:
        """
        检查规则是否能处理该导向

        Args:
            orientation: Orient 阶段的结果

        Returns:
            如果能处理返回 True
        """
        raise NotImplementedError("Subclasses must implement can_handle()")


class IntentBasedRule(DecisionRule):
    """
    基于意图的决策规则

    使用意图识别结果生成决策
    """

    def __init__(self, action_type: str, required_params: Optional[List[str]] = None):
        """
        初始化基于意图的规则

        Args:
            action_type: 动作类型
            required_params: 必需参数列表
        """
        self._action_type = action_type
        self._required_params = required_params or []

    def can_handle(self, orientation: Orientation) -> bool:
        """检查是否能处理该导向"""
        if not orientation.intent:
            return False
        return orientation.intent.action_type == self._action_type

    def evaluate(self, orientation: Orientation) -> Optional[Decision]:
        """评估导向并生成决策"""
        if not self.can_handle(orientation):
            return None

        intent = orientation.intent
        if intent is None:
            return None

        # 提取参数
        action_params = intent.entities.copy()

        # 验证必需参数
        missing_fields = []
        for param in self._required_params:
            if param not in action_params or not action_params[param]:
                missing_fields.append({
                    "field_name": param,
                    "display_name": param.replace("_", " ").title(),
                    "field_type": "string",
                    "required": True,
                })

        # 检查是否需要确认
        requires_confirmation = (
            self._action_type in HIGH_RISK_ACTIONS or
            self._action_type in FINANCIAL_ACTIONS or
            intent.requires_confirmation
        )

        # 计算置信度
        param_completeness = 1.0
        if self._required_params:
            provided = sum(1 for p in self._required_params if p in action_params and action_params[p])
            param_completeness = provided / len(self._required_params)

        confidence = intent.confidence * param_completeness

        return Decision(
            orientation=orientation,
            action_type=self._action_type,
            action_params=action_params,
            requires_confirmation=requires_confirmation or len(missing_fields) > 0,
            confidence=confidence,
            is_valid=len(missing_fields) == 0,
            missing_fields=missing_fields,
        )


class DefaultDecisionRule(DecisionRule):
    """
    默认决策规则

    处理任何有意图的导向，从 ACTION_REQUIRED_PARAMS 获取参数定义
    """

    def can_handle(self, orientation: Orientation) -> bool:
        """检查是否能处理该导向"""
        return orientation.intent is not None

    def evaluate(self, orientation: Orientation) -> Optional[Decision]:
        """评估导向并生成决策"""
        if not self.can_handle(orientation):
            return None

        intent = orientation.intent
        if intent is None:
            return None

        action_type = intent.action_type
        action_params = intent.entities.copy()

        # 获取必需参数
        required_params = ACTION_REQUIRED_PARAMS.get(action_type, [])

        # 验证必需参数
        missing_fields = []
        for param in required_params:
            if param not in action_params or not action_params[param]:
                missing_fields.append({
                    "field_name": param,
                    "display_name": param.replace("_", " ").title(),
                    "field_type": "string",
                    "required": True,
                })

        # 检查是否需要确认
        requires_confirmation = (
            action_type in HIGH_RISK_ACTIONS or
            action_type in FINANCIAL_ACTIONS or
            intent.requires_confirmation
        )

        # 计算置信度
        param_completeness = 1.0
        if required_params:
            provided = sum(1 for p in required_params if p in action_params and action_params[p])
            param_completeness = provided / len(required_params)

        confidence = intent.confidence * param_completeness

        return Decision(
            orientation=orientation,
            action_type=action_type,
            action_params=action_params,
            requires_confirmation=requires_confirmation or len(missing_fields) > 0,
            confidence=confidence,
            is_valid=len(missing_fields) == 0,
            missing_fields=missing_fields,
        )


class DecidePhase:
    """
    Decide 阶段 - OODA Loop 第三步

    特性：
    - 决策规则链
    - 参数验证
    - 确认机制
    - 置信度计算

    Example:
        >>> decide = DecidePhase()
        >>> decide.add_rule(IntentBasedRule("checkin", ["reservation_id", "room_id"]))
        >>> orientation = Orientation(...)
        >>> decision = decide.decide(orientation)
        >>> print(decision.action_type)
    """

    def __init__(self):
        """初始化 Decide 阶段"""
        self._rules: List[DecisionRule] = []

        # 默认规则
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """设置默认规则"""
        # 添加默认规则作为后备
        self.add_rule(DefaultDecisionRule())

    def add_rule(self, rule: DecisionRule) -> None:
        """
        添加决策规则

        Args:
            rule: 决策规则
        """
        self._rules.insert(0, rule)  # 新规则添加到前面
        logger.debug(f"Added decision rule: {rule.__class__.__name__}")

    def remove_rule(self, rule: DecisionRule) -> None:
        """
        移除决策规则

        Args:
            rule: 要移除的决策规则
        """
        if rule in self._rules:
            self._rules.remove(rule)
            logger.debug(f"Removed decision rule: {rule.__class__.__name__}")

    def clear_rules(self) -> None:
        """清空所有规则"""
        self._rules.clear()
        logger.debug("Cleared all decision rules")

    def decide(self, orientation: Orientation) -> Decision:
        """
        执行决策阶段

        Args:
            orientation: Orient 阶段的导向结果

        Returns:
            决策结果
        """
        logger.debug(f"Deciding for orientation: {orientation.intent.action_type if orientation.intent else 'N/A'}")

        errors = []
        is_valid = True

        # 检查导向有效性
        if not orientation.is_valid:
            errors.extend(orientation.errors)
            is_valid = False

        if not orientation.intent:
            errors.append("No intent recognized")
            is_valid = False

        # 尝试应用规则
        decision = None
        if is_valid:
            for rule in self._rules:
                if rule.can_handle(orientation):
                    try:
                        decision = rule.evaluate(orientation)
                        if decision:
                            logger.debug(
                                f"Rule {rule.__class__.__name__} generated decision: "
                                f"{decision.action_type}"
                            )
                            break
                    except Exception as e:
                        logger.error(f"Rule {rule.__class__.__name__} failed: {e}")
                        errors.append(f"Decision rule failed: {e}")
                        is_valid = False

        # 如果没有规则匹配，创建无效决策
        if decision is None:
            errors.append("No decision rule matched")
            is_valid = False

            decision = Decision(
                orientation=orientation,
                action_type="unknown",
                is_valid=False,
                errors=errors,
            )

        # 添加元数据
        if orientation.context:
            decision.metadata["user_id"] = orientation.context.get("user_id")
            decision.metadata["role"] = orientation.context.get("role")

        logger.info(
            f"Decide phase completed: valid={decision.is_valid}, "
            f"action={decision.action_type}, "
            f"confidence={decision.confidence:.2f}, "
            f"requires_confirmation={decision.requires_confirmation}"
        )

        return decision


# 全局 Decide 阶段实例（单例）
_decide_phase_instance: Optional[DecidePhase] = None


def get_decide_phase() -> DecidePhase:
    """
    获取全局 Decide 阶段实例

    Returns:
        DecidePhase 单例
    """
    global _decide_phase_instance

    if _decide_phase_instance is None:
        _decide_phase_instance = DecidePhase()

    return _decide_phase_instance


def set_decide_phase(decide_phase: DecidePhase) -> None:
    """
    设置全局 Decide 阶段实例（用于测试）

    Args:
        decide_phase: DecidePhase 实例
    """
    global _decide_phase_instance
    _decide_phase_instance = decide_phase


# 导出
__all__ = [
    "Decision",
    "DecisionRule",
    "IntentBasedRule",
    "DefaultDecisionRule",
    "DecidePhase",
    "get_decide_phase",
    "set_decide_phase",
    "HIGH_RISK_ACTIONS",
    "FINANCIAL_ACTIONS",
    "ACTION_REQUIRED_PARAMS",
]
