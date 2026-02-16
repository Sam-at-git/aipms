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
import threading

from core.ooda.orient import Orientation
from core.ooda.intent import IntentResult
from core.security.checker import permission_checker, Permission

logger = logging.getLogger(__name__)


# ========== Registry-based helpers (replacing hardcoded constants) ==========

def _is_high_risk(action_type: str, registry) -> bool:
    """Check if action is high-risk via OntologyRegistry metadata."""
    if not registry:
        return False
    action = registry.get_action_by_name(action_type)
    if not action:
        return False
    return action.risk_level in ("high", "critical")


def _is_financial(action_type: str, registry) -> bool:
    """Check if action involves financial operations via OntologyRegistry metadata."""
    if not registry:
        return False
    action = registry.get_action_by_name(action_type)
    return action.is_financial if action else False


def _get_required_params(action_type: str, registry) -> List[str]:
    """Get required parameters for an action from OntologyRegistry metadata."""
    if not registry:
        return []
    action = registry.get_action_by_name(action_type)
    return list(action.ui_required_fields) if action and action.ui_required_fields else []


@dataclass
class OodaDecision:
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
    def evaluate(self, orientation: Orientation) -> Optional[OodaDecision]:
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

    def __init__(self, action_type: str, required_params: Optional[List[str]] = None, registry=None):
        """
        初始化基于意图的规则

        Args:
            action_type: 动作类型
            required_params: 必需参数列表
            registry: OntologyRegistry instance for risk/financial lookups
        """
        self._action_type = action_type
        self._required_params = required_params or []
        self._registry = registry

    def can_handle(self, orientation: Orientation) -> bool:
        """检查是否能处理该导向"""
        if not orientation.intent:
            return False
        return orientation.intent.action_type == self._action_type

    def evaluate(self, orientation: Orientation) -> Optional[OodaDecision]:
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
            _is_high_risk(self._action_type, self._registry) or
            _is_financial(self._action_type, self._registry) or
            intent.requires_confirmation
        )

        # 计算置信度
        param_completeness = 1.0
        if self._required_params:
            provided = sum(1 for p in self._required_params if p in action_params and action_params[p])
            param_completeness = provided / len(self._required_params)

        confidence = intent.confidence * param_completeness

        return OodaDecision(
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

    处理任何有意图的导向，从 OntologyRegistry 获取参数定义
    """

    def __init__(self, registry=None):
        """
        Args:
            registry: OntologyRegistry instance for action metadata lookups
        """
        self._registry = registry

    def can_handle(self, orientation: Orientation) -> bool:
        """检查是否能处理该导向"""
        return orientation.intent is not None

    def evaluate(self, orientation: Orientation) -> Optional[OodaDecision]:
        """评估导向并生成决策"""
        if not self.can_handle(orientation):
            return None

        intent = orientation.intent
        if intent is None:
            return None

        action_type = intent.action_type
        action_params = intent.entities.copy()

        # 获取必需参数（from OntologyRegistry）
        required_params = _get_required_params(action_type, self._registry)

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

        # 检查是否需要确认（from OntologyRegistry）
        requires_confirmation = (
            _is_high_risk(action_type, self._registry) or
            _is_financial(action_type, self._registry) or
            intent.requires_confirmation
        )

        # 计算置信度
        param_completeness = 1.0
        if required_params:
            provided = sum(1 for p in required_params if p in action_params and action_params[p])
            param_completeness = provided / len(required_params)

        confidence = intent.confidence * param_completeness

        return OodaDecision(
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

    def __init__(self, registry=None):
        """
        初始化 Decide 阶段

        Args:
            registry: OntologyRegistry instance for action metadata lookups
        """
        self._rules: List[DecisionRule] = []
        self._registry = registry

        # 默认规则
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """设置默认规则"""
        # 添加默认规则作为后备
        self.add_rule(DefaultDecisionRule(registry=self._registry))

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

    def decide(self, orientation: Orientation) -> OodaDecision:
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

            decision = OodaDecision(
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


# 全局 Decide 阶段实例（线程安全）
_decide_phase_instance: Optional[DecidePhase] = None
_decide_phase_lock = threading.Lock()


def get_decide_phase() -> DecidePhase:
    """
    获取全局 Decide 阶段实例（线程安全）

    Returns:
        DecidePhase 单例
    """
    global _decide_phase_instance

    if _decide_phase_instance is None:
        with _decide_phase_lock:
            if _decide_phase_instance is None:
                _decide_phase_instance = DecidePhase()

    return _decide_phase_instance


def set_decide_phase(decide_phase: Optional[DecidePhase]) -> None:
    """
    设置全局 Decide 阶段实例（用于测试）

    Args:
        decide_phase: DecidePhase 实例，或 None 以重置
    """
    global _decide_phase_instance
    _decide_phase_instance = decide_phase


# Backward-compat alias
Decision = OodaDecision

# 导出
__all__ = [
    "OodaDecision",
    "Decision",  # backward-compat alias
    "DecisionRule",
    "IntentBasedRule",
    "DefaultDecisionRule",
    "DecidePhase",
    "get_decide_phase",
    "set_decide_phase",
]
