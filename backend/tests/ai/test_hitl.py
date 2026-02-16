"""
tests/ai/test_hitl.py

HITL 策略单元测试
"""
import pytest
from dataclasses import dataclass, field as dc_field
from typing import List

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


# ============== Mock Registry for Tests ==============

@dataclass
class _MockActionMetadata:
    """Mock action metadata for HITL tests."""
    action_type: str = ""
    risk_level: str = ""
    is_financial: bool = False
    ui_required_fields: List[str] = dc_field(default_factory=list)


class _MockRegistry:
    """Mock OntologyRegistry for HITL tests."""
    def __init__(self, actions=None):
        self._actions = {a.action_type: a for a in (actions or [])}

    def get_action_by_name(self, action_name):
        return self._actions.get(action_name)


@pytest.fixture
def mock_registry():
    """Registry with sample action metadata matching hotel domain."""
    return _MockRegistry(actions=[
        _MockActionMetadata(action_type="view", risk_level="none"),
        _MockActionMetadata(action_type="query_rooms", risk_level="none"),
        _MockActionMetadata(action_type="query_reservations", risk_level="none"),
        _MockActionMetadata(action_type="start_task", risk_level="none"),
        _MockActionMetadata(action_type="create_task", risk_level="low"),
        _MockActionMetadata(action_type="assign_task", risk_level="low"),
        _MockActionMetadata(action_type="complete_task", risk_level="low"),
        _MockActionMetadata(action_type="checkin", risk_level="medium"),
        _MockActionMetadata(action_type="walkin_checkin", risk_level="medium"),
        _MockActionMetadata(action_type="create_reservation", risk_level="medium"),
        _MockActionMetadata(action_type="checkout", risk_level="high"),
        _MockActionMetadata(action_type="extend_stay", risk_level="high"),
        _MockActionMetadata(action_type="change_room", risk_level="high"),
        _MockActionMetadata(action_type="cancel_reservation", risk_level="high"),
        _MockActionMetadata(action_type="add_payment", risk_level="high", is_financial=True),
        _MockActionMetadata(action_type="adjust_bill", risk_level="critical", is_financial=True),
        _MockActionMetadata(action_type="update_room_status", risk_level="medium"),
    ])


# Hotel-specific policies for testing ConfirmByPolicyStrategy
HOTEL_POLICIES = {
    "high_risk_actions": {
        "actions": ["adjust_bill", "delete_guest"],
        "confirm": True,
        "require_reason": True
    },
    "medium_risk_actions": {
        "actions": ["change_room", "extend_stay", "cancel_reservation"],
        "confirm": True,
        "require_reason": False
    },
    "low_risk_actions": {
        "actions": ["create_task", "assign_task", "complete_task"],
        "confirm": False,
        "require_reason": False
    },
    "role_based": {
        "manager": {
            "skip_confirmation": ["add_payment", "create_reservation", "checkout"]
        },
        "receptionist": {
            "skip_confirmation": ["query_rooms", "query_reservations"]
        }
    }
}


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

    def test_empty_defaults_unknown_action(self):
        """测试空默认映射下未知操作返回 MEDIUM"""
        strategy = ConfirmByRiskStrategy()  # no mapping, no registry
        assert strategy.requires_confirmation("unknown_action", {}, "manager") is True
        assert strategy.get_risk_level("unknown_action", {}) == ConfirmationLevel.MEDIUM

    def test_override_mapping(self):
        """测试覆盖映射优先级最高"""
        mapping = {
            "view": ConfirmationLevel.NONE,
            "checkout": ConfirmationLevel.HIGH,
        }
        strategy = ConfirmByRiskStrategy(risk_mapping=mapping)

        assert strategy.requires_confirmation("view", {}, "manager") is False
        assert strategy.requires_confirmation("checkout", {}, "manager") is True
        assert strategy.get_risk_level("view", {}) == ConfirmationLevel.NONE

    def test_registry_lookup(self, mock_registry):
        """测试从 registry 查询风险等级"""
        strategy = ConfirmByRiskStrategy(registry=mock_registry)

        assert strategy.requires_confirmation("view", {}, "manager") is False
        assert strategy.requires_confirmation("query_rooms", {}, "receptionist") is False
        assert strategy.requires_confirmation("checkin", {}, "receptionist") is True
        assert strategy.requires_confirmation("checkout", {}, "manager") is True
        assert strategy.requires_confirmation("adjust_bill", {}, "manager") is True

    def test_registry_risk_levels(self, mock_registry):
        """测试从 registry 获取正确的风险等级"""
        strategy = ConfirmByRiskStrategy(registry=mock_registry)

        assert strategy.get_risk_level("view", {}) == ConfirmationLevel.NONE
        assert strategy.get_risk_level("checkin", {}) == ConfirmationLevel.MEDIUM
        assert strategy.get_risk_level("adjust_bill", {}) == ConfirmationLevel.CRITICAL

    def test_custom_rules(self):
        """测试自定义规则注入"""
        def check_high_amount(action_type, params):
            if action_type == "adjust_bill":
                amount = params.get("adjustment_amount", 0)
                if abs(float(amount)) > 1000:
                    return ConfirmationLevel.CRITICAL
            return None

        strategy = ConfirmByRiskStrategy(custom_rules=[check_high_amount])

        # Normal amount → default MEDIUM (no registry, no mapping)
        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 100})
        assert level == ConfirmationLevel.MEDIUM

        # Large amount → CRITICAL (custom rule triggers)
        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 1500})
        assert level == ConfirmationLevel.CRITICAL

    def test_priority_order(self, mock_registry):
        """测试优先级: override > custom_rules > registry > default"""
        def always_critical(action_type, params):
            return ConfirmationLevel.CRITICAL

        # Override takes priority over custom rule and registry
        strategy = ConfirmByRiskStrategy(
            risk_mapping={"view": ConfirmationLevel.LOW},
            registry=mock_registry,
            custom_rules=[always_critical],
        )
        assert strategy.get_risk_level("view", {}) == ConfirmationLevel.LOW

        # Custom rule takes priority over registry
        strategy2 = ConfirmByRiskStrategy(
            registry=mock_registry,
            custom_rules=[always_critical],
        )
        assert strategy2.get_risk_level("checkin", {}) == ConfirmationLevel.CRITICAL

    def test_low_risk_no_confirmation(self, mock_registry):
        """测试低风险操作不需要确认"""
        strategy = ConfirmByRiskStrategy(registry=mock_registry)
        assert strategy.requires_confirmation("start_task", {}, "cleaner") is False

    def test_medium_risk_needs_confirmation(self, mock_registry):
        """测试中风险操作需要确认"""
        strategy = ConfirmByRiskStrategy(registry=mock_registry)
        assert strategy.requires_confirmation("checkin", {}, "receptionist") is True
        assert strategy.requires_confirmation("walkin_checkin", {}, "receptionist") is True
        assert strategy.requires_confirmation("create_reservation", {}, "manager") is True

    def test_high_risk_needs_confirmation(self, mock_registry):
        """测试高风险操作需要确认"""
        strategy = ConfirmByRiskStrategy(registry=mock_registry)
        assert strategy.requires_confirmation("extend_stay", {}, "manager") is True
        assert strategy.requires_confirmation("change_room", {}, "manager") is True
        assert strategy.requires_confirmation("cancel_reservation", {}, "manager") is True


class TestConfirmByPolicyStrategy:
    """ConfirmByPolicyStrategy 测试"""

    def test_empty_defaults(self):
        """测试空默认策略下所有操作需要确认"""
        strategy = ConfirmByPolicyStrategy()  # empty policies
        assert strategy.requires_confirmation("any_action", {}, "manager") is True

    def test_high_risk_actions_require_confirmation(self):
        """测试高风险操作需要确认"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        assert strategy.requires_confirmation("adjust_bill", {}, "manager") is True
        assert strategy.requires_confirmation("delete_guest", {}, "manager") is True

    def test_medium_risk_actions_require_confirmation(self):
        """测试中风险操作需要确认"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        assert strategy.requires_confirmation("change_room", {}, "manager") is True
        assert strategy.requires_confirmation("extend_stay", {}, "manager") is True

    def test_low_risk_actions_no_confirmation(self):
        """测试低风险操作不需要确认"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        assert strategy.requires_confirmation("create_task", {}, "manager") is False
        assert strategy.requires_confirmation("assign_task", {}, "manager") is False

    def test_role_exemption(self):
        """测试角色豁免"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        # manager 可以跳过 add_payment 确认
        assert strategy.requires_confirmation("add_payment", {}, "manager") is False

        # receptionist 可以跳过查询确认
        assert strategy.requires_confirmation("query_rooms", {}, "receptionist") is False

    def test_add_policy(self):
        """测试动态添加策略"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        # 添加一个新的低风险策略
        strategy.add_policy("low_risk", ["new_action"], confirm=False)

        assert strategy.requires_confirmation("new_action", {}, "manager") is False

    def test_get_risk_levels(self):
        """测试获取风险等级"""
        strategy = ConfirmByPolicyStrategy(policies=HOTEL_POLICIES)

        assert strategy.get_risk_level("adjust_bill", {}) == ConfirmationLevel.CRITICAL
        assert strategy.get_risk_level("change_room", {}) == ConfirmationLevel.HIGH
        assert strategy.get_risk_level("create_task", {}) == ConfirmationLevel.LOW


class TestConfirmByThresholdStrategy:
    """ConfirmByThresholdStrategy 测试"""

    @pytest.fixture
    def financial_registry(self):
        """Registry with financial actions."""
        return _MockRegistry(actions=[
            _MockActionMetadata(action_type="add_payment", is_financial=True),
            _MockActionMetadata(action_type="adjust_bill", is_financial=True),
        ])

    def test_payment_below_threshold(self, financial_registry):
        """测试低于阈值的支付不需要确认"""
        strategy = ConfirmByThresholdStrategy(
            amount_threshold=1000.0, registry=financial_registry,
        )

        assert strategy.requires_confirmation("add_payment", {"amount": 500}, "manager") is False
        assert strategy.requires_confirmation("add_payment", {"amount": 999}, "manager") is False

    def test_payment_at_threshold(self, financial_registry):
        """测试达到阈值的支付需要确认"""
        strategy = ConfirmByThresholdStrategy(
            amount_threshold=1000.0, registry=financial_registry,
        )

        assert strategy.requires_confirmation("add_payment", {"amount": 1000}, "manager") is True
        assert strategy.requires_confirmation("add_payment", {"amount": 1500}, "manager") is True

    def test_adjustment_threshold(self, financial_registry):
        """测试调整金额阈值"""
        strategy = ConfirmByThresholdStrategy(
            adjustment_threshold=500.0, registry=financial_registry,
        )

        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 200}, "manager") is False
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 500}, "manager") is True
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": 600}, "manager") is True

    def test_negative_adjustment(self, financial_registry):
        """测试负调整（绝对值判断）"""
        strategy = ConfirmByThresholdStrategy(
            adjustment_threshold=500.0, registry=financial_registry,
        )

        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": -200}, "manager") is False
        assert strategy.requires_confirmation("adjust_bill", {"adjustment_amount": -500}, "manager") is True

    def test_quantity_threshold(self):
        """测试数量阈值 (generic, not action-specific)"""
        strategy = ConfirmByThresholdStrategy(quantity_threshold=10)

        assert strategy.requires_confirmation("create_task", {"room_ids": [1, 2, 3]}, "manager") is False
        assert strategy.requires_confirmation("create_task", {"room_ids": list(range(10))}, "manager") is True

    def test_unhandled_actions(self):
        """测试未处理的操作返回 False"""
        strategy = ConfirmByThresholdStrategy()

        assert strategy.requires_confirmation("query_rooms", {}, "manager") is False
        assert strategy.requires_confirmation("checkin", {}, "manager") is False

    def test_no_registry_financial_not_detected(self):
        """测试无 registry 时金融操作不被识别"""
        strategy = ConfirmByThresholdStrategy(amount_threshold=100.0)  # no registry

        # Without registry, is_financial check fails → no confirmation
        assert strategy.requires_confirmation("add_payment", {"amount": 5000}, "manager") is False


class TestCompositeHITLStrategy:
    """CompositeHITLStrategy 测试"""

    def test_all_strategies_false(self):
        """测试所有策略返回 False"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(amount_threshold=10000),  # 高阈值, no registry
        ])

        assert strategy.requires_confirmation("add_payment", {"amount": 100}, "manager") is False

    def test_one_strategy_true(self):
        """测试任一策略返回 True"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(amount_threshold=10000),
            ConfirmAlwaysStrategy(),
        ])

        assert strategy.requires_confirmation("add_payment", {"amount": 100}, "manager") is True

    def test_get_max_risk_level(self, mock_registry):
        """测试获取最高风险等级"""
        strategy = CompositeHITLStrategy([
            ConfirmByThresholdStrategy(),
            ConfirmByRiskStrategy(registry=mock_registry),
        ])

        level = strategy.get_risk_level("adjust_bill", {"adjustment_amount": 100})
        # ConfirmByRiskStrategy returns CRITICAL from registry
        assert level == ConfirmationLevel.CRITICAL


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_create_default_hitl_strategy(self):
        """测试创建默认策略"""
        strategy = create_default_hitl_strategy()
        assert isinstance(strategy, CompositeHITLStrategy)

    def test_create_default_hitl_strategy_with_registry(self, mock_registry):
        """测试创建带 registry 的默认策略"""
        strategy = create_default_hitl_strategy(registry=mock_registry)
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
