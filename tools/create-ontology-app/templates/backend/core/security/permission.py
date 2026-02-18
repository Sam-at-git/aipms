"""
core/security/permission.py — 权限提供者接口

定义 IPermissionProvider 抽象接口，app 层实现此接口提供动态 RBAC。
通过 PermissionProviderRegistry 注册激活的实现。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set
import threading


class IPermissionProvider(ABC):
    """权限提供者接口 — app 层实现此接口以对接动态 RBAC"""

    @abstractmethod
    def has_permission(self, user_id: int, permission_code: str) -> bool:
        """检查用户是否拥有指定权限码"""

    @abstractmethod
    def get_user_permissions(self, user_id: int) -> Set[str]:
        """获取用户所有权限码集合"""

    @abstractmethod
    def get_user_roles(self, user_id: int) -> List[str]:
        """获取用户所有角色编码列表"""


class PermissionProviderRegistry:
    """权限提供者注册表 — 单例模式

    app 层在 lifespan 中注册实现：
        registry = PermissionProviderRegistry()
        registry.set_provider(RBACPermissionProvider(db))
    """

    _instance: Optional["PermissionProviderRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "PermissionProviderRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._provider: Optional[IPermissionProvider] = None
        return cls._instance

    def set_provider(self, provider: IPermissionProvider) -> None:
        """注册权限提供者实现"""
        self._provider = provider

    def get_provider(self) -> Optional[IPermissionProvider]:
        """获取当前注册的权限提供者"""
        return self._provider

    def has_provider(self) -> bool:
        """是否已注册权限提供者"""
        return self._provider is not None

    def has_permission(self, user_id: int, permission_code: str) -> bool:
        """便捷方法：检查权限（未注册 provider 时返回 False）"""
        if self._provider is None:
            return False
        return self._provider.has_permission(user_id, permission_code)

    def get_user_permissions(self, user_id: int) -> Set[str]:
        """便捷方法：获取用户权限集合（未注册 provider 时返回空集）"""
        if self._provider is None:
            return set()
        return self._provider.get_user_permissions(user_id)

    def get_user_roles(self, user_id: int) -> List[str]:
        """便捷方法：获取用户角色列表（未注册 provider 时返回空列表）"""
        if self._provider is None:
            return []
        return self._provider.get_user_roles(user_id)

    def clear(self) -> None:
        """清除注册（用于测试）"""
        self._provider = None


# 模块级单例
permission_provider_registry = PermissionProviderRegistry()

__all__ = [
    "IPermissionProvider",
    "PermissionProviderRegistry",
    "permission_provider_registry",
]
