"""
core/engine - 核心引擎模块

包含框架的核心引擎组件：
- event_bus: 事件总线（发布/订阅）
- rule_engine: 规则引擎（业务规则执行）
- state_machine: 状态机引擎（状态转换）
- snapshot: 快照引擎（操作撤销）
- audit: 审计日志引擎（操作记录）

使用方式:
    >>> from core.engine import event_bus, rule_engine, state_machine_engine
    >>> from core.engine import snapshot_engine, audit_engine
    >>> from core.engine import EventBus, RuleEngine, StateMachineEngine
"""

# 事件总线
from core.engine.event_bus import (
    EventId,
    CorrelationId,
    EventHandler,
    Event,
    PublishResult,
    EventBusStatistics,
    EventBus,
    event_bus,
)

# 规则引擎
from core.engine.rule_engine import (
    RuleContext,
    RuleCondition,
    FunctionCondition,
    ExpressionCondition,
    Rule,
    RuleEngine,
    rule_engine,
)

# 状态机引擎
from core.engine.state_machine import (
    StateTransition,
    StateMachineConfig,
    StateMachineSnapshot,
    StateMachine,
    StateMachineEngine,
    state_machine_engine,
)

# 快照引擎
from core.engine.snapshot import (
    OperationSnapshot,
    SnapshotEngine,
    snapshot_engine,
)

# 审计日志引擎
from core.engine.audit import (
    AuditSeverity,
    AuditLog,
    AuditEngine,
    audit_engine,
)

__all__ = [
    # 事件总线
    "EventId",
    "CorrelationId",
    "EventHandler",
    "Event",
    "PublishResult",
    "EventBusStatistics",
    "EventBus",
    "event_bus",
    # 规则引擎
    "RuleContext",
    "RuleCondition",
    "FunctionCondition",
    "ExpressionCondition",
    "Rule",
    "RuleEngine",
    "rule_engine",
    # 状态机
    "StateTransition",
    "StateMachineConfig",
    "StateMachineSnapshot",
    "StateMachine",
    "StateMachineEngine",
    "state_machine_engine",
    # 快照
    "OperationSnapshot",
    "SnapshotEngine",
    "snapshot_engine",
    # 审计
    "AuditSeverity",
    "AuditLog",
    "AuditEngine",
    "audit_engine",
]
