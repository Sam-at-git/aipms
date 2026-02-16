"""
core/ooda/loop.py

OODA Loop 编排器 - 组合 Observe、Orient、Decide、Act 四个阶段
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import logging
import threading

from core.ooda.observe import ObservePhase, Observation
from core.ooda.orient import OrientPhase, Orientation
from core.ooda.decide import DecidePhase, OodaDecision as Decision
from core.ooda.act import ActPhase, OodaActionResult as ActionResult

logger = logging.getLogger(__name__)


@dataclass
class OodaLoopResult:
    """
    OODA Loop 执行结果

    Attributes:
        observation: Observe 阶段结果
        orientation: Orient 阶段结果
        decision: Decide 阶段结果
        action_result: Act 阶段结果
        success: 是否成功
        completed_stages: 已完成的阶段列表
        errors: 错误列表
        requires_confirmation: 是否需要确认
        timestamp: 执行时间戳
    """

    observation: Optional[Observation] = None
    orientation: Optional[Orientation] = None
    decision: Optional[Decision] = None
    action_result: Optional[ActionResult] = None
    success: bool = False
    completed_stages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "completed_stages": self.completed_stages,
            "errors": self.errors,
            "requires_confirmation": self.requires_confirmation,
            "timestamp": self.timestamp.isoformat(),
            "observation": self.observation.to_dict() if self.observation else None,
            "orientation": self.orientation.to_dict() if self.orientation else None,
            "decision": self.decision.to_dict() if self.decision else None,
            "action_result": self.action_result.to_dict() if self.action_result else None,
        }


class OodaLoop:
    """
    OODA Loop 编排器

    组合 Observe、Orient、Decide、Act 四个阶段，提供完整的决策循环。

    特性：
    - 完整的四个阶段流程
    - 阶段错误处理
    - 中间结果追踪
    - 确认流程支持

    Example:
        >>> loop = OodaLoop(observe, orient, decide, act)
        >>> result = loop.execute("帮客人办理入住")
        >>> if result.requires_confirmation:
        ...     # 向用户请求确认
        ...     confirmed = get_user_confirmation()
        ...     if confirmed:
        ...         result = loop.execute("帮客人办理入住", skip_confirmation=True)
    """

    def __init__(
        self,
        observe_phase: ObservePhase,
        orient_phase: OrientPhase,
        decide_phase: DecidePhase,
        act_phase: ActPhase,
    ):
        """
        初始化 OODA Loop

        Args:
            observe_phase: Observe 阶段
            orient_phase: Orient 阶段
            decide_phase: Decide 阶段
            act_phase: Act 阶段
        """
        self._observe = observe_phase
        self._orient = orient_phase
        self._decide = decide_phase
        self._act = act_phase

    def execute(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        skip_confirmation: bool = False,
    ) -> OodaLoopResult:
        """
        执行完整的 OODA 循环

        Args:
            input: 用户输入
            context: 额外上下文
            skip_confirmation: 是否跳过确认检查

        Returns:
            OODA Loop 执行结果
        """
        result = OodaLoopResult()
        errors = []

        logger.info(f"Starting OODA Loop: input={input[:50]}...")

        # Observe 阶段
        try:
            observation = self._observe.observe(input, context=context)
            result.observation = observation
            result.completed_stages.append("observe")

            if not observation.is_valid:
                errors.extend(observation.validation_errors)
                logger.warning(f"Observe phase failed: {errors}")
                result.errors = errors
                return result

        except Exception as e:
            error_msg = f"Observe phase error: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return result

        # Orient 阶段
        try:
            orientation = self._orient.orient(observation)
            result.orientation = orientation

            if not orientation.is_valid:
                errors.extend(orientation.errors)
                logger.warning(f"Orient phase failed: {errors}")
                result.errors = errors
                return result

            result.completed_stages.append("orient")

        except Exception as e:
            error_msg = f"Orient phase error: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return result

        # Decide 阶段
        try:
            decision = self._decide.decide(orientation)
            result.decision = decision

            # 设置确认标志（无论是否有效）
            result.requires_confirmation = decision.requires_confirmation

            if not decision.is_valid:
                errors.extend(decision.errors)
                logger.warning(f"Decide phase failed: {errors}")
                result.errors = errors

                # 无效且需要确认时返回（用于收集缺失字段）
                if decision.requires_confirmation and not skip_confirmation:
                    return result
                return result

            result.completed_stages.append("decide")

            # 检查确认需求
            if decision.requires_confirmation and not skip_confirmation:
                logger.info("Decision requires confirmation")
                return result

        except Exception as e:
            error_msg = f"Decide phase error: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return result

        # Act 阶段
        try:
            action_result = self._act.act(decision, skip_confirmation=skip_confirmation)
            result.action_result = action_result
            result.completed_stages.append("act")

            result.success = action_result.success

            if not action_result.success:
                if action_result.error_message:
                    errors.append(action_result.error_message)
                logger.warning(f"Act phase failed: {action_result.error_message}")

        except Exception as e:
            error_msg = f"Act phase error: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return result

        result.errors = errors

        logger.info(
            f"OODA Loop completed: success={result.success}, "
            f"stages={result.completed_stages}, "
            f"requires_confirmation={result.requires_confirmation}"
        )

        return result

    def execute_with_confirmation(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> OodaLoopResult:
        """
        执行 OODA 循环（需要确认时返回，不执行 Act）

        这是两阶段确认的第一步：
        1. 执行 Observe -> Orient -> Decide
        2. 如果需要确认，返回决策信息
        3. 用户确认后，使用 execute(..., skip_confirmation=True) 执行完整流程

        Args:
            input: 用户输入
            context: 额外上下文

        Returns:
            OODA Loop 执行结果（可能需要确认）
        """
        result = OodaLoopResult()
        errors = []

        logger.info(f"Starting OODA Loop (with confirmation): input={input[:50]}...")

        # Observe 阶段
        try:
            observation = self._observe.observe(input, context=context)
            result.observation = observation

            if not observation.is_valid:
                errors.extend(observation.validation_errors)
                result.errors = errors
                return result

            result.completed_stages.append("observe")

        except Exception as e:
            result.errors.append(f"Observe phase error: {e}")
            return result

        # Orient 阶段
        try:
            orientation = self._orient.orient(observation)
            result.orientation = orientation

            if not orientation.is_valid:
                errors.extend(orientation.errors)
                result.errors = errors
                return result

            result.completed_stages.append("orient")

        except Exception as e:
            result.errors.append(f"Orient phase error: {e}")
            return result

        # Decide 阶段
        try:
            decision = self._decide.decide(orientation)
            result.decision = decision

            if not decision.is_valid:
                errors.extend(decision.errors)
                result.errors = errors
                return result

            # 设置确认标志
            result.requires_confirmation = decision.requires_confirmation
            result.completed_stages.append("decide")

        except Exception as e:
            result.errors.append(f"Decide phase error: {e}")
            return result

        logger.info(
            f"OODA Loop (with confirmation) completed: "
            f"stages={result.completed_stages}, "
            f"requires_confirmation={result.requires_confirmation}"
        )

        return result


# 全局 OODA Loop 实例（线程安全）
_ooda_loop_instance: Optional[OodaLoop] = None
_ooda_loop_lock = threading.Lock()


def get_ooda_loop() -> Optional[OodaLoop]:
    """
    获取全局 OODA Loop 实例

    Returns:
        OodaLoop 单例，如果未初始化则返回 None
    """
    return _ooda_loop_instance


def set_ooda_loop(loop: Optional[OodaLoop]) -> None:
    """
    设置全局 OODA Loop 实例（线程安全）

    Args:
        loop: OodaLoop 实例，或 None 以重置
    """
    global _ooda_loop_instance
    _ooda_loop_instance = loop


# 导出
__all__ = [
    "OodaLoopResult",
    "OodaLoop",
    "get_ooda_loop",
    "set_ooda_loop",
]
