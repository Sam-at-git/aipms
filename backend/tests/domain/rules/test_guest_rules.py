"""
tests/domain/rules/test_guest_rules.py

客人规则单元测试
"""
import pytest

from core.domain.rules.guest_rules import (
    register_guest_rules,
    calculate_guest_tier,
    get_tier_threshold,
    get_next_tier_threshold,
    GUEST_TIERS,
)
from core.engine.rule_engine import RuleContext, RuleEngine


class TestGuestRulesRegistration:
    """客人规则注册测试"""

    def test_register_guest_rules(self):
        """测试注册客人规则"""
        engine = RuleEngine()
        register_guest_rules(engine)

        # 验证规则已注册
        assert engine.get_rule("guest_auto_upgrade_tier") is not None
        assert engine.get_rule("guest_blacklist_check") is not None
        assert engine.get_rule("guest_vip_service") is not None
        assert engine.get_rule("guest_first_time_recognition") is not None


class TestGuestTierCalculation:
    """客人等级计算测试"""

    def test_basic_tier(self):
        """测试普通客人等级"""
        tier = calculate_guest_tier(0)
        assert tier == "basic"

        tier = calculate_guest_tier(500)
        assert tier == "basic"

    def test_silver_tier(self):
        """测试银卡会员等级"""
        tier = calculate_guest_tier(1000)
        assert tier == "silver"

        tier = calculate_guest_tier(2000)
        assert tier == "silver"

    def test_gold_tier(self):
        """测试金卡会员等级"""
        tier = calculate_guest_tier(5000)
        assert tier == "gold"

        tier = calculate_guest_tier(8000)
        assert tier == "gold"

    def test_vip_tier(self):
        """测试VIP会员等级"""
        tier = calculate_guest_tier(15000)
        assert tier == "vip"

        tier = calculate_guest_tier(20000)
        assert tier == "vip"

    def test_tier_boundaries(self):
        """测试等级边界"""
        # 刚好达到阈值
        assert calculate_guest_tier(999) == "basic"
        assert calculate_guest_tier(1000) == "silver"
        assert calculate_guest_tier(4999) == "silver"
        assert calculate_guest_tier(5000) == "gold"
        assert calculate_guest_tier(14999) == "gold"
        assert calculate_guest_tier(15000) == "vip"


class TestTierThreshold:
    """等级阈值测试"""

    def test_get_tier_threshold(self):
        """测试获取等级阈值"""
        assert get_tier_threshold("basic") == 0
        assert get_tier_threshold("silver") == 1000
        assert get_tier_threshold("gold") == 5000
        assert get_tier_threshold("vip") == 15000

    def test_get_next_tier_from_basic(self):
        """测试从普通客人获取下一等级"""
        next_tier, threshold = get_next_tier_threshold("basic", 0)
        assert next_tier == "silver"
        assert threshold == 1000

    def test_get_next_tier_from_silver(self):
        """测试从银卡获取下一等级"""
        next_tier, threshold = get_next_tier_threshold("silver", 2000)
        assert next_tier == "gold"
        assert threshold == 5000

    def test_get_next_tier_from_gold(self):
        """测试从金卡获取下一等级"""
        next_tier, threshold = get_next_tier_threshold("gold", 6000)
        assert next_tier == "vip"
        assert threshold == 15000

    def test_get_next_tier_from_vip(self):
        """测试VIP已经是最高等级"""
        next_tier, threshold = get_next_tier_threshold("vip", 20000)
        assert next_tier == "vip"
        assert threshold == 0

    def test_get_next_tier_already_met(self):
        """测试已经达到下一等级"""
        # 金卡客人累计消费6000，已经超过银卡阈值
        next_tier, threshold = get_next_tier_threshold("gold", 6000)
        assert next_tier == "vip"  # 下一目标是VIP
        assert threshold == 15000


class TestTierUpgradeRule:
    """等级升级规则测试"""

    def test_upgrade_from_basic_to_silver(self):
        """测试从普通客人升级到银卡"""
        class MockGuest:
            tier = "basic"
            total_spending = 1200

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="check_spending",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "guest_auto_upgrade_tier" in rule_ids
        assert context.metadata.get("tier_upgraded") is True
        assert context.metadata.get("old_tier") == "basic"
        assert context.metadata.get("new_tier") == "silver"

    def test_upgrade_from_silver_to_gold(self):
        """测试从银卡升级到金卡"""
        class MockGuest:
            tier = "silver"
            total_spending = 5500

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="check_spending",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "guest_auto_upgrade_tier" in rule_ids
        assert context.metadata.get("tier_upgraded") is True
        assert context.metadata.get("old_tier") == "silver"
        assert context.metadata.get("new_tier") == "gold"

    def test_no_upgrade_when_threshold_not_met(self):
        """测试未达到阈值时不升级"""
        class MockGuest:
            tier = "silver"
            total_spending = 1500

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="check_spending",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        # 不应该触发升级规则
        assert "guest_auto_upgrade_tier" not in rule_ids


class TestBlacklistRule:
    """黑名单规则测试"""

    def test_blacklisted_guest_blocked(self):
        """测试黑名单客人被阻止"""
        class MockGuest:
            is_blacklisted = True

            def __str__(self):
                return "Blacklisted Guest"

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "guest_blacklist_check" in rule_ids
        assert context.metadata.get("blocked") is True
        assert context.metadata.get("block_reason") == "guest_is_blacklisted"

    def test_normal_guest_not_blocked(self):
        """测试普通客人不被阻止"""
        class MockGuest:
            is_blacklisted = False

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        # 不应该触发黑名单规则
        assert "guest_blacklist_check" not in rule_ids


class TestVIPServiceRule:
    """VIP服务规则测试"""

    def test_vip_gets_special_service(self):
        """测试VIP获得特殊服务"""
        class MockGuest:
            tier = "vip"

            def __str__(self):
                return "VIP Guest"

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "guest_vip_service" in rule_ids
        assert context.metadata.get("vip_service") is True

    def test_vip_checkin_gets_auto_upgrade_available(self):
        """测试VIP入住时自动升级可用"""
        class MockGuest:
            tier = "vip"

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)

        assert context.metadata.get("auto_upgrade_available") is True

    def test_non_vip_no_special_service(self):
        """测试非VIP不获得特殊服务"""
        class MockGuest:
            tier = "silver"

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        # 不应该触发VIP服务规则
        assert "guest_vip_service" not in rule_ids


class TestFirstTimeGuestRule:
    """首次客人规则测试"""

    def test_first_time_guest_welcomed(self):
        """测试首次客人受到欢迎"""
        class MockGuest:
            reservation_count = 0

            def __str__(self):
                return "First Time Guest"

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "guest_first_time_recognition" in rule_ids
        assert context.metadata.get("first_time_guest") is True
        assert context.metadata.get("welcome_message") == "欢迎首次入住！"

    def test_returning_guest_not_welcomed(self):
        """测试回头客不触发首次欢迎"""
        class MockGuest:
            reservation_count = 5

        engine = RuleEngine()
        register_guest_rules(engine)

        context = RuleContext(
            entity=MockGuest(),
            entity_type="guest",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        # 不应该触发首次客人规则
        assert "guest_first_time_recognition" not in rule_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
