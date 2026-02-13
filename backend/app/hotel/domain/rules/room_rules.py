"""
core/domain/rules/room_rules.py

房间状态规则 - SPEC-47

定义房间状态转换的业务规则：
- 退房后房间自动变为 VACANT_DIRTY
- 入住时房间变为 OCCUPIED
- 清洁完成房间变为 VACANT_CLEAN
"""
from typing import Any
from datetime import datetime

from core.engine.rule_engine import (
    Rule,
    RuleContext,
    FunctionCondition,
    RuleEngine,
)
from core.engine.event_bus import Event
import logging

logger = logging.getLogger(__name__)


def register_room_rules(engine: RuleEngine) -> None:
    """
    注册所有房间规则

    Args:
        engine: 规则引擎实例
    """
    # 退房后房间自动转脏房
    engine.register_rule(Rule(
        rule_id="room_checkout_to_dirty",
        name="退房转脏房",
        description="客人退房后，房间状态自动变为 VACANT_DIRTY",
        condition=FunctionCondition(
            _is_checkout_action,
            "退房动作检查"
        ),
        action=_set_room_dirty,
        priority=100
    ))

    # 入住时房间变为 OCCUPIED
    engine.register_rule(Rule(
        rule_id="room_checkin_to_occupied",
        name="入住转占用",
        description="客人入住后，房间状态变为 OCCUPIED",
        condition=FunctionCondition(
            _is_checkin_action,
            "入住动作检查"
        ),
        action=_set_room_occupied,
        priority=100
    ))

    # 清洁完成房间变为 VACANT_CLEAN
    engine.register_rule(Rule(
        rule_id="room_clean_to_vacant",
        name="清洁转空闲",
        description="清洁任务完成后，房间状态变为 VACANT_CLEAN",
        condition=FunctionCondition(
            _is_cleaning_complete_action,
            "清洁完成动作检查"
        ),
        action=_set_room_vacant_clean,
        priority=100
    ))

    logger.info("Room rules registered")


# ==================== 规则条件函数 ====================

def _is_checkout_action(context: RuleContext) -> bool:
    """检查是否是退房动作"""
    return context.action == "checkout"


def _is_checkin_action(context: RuleContext) -> bool:
    """检查是否是入住动作"""
    return context.action in ("checkin", "walkin_checkin")


def _is_cleaning_complete_action(context: RuleContext) -> bool:
    """检查是否是清洁完成动作"""
    return context.action == "complete_task" and context.parameters.get("task_type") == "cleaning"


# ==================== 规则动作函数 ====================

def _set_room_dirty(context: RuleContext) -> None:
    """
    设置房间为脏房状态

    此动作应该由服务层在退房后执行
    这里仅作为规则定义，实际状态变更在服务层完成
    """
    room = context.entity
    if hasattr(room, 'status'):
        from app.models.ontology import RoomStatus
        # 实际的状态变更在服务层处理
        logger.info(f"Room {room} should be set to VACANT_DIRTY after checkout")
        # 这里可以发布事件让服务层处理
        from core.engine.event_bus import event_bus
        event = Event(
            event_type="room_status_change_requested",
            timestamp=datetime.now(),
            data={
                "room": room,
                "new_status": RoomStatus.VACANT_DIRTY,
                "reason": "checkout"
            },
            source="room_rules"
        )
        event_bus.publish(event)


def _set_room_occupied(context: RuleContext) -> None:
    """
    设置房间为占用状态

    此动作应该由服务层在入住时执行
    """
    room = context.entity
    if hasattr(room, 'status'):
        from app.models.ontology import RoomStatus
        logger.info(f"Room {room} should be set to OCCUPIED after checkin")
        from core.engine.event_bus import event_bus
        event = Event(
            event_type="room_status_change_requested",
            timestamp=datetime.now(),
            data={
                "room": room,
                "new_status": RoomStatus.OCCUPIED,
                "reason": "checkin"
            },
            source="room_rules"
        )
        event_bus.publish(event)


def _set_room_vacant_clean(context: RuleContext) -> None:
    """
    设置房间为空闲可住状态

    此动作应该由服务层在清洁完成后执行
    """
    room = context.entity
    if hasattr(room, 'status'):
        from app.models.ontology import RoomStatus
        logger.info(f"Room {room} should be set to VACANT_CLEAN after cleaning")
        from core.engine.event_bus import event_bus
        event = Event(
            event_type="room_status_change_requested",
            timestamp=datetime.now(),
            data={
                "room": room,
                "new_status": RoomStatus.VACANT_CLEAN,
                "reason": "cleaning_complete"
            },
            source="room_rules"
        )
        event_bus.publish(event)


# ==================== 便捷函数 ====================

def should_create_cleaning_task_after_checkout(room_status: str) -> bool:
    """
    判断退房后是否应该创建清洁任务

    Args:
        room_status: 房间当前状态

    Returns:
        是否需要创建清洁任务
    """
    from app.models.ontology import RoomStatus
    return room_status == RoomStatus.VACANT_DIRTY.value


def should_mark_room_occupied_after_checkin(room_status: str) -> bool:
    """
    判断入住后是否应该标记房间为占用

    Args:
        room_status: 房间当前状态

    Returns:
        是否应该标记为占用
    """
    from app.models.ontology import RoomStatus
    return room_status in (RoomStatus.VACANT_CLEAN.value, RoomStatus.VACANT_DIRTY.value)


__all__ = [
    "register_room_rules",
    "should_create_cleaning_task_after_checkout",
    "should_mark_room_occupied_after_checkin",
]
