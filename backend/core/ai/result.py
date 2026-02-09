"""
core/ai/result.py

统一的操作结果类型 - 所有 action handler 应返回此类型
Provides structured, introspectable results for undo/audit/reflexion.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AffectedEntity:
    """受影响的实体记录"""
    entity_type: str
    entity_id: int
    change_type: str  # "created" | "updated" | "deleted"


@dataclass
class ActionResult:
    """
    统一的操作结果

    所有 action handler 返回此类型，提供：
    - 成功/失败状态
    - 结构化错误信息
    - 受影响实体列表（用于 undo/audit）
    - 触发的事件列表
    - 失败时的可选替代方案
    """
    success: bool
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    affected_entities: List[AffectedEntity] = field(default_factory=list)
    events_emitted: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    valid_alternatives: List[str] = field(default_factory=list)

    @staticmethod
    def ok(message: str, **kwargs) -> "ActionResult":
        """快速创建成功结果"""
        return ActionResult(success=True, message=message, **kwargs)

    @staticmethod
    def fail(message: str, error_code: str = None, **kwargs) -> "ActionResult":
        """快速创建失败结果"""
        return ActionResult(success=False, message=message, error_code=error_code, **kwargs)
