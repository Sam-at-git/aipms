"""
core/engine/state_machine.py

状态机引擎 - 支持状态转换和副作用
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    """
    状态转换定义

    Attributes:
        from_state: 源状态
        to_state: 目标状态
        trigger: 触发动作
        condition: 可选的转换条件
        side_effects: 副作用函数列表
    """

    from_state: str
    to_state: str
    trigger: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    side_effects: List[Callable[[], None]] = field(default_factory=list)

    def is_allowed(self, context: Dict[str, Any]) -> bool:
        """检查转换是否被允许"""
        if self.condition is None:
            return True
        try:
            return self.condition(context)
        except Exception as e:
            logger.error(f"Error checking transition condition: {e}")
            return False

    def execute_side_effects(self) -> None:
        """执行副作用"""
        for effect in self.side_effects:
            try:
                effect()
            except Exception as e:
                logger.error(f"Error executing side effect: {e}")


@dataclass
class StateMachineConfig:
    """
    状态机配置

    Attributes:
        name: 状态机名称
        states: 所有状态的列表
        transitions: 转换列表
        initial_state: 初始状态
    """

    name: str
    states: List[str]
    transitions: List[StateTransition]
    initial_state: str


@dataclass
class StateMachineSnapshot:
    """
    状态机快照 - 用于撤销/重做

    Attributes:
        current_state: 当前状态
        previous_state: 前一状态
        transition: 触发的转换
        timestamp: 快照时间
    """

    current_state: str
    previous_state: str
    transition: Optional[StateTransition]
    timestamp: float


class StateMachine:
    """
    状态机引擎

    特性：
    - 状态转换验证
    - 副作用执行
    - 历史记录（用于审计）
    - 快照支持

    Example:
        >>> machine = StateMachine(
        ...     config=StateMachineConfig(
        ...         name="Room",
        ...         states=["vacant", "occupied", "dirty"],
        ...         transitions=[...],
        ...         initial_state="vacant"
        ...     )
        ... )
        >>> if machine.can_transition_to("occupied", "checkin"):
        ...     machine.transition_to("occupied", "checkin")
    """

    def __init__(self, config: StateMachineConfig):
        self._config = config
        self._current_state = config.initial_state
        self._history: List[StateMachineSnapshot] = []
        self._transition_map: Dict[str, Dict[str, StateTransition]] = {}

        # 构建转换映射: (from_state, trigger) -> transition
        for t in config.transitions:
            if t.from_state not in self._transition_map:
                self._transition_map[t.from_state] = {}
            self._transition_map[t.from_state][t.trigger] = t

    @property
    def current_state(self) -> str:
        """获取当前状态"""
        return self._current_state

    @property
    def config(self) -> StateMachineConfig:
        """获取状态机配置"""
        return self._config

    def can_transition_to(self, target_state: str, trigger: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state: 目标状态
            trigger: 触发动作
            context: 可选的上下文数据

        Returns:
            True 如果转换被允许
        """
        if target_state not in self._config.states:
            return False

        transitions = self._transition_map.get(self._current_state, {})
        transition = transitions.get(trigger)

        if transition is None or transition.to_state != target_state:
            return False

        if transition.is_allowed(context or {}):
            return True

        return False

    def transition_to(self, target_state: str, trigger: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        执行状态转换

        Args:
            target_state: 目标状态
            trigger: 触发动作
            context: 可选的上下文数据

        Returns:
            True 如果转换成功
        """
        if not self.can_transition_to(target_state, trigger, context):
            logger.warning(
                f"Invalid transition: {self._current_state} -> {target_state} (trigger: {trigger})"
            )
            return False

        transitions = self._transition_map.get(self._current_state, {})
        transition = transitions.get(trigger)

        # 记录快照
        snapshot = StateMachineSnapshot(
            current_state=self._current_state,
            previous_state=self._current_state,
            transition=transition,
            timestamp=__import__("time").time(),
        )

        # 执行转换
        previous_state = self._current_state
        self._current_state = target_state

        # 执行副作用
        if transition:
            transition.execute_side_effects()

        # 更新快照
        snapshot.previous_state = previous_state
        self._history.append(snapshot)

        logger.info(f"State transition: {previous_state} -> {target_state} (trigger: {trigger})")
        return True

    def get_history(self) -> List[StateMachineSnapshot]:
        """获取转换历史"""
        return list(self._history)

    def reset(self, state: Optional[str] = None) -> None:
        """
        重置状态机

        Args:
            state: 要重置到的状态，如果为 None 则使用初始状态
        """
        self._current_state = state if state is not None else self._config.initial_state
        self._history.clear()


class StateMachineEngine:
    """
    状态机引擎管理器 - 管理多个状态机实例

    Example:
        >>> engine = StateMachineEngine()
        >>> engine.register("Room", room_state_machine)
        >>> room_machine = engine.get("Room")
        >>> room_machine.transition_to("occupied", "checkin")
    """

    def __init__(self):
        self._machines: Dict[str, StateMachine] = {}

    def register(self, entity_type: str, machine: StateMachine) -> None:
        """注册状态机"""
        self._machines[entity_type] = machine
        logger.info(f"StateMachine registered for {entity_type}")

    def get(self, entity_type: str) -> Optional[StateMachine]:
        """获取状态机"""
        return self._machines.get(entity_type)

    def get_all(self) -> Dict[str, StateMachine]:
        """获取所有状态机"""
        return self._machines.copy()

    def clear(self) -> None:
        """清空所有状态机（用于测试）"""
        self._machines.clear()


# 全局状态机引擎实例
state_machine_engine = StateMachineEngine()


# 导出
__all__ = [
    "StateTransition",
    "StateMachineConfig",
    "StateMachineSnapshot",
    "StateMachine",
    "StateMachineEngine",
    "state_machine_engine",
]
