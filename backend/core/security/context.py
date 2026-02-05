"""
core/security/context.py

安全上下文管理 - 为整个框架提供统一的安全上下文访问接口
支持线程安全、上下文嵌套和服务层访问
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging

from core.ontology.security import SecurityLevel

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """
    安全上下文数据类

    Attributes:
        user_id: 用户ID
        username: 用户名
        role: 角色（如 'manager', 'receptionist', 'cleaner'）
        security_level: 安全级别
        is_active: 账户是否激活
        ip_address: 客户端IP地址
        session_id: 会话ID
        metadata: 额外元数据
        parent_context: 父上下文（用于嵌套上下文）
    """

    user_id: Optional[int]
    username: Optional[str]
    role: Optional[str]
    security_level: SecurityLevel
    is_active: bool = True
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional["SecurityContext"] = None

    def is_admin(self) -> bool:
        """检查是否为管理员"""
        return self.role == "manager"

    def has_role(self, role: str) -> bool:
        """检查是否具有指定角色"""
        return self.role == role

    def has_clearance(self, level: SecurityLevel) -> bool:
        """检查是否具有指定的安全级别权限"""
        return self.security_level.value >= level.value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "security_level": self.security_level.value,
            "is_active": self.is_active,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"SecurityContext(user_id={self.user_id}, username={self.username!r}, "
            f"role={self.role!r}, level={self.security_level.name})"
        )


class SecurityContextManager:
    """
    安全上下文管理器 - 单例模式

    特性：
    - 线程安全：使用 threading.local() 存储上下文
    - 上下文嵌套：支持临时切换上下文（如 sudo 模式）
    - 服务层访问：可在任意位置获取当前上下文

    Example:
        >>> manager = SecurityContextManager()
        >>> ctx = SecurityContext(user_id=1, username="admin", role="manager",
        ...                      security_level=SecurityLevel.RESTRICTED)
        >>> manager.set_context(ctx)
        >>> manager.get_user_id()
        1
        >>> manager.clear_context()

        # 使用 with 语句进行临时上下文切换
        >>> with manager.enter_context(admin_context):
        ...     sensitive_operation()  # 以 admin 权限执行
        >>> # 自动恢复原上下文
    """

    _instance: Optional["SecurityContextManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SecurityContextManager":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._local = threading.local()
        self._initialized = True
        logger.debug("SecurityContextManager initialized")

    def _get_context_stack(self) -> List[SecurityContext]:
        """获取当前线程的上下文栈"""
        if not hasattr(self._local, "context_stack"):
            self._local.context_stack = []
        return self._local.context_stack

    def set_context(self, context: SecurityContext) -> None:
        """
        设置当前上下文

        Args:
            context: 要设置的安全上下文
        """
        stack = self._get_context_stack()
        if stack:
            # 如果已有上下文，将新上下文设置为子上下文
            context.parent_context = stack[-1]
        stack.append(context)
        logger.debug(f"Security context set: {context}")

    def get_context(self) -> Optional[SecurityContext]:
        """
        获取当前上下文

        Returns:
            当前安全上下文，如果未设置则返回 None
        """
        stack = self._get_context_stack()
        return stack[-1] if stack else None

    def clear_context(self) -> None:
        """清除当前上下文"""
        stack = self._get_context_stack()
        if stack:
            context = stack.pop()
            logger.debug(f"Security context cleared: {context}")

    def enter_context(self, context: SecurityContext) -> "SecurityContextManager":
        """
        进入临时上下文（用于 with 语句）

        Args:
            context: 要进入的上下文

        Returns:
            self，用于支持 with 语句
        """
        self.set_context(context)
        return self

    def exit_context(self) -> None:
        """退出临时上下文"""
        self.clear_context()

    def __enter__(self) -> "SecurityContextManager":
        """支持 with 语句（直接使用管理器）"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出 with 块，恢复上下文"""
        self.exit_context()

    # 便捷方法

    def get_user_id(self) -> Optional[int]:
        """获取当前用户ID"""
        context = self.get_context()
        return context.user_id if context else None

    def get_username(self) -> Optional[str]:
        """获取当前用户名"""
        context = self.get_context()
        return context.username if context else None

    def get_role(self) -> Optional[str]:
        """获取当前角色"""
        context = self.get_context()
        return context.role if context else None

    def get_security_level(self) -> SecurityLevel:
        """
        获取当前安全级别

        Returns:
            当前安全级别，如果没有上下文则返回 PUBLIC
        """
        context = self.get_context()
        return context.security_level if context else SecurityLevel.PUBLIC

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        context = self.get_context()
        return context is not None and context.user_id is not None

    def has_permission(self, permission: str) -> bool:
        """
        检查是否具有指定权限

        Args:
            permission: 权限标识（如 "room.update_status"）

        Returns:
            True 如果有权限
        """
        context = self.get_context()
        if not context:
            return False

        # 基础实现：管理员拥有所有权限
        if context.is_admin():
            return True

        # TODO: 实现更细粒度的权限检查
        # 这里需要在 SPEC-18 中实现权限检查器
        return True


# 全局安全上下文管理器实例
security_context_manager = SecurityContextManager()


# 导出
__all__ = [
    "SecurityContext",
    "SecurityContextManager",
    "security_context_manager",
]
