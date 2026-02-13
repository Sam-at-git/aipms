"""
core/domain/rules/guest_rules.py

客人规则 - SPEC-49

定义客人相关的业务规则：
- 客人等级自动升级规则
- 黑名单检查规则
- VIP 客人特殊服务规则
"""
from typing import Any
from decimal import Decimal
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


# 客人等级定义
GUEST_TIERS = {
    "basic": 0,       # 普通客人
    "silver": 1000,   # 银卡会员（累计消费满1000元）
    "gold": 5000,     # 金卡会员（累计消费满5000元）
    "vip": 15000,     # VIP会员（累计消费满15000元）
}


def register_guest_rules(engine: RuleEngine) -> None:
    """
    注册所有客人规则

    Args:
        engine: 规则引擎实例
    """
    # 客人等级自动升级规则
    engine.register_rule(Rule(
        rule_id="guest_auto_upgrade_tier",
        name="客人等级自动升级",
        description="根据累计消费自动升级客人等级",
        condition=FunctionCondition(
            _should_upgrade_tier,
            "等级升级检查"
        ),
        action=_upgrade_guest_tier,
        priority=80
    ))

    # 黑名单检查规则
    engine.register_rule(Rule(
        rule_id="guest_blacklist_check",
        name="黑名单检查",
        description="阻止黑名单客人的操作",
        condition=FunctionCondition(
            _is_blacklisted_guest,
            "黑名单检查"
        ),
        action=_block_blacklisted_guest,
        priority=100
    ))

    # VIP 特殊服务规则
    engine.register_rule(Rule(
        rule_id="guest_vip_service",
        name="VIP特殊服务",
        description="为VIP客人提供特殊服务（自动升级房型等）",
        condition=FunctionCondition(
            _is_vip_guest,
            "VIP客人检查"
        ),
        action=_provide_vip_service,
        priority=60
    ))

    # 首次客人识别规则
    engine.register_rule(Rule(
        rule_id="guest_first_time_recognition",
        name="首次客人识别",
        description="识别首次入住的客人并提供欢迎服务",
        condition=FunctionCondition(
            _is_first_time_guest,
            "首次客人检查"
        ),
        action=_welcome_first_time_guest,
        priority=40
    ))

    logger.info("Guest rules registered")


# ==================== 规则条件函数 ====================

def _should_upgrade_tier(context: RuleContext) -> bool:
    """检查是否应该升级客人等级"""
    guest = context.entity
    if not guest:
        return False

    # 获取当前累计消费
    current_spending = _get_guest_total_spending(guest)
    current_tier = _get_guest_tier(guest)

    # 检查是否达到下一等级
    for tier_name, threshold in sorted(GUEST_TIERS.items(), key=lambda x: x[1], reverse=True):
        if current_spending >= threshold and _tier_rank(tier_name) > _tier_rank(current_tier):
            return True

    return False


def _is_blacklisted_guest(context: RuleContext) -> bool:
    """检查是否是黑名单客人"""
    guest = context.entity
    if not guest:
        return False

    if hasattr(guest, 'is_blacklisted'):
        return guest.is_blacklisted
    elif isinstance(guest, dict):
        return guest.get("is_blacklisted", False)

    return False


def _is_vip_guest(context: RuleContext) -> bool:
    """检查是否是VIP客人"""
    guest = context.entity
    if not guest:
        return False

    tier = _get_guest_tier(guest)
    return tier == "vip"


def _is_first_time_guest(context: RuleContext) -> bool:
    """检查是否是首次入住客人"""
    guest = context.entity
    if not guest:
        return False

    if hasattr(guest, 'reservation_count'):
        return guest.reservation_count == 0
    elif isinstance(guest, dict):
        return guest.get("reservation_count", 0) == 0

    return False


# ==================== 规则动作函数 ====================

def _upgrade_guest_tier(context: RuleContext) -> None:
    """升级客人等级"""
    guest = context.entity
    if not guest:
        return

    current_spending = _get_guest_total_spending(guest)
    current_tier = _get_guest_tier(guest)

    # 确定新等级
    new_tier = current_tier
    for tier_name, threshold in sorted(GUEST_TIERS.items(), key=lambda x: x[1]):
        if current_spending >= threshold and _tier_rank(tier_name) > _tier_rank(current_tier):
            new_tier = tier_name
            break

    if new_tier != current_tier:
        context.metadata["tier_upgraded"] = True
        context.metadata["old_tier"] = current_tier
        context.metadata["new_tier"] = new_tier

        logger.info(f"Guest {guest} tier upgraded: {current_tier} -> {new_tier}")

        # 发布等级升级事件
        from core.engine.event_bus import event_bus
        event = Event(
            event_type="guest_tier_upgraded",
            timestamp=datetime.now(),
            data={
                "guest": guest,
                "old_tier": current_tier,
                "new_tier": new_tier,
                "total_spending": current_spending
            },
            source="guest_rules"
        )
        event_bus.publish(event)


def _block_blacklisted_guest(context: RuleContext) -> None:
    """阻止黑名单客人的操作"""
    guest = context.entity
    action = context.action

    context.metadata["blocked"] = True
    context.metadata["block_reason"] = "guest_is_blacklisted"

    logger.warning(f"Blacklisted guest {guest} attempted action: {action}")

    # 发布黑名单阻止事件
    from core.engine.event_bus import event_bus
    event = Event(
        event_type="guest_blacklisted_action_blocked",
        timestamp=datetime.now(),
        data={
            "guest": guest,
            "action": action
        },
        source="guest_rules"
    )
    event_bus.publish(event)


def _provide_vip_service(context: RuleContext) -> None:
    """为VIP客人提供特殊服务"""
    guest = context.entity

    context.metadata["vip_service"] = True

    # 根据操作类型提供不同的VIP服务
    if context.action == "checkin" or context.action == "walkin_checkin":
        # VIP入住时可以自动升级房型
        context.metadata["auto_upgrade_available"] = True

    logger.info(f"VIP service provided for guest {guest}")

    # 发布VIP服务事件
    from core.engine.event_bus import event_bus
    event = Event(
        event_type="guest_vip_service_provided",
        timestamp=datetime.now(),
        data={
            "guest": guest,
            "action": context.action
        },
        source="guest_rules"
    )
    event_bus.publish(event)


def _welcome_first_time_guest(context: RuleContext) -> None:
    """欢迎首次客人"""
    guest = context.entity

    context.metadata["first_time_guest"] = True
    context.metadata["welcome_message"] = "欢迎首次入住！"

    logger.info(f"First time guest {guest} welcomed")

    # 发布首次客人事件
    from core.engine.event_bus import event_bus
    event = Event(
        event_type="guest_first_time_visit",
        timestamp=datetime.now(),
        data={
            "guest": guest
        },
        source="guest_rules"
    )
    event_bus.publish(event)


# ==================== 辅助函数 ====================

def _get_guest_tier(guest: Any) -> str:
    """获取客人等级"""
    if hasattr(guest, 'tier'):
        return guest.tier.value if hasattr(guest.tier, 'value') else guest.tier
    elif isinstance(guest, dict):
        return guest.get("tier", "basic")
    return "basic"


def _get_guest_total_spending(guest: Any) -> float:
    """获取客人累计消费"""
    if hasattr(guest, 'total_spending'):
        return float(guest.total_spending)
    elif isinstance(guest, dict):
        return float(guest.get("total_spending", 0))
    return 0.0


def _tier_rank(tier: str) -> int:
    """获取客人等级的排名（数字越大等级越高）"""
    ranks = {"basic": 0, "silver": 1, "gold": 2, "vip": 3}
    return ranks.get(tier, 0)


# ==================== 便捷函数 ====================

def calculate_guest_tier(total_spending: float) -> str:
    """
    根据累计消费计算客人等级

    Args:
        total_spending: 累计消费金额

    Returns:
        客人等级
    """
    for tier_name, threshold in sorted(GUEST_TIERS.items(), key=lambda x: x[1], reverse=True):
        if total_spending >= threshold:
            return tier_name
    return "basic"


def get_tier_threshold(tier: str) -> int:
    """
    获取升级到指定等级所需的消费阈值

    Args:
        tier: 客人等级

    Returns:
        消费阈值
    """
    return GUEST_TIERS.get(tier, 0)


def get_next_tier_threshold(current_tier: str, current_spending: float) -> tuple[str, int]:
    """
    获取下一等级及其阈值

    Args:
        current_tier: 当前等级
        current_spending: 当前累计消费

    Returns:
        (下一等级, 阈值)，如果没有下一等级则返回 (current_tier, 0)
    """
    current_rank = _tier_rank(current_tier)

    for tier_name, threshold in sorted(GUEST_TIERS.items(), key=lambda x: x[1]):
        rank = _tier_rank(tier_name)
        if rank > current_rank and current_spending < threshold:
            return tier_name, threshold

    return current_tier, 0


__all__ = [
    "register_guest_rules",
    "calculate_guest_tier",
    "get_tier_threshold",
    "get_next_tier_threshold",
    "GUEST_TIERS",
]
