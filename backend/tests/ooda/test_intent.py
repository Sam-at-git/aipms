"""
测试 core.ooda.intent 意图识别服务
"""
import pytest
from core.ooda.intent import (
    IntentResult,
    MissingField,
    IntentRecognitionStrategy,
    IntentRecognitionService,
)


class MockStrategy(IntentRecognitionStrategy):
    """测试用的模拟策略"""

    def __init__(self, action_type: str = "test", confidence: float = 1.0):
        self.action_type = action_type
        self.confidence = confidence

    def recognize(self, input: str, context=None) -> IntentResult:
        return IntentResult(action_type=self.action_type, confidence=self.confidence)


def test_intent_result_creation():
    """测试创建意图结果"""
    result = IntentResult(action_type="checkin", confidence=0.9)
    assert result.action_type == "checkin"
    assert result.confidence == 0.9
    assert result.entities == {}
    assert result.requires_confirmation is False


def test_intent_result_with_entities():
    """测试带实体的意图结果"""
    result = IntentResult(
        action_type="checkin",
        confidence=0.9,
        entities={"room_id": 101, "guest_name": "张三"},
    )
    assert result.entities["room_id"] == 101
    assert result.entities["guest_name"] == "张三"


def test_intent_result_is_valid():
    """测试意图结果有效性检查"""
    valid = IntentResult(action_type="test", confidence=0.8)
    assert valid.is_valid()

    invalid = IntentResult(action_type="test", confidence=0.3)
    assert not invalid.is_valid()

    borderline = IntentResult(action_type="test", confidence=0.5)
    assert borderline.is_valid()


def test_intent_result_with_missing_fields():
    """测试带缺失字段的意图结果"""
    result = IntentResult(
        action_type="checkin",
        confidence=0.9,
        missing_fields=[
            {"field_name": "room_id", "display_name": "房间号", "field_type": "integer"},
        ],
    )
    assert len(result.missing_fields) == 1
    assert result.missing_fields[0]["field_name"] == "room_id"


def test_intent_result_requires_confirmation():
    """测试需要确认的意图结果"""
    result = IntentResult(action_type="adjust_price", confidence=0.9, requires_confirmation=True)
    assert result.requires_confirmation is True


def test_intent_strategy_abstract():
    """测试策略类是抽象的"""
    with pytest.raises(TypeError):
        IntentRecognitionStrategy()


def test_intent_recognition_service_creation():
    """测试创建意图识别服务"""
    strategy = MockStrategy()
    service = IntentRecognitionService(strategy)
    assert service._strategy is strategy


def test_intent_recognition_service_recognize():
    """测试意图识别服务调用策略"""
    strategy = MockStrategy(action_type="checkin", confidence=0.95)
    service = IntentRecognitionService(strategy)

    result = service.recognize("帮客人办理入住")
    assert result.action_type == "checkin"
    assert result.confidence == 0.95


def test_intent_recognition_service_with_context():
    """测试带上下文的意图识别"""
    class ContextStrategy(MockStrategy):
        def recognize(self, input: str, context=None) -> IntentResult:
            if context and context.get("previous_intent"):
                return IntentResult(action_type="followup", confidence=1.0)
            return super().recognize(input, context)

    strategy = ContextStrategy()
    service = IntentRecognitionService(strategy)

    result1 = service.recognize("test")
    assert result1.action_type == "test"

    result2 = service.recognize("test", context={"previous_intent": True})
    assert result2.action_type == "followup"


def test_intent_recognition_service_set_strategy():
    """测试更换策略"""
    strategy1 = MockStrategy(action_type="strategy1", confidence=0.8)
    strategy2 = MockStrategy(action_type="strategy2", confidence=0.9)

    service = IntentRecognitionService(strategy1)
    assert service.recognize("test").action_type == "strategy1"

    service.set_strategy(strategy2)
    assert service.recognize("test").action_type == "strategy2"


def test_intent_result_raw_response():
    """测试原始响应字段"""
    result = IntentResult(action_type="test", confidence=1.0, raw_response='{"action": "test"}')
    assert result.raw_response == '{"action": "test"}'


def test_missing_field_dict_structure():
    """测试缺失字段的字典结构"""
    field = MissingField(
        field_name="room_type",
        display_name="房型",
        field_type="enum",
        options=["single", "double", "suite"],
        required=True,
    )

    assert field.field_name == "room_type"
    assert field.display_name == "房型"
    assert field.field_type == "enum"
    assert field.options == ["single", "double", "suite"]
    assert field.required is True
