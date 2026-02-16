"""
core/security/attribute_acl.py

属性级访问控制 - 在实体属性级别进行权限控制
与 ObjectProxy 集成，在属性访问时自动检查权限
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging
import threading

from core.security.context import SecurityContext, security_context_manager
from core.ontology.security import SecurityLevel
from core.engine.audit import AuditEngine, audit_engine, AuditSeverity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttributePermission:
    """
    属性权限定义

    Attributes:
        entity_type: 实体类型 (如 "Room", "Guest")
        attribute: 属性名 (如 "phone", "id_card")
        security_level: 需要的安全级别
        allow_read: 是否允许读取（满足级别条件后）
        allow_write: 是否允许写入（满足级别条件后）
    """

    entity_type: str
    attribute: str
    security_level: SecurityLevel
    allow_read: bool = True
    allow_write: bool = False

    def __repr__(self) -> str:
        return (
            f"AttributePermission({self.entity_type}.{self.attribute}, "
            f"level={self.security_level.name})"
        )


class AttributeAccessDenied(Exception):
    """属性访问拒绝异常"""

    def __init__(self, message: str, entity_type: str, attribute: str, operation: str):
        self.entity_type = entity_type
        self.attribute = attribute
        self.operation = operation
        super().__init__(message)


class AttributeACL:
    """
    属性级访问控制 - 单例模式

    特性：
    - 属性级权限控制
    - 安全级别检查
    - 自动过滤敏感属性
    - 审计日志集成

    Example:
        >>> acl = AttributeACL()
        >>> acl.register_attribute(AttributePermission(
        ...     "Guest", "phone", SecurityLevel.CONFIDENTIAL
        ... ))
        >>> acl.can_read("Guest", "phone", context)
        False  # 如果 context.security_level < CONFIDENTIAL
    """

    _instance: Optional["AttributeACL"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AttributeACL":
        """单例模式（double-checked locking）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._rules: Dict[str, Dict[str, AttributePermission]] = {}
        self._audit_engine: Optional[AuditEngine] = None
        self._initialized = True

        logger.debug("AttributeACL initialized")

    def register_domain_permissions(self, permissions: list) -> None:
        """
        Register domain-specific attribute permissions.
        Called by app layer (e.g., HotelDomainAdapter) at startup.

        Args:
            permissions: List of AttributePermission objects
        """
        for attr in permissions:
            self.register_attribute(attr)

    def set_audit_engine(self, engine: AuditEngine) -> None:
        """设置审计引擎"""
        self._audit_engine = engine

    def register_attribute(self, permission: AttributePermission) -> None:
        """
        注册属性权限

        Args:
            permission: 属性权限定义
        """
        if permission.entity_type not in self._rules:
            self._rules[permission.entity_type] = {}

        self._rules[permission.entity_type][permission.attribute] = permission
        logger.debug(f"Registered attribute permission: {permission}")

    def get_permission(
        self, entity_type: str, attribute: str
    ) -> Optional[AttributePermission]:
        """
        获取属性权限定义

        Args:
            entity_type: 实体类型
            attribute: 属性名

        Returns:
            属性权限定义，如果未注册则返回 None
        """
        return self._rules.get(entity_type, {}).get(attribute)

    def has_rule(self, entity_type: str, attribute: str) -> bool:
        """检查是否有属性规则"""
        return entity_type in self._rules and attribute in self._rules[entity_type]

    def can_read(
        self,
        entity_type: str,
        attribute: str,
        context: Optional[SecurityContext] = None,
    ) -> bool:
        """
        检查是否可以读取属性

        Args:
            entity_type: 实体类型
            attribute: 属性名
            context: 安全上下文 (None 时使用当前上下文)

        Returns:
            True 如果允许读取
        """
        perm = self.get_permission(entity_type, attribute)

        # 没有规则，默认允许读取
        if perm is None:
            return True

        # 检查 allow_read 标志
        if not perm.allow_read:
            self._log_denied_access(context, entity_type, attribute, "read")
            return False

        # 检查安全级别
        if context is None:
            context = security_context_manager.get_context()

        if context is None:
            # 没有上下文，默认不允许（除非是 PUBLIC）
            if perm.security_level == SecurityLevel.PUBLIC:
                return True
            return False

        if not context.has_clearance(perm.security_level):
            self._log_denied_access(context, entity_type, attribute, "read")
            return False

        return True

    def can_write(
        self,
        entity_type: str,
        attribute: str,
        context: Optional[SecurityContext] = None,
    ) -> bool:
        """
        检查是否可以写入属性

        Args:
            entity_type: 实体类型
            attribute: 属性名
            context: 安全上下文 (None 时使用当前上下文)

        Returns:
            True 如果允许写入
        """
        perm = self.get_permission(entity_type, attribute)

        # 没有规则，默认允许写入
        if perm is None:
            return True

        # 检查 allow_write 标志
        if not perm.allow_write:
            self._log_denied_access(context, entity_type, attribute, "write")
            return False

        # 检查安全级别
        if context is None:
            context = security_context_manager.get_context()

        if context is None:
            # 没有上下文时，PUBLIC 级别允许
            return perm.security_level == SecurityLevel.PUBLIC

        if not context.has_clearance(perm.security_level):
            self._log_denied_access(context, entity_type, attribute, "write")
            return False

        return True

    def filter_attributes(
        self,
        entity_type: str,
        attributes: Dict[str, Any],
        context: Optional[SecurityContext] = None,
    ) -> Dict[str, Any]:
        """
        过滤属性，只返回允许读取的

        Args:
            entity_type: 实体类型
            attributes: 属性字典
            context: 安全上下文

        Returns:
            过滤后的属性字典
        """
        filtered = {}
        for attr_name, attr_value in attributes.items():
            if self.can_read(entity_type, attr_name, context):
                filtered[attr_name] = attr_value
        return filtered

    def _log_denied_access(
        self,
        context: Optional[SecurityContext],
        entity_type: str,
        attribute: str,
        operation: str,
    ) -> None:
        """记录拒绝访问"""
        if self._audit_engine and context:
            self._audit_engine.log(
                operator_id=context.user_id,
                action=f"attribute.{operation}.denied",
                entity_type=entity_type,
                entity_id=None,
                old_value=None,
                new_value=None,
                severity=AuditSeverity.WARNING,
                extra={"attribute": attribute},
            )

    def get_entity_attributes(self, entity_type: str) -> List[str]:
        """获取实体所有受控属性名"""
        return list(self._rules.get(entity_type, {}).keys())


# 全局属性 ACL 实例
attribute_acl = AttributeACL()


# 导出
__all__ = [
    "AttributePermission",
    "AttributeAccessDenied",
    "AttributeACL",
    "attribute_acl",
]
