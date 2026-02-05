"""
core/ooda/act.py

Act 阶段 - OODA Loop 第四步
负责动作执行和结果处理
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import logging

from core.ooda.decide import Decision

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """
    动作执行结果 - Act 阶段的输出

    Attributes:
        decision: Decide 阶段的决策
        success: 是否成功
        result_data: 结果数据
        error_message: 错误消息
        metadata: 额外元数据
        timestamp: 执行时间戳
        executed: 是否实际执行了动作（False 表示需要确认）
    """

    decision: Decision
    success: bool = False
    result_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    executed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "action_type": self.decision.action_type,
            "success": self.success,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "executed": self.executed,
        }


class ActionHandler(ABC):
    """动作处理器接口"""

    @abstractmethod
    def can_handle(self, action_type: str) -> bool:
        """
        检查是否能处理该动作类型

        Args:
            action_type: 动作类型

        Returns:
            如果能处理返回 True
        """
        pass

    @abstractmethod
    def execute(self, decision: Decision) -> ActionResult:
        """
        执行动作

        Args:
            decision: 决策结果

        Returns:
            动作执行结果
        """
        pass


class MockActionHandler(ActionHandler):
    """
    模拟动作处理器（用于测试）

    返回预设的结果，不调用实际服务
    """

    def __init__(self, action_types: Optional[List[str]] = None):
        """
        初始化模拟处理器

        Args:
            action_types: 能处理的动作类型列表，None 表示处理所有
        """
        self._action_types = action_types
        self._mock_results: Dict[str, Dict[str, Any]] = {}
        self.execute_calls: List[Decision] = []

    def set_mock_result(self, action_type: str, result: Dict[str, Any]) -> None:
        """设置模拟结果"""
        self._mock_results[action_type] = result

    def can_handle(self, action_type: str) -> bool:
        """检查是否能处理该动作类型"""
        if self._action_types is None:
            return True
        return action_type in self._action_types

    def execute(self, decision: Decision) -> ActionResult:
        """执行动作（模拟）"""
        self.execute_calls.append(decision)

        mock_result = self._mock_results.get(decision.action_type, {})

        return ActionResult(
            decision=decision,
            success=True,
            result_data=mock_result,
            executed=True,
        )


class DelegatingActionHandler(ActionHandler):
    """
    委托动作处理器

    将动作委托给外部服务执行
    """

    def __init__(self, service_registry: Optional[Dict[str, Any]] = None):
        """
        初始化委托处理器

        Args:
            service_registry: 服务注册表，动作类型到服务方法的映射
        """
        self._service_registry = service_registry or {}

    def can_handle(self, action_type: str) -> bool:
        """检查是否能处理该动作类型"""
        return action_type in self._service_registry

    def execute(self, decision: Decision) -> ActionResult:
        """执行动作（委托给服务）"""
        service_func = self._service_registry.get(decision.action_type)

        if service_func is None:
            return ActionResult(
                decision=decision,
                success=False,
                error_message=f"No service registered for action: {decision.action_type}",
            )

        try:
            result = service_func(decision.action_params)
            return ActionResult(
                decision=decision,
                success=True,
                result_data=result if isinstance(result, dict) else {"result": result},
                executed=True,
            )
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return ActionResult(
                decision=decision,
                success=False,
                error_message=str(e),
            )


class ActPhase:
    """
    Act 阶段 - OODA Loop 第四步

    特性：
    - 动作处理器链
    - 错误处理
    - 确认机制检查
    - 执行状态记录

    Example:
        >>> act = ActPhase()
        >>> act.add_handler(MockActionHandler(["checkin"]))
        >>> decision = Decision(...)
        >>> result = act.act(decision)
        >>> print(result.success)
    """

    def __init__(self):
        """初始化 Act 阶段"""
        self._handlers: List[ActionHandler] = []

    def add_handler(self, handler: ActionHandler) -> None:
        """
        添加动作处理器

        Args:
            handler: 动作处理器
        """
        self._handlers.append(handler)
        logger.debug(f"Added action handler: {handler.__class__.__name__}")

    def remove_handler(self, handler: ActionHandler) -> None:
        """
        移除动作处理器

        Args:
            handler: 要移除的动作处理器
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
            logger.debug(f"Removed action handler: {handler.__class__.__name__}")

    def clear_handlers(self) -> None:
        """清空所有处理器"""
        self._handlers.clear()
        logger.debug("Cleared all action handlers")

    def act(self, decision: Decision, skip_confirmation: bool = False) -> ActionResult:
        """
        执行动作阶段

        Args:
            decision: Decide 阶段的决策结果
            skip_confirmation: 是否跳过确认检查（True 时即使需要确认也执行）

        Returns:
            动作执行结果
        """
        logger.debug(f"Acting on decision: {decision.action_type}")

        # 检查决策有效性
        if not decision.is_valid:
            return ActionResult(
                decision=decision,
                success=False,
                error_message="Invalid decision: " + "; ".join(decision.errors),
            )

        # 检查确认需求
        if decision.requires_confirmation and not skip_confirmation:
            return ActionResult(
                decision=decision,
                success=False,
                error_message="Action requires confirmation",
                executed=False,
            )

        # 查找能处理的处理器
        handler = None
        for h in self._handlers:
            if h.can_handle(decision.action_type):
                handler = h
                break

        if handler is None:
            return ActionResult(
                decision=decision,
                success=False,
                error_message=f"No handler found for action: {decision.action_type}",
            )

        # 执行动作
        try:
            result = handler.execute(decision)

            # 添加元数据
            if decision.metadata:
                result.metadata.update(decision.metadata)

            logger.info(
                f"Act phase completed: success={result.success}, "
                f"action={decision.action_type}, "
                f"executed={result.executed}"
            )

            return result

        except Exception as e:
            logger.error(f"Action handler failed: {e}")
            return ActionResult(
                decision=decision,
                success=False,
                error_message=f"Handler failed: {e}",
            )


# 全局 Act 阶段实例
_act_phase_instance: Optional[ActPhase] = None


def get_act_phase() -> ActPhase:
    """
    获取全局 Act 阶段实例

    Returns:
        ActPhase 单例
    """
    global _act_phase_instance

    if _act_phase_instance is None:
        _act_phase_instance = ActPhase()

    return _act_phase_instance


def set_act_phase(act_phase: ActPhase) -> None:
    """
    设置全局 Act 阶段实例（用于测试）

    Args:
        act_phase: ActPhase 实例
    """
    global _act_phase_instance
    _act_phase_instance = act_phase


# 导出
__all__ = [
    "ActionResult",
    "ActionHandler",
    "MockActionHandler",
    "DelegatingActionHandler",
    "ActPhase",
    "get_act_phase",
    "set_act_phase",
]
