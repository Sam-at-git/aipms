"""
测试 core.engine 模块 - 核心引擎单元测试
"""
import pytest
from datetime import datetime, timedelta
from core.engine.event_bus import Event, EventBus, PublishResult, EventBusStatistics
from core.engine.rule_engine import (
    RuleContext,
    FunctionCondition,
    ExpressionCondition,
    Rule,
    RuleEngine,
    rule_engine,
)
from core.engine.state_machine import (
    StateTransition,
    StateMachineConfig,
    StateMachineSnapshot,
    StateMachine,
    StateMachineEngine,
    state_machine_engine,
)
from core.engine.snapshot import OperationSnapshot, SnapshotEngine, snapshot_engine
from core.engine.audit import AuditSeverity, AuditLog, AuditEngine, audit_engine


# ============== EventBus Tests ==============
class TestEventBus:
    """EventBus 已经在 tests/engine/test_event_bus.py 中测试"""

    def test_import(self):
        """测试导入"""
        from core.engine import EventBus, event_bus
        assert EventBus is not None
        assert event_bus is not None


# ============== RuleEngine Tests ==============
class TestRuleContext:
    def test_creation(self):
        """测试RuleContext创建"""
        entity = {"status": "active"}
        context = RuleContext(
            entity=entity,
            entity_type="TestEntity",
            action="test_action",
            parameters={"param1": "value1"},
        )
        assert context.entity_type == "TestEntity"
        assert context.get_parameter("param1") == "value1"
        assert context.get_parameter("nonexistent", "default") == "default"
        assert not context.has_parameter("nonexistent")

    def test_has_parameter(self):
        """测试参数检查"""
        context = RuleContext(
            entity=None, entity_type="Test", action="test", parameters={"a": 1}
        )
        assert context.has_parameter("a")
        assert not context.has_parameter("b")


class TestFunctionCondition:
    def test_condition_true(self):
        """测试条件为真"""
        cond = FunctionCondition(lambda ctx: True, "Always True")
        assert cond.evaluate(None)

    def test_condition_false(self):
        """测试条件为假"""
        cond = FunctionCondition(lambda ctx: False, "Always False")
        assert not cond.evaluate(None)

    def test_condition_with_context(self):
        """测试带上下文的条件"""
        def check_status(ctx):
            return ctx.entity.get("status") == "active"

        cond = FunctionCondition(check_status, "Check Active")

        entity = {"status": "active"}
        context = RuleContext(entity, "Entity", "test", {})
        assert cond.evaluate(context)


class TestExpressionCondition:
    def test_equality_true(self):
        """测试相等条件为真"""
        entity = {"status": "active"}
        cond = ExpressionCondition("status == 'active'")
        context = RuleContext(entity, "Entity", "test", {})
        assert cond.evaluate(context)

    def test_equality_false(self):
        """测试相等条件为假"""
        entity = {"status": "inactive"}
        cond = ExpressionCondition("status == 'active'")
        context = RuleContext(entity, "Entity", "test", {})
        assert not cond.evaluate(context)

    def test_inequality(self):
        """测试不等条件"""
        entity = {"status": "active"}
        cond = ExpressionCondition("status != 'inactive'")
        context = RuleContext(entity, "Entity", "test", {})
        assert cond.evaluate(context)


class TestRule:
    def test_creation(self):
        """测试规则创建"""
        rule = Rule(
            rule_id="test_rule",
            name="Test Rule",
            description="A test rule",
            condition=FunctionCondition(lambda ctx: True),
            action=lambda ctx: None,
        )
        assert rule.rule_id == "test_rule"
        assert rule.enabled is True

    def test_priority(self):
        """测试规则优先级"""
        rule1 = Rule(
            rule_id="r1",
            name="R1",
            description="",
            condition=FunctionCondition(lambda ctx: True),
            action=lambda ctx: None,
            priority=1,
        )
        rule2 = Rule(
            rule_id="r2",
            name="R2",
            description="",
            condition=FunctionCondition(lambda ctx: True),
            action=lambda ctx: None,
            priority=10,
        )
        assert rule2.priority > rule1.priority


class TestRuleEngine:
    def test_register_rule(self):
        """测试注册规则"""
        engine = RuleEngine()
        engine.clear()

        rule = Rule(
            rule_id="test_rule",
            name="Test",
            description="",
            condition=FunctionCondition(lambda ctx: True),
            action=lambda ctx: None,
        )
        engine.register_rule(rule)
        assert engine.get_rule("test_rule") is rule

    def test_register_duplicate(self):
        """测试重复注册抛出异常"""
        engine = RuleEngine()
        engine.clear()

        rule = Rule(
            rule_id="test",
            name="Test",
            description="",
            condition=FunctionCondition(lambda ctx: True),
            action=lambda ctx: None,
        )
        engine.register_rule(rule)

        with pytest.raises(ValueError):
            engine.register_rule(rule)

    def test_unregister_rule(self):
        """测试注销规则"""
        engine = RuleEngine()
        engine.clear()

        rule = Rule(
            rule_id="test", name="T", description="", condition=FunctionCondition(lambda ctx: True), action=lambda ctx: None
        )
        engine.register_rule(rule)
        assert engine.get_rule("test") is not None

        engine.unregister_rule("test")
        assert engine.get_rule("test") is None

    def test_evaluate_triggers_matching(self):
        """测试评估触发匹配规则"""
        engine = RuleEngine()
        engine.clear()

        results = []

        def action(ctx):
            results.append(ctx.action)

        rule = Rule(
            rule_id="test_action",
            name="Test",
            description="",
            condition=FunctionCondition(lambda ctx: ctx.action == "test_action"),
            action=action,
        )
        engine.register_rule(rule)

        entity = {"status": "active"}
        context = RuleContext(entity, "test", "test_action", {})
        triggered = engine.evaluate(context)

        assert len(triggered) == 1
        assert len(results) == 1

    def test_enable_disable_rule(self):
        """测试启用/禁用规则"""
        engine = RuleEngine()
        engine.clear()

        rule = Rule(
            rule_id="test", name="T", description="", condition=FunctionCondition(lambda ctx: True), action=lambda ctx: None
        )
        engine.register_rule(rule)

        engine.disable_rule("test")
        assert not engine.get_rule("test").enabled

        engine.enable_rule("test")
        assert engine.get_rule("test").enabled


# ============== StateMachine Tests ==============
class TestStateMachineConfig:
    def test_creation(self):
        """测试状态机配置创建"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2", "s3"],
            transitions=[],
            initial_state="s1",
        )
        assert config.name == "Test"
        assert config.initial_state == "s1"


class TestStateTransition:
    def test_creation(self):
        """测试状态转换创建"""
        transition = StateTransition(
            from_state="s1", to_state="s2", trigger="t1"
        )
        assert transition.from_state == "s1"
        assert transition.to_state == "s2"
        assert transition.trigger == "t1"

    def test_condition_allowed(self):
        """测试条件允许转换"""
        transition = StateTransition(
            from_state="s1",
            to_state="s2",
            trigger="t1",
            condition=lambda ctx: ctx.get("allowed", False),
        )
        assert transition.is_allowed({"allowed": True})
        assert not transition.is_allowed({"allowed": False})

    def test_no_condition_always_allowed(self):
        """测试无条件总是允许"""
        transition = StateTransition(from_state="s1", to_state="s2", trigger="t1")
        assert transition.is_allowed({})

    def test_side_effects(self):
        """测试副作用执行"""
        results = []

        def effect():
            results.append("executed")

        transition = StateTransition(
            from_state="s1", to_state="s2", trigger="t1", side_effects=[effect]
        )
        transition.execute_side_effects()
        assert len(results) == 1
        assert results[0] == "executed"


class TestStateMachine:
    def test_creation(self):
        """测试状态机创建"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2", "s3"],
            transitions=[],
            initial_state="s1",
        )
        machine = StateMachine(config)
        assert machine.current_state == "s1"

    def test_can_transition(self):
        """测试转换检查"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2"],
            transitions=[
                StateTransition(from_state="s1", to_state="s2", trigger="t1")
            ],
            initial_state="s1",
        )
        machine = StateMachine(config)
        assert machine.can_transition_to("s2", "t1")
        assert not machine.can_transition_to("s3", "t1")  # 不存在的状态
        assert not machine.can_transition_to("s2", "t2")  # 错误触发器

    def test_transition_success(self):
        """测试成功转换"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2"],
            transitions=[
                StateTransition(from_state="s1", to_state="s2", trigger="t1")
            ],
            initial_state="s1",
        )
        machine = StateMachine(config)
        assert machine.transition_to("s2", "t1")
        assert machine.current_state == "s2"

    def test_transition_failure(self):
        """测试失败转换"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2"],
            transitions=[
                StateTransition(from_state="s1", to_state="s2", trigger="t1")
            ],
            initial_state="s1",
        )
        machine = StateMachine(config)
        assert not machine.transition_to("s2", "t2")  # 错误触发器
        assert machine.current_state == "s1"  # 状态不变

    def test_history(self):
        """测试转换历史"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2", "s3"],
            transitions=[
                StateTransition(from_state="s1", to_state="s2", trigger="t1"),
                StateTransition(from_state="s2", to_state="s3", trigger="t2"),
            ],
            initial_state="s1",
        )
        machine = StateMachine(config)
        machine.transition_to("s2", "t1")
        machine.transition_to("s3", "t2")

        history = machine.get_history()
        assert len(history) == 2

    def test_reset(self):
        """测试重置状态机"""
        config = StateMachineConfig(
            name="Test",
            states=["s1", "s2"],
            transitions=[
                StateTransition(from_state="s1", to_state="s2", trigger="t1")
            ],
            initial_state="s1",
        )
        machine = StateMachine(config)
        machine.transition_to("s2", "t1")
        assert machine.current_state == "s2"

        machine.reset()
        assert machine.current_state == "s1"


class TestStateMachineEngine:
    def test_register_and_get(self):
        """测试注册和获取状态机"""
        engine = StateMachineEngine()
        engine.clear()

        config = StateMachineConfig(
            name="Test", states=["s1", "s2"], transitions=[], initial_state="s1"
        )
        machine = StateMachine(config)
        engine.register("Test", machine)

        assert engine.get("Test") is machine

    def test_get_all(self):
        """测试获取所有状态机"""
        engine = StateMachineEngine()
        engine.clear()

        engine.register("M1", StateMachine(
            config=StateMachineConfig(name="M1", states=["s1"], transitions=[], initial_state="s1")
        ))
        engine.register("M2", StateMachine(
            config=StateMachineConfig(name="M2", states=["s1"], transitions=[], initial_state="s1")
        ))

        machines = engine.get_all()
        assert len(machines) == 2


# ============== SnapshotEngine Tests ==============
class TestOperationSnapshot:
    def test_creation(self):
        """测试快照创建"""
        snapshot = OperationSnapshot(
            snapshot_id="test_id",
            operation_type="test",
            entity_type="Entity",
            entity_id=123,
            before_state={"status": "pending"},
        )
        assert snapshot.snapshot_id == "test_id"
        assert snapshot.after_state is None
        assert not snapshot.is_expired()

    def test_mark_executed(self):
        """测试标记已执行"""
        snapshot = OperationSnapshot(
            snapshot_id="test",
            operation_type="test",
            entity_type="Entity",
            entity_id=123,
            before_state={"status": "pending"},
        )
        snapshot.mark_executed({"status": "done"})
        assert snapshot.after_state == {"status": "done"}

    def test_expiration(self):
        """测试快照过期"""
        snapshot = OperationSnapshot(
            snapshot_id="test",
            operation_type="test",
            entity_type="Entity",
            entity_id=123,
            before_state={},
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert snapshot.is_expired()


class TestSnapshotEngine:
    def test_create_snapshot(self):
        """测试创建快照"""
        engine = SnapshotEngine()
        engine.clear()

        snapshot = engine.create_snapshot(
            operation_type="checkin",
            entity_type="StayRecord",
            entity_id=1,
            before_state={"status": "pending"},
        )
        assert snapshot.snapshot_id is not None
        assert engine.get_snapshot(snapshot.snapshot_id) is snapshot

    def test_get_undoable_snapshots(self):
        """测试获取可撤销快照"""
        engine = SnapshotEngine()
        engine.clear()

        s1 = engine.create_snapshot(
            operation_type="op1",
            entity_type="E",
            entity_id=1,
            before_state={"v": 1},
        )
        s2 = engine.create_snapshot(
            operation_type="op2",
            entity_type="E",
            entity_id=1,
            before_state={"v": 2},
        )
        s2.mark_executed({"v": 2})

        s1.mark_executed({"v": 1})

        snapshots = engine.get_undoable_snapshots(entity_id=1)
        assert len(snapshots) == 2
        # 最新的在前
        assert snapshots[0].operation_type == "op2"

    def test_undo(self):
        """测试撤销"""
        engine = SnapshotEngine()
        engine.clear()

        result = []

        def rollback():
            result.append("rolled_back")

        snapshot = engine.create_snapshot(
            operation_type="test",
            entity_type="E",
            entity_id=1,
            before_state={},
            rollback_func=rollback,
        )
        snapshot.mark_executed({})

        assert engine.undo(snapshot.snapshot_id)
        assert len(result) == 1

    def test_undo_not_found(self):
        """测试撤销不存在的快照"""
        engine = SnapshotEngine()
        engine.clear()
        assert not engine.undo("nonexistent")

    def test_clear(self):
        """测试清空"""
        engine = SnapshotEngine()
        engine.clear()

        snapshot = engine.create_snapshot(
            operation_type="test", entity_type="E", entity_id=1, before_state={}
        )
        snapshot.mark_executed({})

        assert len(engine.get_undoable_snapshots()) > 0

        engine.clear()
        assert len(engine.get_undoable_snapshots()) == 0


# ============== AuditEngine Tests ==============
class TestAuditLog:
    def test_creation(self):
        """测试审计日志创建"""
        log = AuditLog(
            log_id="test_id",
            timestamp=datetime.utcnow(),
            operator_id=1,
            action="test.action",
            entity_type="Entity",
            entity_id=123,
            old_value='{"a": 1}',
            new_value='{"a": 2}',
            severity=AuditSeverity.INFO,
        )
        assert log.log_id == "test_id"
        assert log.severity == AuditSeverity.INFO

    def test_to_dict(self):
        """测试转换为字典"""
        log = AuditLog(
            log_id="test",
            timestamp=datetime.utcnow(),
            operator_id=1,
            action="test",
            entity_type="Entity",
            entity_id=123,
            old_value='{"a": 1}',
            new_value='{"a": 2}',
            severity=AuditSeverity.INFO,
        )
        d = log.to_dict()
        assert d["log_id"] == "test"
        assert "timestamp" in d
        assert d["severity"] == "info"


class TestAuditEngine:
    def test_log(self):
        """测试记录日志"""
        engine = AuditEngine()
        engine.clear()

        log = engine.log(
            operator_id=1,
            action="test.action",
            entity_type="Entity",
            entity_id=123,
            old_value='{"v": 1}',
            new_value='{"v": 2}',
        )
        assert log.log_id is not None
        assert engine.get_by_id(log.log_id) is log

    def test_get_by_operator(self):
        """测试按操作人查询"""
        engine = AuditEngine()
        engine.clear()

        engine.log(operator_id=1, action="a1", entity_type="E", entity_id=1)
        engine.log(operator_id=1, action="a2", entity_type="E", entity_id=1)
        engine.log(operator_id=2, action="a3", entity_type="E", entity_id=1)

        logs_op1 = engine.get_by_operator(1)
        assert len(logs_op1) == 2

    def test_get_by_entity(self):
        """测试按实体查询"""
        engine = AuditEngine()
        engine.clear()

        engine.log(operator_id=1, action="a1", entity_type="E1", entity_id=1)
        engine.log(operator_id=1, action="a2", entity_type="E1", entity_id=2)
        engine.log(operator_id=1, action="a3", entity_type="E2", entity_id=1)

        logs_e1_1 = engine.get_by_entity("E1", 1)
        assert len(logs_e1_1) == 1

    def test_get_by_action(self):
        """测试按操作查询"""
        engine = AuditEngine()
        engine.clear()

        engine.log(operator_id=1, action="create", entity_type="E", entity_id=1)
        engine.log(operator_id=1, action="update", entity_type="E", entity_id=1)
        engine.log(operator_id=1, action="update", entity_type="E", entity_id=2)

        logs_update = engine.get_by_action("update")
        assert len(logs_update) == 2

    def test_get_statistics(self):
        """测试获取统计"""
        engine = AuditEngine()
        engine.clear()

        engine.log(
            operator_id=1,
            action="create",
            entity_type="E",
            entity_id=1,
            severity=AuditSeverity.INFO,
        )
        engine.log(
            operator_id=1,
            action="update",
            entity_type="E",
            entity_id=1,
            severity=AuditSeverity.WARNING,
        )

        stats = engine.get_statistics()
        assert stats["total_logs"] == 2
        assert stats["by_severity"]["info"] == 1
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_action"]["create"] == 1
        assert stats["by_action"]["update"] == 1

    def test_clear(self):
        """测试清空"""
        engine = AuditEngine()
        engine.log(operator_id=1, action="test", entity_type="E", entity_id=1)
        assert engine.get_statistics()["total_logs"] == 1

        engine.clear()
        assert engine.get_statistics()["total_logs"] == 0
