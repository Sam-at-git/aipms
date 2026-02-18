"""
RBACPermissionProvider — IPermissionProvider 的 app 层实现

通过 PermissionService 查询数据库，带内存缓存。
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from core.security.permission import IPermissionProvider
from app.system.services.rbac_service import PermissionService


class RBACPermissionProvider(IPermissionProvider):
    """基于数据库的 RBAC 权限提供者"""

    def __init__(self, db_session_factory):
        """
        Args:
            db_session_factory: callable that returns a new DB session
        """
        self._db_session_factory = db_session_factory
        self._permission_cache: Dict[int, Set[str]] = {}
        self._role_cache: Dict[int, List[str]] = {}

    def has_permission(self, user_id: int, permission_code: str) -> bool:
        permissions = self.get_user_permissions(user_id)
        return permission_code in permissions

    def get_user_permissions(self, user_id: int) -> Set[str]:
        if user_id in self._permission_cache:
            return self._permission_cache[user_id]

        db = self._db_session_factory()
        try:
            svc = PermissionService(db)
            permissions = svc.get_user_permissions(user_id)
            self._permission_cache[user_id] = permissions
            return permissions
        finally:
            db.close()

    def get_user_roles(self, user_id: int) -> List[str]:
        if user_id in self._role_cache:
            return self._role_cache[user_id]

        db = self._db_session_factory()
        try:
            svc = PermissionService(db)
            roles = svc.get_user_roles(user_id)
            role_codes = [r.code for r in roles]
            self._role_cache[user_id] = role_codes
            return role_codes
        finally:
            db.close()

    def invalidate_user(self, user_id: int) -> None:
        """Invalidate cache for a specific user (call after role/permission change)"""
        self._permission_cache.pop(user_id, None)
        self._role_cache.pop(user_id, None)

    def invalidate_all(self) -> None:
        """Invalidate all caches (call after bulk role/permission changes)"""
        self._permission_cache.clear()
        self._role_cache.clear()
