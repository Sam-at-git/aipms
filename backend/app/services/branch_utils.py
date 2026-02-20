"""
分店 branch_id 自动注入工具
Service 层创建记录时自动从 SecurityContext 获取当前分店 ID
"""
from typing import Optional


def inject_branch_id(record) -> None:
    """为新记录自动注入 branch_id（如果尚未设置）。

    从 SecurityContext 读取当前 branch_id，写入 record.branch_id。
    如果 SecurityContext 不可用（如测试环境、init_data），不做任何操作。
    """
    if not hasattr(record, 'branch_id') or record.branch_id is not None:
        return

    try:
        from core.security.context import SecurityContextManager
        ctx = SecurityContextManager().get_context()
        if ctx and ctx.branch_id:
            record.branch_id = ctx.branch_id
    except Exception:
        pass


def get_current_branch_id() -> Optional[int]:
    """获取当前 SecurityContext 中的 branch_id，如不可用返回 None。"""
    try:
        from core.security.context import SecurityContextManager
        ctx = SecurityContextManager().get_context()
        return ctx.branch_id if ctx else None
    except Exception:
        return None
