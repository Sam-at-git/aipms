"""
core/security/checker.py

权限检查器 - 提供细粒度的权限验证机制
支持基于角色、资源和操作的权限检查
"""
from typing import Dict, Set, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from functools import wraps
import logging

from core.security.context import SecurityContext, security_context_manager
from core.engine.audit import AuditEngine, audit_engine, AuditSeverity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Permission:
    """
    权限定义

    Attributes:
        resource: 资源类型 (如 "room", "guest", "bill")
        action: 操作类型 (如 "read", "write", "delete", "*")
    """

    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"

    def __hash__(self) -> int:
        return hash((self.resource, self.action))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Permission):
            return False
        return self.resource == other.resource and self.action == other.action

    def matches(self, other: "Permission") -> bool:
        """
        检查是否匹配权限（支持通配符）

        Args:
            other: 要检查的权限

        Returns:
            True 如果匹配
        """
        # 完全匹配
        if self == other:
            return True

        # 双重通配符匹配所有
        if self.resource == "*" and self.action == "*":
            return True

        # 资源通配符：只检查操作
        if self.resource == "*":
            return self.action == other.action

        # 操作通配符：只检查资源
        if self.action == "*":
            return self.resource == other.resource

        return False

    @classmethod
    def from_string(cls, perm_str: str) -> "Permission":
        """
        从字符串解析权限

        Args:
            perm_str: 权限字符串，格式 "resource:action"

        Returns:
            Permission 对象

        Raises:
            ValueError: 如果格式无效
        """
        if ":" not in perm_str:
            raise ValueError(f"Invalid permission string: {perm_str}")

        resource, action = perm_str.split(":", 1)
        return cls(resource=resource.strip(), action=action.strip())


class PermissionRule(ABC):
    """权限规则抽象基类"""

    @abstractmethod
    def check(
        self,
        context: Optional[SecurityContext],
        permission: Permission,
        resource_id: Optional[Any] = None,
    ) -> bool:
        """
        检查是否允许执行操作

        Args:
            context: 安全上下文
            permission: 要检查的权限
            resource_id: 资源ID（可选，用于所有者检查）

        Returns:
            True 如果允许
        """
        raise NotImplementedError


class RolePermissionRule(PermissionRule):
    """
    基于角色的权限规则

    使用角色到权限集合的映射进行检查
    """

    def __init__(self):
        self._role_permissions: Dict[str, Set[Permission]] = {}

    def register_role_permissions(
        self, role: str, permissions: List[Permission]
    ) -> None:
        """
        注册角色权限

        Args:
            role: 角色名称
            permissions: 权限列表
        """
        self._role_permissions[role] = set(permissions)
        logger.debug(f"Registered {len(permissions)} permissions for role: {role}")

    def get_role_permissions(self, role: str) -> Set[Permission]:
        """获取角色的权限集合"""
        return self._role_permissions.get(role, set())

    def check(
        self,
        context: Optional[SecurityContext],
        permission: Permission,
        resource_id: Optional[Any] = None,
    ) -> bool:
        """基于角色检查权限"""
        if context is None or context.role is None:
            return False

        role_perms = self.get_role_permissions(context.role)

        # 检查是否有匹配的权限
        for perm in role_perms:
            if perm.matches(permission):
                return True

        return False


class OwnerPermissionRule(PermissionRule):
    """
    基于所有者的权限规则

    如果资源有 owner_id 字段且与当前用户匹配，则允许操作
    """

    def __init__(self, get_owner_func: Optional[Callable[[Any], Optional[int]]] = None):
        """
        初始化所有者权限规则

        Args:
            get_owner_func: 获取资源所有者的函数，接受 resource_id，返回 owner_id
        """
        self._get_owner_func = get_owner_func

    def set_get_owner_func(self, func: Callable[[Any], Optional[int]]) -> None:
        """设置获取所有者的函数"""
        self._get_owner_func = func

    def check(
        self,
        context: Optional[SecurityContext],
        permission: Permission,
        resource_id: Optional[Any] = None,
    ) -> bool:
        """
        检查是否为资源所有者

        Args:
            context: 安全上下文
            permission: 要检查的权限
            resource_id: 资源ID

        Returns:
            True 如果是所有者
        """
        if context is None or context.user_id is None:
            return False

        if resource_id is None:
            return False

        if self._get_owner_func is None:
            # 未设置获取函数时，默认不通过所有者检查
            return False

        owner_id = self._get_owner_func(resource_id)
        return owner_id == context.user_id


class PermissionChecker:
    """
    权限检查器 - 单例模式

    特性：
    - 规则链：按顺序检查多个规则
    - 缓存：缓存权限检查结果
    - 装饰器：提供 require_permission 装饰器
    - 审计：记录权限拒绝事件

    Example:
        >>> checker = PermissionChecker()
        >>> checker.check_permission("room:update_status")
        True
        >>>
        >>> @checker.require_permission("guest:write")
        >>> def create_guest(name: str):
        ...     pass
    """

    _instance: Optional["PermissionChecker"] = None
    _lock = object()  # 使用简单对象锁避免 threading 导入问题

    def __new__(cls) -> "PermissionChecker":
        """单例模式（简化版，单线程）"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._rules: List[PermissionRule] = []
        self._cache: Dict[
            tuple[str, str, Optional[int], Optional[str]], bool
        ] = {}
        self._audit_engine: Optional[AuditEngine] = None

        # 添加默认规则
        self._role_rule = RolePermissionRule()
        self._owner_rule = OwnerPermissionRule()
        self.add_rule(self._role_rule)
        self.add_rule(self._owner_rule)

        self._initialized = True
        logger.debug("PermissionChecker initialized")

    def add_rule(self, rule: PermissionRule) -> None:
        """
        添加权限规则

        Args:
            rule: 要添加的规则
        """
        self._rules.append(rule)
        # 清空缓存，因为规则改变了
        self._cache.clear()

    def set_audit_engine(self, engine: AuditEngine) -> None:
        """设置审计引擎"""
        self._audit_engine = engine

    def set_get_owner_func(self, func: Callable[[Any], Optional[int]]) -> None:
        """设置获取资源所有者的函数"""
        self._owner_rule.set_get_owner_func(func)

    def register_role_permissions(self, role: str, permissions: List[Permission]) -> None:
        """
        注册角色权限（便捷方法）

        Args:
            role: 角色名称
            permissions: 权限列表
        """
        self._role_rule.register_role_permissions(role, permissions)
        self._cache.clear()

    def check_permission(
        self,
        permission: Union[str, Permission],
        context: Optional[SecurityContext] = None,
        resource_id: Optional[Any] = None,
    ) -> bool:
        """
        检查权限

        Args:
            permission: 权限 (字符串或 Permission 对象)
            context: 安全上下文 (None 时使用当前上下文)
            resource_id: 资源ID (用于所有者检查)

        Returns:
            True 如果允许
        """
        # 解析权限
        if isinstance(permission, str):
            try:
                permission = Permission.from_string(permission)
            except ValueError:
                logger.warning(f"Invalid permission string: {permission}")
                return False

        # 获取上下文
        if context is None:
            context = security_context_manager.get_context()

        # 检查缓存
        cache_key = (
            str(permission),
            str(resource_id) if resource_id is not None else None,
            context.username if context else None,
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 按规则链检查
        allowed = False
        for rule in self._rules:
            if rule.check(context, permission, resource_id):
                allowed = True
                break

        # 缓存结果
        self._cache[cache_key] = allowed

        # 记录拒绝
        if not allowed and self._audit_engine:
            self._audit_engine.log(
                operator_id=context.user_id if context else None,
                action=f"permission.denied:{permission}",
                entity_type=permission.resource,
                entity_id=resource_id,
                severity=AuditSeverity.WARNING,
            )

        return allowed

    def require_permission(
        self,
        permission: Union[str, Permission],
        resource_id_param: Optional[str] = None,
    ) -> Callable:
        """
        装饰器: 要求指定权限

        Args:
            permission: 需要的权限
            resource_id_param: 资源ID参数名（用于所有者检查）

        Usage:
            @checker.require_permission("room:update_status")
            def update_room_status(room_id: int, status: str):
                ...

            @checker.require_permission("guest:write", resource_id_param="guest_id")
            def update_guest(guest_id: int, name: str):
                ...
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 获取 resource_id
                resource_id = None
                if resource_id_param:
                    resource_id = kwargs.get(resource_id_param)
                    if resource_id is None and resource_id_param in func.__code__.co_varnames:
                        # 尝试从位置参数获取
                        try:
                            param_index = func.__code__.co_varnames.index(resource_id_param)
                            if param_index < len(args):
                                resource_id = args[param_index]
                        except (ValueError, IndexError):
                            pass

                # 检查权限
                if not self.check_permission(permission, resource_id=resource_id):
                    raise PermissionDenied(
                        f"Permission denied: {permission} "
                        f"(resource_id={resource_id}, user={security_context_manager.get_username()})"
                    )

                return func(*args, **kwargs)

            return wrapper

        return decorator

    def clear_cache(self) -> None:
        """清空权限缓存"""
        self._cache.clear()

    def get_role_permissions(self, role: str) -> Set[Permission]:
        """获取角色的权限集合（便捷方法）"""
        return self._role_rule.get_role_permissions(role)


class PermissionDenied(Exception):
    """权限拒绝异常"""

    pass


# 全局权限检查器实例
permission_checker = PermissionChecker()


# 导出
__all__ = [
    "Permission",
    "PermissionRule",
    "RolePermissionRule",
    "OwnerPermissionRule",
    "PermissionChecker",
    "PermissionDenied",
    "permission_checker",
]
