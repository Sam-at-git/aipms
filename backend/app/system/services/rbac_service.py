"""
RBAC Service — 角色管理 + 权限管理
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from app.system.models.rbac import SysRole, SysPermission, SysRolePermission, SysUserRole


class RoleService:
    """角色管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_roles(self, include_inactive: bool = False) -> List[SysRole]:
        q = self.db.query(SysRole)
        if not include_inactive:
            q = q.filter(SysRole.is_active == True)
        return q.order_by(SysRole.sort_order, SysRole.id).all()

    def get_role_by_id(self, role_id: int) -> Optional[SysRole]:
        return self.db.query(SysRole).filter(SysRole.id == role_id).first()

    def get_role_by_code(self, code: str) -> Optional[SysRole]:
        return self.db.query(SysRole).filter(SysRole.code == code).first()

    def create_role(self, code: str, name: str, description: str = "",
                    data_scope: str = "ALL", sort_order: int = 0) -> SysRole:
        existing = self.get_role_by_code(code)
        if existing:
            raise ValueError(f"角色编码 '{code}' 已存在")

        role = SysRole(
            code=code, name=name, description=description,
            data_scope=data_scope, sort_order=sort_order
        )
        self.db.add(role)
        self.db.flush()
        return role

    def update_role(self, role_id: int, **kwargs) -> SysRole:
        role = self.get_role_by_id(role_id)
        if not role:
            raise ValueError(f"角色 ID {role_id} 不存在")

        for key, value in kwargs.items():
            if key == "code" and value != role.code:
                existing = self.get_role_by_code(value)
                if existing:
                    raise ValueError(f"角色编码 '{value}' 已存在")
            if hasattr(role, key):
                setattr(role, key, value)

        self.db.flush()
        return role

    def delete_role(self, role_id: int) -> None:
        role = self.get_role_by_id(role_id)
        if not role:
            raise ValueError(f"角色 ID {role_id} 不存在")
        if role.is_system:
            raise ValueError(f"系统内置角色 '{role.name}' 不可删除")

        # Delete role-permission and user-role mappings
        self.db.query(SysRolePermission).filter(SysRolePermission.role_id == role_id).delete()
        self.db.query(SysUserRole).filter(SysUserRole.role_id == role_id).delete()
        self.db.delete(role)
        self.db.flush()

    def get_role_permissions(self, role_id: int) -> List[SysPermission]:
        role = self.get_role_by_id(role_id)
        if not role:
            return []
        return role.permissions

    def assign_permissions(self, role_id: int, permission_ids: List[int]) -> None:
        """Replace all permissions for a role"""
        role = self.get_role_by_id(role_id)
        if not role:
            raise ValueError(f"角色 ID {role_id} 不存在")

        # Clear existing
        self.db.query(SysRolePermission).filter(SysRolePermission.role_id == role_id).delete()

        # Add new
        for pid in permission_ids:
            self.db.add(SysRolePermission(role_id=role_id, permission_id=pid))

        self.db.flush()

    def add_permission(self, role_id: int, permission_id: int) -> None:
        existing = self.db.query(SysRolePermission).filter(
            SysRolePermission.role_id == role_id,
            SysRolePermission.permission_id == permission_id
        ).first()
        if not existing:
            self.db.add(SysRolePermission(role_id=role_id, permission_id=permission_id))
            self.db.flush()

    def remove_permission(self, role_id: int, permission_id: int) -> None:
        self.db.query(SysRolePermission).filter(
            SysRolePermission.role_id == role_id,
            SysRolePermission.permission_id == permission_id
        ).delete()
        self.db.flush()


class PermissionService:
    """权限管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_permissions(self, perm_type: Optional[str] = None) -> List[SysPermission]:
        q = self.db.query(SysPermission).filter(SysPermission.is_active == True)
        if perm_type:
            q = q.filter(SysPermission.type == perm_type)
        return q.order_by(SysPermission.sort_order, SysPermission.id).all()

    def get_permission_by_id(self, perm_id: int) -> Optional[SysPermission]:
        return self.db.query(SysPermission).filter(SysPermission.id == perm_id).first()

    def get_permission_by_code(self, code: str) -> Optional[SysPermission]:
        return self.db.query(SysPermission).filter(SysPermission.code == code).first()

    def create_permission(self, code: str, name: str, perm_type: str = "api",
                          resource: str = "", action: str = "",
                          parent_id: Optional[int] = None,
                          sort_order: int = 0) -> SysPermission:
        existing = self.get_permission_by_code(code)
        if existing:
            raise ValueError(f"权限编码 '{code}' 已存在")

        perm = SysPermission(
            code=code, name=name, type=perm_type,
            resource=resource, action=action,
            parent_id=parent_id, sort_order=sort_order
        )
        self.db.add(perm)
        self.db.flush()
        return perm

    def update_permission(self, perm_id: int, **kwargs) -> SysPermission:
        perm = self.get_permission_by_id(perm_id)
        if not perm:
            raise ValueError(f"权限 ID {perm_id} 不存在")

        for key, value in kwargs.items():
            if key == "code" and value != perm.code:
                existing = self.get_permission_by_code(value)
                if existing:
                    raise ValueError(f"权限编码 '{value}' 已存在")
            if key == "type":
                key = "type"  # Map perm_type to type column
            if hasattr(perm, key):
                setattr(perm, key, value)

        self.db.flush()
        return perm

    def delete_permission(self, perm_id: int) -> None:
        perm = self.get_permission_by_id(perm_id)
        if not perm:
            raise ValueError(f"权限 ID {perm_id} 不存在")

        # Check if assigned to any role
        role_count = self.db.query(SysRolePermission).filter(
            SysRolePermission.permission_id == perm_id
        ).count()
        if role_count > 0:
            raise ValueError(f"权限 '{perm.name}' 仍被 {role_count} 个角色使用，请先解除关联")

        self.db.delete(perm)
        self.db.flush()

    def get_permission_tree(self) -> List[Dict]:
        """Build hierarchical permission tree"""
        all_perms = self.get_permissions()
        perm_map = {p.id: {
            "id": p.id, "code": p.code, "name": p.name,
            "type": p.type, "resource": p.resource, "action": p.action,
            "parent_id": p.parent_id, "children": []
        } for p in all_perms}

        tree = []
        for item in perm_map.values():
            if item["parent_id"] and item["parent_id"] in perm_map:
                perm_map[item["parent_id"]]["children"].append(item)
            else:
                tree.append(item)

        return tree

    # ===== User-Role Operations =====

    def get_user_roles(self, user_id: int) -> List[SysRole]:
        user_roles = self.db.query(SysUserRole).filter(SysUserRole.user_id == user_id).all()
        role_ids = [ur.role_id for ur in user_roles]
        if not role_ids:
            return []
        return self.db.query(SysRole).filter(
            SysRole.id.in_(role_ids),
            SysRole.is_active == True
        ).all()

    def get_user_permissions(self, user_id: int) -> Set[str]:
        """Get all permission codes for a user (aggregated from all roles)"""
        roles = self.get_user_roles(user_id)
        permissions: Set[str] = set()
        for role in roles:
            for perm in role.permissions:
                if perm.is_active:
                    permissions.add(perm.code)
        return permissions

    def assign_user_roles(self, user_id: int, role_ids: List[int]) -> None:
        """Replace all roles for a user"""
        self.db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
        for rid in role_ids:
            self.db.add(SysUserRole(user_id=user_id, role_id=rid))
        self.db.flush()

    def add_user_role(self, user_id: int, role_id: int) -> None:
        existing = self.db.query(SysUserRole).filter(
            SysUserRole.user_id == user_id,
            SysUserRole.role_id == role_id
        ).first()
        if not existing:
            self.db.add(SysUserRole(user_id=user_id, role_id=role_id))
            self.db.flush()

    def remove_user_role(self, user_id: int, role_id: int) -> None:
        self.db.query(SysUserRole).filter(
            SysUserRole.user_id == user_id,
            SysUserRole.role_id == role_id
        ).delete()
        self.db.flush()
