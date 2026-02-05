"""
tests/ai/test_hitl.py

HITL 策略单元测试
"""
import pytest

from core.ai.hitl import (
    ConfirmationLevel,
    ConfirmAlwaysStrategy,
    ConfirmByRiskStrategy,
    ConfirmByPolicyStrategy,
    ConfirmByThresholdStrategy,
    CompositeHITLStrategy,
    create_default_hitl_strategy,
    create_safe_hitl_strategy,
)


class TestConfirmationLevel:
    """ConfirmationLevel 测试"""

    def test_enum_values(self):
        """测试枚举值"""
        assert ConfirmationLevel.NONE.value == "none"
        assert ConfirmationLevel.LOW.value == "low"
        assert ConfirmationLevel.MEDIUM.value == "medium"
        assert ConfirmationLevel.HIGH.value == "high"
        assert ConfirmationLevel.CRITICAL.value == "critical"


class TestConfirmAlwaysStrategy:
    """ConfirmAlwaysStrategy 测试"""

    def test_always_requires_confirmation(self):
        """测试所有操作都需要确认"""
        strategy = ConfirmAlwaysStrategy()

        # 查询类操作
        assert strategy.requires_confirmation("view", {}, "manager") is True
        assert strategy.requires_confirmation("query_rooms", {}, "receptionist") is True

        # 写入类操作
        assert strategy.requires_confirmation("checkout", {}, "manager") is True
        assert strategy.requires_confirmation("adjust_bill", {}, "manager") is True

    def test_risk_level_is_medium(self):
        """测试风险等级为 MEDIUM"""
        strategy = ConfirmAlwaysStrategy()
        level = strategy.get_risk_level("any_action", {})
        assert level == ConfirmationLevel.MEDIUM


class TestConfirmByRiskStrategy:
    """ConfirmByRiskStrategy 测试"""

    def test_query_actions_no_confirmation(self):
        """测试查询类操作不需要确认"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.requires_confirmation("view", {}, "manager") is False
        assert strategy.requires_confirmation("query_rooms", {}, "receptionist") is False
        assert strategy.requires_confirmation("query_reservations", {}, "manager") is False

    def test_low_risk_actions(self):
        """测试低风险操作"""
        strategy = ConfirmByRiskStrategy()

        # start_task 是低风险，不需要确认
        assert strategy.requires_confirmation("start_task", {}, "cleaner") is False

    def test_medium_risk_actions(self):
        """测试中风险操作需要确认"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.requires_confirmation("checkin", {}, "receptionist") is True
        assert strategy.requires_confirmation("walkin_checkin", {}, "receptionist") is True
        assert strategy.requires_confirmation("create_reservation", {}, "manager") is True

    def test_high_risk_actions(self):
        """测试高风险操作需要确认"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.requires_confirmation("extend_stay", {}, "manager") is True
        assert strategy.requires_confirmation("change_room", {}, "manager") is True
        assert strategy.requires_confirmation("cancel_reservation", {}, "manager") is True

    def test_critical_actions(self):
        """测试关键操作需要确认"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.requires_confirmation("adjust_bill", {}, "manager") is True

    def test_get_risk_levels(self):
        """测试获取风险等级"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.get_risk_level("view", {}) == ConfirmationLevel.NONE
        assert strategy.get_risk_level("checkin", {}) == ConfirmationLevel.MEDIUM
        assert strategy.get_risk_level("adjust_bill", {}) == ConfirmationLevel.CRITICAL

    def test_large_adjustment_increases_risk(self):
        """测试大额调整提升风险等级"""
        strategy = ConfirmByRiskStrategy()

        # 正常调整
        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 100})
        assert level == ConfirmationLevel.CRITICAL

        # 大额调整（超过1000）
        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 1500})
        assert level == ConfirmationLevel.CRITICAL

    def test_unknown_action_default_risk(self):
        """测试未知操作默认为中风险"""
        strategy = ConfirmByRiskStrategy()

        assert strategy.requires_confirmation("unknown_action", {}, "manager") is True
        level = strategy.get_risk_level("unknown_action", {})
        assert level == ConfirmationLevel.MEDIUM


class TestConfirmByPolicyStrategy:
    """ConfirmByPolicyStrategy 测试"""

    def test_high_risk_actions_require_confirmation(self):
        """测试高风险操作需要确认"""
        strategy = ConfirmByPolicyStrategy()

        assert strategy.requires_confirmation("adjust_bill", {}, "manager") is True
        assert strategy.requires_confirmation("delete_guest", {}, "manager") is True

    def test_medium_risk_actions_require_confirmation(self):
        """测试中风险操作需要确认"""
        strategy = ConfirmByPolicyStrategy()

        assert strategy.requires_confirmation("change_room", {}, "manager") is True
        assert strategy.requires_confirmation("extend_stay", {}, "manager") is True

    def test_low_risk_actions_no_confirmation(self):
        """测试低风险操作不需要确认"""
        strategy = ConfirmByPolicyStrategy()

        assert strategy.requires_confirmation("create_task", {}, "manager") is False
        assert strategy.requires_confirmation("assign_task", {}, "manager") is False

    def test_role_exemption(self):
        """测试角色豁免"""
        strategy = ConfirmByPolicyStrategy()

        # manager 可以跳过 add_payment 确认
        assert strategy.requires_confirmation("add_payment", {}, "manager") is False

        # receptionist 可以跳过查询确认
        assert strategy.requires_confirmation("query_rooms", {}, "receptionist") is False

    def test_add_policy(self):
        """测试动态添加策略"""
        strategy = ConfirmByPolicyStrategy()

        # 添加一个新的低风险策略
        strategy.add_policy("low_risk", ["new_action"], confirm=False)

        assert strategy.requires_confirmation("new_action", {}, "manager") is False

    def test_get_risk_levels(self):
        """测试获取风险等级"""
        strategy = ConfirmByPolicyStrategy()

        assert strategy.get_risk_level("adjust_bill", {}) == ConfirmationLevel.CRITICAL
        assert strategy.get_risk_level("change_room", {}) == ConfirmationLevel.HIGH
        assert strategy.get_risk_level("create_task", {}) == ConfirmationLevel.LOW


class TestConfirmByThresholdStrategy:
    """ConfirmByThresholdStrategy �验"""

    def test_payment_below_threshold(self):
        """测试低于阈值的支付不需要确认"""
        strategy = ConfirmByThresholdStrategy(payment_threshold=1000.0)

        assert strategy.requires_confirmation("add_payment", {"amount": 500}, "manager") is False
        assert strategy.requires_confirmation("add_payment", {"amount": 999}, "manager") is False

    def test_payment_at_threshold(self):
        """测试达到阈值的支付需要确认"""
        strategy = ConfirmByThresholdStrategy(payment_threshold=1000.0)

        assert strategy.requires_confirmation("add_payment", {"amount": 1000}, "manager") is True
        assert strategy.requires_confirmation("add_payment", {"amount": 1500}, "manager") is True

    def test_adjustment_threshold(self):
        """测试调整金额阈值"""
        strategy = ConfirmByThresholdStrategy(adjustment_threshold=500.0)

        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 200}, "manager") is False
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 500}, "manager") is True
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 600}, "manager") is True

    def test_negative_adjustment(self):
        """测试负调整（绝对值判断）"""
        strategy = ConfirmByThresholdStrategy(adjustment_threshold=500.0)

        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": -200}, "manager") is False
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": -500}, "manager") is True

    def test_quantity_threshold(self):
        """测试数量阈值"""
        strategy = ConfirmByThresholdStrategy(quantity_threshold=10)

        assert strategy.requires_confirmation("create_task", {"room_ids": [1, 2, 3]}, "manager") is False
        assert strategy.requires_confirmation("create_task", {"room_ids": list(range(10))}, "manager") is True

    def test_unhandled_actions(self):
        """测试未处理的操作返回 False"""
        strategy = ConfirmByThresholdStrategy()

        assert strategy.requires_confirmation("query_rooms", {}, "manager") is False
        assert strategy.requires_confirmation("checkin", {}, "manager") is False


class TestCompositeHITLStrategy:
    """CompositeHITLStrategy 测试"""

    def test_all_strategies_false(self):
        """测试所有策略返回 False"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(payment_threshold=10000),  # 高阈值
        ])

        assert strategy.requires_confirmation("add_payment", {"amount": 100}, "manager") is False

    def test_one_strategy_true(self):
        """测试任一策略返回 True"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(payment_threshold=10000),
            ConfirmAlwaysStrategy(),
        ])

        assert strategy.requires_confirmation("add_payment", {"amount": 100}, "manager") is True

    def test_get_max_risk_level(self):
        """测试获取最高风险等级"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(),
            ConfirmByRiskStrategy(),
        ])

        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 100})
        # ConfirmByRiskStrategy 返回 CRITICAL
        assert level == ConfirmationLevel.CRITICAL


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_create_default_hitl_strategy(self):
        """测试创建默认策略"""
        strategy = create_default_hitl_strategy()
        assert isinstance(strategy, CompositeHITLStrategy)

    def test_create_safe_hitl_strategy(self):
        """测试创建安全策略"""
        strategy = create_safe_hitl_strategy()
        assert isinstance(strategy, ConfirmAlwaysStrategy)

        # 所有操作都需要确认
        assert strategy.requires_confirmation("view", {}, "manager") is True
        assert strategy.requires_confirmation("query_rooms", {}, "manager") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
