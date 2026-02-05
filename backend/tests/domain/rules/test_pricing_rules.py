"""
tests/domain/rules/test_pricing_rules.py

定价规则单元测试
"""
import pytest
from datetime import date, timedelta

from core.domain.rules.pricing_rules import (
    register_pricing_rules,
    calculate_room_price,
    is_weekend,
    is_holiday,
)
from core.engine.rule_engine import RuleContext, RuleEngine


class TestPricingRulesRegistration:
    """定价规则注册测试"""

    def test_register_pricing_rules(self):
        """测试注册定价规则"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        # 验证规则已注册
        assert engine.get_rule("pricing_weekend_surcharge") is not None
        assert engine.get_rule("pricing_holiday_surcharge") is not None
        assert engine.get_rule("pricing_member_discount") is not None
        assert engine.get_rule("pricing_long_stay_discount") is not None


class TestWeekendPricing:
    """周末定价测试"""

    def test_friday_is_weekend(self):
        """测试周五是周末"""
        # 2025年1月3日是周五
        friday = date(2025, 1, 3)
        assert is_weekend(friday) is True

    def test_saturday_is_weekend(self):
        """测试周六是周末"""
        # 2025年1月4日是周六
        saturday = date(2025, 1, 4)
        assert is_weekend(saturday) is True

    def test_sunday_is_not_weekend(self):
        """测试周日不是周末（酒店定义）"""
        # 2025年1月5日是周日
        sunday = date(2025, 1, 5)
        assert is_weekend(sunday) is False

    def test_weekday_is_not_weekend(self):
        """测试工作日不是周末"""
        # 2025年1月2日是周四
        thursday = date(2025, 1, 2)
        assert is_weekend(thursday) is False

    def test_weekend_surcharge_rule(self):
        """测试周末价格上调规则"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        # 周五预订
        friday = date(2025, 1, 3)
        context = RuleContext(
            entity=None,
            entity_type="pricing",  # 使用 pricing 作为实体类型
            action="calculate",
            parameters={
                "check_in_date": friday,
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "pricing_weekend_surcharge" in rule_ids
        assert context.metadata.get("weekend_surcharge") is not None


class TestHolidayPricing:
    """节假日定价测试"""

    def test_new_year_is_holiday(self):
        """测试元旦是节假日"""
        new_year = date(2025, 1, 1)
        assert is_holiday(new_year) is True

    def test_labor_day_is_holiday(self):
        """测试劳动节是节假日"""
        labor_day = date(2025, 5, 1)
        assert is_holiday(labor_day) is True

    def test_national_day_is_holiday(self):
        """测试国庆节是节假日"""
        national_day = date(2025, 10, 1)
        assert is_holiday(national_day) is True

    def test_regular_day_is_not_holiday(self):
        """测试普通日不是节假日"""
        regular_day = date(2025, 1, 2)
        assert is_holiday(regular_day) is False

    def test_holiday_surcharge_rule(self):
        """测试节假日价格上调规则"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        # 元旦预订
        new_year = date(2025, 1, 1)
        context = RuleContext(
            entity=None,
            entity_type="pricing",
            action="calculate",
            parameters={
                "check_in_date": new_year,
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "pricing_holiday_surcharge" in rule_ids
        assert context.metadata.get("holiday_surcharge") is not None


class TestMemberDiscount:
    """会员折扣测试"""

    def test_vip_member_discount(self):
        """测试VIP会员折扣"""
        class MockGuest:
            tier = "vip"

        engine = RuleEngine()
        register_pricing_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="pricing",
            action="calculate",
            parameters={
                "guest": MockGuest(),
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "pricing_member_discount" in rule_ids
        assert context.metadata.get("member_discount") is not None
        assert context.metadata.get("discount_rate") == 0.15

    def test_gold_member_discount(self):
        """测试金卡会员折扣"""
        class MockGuest:
            tier = "gold"

        engine = RuleEngine()
        register_pricing_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="pricing",
            action="calculate",
            parameters={
                "guest": MockGuest(),
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        assert context.metadata.get("discount_rate") == 0.10

    def test_silver_member_discount(self):
        """测试银卡会员折扣"""
        class MockGuest:
            tier = "silver"

        engine = RuleEngine()
        register_pricing_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="pricing",
            action="calculate",
            parameters={
                "guest": MockGuest(),
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        assert context.metadata.get("discount_rate") == 0.05

    def test_basic_member_no_discount(self):
        """测试普通会员无折扣"""
        class MockGuest:
            tier = "basic"

        engine = RuleEngine()
        register_pricing_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="pricing",
            action="calculate",
            parameters={
                "guest": MockGuest(),
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        # 基本会员不触发折扣规则（条件不满足）
        assert "pricing_member_discount" not in rule_ids


class TestLongStayDiscount:
    """长住折扣测试"""

    def test_7_nights_gets_discount(self):
        """测试7天及以上获得折扣"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        check_in = date(2025, 1, 5)
        check_out = date(2025, 1, 12)  # 7晚

        context = RuleContext(
            entity=None,
            entity_type="pricing",
            action="calculate",
            parameters={
                "check_in_date": check_in,
                "check_out_date": check_out,
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "pricing_long_stay_discount" in rule_ids
        assert context.metadata.get("discount_rate") == 0.10

    def test_14_nights_gets_higher_discount(self):
        """测试14天及以上获得更高折扣"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        check_in = date(2025, 1, 5)
        check_out = date(2025, 1, 19)  # 14晚

        context = RuleContext(
            entity=None,
            entity_type="pricing",
            action="calculate",
            parameters={
                "check_in_date": check_in,
                "check_out_date": check_out,
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        assert context.metadata.get("discount_rate") == 0.15

    def test_less_than_7_nights_no_discount(self):
        """测试少于7天无折扣"""
        engine = RuleEngine()
        register_pricing_rules(engine)

        check_in = date(2025, 1, 5)
        check_out = date(2025, 1, 10)  # 5晚

        context = RuleContext(
            entity=None,
            entity_type="pricing",
            action="calculate",
            parameters={
                "check_in_date": check_in,
                "check_out_date": check_out,
                "base_price": 288
            }
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "pricing_long_stay_discount" not in rule_ids


class TestCalculateRoomPrice:
    """计算房间价格测试"""

    def test_base_price_only(self):
        """测试只有基础价格"""
        check_in = date(2025, 1, 7)  # 周二
        check_out = date(2025, 1, 8)  # 周三

        price, details = calculate_room_price(288, check_in, check_out, "basic")

        assert price == 288
        assert details["nights"] == 1

    def test_weekend_surcharge(self):
        """测试周末价格上调"""
        check_in = date(2025, 1, 3)  # 周五
        check_out = date(2025, 1, 4)  # 周六

        price, details = calculate_room_price(288, check_in, check_out, "basic")

        assert price > 288  # 20% 上调
        assert any(a["name"] == "周末上调" for a in details["adjustments"])

    def test_member_discount(self):
        """测试会员折扣"""
        check_in = date(2025, 1, 7)
        check_out = date(2025, 1, 8)

        price, details = calculate_room_price(288, check_in, check_out, "gold")

        assert price < 288  # 10% 折扣
        assert any(a["name"] == "GOLD会员折扣" for a in details["adjustments"])

    def test_long_stay_discount(self):
        """测试长住折扣"""
        check_in = date(2025, 1, 5)
        check_out = date(2025, 1, 13)  # 8晚

        price, details = calculate_room_price(288, check_in, check_out, "basic")

        assert price < 288
        assert any(a["name"] == "长住折扣（7+天）" for a in details["adjustments"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
