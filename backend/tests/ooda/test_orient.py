"""
测试 core.ooda.orient 模块 - Orient 阶段单元测试
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from core.ooda.orient import (
    Orientation,
    ContextProvider,
    SecurityContextProvider,
    StaticContextProvider,
    CompositeContextProvider,
    OrientPhase,
    get_orient_phase,
    set_orient_phase,
)
from core.ooda.observe import Observation
from core.ooda.intent import IntentResult, IntentRecognitionService, IntentRecognitionStrategy
from core.security.context import security_context_manager, SecurityContext, SecurityLevel


# ============== Test Context Providers ==============

class MockContextProvider(ContextProvider):
    """测试用上下文提供者"""

    def __init__(self, data: dict):
        self._data = data

    def provide(self) -> dict:
        return self._data.copy()


class TestSecurityContextProvider:
    def test_provide_with_context(self):
        """测试有安全上下文时提供数据"""
        provider = SecurityContextProvider()

        # 设置安全上下文（使用非管理员角色）
        context = SecurityContext(
            user_id=1,
            username="test_user",
            role="receptionist",
            security_level=SecurityLevel.CONFIDENTIAL,
        )
        security_context_manager.set_context(context)

        result = provider.provide()

        assert result["user_id"] == 1
        assert result["username"] == "test_user"
        assert result["role"] == "receptionist"
        assert result["security_level"] == SecurityLevel.CONFIDENTIAL.value
        assert result["is_admin"] is False

        # 清理
        security_context_manager.clear_context()

    def test_provide_without_context(self):
        """测试无安全上下文时返回空字典"""
        provider = SecurityContextProvider()

        # 确保没有上下文
        security_context_manager.clear_context()

        result = provider.provide()

        assert result == {}


class TestStaticContextProvider:
    def test_provide_static_data(self):
        """测试提供静态数据"""
        data = {"key1": "value1", "key2": 123}
        provider = StaticContextProvider(data)

        result = provider.provide()

        assert result == data

    def test_provide_returns_copy(self):
        """测试返回数据的副本"""
        data = {"key": "value"}
        provider = StaticContextProvider(data)

        result1 = provider.provide()
        result2 = provider.provide()

        # 修改返回值不影响原始数据
        result1["key"] = "modified"
        assert provider._data["key"] == "value"
        assert result2["key"] == "value"


class TestCompositeContextProvider:
    def test_merge_multiple_providers(self):
        """测试合并多个提供者"""
        provider1 = MockContextProvider({"key1": "value1"})
        provider2 = MockContextProvider({"key2": "value2"})
        provider3 = MockContextProvider({"key3": "value3"})

        composite = CompositeContextProvider([provider1, provider2, provider3])

        result = composite.provide()

        assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}

    def test_later_provider_overwrites(self):
        """测试后添加的提供者覆盖前面的值"""
        provider1 = MockContextProvider({"key": "value1"})
        provider2 = MockContextProvider({"key": "value2"})

        composite = CompositeContextProvider([provider1, provider2])

        result = composite.provide()

        assert result["key"] == "value2"


# ============== Orientation Tests ==============

class TestOrientation:
    def test_creation(self):
        """测试创建导向结果"""
        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )
        intent = IntentResult(action_type="test_action", confidence=0.9)

        orientation = Orientation(
            observation=obs,
            intent=intent,
            confidence=0.9,
        )

        assert orientation.observation == obs
        assert orientation.intent == intent
        assert orientation.confidence == 0.9
        assert orientation.is_valid is True

    def test_to_dict(self):
        """测试转换为字典"""
        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )
        intent = IntentResult(
            action_type="test_action",
            confidence=0.85,
            entities={"room_id": 101},
        )

        orientation = Orientation(
            observation=obs,
            intent=intent,
            confidence=0.85,
        )

        d = orientation.to_dict()

        assert d["observation"]["raw_input"] == "test"
        assert d["intent"]["action_type"] == "test_action"
        assert d["intent"]["confidence"] == 0.85
        assert d["intent"]["entities"] == {"room_id": 101}
        assert d["confidence"] == 0.85

    def test_to_dict_with_none_intent(self):
        """测试意图为空时转换为字典"""
        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )

        orientation = Orientation(
            observation=obs,
            intent=None,
            is_valid=False,
        )

        d = orientation.to_dict()

        assert d["intent"] is None
        assert d["is_valid"] is False


# ============== Mock Intent Strategy ==============

class MockIntentStrategy(IntentRecognitionStrategy):
    """测试用意图识别策略"""

    def __init__(self, action_type: str = "test_action", confidence: float = 0.9):
        self._action_type = action_type
        self._confidence = confidence
        self.recognize_calls = []

    def recognize(self, input: str, context: dict = None) -> IntentResult:
        self.recognize_calls.append((input, context))
        return IntentResult(
            action_type=self._action_type,
            confidence=self._confidence,
            entities={"test_entity": "test_value"},
        )


# ============== OrientPhase Tests ==============

class TestOrientPhase:
    def test_orient_basic(self):
        """测试基本导向"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        obs = Observation(
            raw_input="test input",
            normalized_input="test input",
        )

        orientation = orient.orient(obs)

        assert orientation.observation == obs
        assert orientation.intent.action_type == "test_action"
        assert orientation.confidence == 0.9
        assert orientation.extracted_entities == {"test_entity": "test_value"}
        assert orientation.is_valid is True

    def test_orient_with_invalid_observation(self):
        """测试无效观察结果"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        obs = Observation(
            raw_input="",
            normalized_input="",
            is_valid=False,
            validation_errors=["Input cannot be empty"],
        )

        orientation = orient.orient(obs)

        # 无效观察不应进行意图识别
        assert orientation.intent is None
        assert orientation.is_valid is False
        assert "Input cannot be empty" in orientation.errors

    def test_orient_passes_context_to_intent(self):
        """测试上下文传递给意图识别"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        # 添加静态上下文
        orient.add_context_provider(StaticContextProvider({"test_key": "test_value"}))

        obs = Observation(
            raw_input="test input",
            normalized_input="test input",
        )

        orientation = orient.orient(obs)

        # 验证上下文被传递
        assert len(strategy.recognize_calls) == 1
        input_arg, context_arg = strategy.recognize_calls[0]
        assert context_arg["test_key"] == "test_value"
        assert orientation.context["test_key"] == "test_value"

    def test_add_context_provider(self):
        """测试添加上下文提供者"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        # 清空默认提供者
        orient.clear_context_providers()

        # 添加自定义提供者
        provider = MockContextProvider({"custom": "data"})
        orient.add_context_provider(provider)

        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )

        orientation = orient.orient(obs)

        assert orientation.context == {"custom": "data"}

    def test_remove_context_provider(self):
        """测试移除上下文提供者"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        # 添加一个提供者然后移除
        provider = StaticContextProvider({"temp": "data"})
        orient.add_context_provider(provider)
        orient.remove_context_provider(provider)

        # 验证提供者列表不包含被移除的提供者
        assert provider not in orient._context_providers

    def test_clear_context_providers(self):
        """测试清空上下文提供者"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        orient.clear_context_providers()

        assert len(orient._context_providers) == 0

        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )

        orientation = orient.orient(obs)

        # 没有上下文提供者，context 应该为空
        assert orientation.context == {}

    def test_context_provider_failure(self):
        """测试上下文提供者失败时的处理"""

        class FailingProvider(ContextProvider):
            def provide(self) -> dict:
                raise RuntimeError("Provider failed")

        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        orient.add_context_provider(FailingProvider())

        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )

        orientation = orient.orient(obs)

        # 失败的提供者应该被记录但不中断处理
        assert orientation.is_valid is True
        assert any("Provider failed" in e for e in orientation.errors)

    def test_metadata_from_observation(self):
        """测试元数据从观察结果传递"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        obs = Observation(
            raw_input="test",
            normalized_input="test",
            metadata={"custom_meta": "value"},
        )

        orientation = orient.orient(obs)

        assert orientation.metadata["custom_meta"] == "value"

    def test_timestamp(self):
        """测试时间戳"""
        before = datetime.utcnow()
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        orient = OrientPhase(intent_service)

        obs = Observation(raw_input="test", normalized_input="test")
        orientation = orient.orient(obs)
        after = datetime.utcnow()

        assert before <= orientation.timestamp <= after


class TestGlobalInstance:
    def test_get_orient_phase_creates_instance(self):
        """测试首次调用创建实例"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)

        # 重置全局实例
        set_orient_phase(None)

        orient = get_orient_phase(intent_service)

        assert isinstance(orient, OrientPhase)

    def test_get_orient_phase_returns_singleton(self):
        """测试返回单例"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)

        # 重置并设置实例
        set_orient_phase(None)
        orient1 = get_orient_phase(intent_service)
        orient2 = get_orient_phase()

        assert orient1 is orient2

    def test_get_orient_phase_requires_service_on_first_call(self):
        """测试首次调用需要提供 intent_service"""
        # 重置全局实例
        set_orient_phase(None)

        with pytest.raises(ValueError, match="intent_service must be provided"):
            get_orient_phase()

    def test_set_orient_phase(self):
        """测试设置全局实例"""
        strategy = MockIntentStrategy()
        intent_service = IntentRecognitionService(strategy)
        custom_orient = OrientPhase(intent_service)

        set_orient_phase(custom_orient)
        result = get_orient_phase()

        assert result is custom_orient
