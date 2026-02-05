"""
测试 core.ooda.act 模块 - Act 阶段单元测试
"""
import pytest
from datetime import datetime

from core.ooda.act import (
    ActionResult,
    ActionHandler,
    MockActionHandler,
    DelegatingActionHandler,
    ActPhase,
    get_act_phase,
    set_act_phase,
)
from core.ooda.decide import Decision
from core.ooda.orient import Orientation
from core.ooda.observe import Observation
from core.ooda.intent import IntentResult


# ============== Fixtures ==============

@pytest.fixture
def sample_decision():
    """示例决策结果"""
    obs = Observation(raw_input="test", normalized_input="test")
    intent = IntentResult(action_type="checkin", confidence=0.9, entities={"reservation_id": 1})
    orient = Orientation(observation=obs, intent=intent, confidence=0.9)

    return Decision(
        orientation=orient,
        action_type="checkin",
        action_params={"reservation_id": 1, "room_id": 101},
        confidence=0.9,
    )


# ============== ActionResult Tests ==============

class TestActionResult:
    def test_creation(self, sample_decision):
        """测试创建动作结果"""
        result = ActionResult(
            decision=sample_decision,
            success=True,
            result_data={"id": 123},
        )

        assert result.decision == sample_decision
        assert result.success is True
        assert result.result_data == {"id": 123}
        assert result.executed is False

    def test_creation_with_executed(self, sample_decision):
        """测试创建已执行的结果"""
        result = ActionResult(
            decision=sample_decision,
            success=True,
            executed=True,
        )

        assert result.executed is True

    def test_to_dict(self, sample_decision):
        """测试转换为字典"""
        result = ActionResult(
            decision=sample_decision,
            success=True,
            result_data={"stay_record_id": 456},
        )

        d = result.to_dict()

        assert d["action_type"] == "checkin"
        assert d["success"] is True
        assert d["result_data"] == {"stay_record_id": 456}
        assert d["executed"] is False


# ============== MockActionHandler Tests ==============

class TestMockActionHandler:
    def test_can_handle_all_actions(self):
        """测试处理所有动作类型"""
        handler = MockActionHandler()

        assert handler.can_handle("checkin") is True
        assert handler.can_handle("checkout") is True
        assert handler.can_handle("unknown") is True

    def test_can_handle_specific_actions(self):
        """测试处理特定动作类型"""
        handler = MockActionHandler(["checkin", "checkout"])

        assert handler.can_handle("checkin") is True
        assert handler.can_handle("checkout") is True
        assert handler.can_handle("unknown") is False

    def test_execute_returns_success(self, sample_decision):
        """测试执行返回成功"""
        handler = MockActionHandler()

        result = handler.execute(sample_decision)

        assert result.success is True
        assert result.decision == sample_decision
        assert result.executed is True

    def test_execute_tracks_calls(self, sample_decision):
        """测试记录执行调用"""
        handler = MockActionHandler()

        handler.execute(sample_decision)

        assert len(handler.execute_calls) == 1
        assert handler.execute_calls[0] == sample_decision

    def test_set_mock_result(self, sample_decision):
        """测试设置模拟结果"""
        handler = MockActionHandler()
        handler.set_mock_result("checkin", {"stay_record_id": 789})

        result = handler.execute(sample_decision)

        assert result.result_data == {"stay_record_id": 789}


# ============== DelegatingActionHandler Tests ==============

class TestDelegatingActionHandler:
    def test_can_handle_registered_action(self):
        """测试能处理已注册的动作"""
        handler = DelegatingActionHandler({"checkin": lambda x: {"id": 1}})

        assert handler.can_handle("checkin") is True
        assert handler.can_handle("checkout") is False

    def test_execute_delegates_to_service(self, sample_decision):
        """测试委托给服务执行"""
        service_called = []

        def mock_service(params):
            service_called.append(params)
            return {"stay_record_id": 999}

        handler = DelegatingActionHandler({"checkin": mock_service})

        result = handler.execute(sample_decision)

        assert result.success is True
        assert result.result_data == {"stay_record_id": 999}
        assert service_called == [sample_decision.action_params]

    def test_execute_with_non_dict_result(self, sample_decision):
        """测试处理非字典结果"""
        handler = DelegatingActionHandler({"checkin": lambda x: "success"})

        result = handler.execute(sample_decision)

        assert result.success is True
        assert result.result_data == {"result": "success"}

    def test_execute_with_exception(self, sample_decision):
        """测试处理异常"""
        def failing_service(params):
            raise ValueError("Service error")

        handler = DelegatingActionHandler({"checkin": failing_service})

        result = handler.execute(sample_decision)

        assert result.success is False
        assert "Service error" in result.error_message

    def test_execute_with_no_service(self, sample_decision):
        """测试没有注册服务"""
        handler = DelegatingActionHandler({})

        result = handler.execute(sample_decision)

        assert result.success is False
        assert "No service registered" in result.error_message


# ============== ActPhase Tests ==============

class TestActPhase:
    def test_act_with_valid_decision(self, sample_decision):
        """测试执行有效决策"""
        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(sample_decision)

        assert result.success is True
        assert result.executed is True
        assert len(handler.execute_calls) == 1

    def test_act_with_invalid_decision(self):
        """测试执行无效决策"""
        obs = Observation(raw_input="test", normalized_input="test")
        intent = IntentResult(action_type="checkin", confidence=0.9, entities={})
        orient = Orientation(observation=obs, intent=intent, confidence=0.9)
        decision = Decision(
            orientation=orient,
            action_type="checkin",
            action_params={},
            is_valid=False,
            errors=["Missing required params"],
        )

        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(decision)

        assert result.success is False
        assert "Invalid decision" in result.error_message
        assert len(handler.execute_calls) == 0

    def test_act_with_confirmation_required(self, sample_decision):
        """测试需要确认的决策"""
        sample_decision.requires_confirmation = True

        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(sample_decision, skip_confirmation=False)

        assert result.success is False
        assert "requires confirmation" in result.error_message
        assert result.executed is False
        assert len(handler.execute_calls) == 0

    def test_act_skip_confirmation(self, sample_decision):
        """测试跳过确认"""
        sample_decision.requires_confirmation = True

        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(sample_decision, skip_confirmation=True)

        assert result.success is True
        assert result.executed is True
        assert len(handler.execute_calls) == 1

    def test_act_with_no_matching_handler(self, sample_decision):
        """测试没有匹配的处理器"""
        act = ActPhase()
        handler = MockActionHandler(["checkout"])  # 不处理 checkin
        act.add_handler(handler)

        result = act.act(sample_decision)

        assert result.success is False
        assert "No handler found" in result.error_message

    def test_add_handler(self):
        """测试添加处理器"""
        act = ActPhase()
        handler = MockActionHandler()

        act.add_handler(handler)

        assert handler in act._handlers

    def test_remove_handler(self):
        """测试移除处理器"""
        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        act.remove_handler(handler)

        assert handler not in act._handlers

    def test_clear_handlers(self):
        """测试清空处理器"""
        act = ActPhase()
        act.add_handler(MockActionHandler())
        act.add_handler(MockActionHandler())

        act.clear_handlers()

        assert len(act._handlers) == 0

    def test_act_preserves_metadata(self, sample_decision):
        """测试保留元数据"""
        sample_decision.metadata = {"user_id": 123, "role": "manager"}

        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(sample_decision)

        assert result.metadata["user_id"] == 123
        assert result.metadata["role"] == "manager"

    def test_timestamp(self, sample_decision):
        """测试时间戳"""
        before = datetime.utcnow()
        act = ActPhase()
        handler = MockActionHandler()
        act.add_handler(handler)

        result = act.act(sample_decision)
        after = datetime.utcnow()

        assert before <= result.timestamp <= after

    def test_act_with_handler_exception(self, sample_decision):
        """测试处理器异常处理"""

        class FailingHandler(ActionHandler):
            def can_handle(self, action_type):
                return True

            def execute(self, decision):
                raise RuntimeError("Handler error")

        act = ActPhase()
        act.add_handler(FailingHandler())

        result = act.act(sample_decision)

        assert result.success is False
        assert "Handler error" in result.error_message


class TestGlobalInstance:
    def test_get_act_phase_creates_singleton(self):
        """测试获取单例"""
        set_act_phase(None)

        act1 = get_act_phase()
        act2 = get_act_phase()

        assert act1 is act2
        assert isinstance(act1, ActPhase)

    def test_set_act_phase(self):
        """测试设置实例"""
        custom = ActPhase()
        set_act_phase(custom)

        result = get_act_phase()

        assert result is custom
