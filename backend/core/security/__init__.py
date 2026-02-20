"""
core/security - 安全模块

包含框架的核心安全组件：
- context: 安全上下文管理器
- checker: 权限检查器 (SPEC-18)
- attribute_acl: 属性级访问控制 (SPEC-19)
- masking: 敏感数据脱敏 (SPEC-20)

使用方式:
    >>> from core.security import SecurityContext, security_context_manager
    >>> from core.security import SecurityLevel, Permission, permission_checker
    >>> from core.security import AttributePermission, attribute_acl, data_masker
    >>> ctx = SecurityContext(user_id=1, username="admin", role="manager",
    ...                      security_level=SecurityLevel.RESTRICTED)
    >>> security_context_manager.set_context(ctx)
    >>> permission_checker.check_permission("room:update_status")
    >>> attribute_acl.can_read("Guest", "phone", ctx)
    >>> data_masker.mask("phone", "13800138000", ctx)
"""

# 安全上下文
from core.security.context import (
    SecurityContext,
    SecurityContextManager,
    security_context_manager,
)

# 权限检查器
from core.security.checker import (
    Permission,
    PermissionRule,
    RolePermissionRule,
    OwnerPermissionRule,
    PermissionChecker,
    PermissionDenied,
    permission_checker,
)

# 属性级访问控制
from core.security.attribute_acl import (
    AttributePermission,
    AttributeAccessDenied,
    AttributeACL,
    attribute_acl,
)

# 敏感数据脱敏
from core.security.masking import (
    MaskingStrategy,
    MaskingRule,
    DataMasker,
    data_masker,
)

# 权限提供者接口
from core.security.permission import (
    IPermissionProvider,
    PermissionProviderRegistry,
    permission_provider_registry,
)

# 数据作用域
from core.security.data_scope import (
    DataScopeType,
    DataScopeLevel,
    DataScopeContext,
    IDataScopeResolver,
)

# 安全级别（从 core.ontology.security 重新导出）
from core.ontology.security import SecurityLevel

__all__ = [
    # 安全上下文
    "SecurityContext",
    "SecurityContextManager",
    "security_context_manager",
    # 权限检查器
    "Permission",
    "PermissionRule",
    "RolePermissionRule",
    "OwnerPermissionRule",
    "PermissionChecker",
    "PermissionDenied",
    "permission_checker",
    # 属性级访问控制
    "AttributePermission",
    "AttributeAccessDenied",
    "AttributeACL",
    "attribute_acl",
    # 敏感数据脱敏
    "MaskingStrategy",
    "MaskingRule",
    "DataMasker",
    "data_masker",
    # 权限提供者
    "IPermissionProvider",
    "PermissionProviderRegistry",
    "permission_provider_registry",
    # 数据作用域
    "DataScopeType",
    "DataScopeLevel",
    "DataScopeContext",
    "IDataScopeResolver",
    # 安全级别
    "SecurityLevel",
]
