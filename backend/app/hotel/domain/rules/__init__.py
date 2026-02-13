"""
core/domain/rules/ - 酒店业务规则模块

提供酒店业务的自动化规则，包括：
- 房间状态规则（退房转脏房等）
- 定价规则（周末、节假日、会员折扣）
- 客人规则（等级升级、黑名单、VIP服务）
"""
from app.hotel.domain.rules.room_rules import register_room_rules
from app.hotel.domain.rules.pricing_rules import register_pricing_rules
from app.hotel.domain.rules.guest_rules import register_guest_rules

__all__ = [
    "register_room_rules",
    "register_pricing_rules",
    "register_guest_rules",
]


def register_all_rules(rule_engine=None):
    """
    注册所有业务规则

    Args:
        rule_engine: 规则引擎实例，默认使用全局实例
    """
    if rule_engine is None:
        from core.engine.rule_engine import rule_engine as default_engine
        rule_engine = default_engine

    register_room_rules(rule_engine)
    register_pricing_rules(rule_engine)
    register_guest_rules(rule_engine)
