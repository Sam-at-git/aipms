"""
测试 core.ooda.decide 模块 - Decide 阶段单元测试
"""
import pytest
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from typing import List, Optional

from core.ooda.decide import (
    Decision,
    DecisionRule,
    IntentBasedRule,
    DefaultDecisionRule,
    DecidePhase,
    get_decide_phase,
    set_decide_phase,
)
from core.ooda.orient import Orientation
from core.ooda.observe import Observation
from core.ooda.intent import IntentResult


# ============== Mock Registry for Tests ==============

@dataclass
class _MockActionMetadata:
    """Mock action metadata for tests."""
    action_type: str = ""
    risk_level: str = ""
    is_financial: bool = False
    ui_required_fields: List[str] = dc_field(default_factory=list)


class _MockRegistry:
    """Mock OntologyRegistry for decide tests."""
    def __init__(self, actions=None):
        self._actions = {a.action_type: a for a in (actions or [])}

    def get_action_by_name(self, action_name):
        return self._actions.get(action_name)


@pytest.fixture
def mock_registry():
    """Registry with sample action metadata."""
    return _MockRegistry(actions=[
        _MockActionMetadata(
            action_type="checkin",
            risk_level="medium",
            ui_required_fields=["reservation_id", "room_id"],
        ),
        _MockActionMetadata(
            action_type="checkout",
            risk_level="high",
            ui_required_fields=["stay_record_id"],
        ),
        _MockActionMetadata(
            action_type="adjust_bill",
            risk_level="critical",
            is_financial=True,
            ui_required_fields=["bill_id", "adjustment_amount", "reason"],
        ),
        _MockActionMetadata(
            action_type="add_payment",
            risk_level="high",
            is_financial=True,
            ui_required_fields=["bill_id", "amount", "method"],
        ),
    ])


# ============== Fixtures ==============

@pytest.fixture
def sample_observation():
    """示例观察结果"""
    return Observation(
        raw_input="test input",
        normalized_input="test input",
    )


@pytest.fixture
def sample_intent():
    """示例意图结果"""
    return IntentResult(
        action_type="checkin",
        confidence=0.9,
        entities={"reservation_id": 1, "room_id": 101},
    )


@pytest.fixture
def sample_orientation(sample_observation, sample_intent):
    """示例导向结果"""
    return Orientation(
        observation=sample_observation,
        intent=sample_intent,
        confidence=0.9,
    )


# ============== Decision Tests ==============

class TestDecision:
    def test_creation(self):
        """测试创建决策结果"""
        obs = Observation(raw_input="test", normalized_input="test")
        intent = IntentResult(action_type="test_action", confidence=0.9)
        orient = Orientation(observation=obs, intent=intent, confidence=0.9)

        decision = Decision(
            orientation=orient,
            action_type="test_action",
            action_params={"param1": "value1"},
            confidence=0.9,
        )

        assert decision.orientation == orient
        assert decision.action_type == "test_action"
        assert decision.action_params == {"param1": "value1"}
        assert decision.confidence == 0.9
        assert decision.is_valid is True

    def test_to_dict(self):
        """测试转换为字典"""
        obs = Observation(raw_input="test", normalized_input="test")
        intent = IntentResult(action_type="test_action", confidence=0.85)
        orient = Orientation(observation=obs, intent=intent, confidence=0.85)

        decision = Decision(
            orientation=orient,
            action_type="test_action",
            action_params={"room_id": 101},
            confidence=0.85,
        )

        d = decision.to_dict()

        assert d["action_type"] == "test_action"
        assert d["action_params"] == {"room_id": 101}
        assert d["confidence"] == 0.85


# ============== IntentBasedRule Tests ==============

class TestIntentBasedRule:
    def test_can_handle_matching_action(self, sample_orientation):
        """测试能处理匹配的动作"""
        rule = IntentBasedRule("checkin", ["reservation_id", "room_id"])

        assert rule.can_handle(sample_orientation) is True

    def test_can_handle_non_matching_action(self, sample_orientation):
        """测试不能处理不匹配的动作"""
        rule = IntentBasedRule("checkout", ["stay_record_id"])

        assert rule.can_handle(sample_orientation) is False

    def test_can_handle_no_intent(self, sample_observation):
        """测试没有意图时返回 False"""
        rule = IntentBasedRule("checkin", ["reservation_id", "room_id"])
        orient = Orientation(observation=sample_observation, intent=None)

        assert rule.can_handle(orient) is False

    def test_evaluate_with_all_params(self, sample_orientation):
        """测试所有参数都存在时生成有效决策"""
        rule = IntentBasedRule("checkin", ["reservation_id", "room_id"])

        decision = rule.evaluate(sample_orientation)

        assert decision is not None
        assert decision.action_type == "checkin"
        assert decision.action_params == {"reservation_id": 1, "room_id": 101}
        assert decision.is_valid is True
        assert decision.missing_fields == []

    def test_evaluate_with_missing_params(self, sample_observation):
        """测试缺少参数时生成无效决策"""
        intent = IntentResult(
            action_type="checkin",
            confidence=0.9,
            entities={"reservation_id": 1},  # 缺少 room_id
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = IntentBasedRule("checkin", ["reservation_id", "room_id"])

        decision = rule.evaluate(orient)

        assert decision is not None
        assert decision.is_valid is False
        assert len(decision.missing_fields) == 1
        assert decision.missing_fields[0]["field_name"] == "room_id"
        assert decision.requires_confirmation is True

    def test_evaluate_requires_confirmation_for_high_risk(self, sample_observation, mock_registry):
        """测试高风险操作需要确认 (via registry)"""
        intent = IntentResult(
            action_type="checkout",
            confidence=0.9,
            entities={"stay_record_id": 1},
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = IntentBasedRule("checkout", ["stay_record_id"], registry=mock_registry)

        decision = rule.evaluate(orient)

        assert decision is not None
        assert decision.requires_confirmation is True

    def test_evaluate_requires_confirmation_for_financial(self, sample_observation, mock_registry):
        """测试金融操作需要确认 (via registry)"""
        intent = IntentResult(
            action_type="adjust_bill",
            confidence=0.9,
            entities={"bill_id": 1, "adjustment_amount": 100, "reason": "discount"},
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = IntentBasedRule(
            "adjust_bill",
            ["bill_id", "adjustment_amount", "reason"],
            registry=mock_registry,
        )

        decision = rule.evaluate(orient)

        assert decision is not None
        assert decision.requires_confirmation is True

    def test_no_registry_means_no_auto_confirmation(self, sample_observation):
        """测试无 registry 时高风险/金融判断不触发"""
        intent = IntentResult(
            action_type="checkout",
            confidence=0.9,
            entities={"stay_record_id": 1},
            requires_confirmation=False,
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = IntentBasedRule("checkout", ["stay_record_id"])  # no registry

        decision = rule.evaluate(orient)

        assert decision is not None
        # Without registry, risk/financial checks return False
        assert decision.requires_confirmation is False

    def test_confidence_calculation(self, sample_observation):
        """测试置信度计算"""
        intent = IntentResult(
            action_type="checkin",
            confidence=0.8,
            entities={"reservation_id": 1},  # 缺少一个参数
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.8)

        rule = IntentBasedRule("checkin", ["reservation_id", "room_id"])

        decision = rule.evaluate(orient)

        # 置信度 = 意图置信度 * 参数完整性
        # 0.8 * (1/2) = 0.4
        assert decision.confidence == 0.4


# ============== DefaultDecisionRule Tests ==============

class TestDefaultDecisionRule:
    def test_can_handle_with_intent(self, sample_orientation):
        """测试有意图时能处理"""
        rule = DefaultDecisionRule()

        assert rule.can_handle(sample_orientation) is True

    def test_can_handle_without_intent(self, sample_observation):
        """测试没有意图时不能处理"""
        rule = DefaultDecisionRule()
        orient = Orientation(observation=sample_observation, intent=None)

        assert rule.can_handle(orient) is False

    def test_evaluate_known_action_with_registry(self, sample_observation, mock_registry):
        """测试评估已知动作类型 (with registry)"""
        intent = IntentResult(
            action_type="checkout",
            confidence=0.9,
            entities={"stay_record_id": 1},
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = DefaultDecisionRule(registry=mock_registry)

        decision = rule.evaluate(orient)

        assert decision is not None
        assert decision.action_type == "checkout"
        assert decision.action_params == {"stay_record_id": 1}
        assert decision.is_valid is True
        assert decision.requires_confirmation is True  # checkout is high risk

    def test_evaluate_unknown_action(self, sample_observation):
        """测试评估未知动作类型"""
        intent = IntentResult(
            action_type="unknown_action",
            confidence=0.9,
            entities={"param": "value"},
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = DefaultDecisionRule()

        decision = rule.evaluate(orient)

        # 未知动作类型没有必需参数，应该生成有效决策
        assert decision is not None
        assert decision.action_type == "unknown_action"
        assert decision.is_valid is True

    def test_evaluate_with_missing_required_params(self, sample_observation, mock_registry):
        """测试缺少必需参数 (registry provides required fields)"""
        intent = IntentResult(
            action_type="checkin",
            confidence=0.9,
            entities={"reservation_id": 1},  # 缺少 room_id
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = DefaultDecisionRule(registry=mock_registry)

        decision = rule.evaluate(orient)

        assert decision is not None
        assert decision.is_valid is False
        assert len(decision.missing_fields) == 1
        assert decision.missing_fields[0]["field_name"] == "room_id"

    def test_evaluate_no_registry_no_required_params(self, sample_observation):
        """测试无 registry 时不验证必需参数"""
        intent = IntentResult(
            action_type="checkin",
            confidence=0.9,
            entities={"reservation_id": 1},  # 缺少 room_id but no registry
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        rule = DefaultDecisionRule()  # no registry

        decision = rule.evaluate(orient)

        # Without registry, no required params → valid
        assert decision is not None
        assert decision.is_valid is True
        assert decision.missing_fields == []


# ============== DecidePhase Tests ==============

class TestDecidePhase:
    def test_decide_basic(self, sample_orientation):
        """测试基本决策"""
        decide = DecidePhase()

        decision = decide.decide(sample_orientation)

        assert decision.orientation == sample_orientation
        assert decision.action_type == "checkin"
        assert decision.action_params == {"reservation_id": 1, "room_id": 101}
        assert decision.is_valid is True

    def test_decide_with_invalid_orientation(self, sample_observation):
        """测试无效导向"""
        orient = Orientation(
            observation=sample_observation,
            intent=None,
            is_valid=False,
            errors=["No intent"],
        )

        decide = DecidePhase()

        decision = decide.decide(orient)

        assert decision.is_valid is False
        assert "No intent recognized" in decision.errors

    def test_decide_adds_metadata(self, sample_orientation):
        """测试添加元数据"""
        sample_orientation.context = {"user_id": 123, "role": "manager"}

        decide = DecidePhase()

        decision = decide.decide(sample_orientation)

        assert decision.metadata["user_id"] == 123
        assert decision.metadata["role"] == "manager"

    def test_decide_with_custom_rule(self, sample_observation):
        """测试使用自定义规则"""
        # 创建自定义规则
        class CustomRule(DecisionRule):
            def can_handle(self, orientation):
                return orientation.intent and orientation.intent.action_type == "custom"

            def evaluate(self, orientation):
                return Decision(
                    orientation=orientation,
                    action_type="custom_result",
                    action_params={"custom": "value"},
                )

        intent = IntentResult(action_type="custom", confidence=0.9)
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        decide = DecidePhase()
        decide.clear_rules()
        decide.add_rule(CustomRule())

        decision = decide.decide(orient)

        assert decision.action_type == "custom_result"
        assert decision.action_params == {"custom": "value"}

    def test_decide_with_registry(self, sample_observation, mock_registry):
        """测试 DecidePhase 传递 registry 到 DefaultDecisionRule"""
        intent = IntentResult(
            action_type="checkout",
            confidence=0.9,
            entities={"stay_record_id": 1},
        )
        orient = Orientation(observation=sample_observation, intent=intent, confidence=0.9)

        decide = DecidePhase(registry=mock_registry)

        decision = decide.decide(orient)

        assert decision.action_type == "checkout"
        assert decision.requires_confirmation is True  # high risk via registry

    def test_add_rule(self):
        """测试添加规则"""
        decide = DecidePhase()
        initial_count = len(decide._rules)

        rule = IntentBasedRule("test", ["param1"])
        decide.add_rule(rule)

        assert len(decide._rules) == initial_count + 1
        assert decide._rules[0] is rule

    def test_remove_rule(self):
        """测试移除规则"""
        decide = DecidePhase()
        rule = IntentBasedRule("test", ["param1"])
        decide.add_rule(rule)

        decide.remove_rule(rule)

        assert rule not in decide._rules

    def test_clear_rules(self):
        """测试清空规则"""
        decide = DecidePhase()
        decide.clear_rules()

        assert len(decide._rules) == 0

    def test_timestamp(self, sample_orientation):
        """测试时间戳"""
        before = datetime.utcnow()
        decide = DecidePhase()

        decision = decide.decide(sample_orientation)
        after = datetime.utcnow()

        assert before <= decision.timestamp <= after


class TestGlobalInstance:
    def test_get_decide_phase_creates_singleton(self):
        """测试获取单例"""
        # 重置
        set_decide_phase(None)

        decide1 = get_decide_phase()
        decide2 = get_decide_phase()

        assert decide1 is decide2
        assert isinstance(decide1, DecidePhase)

    def test_set_decide_phase(self):
        """测试设置实例"""
        custom = DecidePhase()
        set_decide_phase(custom)

        result = get_decide_phase()

        assert result is custom


class TestRegistryHelpers:
    """Test the registry-based helper functions used by decision rules."""

    def test_high_risk_detected_from_registry(self, mock_registry):
        """Registry returns high risk correctly"""
        from core.ooda.decide import _is_high_risk
        assert _is_high_risk("checkout", mock_registry) is True
        assert _is_high_risk("adjust_bill", mock_registry) is True  # critical is also high
        assert _is_high_risk("checkin", mock_registry) is False  # medium is not high

    def test_financial_detected_from_registry(self, mock_registry):
        """Registry returns is_financial correctly"""
        from core.ooda.decide import _is_financial
        assert _is_financial("adjust_bill", mock_registry) is True
        assert _is_financial("add_payment", mock_registry) is True
        assert _is_financial("checkout", mock_registry) is False

    def test_required_params_from_registry(self, mock_registry):
        """Registry returns ui_required_fields correctly"""
        from core.ooda.decide import _get_required_params
        assert _get_required_params("checkin", mock_registry) == ["reservation_id", "room_id"]
        assert _get_required_params("unknown", mock_registry) == []

    def test_helpers_with_no_registry(self):
        """All helpers return safe defaults when registry is None"""
        from core.ooda.decide import _is_high_risk, _is_financial, _get_required_params
        assert _is_high_risk("checkout", None) is False
        assert _is_financial("adjust_bill", None) is False
        assert _get_required_params("checkin", None) == []
