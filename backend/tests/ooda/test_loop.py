"""
测试 core.ooda.loop 模块 - OODA Loop 编排器单元测试
"""
import pytest
from datetime import datetime

from core.ooda.loop import (
    OodaLoopResult,
    OodaLoop,
    get_ooda_loop,
    set_ooda_loop,
)
from core.ooda.observe import ObservePhase
from core.ooda.orient import OrientPhase, StaticContextProvider
from core.ooda.decide import DecidePhase
from core.ooda.act import ActPhase, MockActionHandler
from core.ooda.intent import IntentRecognitionService, IntentRecognitionStrategy, IntentResult


# ============== Mock Intent Strategy ==============

class MockIntentStrategy(IntentRecognitionStrategy):
    """测试用意图识别策略"""

    def __init__(self, action_type: str = "test_action", confidence: float = 0.9,
                 entities: dict = None, requires_confirmation: bool = False):
        self._action_type = action_type
        self._confidence = confidence
        self._entities = entities or {"test_param": "test_value"}
        self._requires_confirmation = requires_confirmation

    def recognize(self, input: str, context: dict = None) -> IntentResult:
        return IntentResult(
            action_type=self._action_type,
            confidence=self._confidence,
            entities=self._entities,
            requires_confirmation=self._requires_confirmation,
        )


# Action type to required params mapping for testing
ACTION_TEST_PARAMS = {
    "checkout": {"stay_record_id": 1},
    "checkin": {"reservation_id": 1, "room_id": 101},
    "complete_task": {"task_id": 1},
}


# ============== Fixtures ==============

@pytest.fixture
def sample_ooda_loop():
    """创建示例 OODA Loop"""
    observe = ObservePhase()
    intent_service = IntentRecognitionService(MockIntentStrategy())
    orient = OrientPhase(intent_service)
    decide = DecidePhase()
    act = ActPhase()

    # 添加 mock handler
    act.add_handler(MockActionHandler())

    return OodaLoop(observe, orient, decide, act)


# ============== OodaLoopResult Tests ==============

class TestOodaLoopResult:
    def test_creation(self):
        """测试创建结果"""
        result = OodaLoopResult()

        assert result.success is False
        assert result.completed_stages == []
        assert result.observation is None
        assert result.orientation is None
        assert result.decision is None
        assert result.action_result is None

    def test_to_dict(self):
        """测试转换为字典"""
        result = OodaLoopResult(
            success=True,
            completed_stages=["observe", "orient"],
            requires_confirmation=True,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["completed_stages"] == ["observe", "orient"]
        assert d["requires_confirmation"] is True


# ============== OodaLoop Tests ==============

class TestOodaLoop:
    def test_execute_full_cycle(self, sample_ooda_loop):
        """测试完整循环执行"""
        result = sample_ooda_loop.execute("test input")

        assert result.success is True
        assert "observe" in result.completed_stages
        assert "orient" in result.completed_stages
        assert "decide" in result.completed_stages
        assert "act" in result.completed_stages
        assert result.observation is not None
        assert result.orientation is not None
        assert result.decision is not None
        assert result.action_result is not None

    def test_execute_with_context(self, sample_ooda_loop):
        """测试带上下文执行"""
        result = sample_ooda_loop.execute(
            "test input",
            context={"user_id": 123}
        )

        assert result.success is True
        # 上下文应该被传递到观察结果
        assert result.observation.metadata.get("user_id") == 123

    def test_execute_with_invalid_input(self, sample_ooda_loop):
        """测试无效输入"""
        result = sample_ooda_loop.execute("")

        assert result.success is False
        assert "observe" in result.completed_stages
        # 应该在 Observe 阶段停止
        assert "orient" not in result.completed_stages
        assert len(result.errors) > 0

    def test_execute_with_skip_confirmation(self, sample_ooda_loop):
        """测试跳过确认"""
        # 创建需要确认的意图（requires_confirmation=True signals confirmation needed）
        intent_service = IntentRecognitionService(
            MockIntentStrategy("checkout", 0.9, ACTION_TEST_PARAMS["checkout"],
                               requires_confirmation=True)
        )
        observe = ObservePhase()
        orient = OrientPhase(intent_service)
        decide = DecidePhase()
        act = ActPhase()
        act.add_handler(MockActionHandler())

        loop = OodaLoop(observe, orient, decide, act)

        # 不跳过确认
        result1 = loop.execute("test", skip_confirmation=False)

        assert result1.requires_confirmation is True
        assert result1.success is False
        assert "act" not in result1.completed_stages

        # 跳过确认
        result2 = loop.execute("test", skip_confirmation=True)

        assert result2.success is True
        assert "act" in result2.completed_stages

    def test_execute_with_confirmation(self, sample_ooda_loop):
        """测试 execute_with_confirmation"""
        # 创建需要确认的意图（requires_confirmation=True signals confirmation needed）
        intent_service = IntentRecognitionService(
            MockIntentStrategy("checkout", 0.9, ACTION_TEST_PARAMS["checkout"],
                               requires_confirmation=True)
        )
        observe = ObservePhase()
        orient = OrientPhase(intent_service)
        decide = DecidePhase()
        act = ActPhase()
        act.add_handler(MockActionHandler())

        loop = OodaLoop(observe, orient, decide, act)

        result = loop.execute_with_confirmation("test")

        # 应该完成到 decide 阶段
        assert "observe" in result.completed_stages
        assert "orient" in result.completed_stages
        assert "decide" in result.completed_stages
        assert "act" not in result.completed_stages
        assert result.requires_confirmation is True

    def test_execute_with_confirmation_then_execute(self, sample_ooda_loop):
        """测试先确认后执行的流程"""
        # 创建需要确认的意图（requires_confirmation=True signals confirmation needed）
        intent_service = IntentRecognitionService(
            MockIntentStrategy("checkout", 0.9, ACTION_TEST_PARAMS["checkout"],
                               requires_confirmation=True)
        )
        observe = ObservePhase()
        orient = OrientPhase(intent_service)
        decide = DecidePhase()
        act = ActPhase()
        act.add_handler(MockActionHandler())

        loop = OodaLoop(observe, orient, decide, act)

        # 第一步：获取决策
        result1 = loop.execute_with_confirmation("test")

        assert result1.requires_confirmation is True
        assert result1.decision is not None
        assert result1.action_result is None

        # 第二步：用户确认后执行
        result2 = loop.execute("test", skip_confirmation=True)

        assert result2.success is True
        assert result2.action_result is not None
        assert "act" in result2.completed_stages

    def test_stage_failure_stops_loop(self):
        """测试阶段失败停止循环"""
        # 创建失败的意图服务
        class FailingIntentStrategy(IntentRecognitionStrategy):
            def recognize(self, input: str, context: dict = None):
                raise RuntimeError("Intent failed")

        intent_service = IntentRecognitionService(FailingIntentStrategy())
        observe = ObservePhase()
        orient = OrientPhase(intent_service)
        decide = DecidePhase()
        act = ActPhase()

        loop = OodaLoop(observe, orient, decide, act)

        result = loop.execute("test")

        assert result.success is False
        assert "observe" in result.completed_stages
        assert "orient" not in result.completed_stages
        assert len(result.errors) > 0

    def test_timestamp(self, sample_ooda_loop):
        """测试时间戳"""
        before = datetime.utcnow()

        result = sample_ooda_loop.execute("test")

        after = datetime.utcnow()

        assert before <= result.timestamp <= after

    def test_to_dict(self, sample_ooda_loop):
        """测试转换为字典"""
        result = sample_ooda_loop.execute("test")

        d = result.to_dict()

        assert d["success"] is True
        assert "observe" in d["completed_stages"]
        assert d["observation"] is not None
        assert d["orientation"] is not None
        assert d["decision"] is not None
        assert d["action_result"] is not None


class TestGlobalInstance:
    def test_get_ooda_loop_returns_none_initially(self):
        """测试初始返回 None"""
        set_ooda_loop(None)

        result = get_ooda_loop()

        assert result is None

    def test_set_and_get_ooda_loop(self):
        """测试设置和获取"""
        observe = ObservePhase()
        intent_service = IntentRecognitionService(MockIntentStrategy())
        orient = OrientPhase(intent_service)
        decide = DecidePhase()
        act = ActPhase()

        loop = OodaLoop(observe, orient, decide, act)

        set_ooda_loop(loop)

        result = get_ooda_loop()

        assert result is loop
