"""
core/domain/rules/pricing_rules.py

定价规则 - SPEC-48

定义价格调整的业务规则：
- 周末价格上调规则
- 节假日价格规则
- 会员折扣规则
- 住宿天数折扣规则
"""
from datetime import date, timedelta
from typing import Any, Optional
from decimal import Decimal

from core.engine.rule_engine import (
    Rule,
    RuleContext,
    FunctionCondition,
    RuleEngine,
)
import logging

logger = logging.getLogger(__name__)


def register_pricing_rules(engine: RuleEngine) -> None:
    """
    注册所有定价规则

    Args:
        engine: 规则引擎实例
    """
    # 周末价格上调规则
    engine.register_rule(Rule(
        rule_id="pricing_weekend_surcharge",
        name="周末价格上调",
        description="周五、周六晚上价格上调 20%",
        condition=FunctionCondition(
            _is_weekend_booking,
            "周末预订检查"
        ),
        action=_apply_weekend_surcharge,
        priority=50
    ))

    # 节假日价格上调规则
    engine.register_rule(Rule(
        rule_id="pricing_holiday_surcharge",
        name="节假日价格上调",
        description="法定节假日价格上调 30%",
        condition=FunctionCondition(
            _is_holiday_booking,
            "节假日预订检查"
        ),
        action=_apply_holiday_surcharge,
        priority=60
    ))

    # 会员折扣规则
    engine.register_rule(Rule(
        rule_id="pricing_member_discount",
        name="会员折扣",
        description="根据客人等级提供折扣（VIP 15%，金卡 10%，银卡 5%）",
        condition=FunctionCondition(
            _is_member_booking,
            "会员预订检查"
        ),
        action=_apply_member_discount,
        priority=70
    ))

    # 长住折扣规则
    engine.register_rule(Rule(
        rule_id="pricing_long_stay_discount",
        name="长住折扣",
        description="连续住宿 7 天及以上享 10% 折扣，14 天及以上享 15% 折扣",
        condition=FunctionCondition(
            _is_long_stay,
            "长住检查"
        ),
        action=_apply_long_stay_discount,
        priority=40
    ))

    logger.info("Pricing rules registered")


# ==================== 规则条件函数 ====================

def _is_weekend_booking(context: RuleContext) -> bool:
    """检查是否是周末预订（周五、周六）"""
    check_in = context.parameters.get("check_in_date")
    if not check_in:
        return False

    if isinstance(check_in, str):
        check_in = date.fromisoformat(check_in)
    elif not isinstance(check_in, date):
        return False

    # 周五 (4) 或周六 (5)
    return check_in.weekday() in (4, 5)


def _is_holiday_booking(context: RuleContext) -> bool:
    """检查是否是节假日预订"""
    check_in = context.parameters.get("check_in_date")
    if not check_in:
        return False

    if isinstance(check_in, str):
        check_in = date.fromisoformat(check_in)
    elif not isinstance(check_in, date):
        return False

    # 中国法定节假日列表（简化版）
    holidays = _get_chinese_holidays(check_in.year)
    return check_in in holidays


def _is_member_booking(context: RuleContext) -> bool:
    """检查是否是会员预订"""
    guest = context.parameters.get("guest")
    if not guest:
        return False

    # 检查客人是否有会员等级
    if hasattr(guest, 'tier'):
        return guest.tier != "basic"
    elif isinstance(guest, dict):
        return guest.get("tier", "basic") != "basic"

    return False


def _is_long_stay(context: RuleContext) -> bool:
    """检查是否是长住（7天及以上）"""
    check_in = context.parameters.get("check_in_date")
    check_out = context.parameters.get("check_out_date")

    if not check_in or not check_out:
        return False

    if isinstance(check_in, str):
        check_in = date.fromisoformat(check_in)
    if isinstance(check_out, str):
        check_out = date.fromisoformat(check_out)

    nights = (check_out - check_in).days
    return nights >= 7


# ==================== 规则动作函数 ====================

def _apply_weekend_surcharge(context: RuleContext) -> None:
    """应用周末价格上调（20%）"""
    base_price = context.parameters.get("base_price")
    if base_price:
        surcharge = Decimal(str(base_price)) * Decimal("0.20")
        adjusted_price = Decimal(str(base_price)) + surcharge

        context.metadata["weekend_surcharge"] = float(surcharge)
        context.metadata["adjusted_price"] = float(adjusted_price)
        logger.info(f"Weekend surcharge applied: +{surcharge}")


def _apply_holiday_surcharge(context: RuleContext) -> None:
    """应用节假日价格上调（30%）"""
    base_price = context.parameters.get("base_price")
    if base_price:
        surcharge = Decimal(str(base_price)) * Decimal("0.30")
        adjusted_price = Decimal(str(base_price)) + surcharge

        context.metadata["holiday_surcharge"] = float(surcharge)
        context.metadata["adjusted_price"] = float(adjusted_price)
        logger.info(f"Holiday surcharge applied: +{surcharge}")


def _apply_member_discount(context: RuleContext) -> None:
    """应用会员折扣"""
    guest = context.parameters.get("guest")
    base_price = context.parameters.get("base_price")

    if not guest or not base_price:
        return

    # 获取会员等级
    if hasattr(guest, 'tier'):
        tier = guest.tier
    elif isinstance(guest, dict):
        tier = guest.get("tier", "basic")
    else:
        return

    # 折扣率
    discount_rates = {
        "vip": 0.15,      # VIP 15% 折扣
        "gold": 0.10,     # 金卡 10% 折扣
        "silver": 0.05,   # 银卡 5% 折扣
    }

    discount_rate = discount_rates.get(tier, 0)
    if discount_rate > 0:
        discount = Decimal(str(base_price)) * Decimal(str(discount_rate))
        adjusted_price = Decimal(str(base_price)) - discount

        context.metadata["member_discount"] = float(discount)
        context.metadata["adjusted_price"] = float(adjusted_price)
        context.metadata["discount_rate"] = discount_rate
        logger.info(f"Member discount applied ({tier}): -{discount}")


def _apply_long_stay_discount(context: RuleContext) -> None:
    """应用长住折扣"""
    check_in = context.parameters.get("check_in_date")
    check_out = context.parameters.get("check_out_date")
    base_price = context.parameters.get("base_price")

    if not all([check_in, check_out, base_price]):
        return

    if isinstance(check_in, str):
        check_in = date.fromisoformat(check_in)
    if isinstance(check_out, str):
        check_out = date.fromisoformat(check_out)

    nights = (check_out - check_in).days

    # 折扣率
    if nights >= 14:
        discount_rate = 0.15
    elif nights >= 7:
        discount_rate = 0.10
    else:
        return

    discount = Decimal(str(base_price)) * Decimal(str(discount_rate))
    adjusted_price = Decimal(str(base_price)) - discount

    context.metadata["long_stay_discount"] = float(discount)
    context.metadata["adjusted_price"] = float(adjusted_price)
    context.metadata["discount_rate"] = discount_rate
    context.metadata["nights"] = nights
    logger.info(f"Long stay discount applied ({nights} nights): -{discount}")


# ==================== 辅助函数 ====================

def _get_chinese_holidays(year: int) -> list[date]:
    """
    获取中国法定节假日列表（简化版）

    Args:
        year: 年份

    Returns:
        节假日日期列表
    """
    # 简化版节假日列表
    # 实际项目中应该从配置或数据库读取
    holidays = []

    # 元旦
    holidays.append(date(year, 1, 1))

    # 春节（简化，每年日期不同）
    # 2025年春节：1月28日-2月3日
    if year == 2025:
        holidays.extend([date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
                        date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2), date(2025, 2, 3)])

    # 清明节
    holidays.append(date(year, 4, 4))

    # 劳动节
    holidays.extend([date(year, 5, 1), date(year, 5, 2), date(year, 5, 3)])

    # 端午节（简化）
    holidays.append(date(year, 5, 31))

    # 中秋节（简化）
    holidays.append(date(year, 9, 6))

    # 国庆节
    holidays.extend([date(year, 10, 1), date(year, 10, 2), date(year, 10, 3),
                    date(year, 10, 4), date(year, 10, 5), date(year, 10, 6), date(year, 10, 7)])

    return holidays


# ==================== 便捷函数 ====================

def calculate_room_price(
    base_price: float,
    check_in: date,
    check_out: date,
    guest_tier: str = "basic"
) -> tuple[float, dict]:
    """
    计算房间价格（应用所有定价规则）

    Args:
        base_price: 基础价格
        check_in: 入住日期
        check_out: 退房日期
        guest_tier: 客人等级

    Returns:
        (最终价格, 优惠明细)
    """
    price = Decimal(str(base_price))
    adjustments = []

    # 周末上调
    if check_in.weekday() in (4, 5):
        surcharge = price * Decimal("0.20")
        price += surcharge
        adjustments.append({"name": "周末上调", "amount": float(surcharge)})

    # 节假日上调
    holidays = _get_chinese_holidays(check_in.year)
    if check_in in holidays:
        surcharge = price * Decimal("0.30")
        price += surcharge
        adjustments.append({"name": "节假日上调", "amount": float(surcharge)})

    # 会员折扣
    discount_rates = {
        "vip": 0.15,
        "gold": 0.10,
        "silver": 0.05,
    }
    if guest_tier in discount_rates:
        discount = Decimal(str(base_price)) * Decimal(str(discount_rates[guest_tier]))
        price -= discount
        adjustments.append({"name": f"{guest_tier.upper()}会员折扣", "amount": -float(discount)})

    # 长住折扣
    nights = (check_out - check_in).days
    if nights >= 14:
        discount = Decimal(str(base_price)) * Decimal("0.15")
        price -= discount
        adjustments.append({"name": "长住折扣（14+天）", "amount": -float(discount)})
    elif nights >= 7:
        discount = Decimal(str(base_price)) * Decimal("0.10")
        price -= discount
        adjustments.append({"name": "长住折扣（7+天）", "amount": -float(discount)})

    return float(price), {"adjustments": adjustments, "nights": nights}


def is_weekend(date_to_check: date) -> bool:
    """检查是否是周末（周五或周六）"""
    return date_to_check.weekday() in (4, 5)


def is_holiday(date_to_check: date) -> bool:
    """检查是否是节假日"""
    holidays = _get_chinese_holidays(date_to_check.year)
    return date_to_check in holidays


__all__ = [
    "register_pricing_rules",
    "calculate_room_price",
    "is_weekend",
    "is_holiday",
]
