"""
core/ai/context.py

执行上下文 - 为 action handler 提供类型安全的依赖注入
替代原有的 **context 字典传递方式。
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExecutionContext:
    """
    Action handler 执行上下文

    提供 handler 所需的所有依赖，替代 **kwargs 传递：
    - db: SQLAlchemy Session
    - user_id/role/name: 当前操作用户
    - param_parser: 参数解析服务
    - event_bus: 事件总线
    - audit_logger: 审计日志
    - state_machine: 状态机执行器 (Phase 4)
    """
    db: Any  # sqlalchemy.orm.Session
    user_id: int
    user_role: str
    user_name: str
    param_parser: Any = None
    event_bus: Any = None
    audit_logger: Any = None
    state_machine: Any = None
