"""
RBAC API 路由 — 角色管理 + 权限管理 + 用户角色分配
前缀: /api/system/roles, /api/system/permissions, /api/system/users
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ontology import Employee
from app.security.auth import get_current_user, require_manager
from app.system.schemas import (
    RoleCreate, RoleUpdate, RoleResponse, RoleDetailResponse,
    PermissionCreate, PermissionUpdate, PermissionResponse,
    UserRoleAssign, UserRoleResponse,
)
from app.system.services.rbac_service import RoleService, PermissionService


# ========== Role Router ==========

role_router = APIRouter(prefix="/system/roles", tags=["角色管理"])


@role_router.get("", response_model=List[RoleResponse])
def list_roles(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取角色列表"""
    service = RoleService(db)
    roles = service.get_roles(include_inactive=include_inactive)
    result = []
    for r in roles:
        resp = RoleResponse.model_validate(r)
        resp.permission_count = len(r.permissions) if r.permissions else 0
        result.append(resp)
    return result


@role_router.get("/{role_id}", response_model=RoleDetailResponse)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取角色详情（含权限列表）"""
    service = RoleService(db)
    role = service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    resp = RoleDetailResponse.model_validate(role)
    resp.permission_count = len(role.permissions) if role.permissions else 0
    resp.permissions = [PermissionResponse.model_validate(p) for p in role.permissions]
    return resp


@role_router.post("", response_model=RoleResponse, status_code=201)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建角色"""
    service = RoleService(db)
    try:
        role = service.create_role(
            code=data.code, name=data.name,
            description=data.description,
            data_scope=data.data_scope,
            sort_order=data.sort_order,
        )
        db.commit()
        return RoleResponse.model_validate(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@role_router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新角色"""
    service = RoleService(db)
    try:
        updates = data.model_dump(exclude_unset=True)
        role = service.update_role(role_id, **updates)
        db.commit()
        resp = RoleResponse.model_validate(role)
        resp.permission_count = len(role.permissions) if role.permissions else 0
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@role_router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除角色"""
    service = RoleService(db)
    try:
        service.delete_role(role_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@role_router.put("/{role_id}/permissions")
def assign_role_permissions(
    role_id: int,
    permission_ids: List[int],
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """批量设置角色权限"""
    service = RoleService(db)
    try:
        service.assign_permissions(role_id, permission_ids)
        db.commit()
        return {"message": "权限分配成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Permission Router ==========

permission_router = APIRouter(prefix="/system/permissions", tags=["权限管理"])


@permission_router.get("", response_model=List[PermissionResponse])
def list_permissions(
    perm_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取权限列表"""
    service = PermissionService(db)
    return [PermissionResponse.model_validate(p) for p in service.get_permissions(perm_type)]


@permission_router.get("/tree")
def get_permission_tree(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取权限树"""
    service = PermissionService(db)
    return service.get_permission_tree()


@permission_router.post("", response_model=PermissionResponse, status_code=201)
def create_permission(
    data: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建权限"""
    service = PermissionService(db)
    try:
        perm = service.create_permission(
            code=data.code, name=data.name,
            perm_type=data.type, resource=data.resource,
            action=data.action, parent_id=data.parent_id,
            sort_order=data.sort_order,
        )
        db.commit()
        return PermissionResponse.model_validate(perm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@permission_router.put("/{perm_id}", response_model=PermissionResponse)
def update_permission(
    perm_id: int,
    data: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新权限"""
    service = PermissionService(db)
    try:
        updates = data.model_dump(exclude_unset=True)
        perm = service.update_permission(perm_id, **updates)
        db.commit()
        return PermissionResponse.model_validate(perm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@permission_router.delete("/{perm_id}", status_code=204)
def delete_permission(
    perm_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除权限"""
    service = PermissionService(db)
    try:
        service.delete_permission(perm_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== User-Role Router ==========

user_role_router = APIRouter(prefix="/system/users", tags=["用户角色"])


@user_role_router.get("/{user_id}/roles", response_model=UserRoleResponse)
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取用户角色"""
    service = PermissionService(db)
    roles = service.get_user_roles(user_id)
    return UserRoleResponse(
        user_id=user_id,
        roles=[RoleResponse.model_validate(r) for r in roles],
    )


@user_role_router.put("/{user_id}/roles")
def assign_user_roles(
    user_id: int,
    data: UserRoleAssign,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """设置用户角色"""
    service = PermissionService(db)
    service.assign_user_roles(user_id, data.role_ids)
    db.commit()

    # Invalidate RBAC cache for this user
    from core.security.permission import permission_provider_registry
    if permission_provider_registry.has_provider():
        provider = permission_provider_registry._provider
        if hasattr(provider, 'invalidate_user'):
            provider.invalidate_user(user_id)

    return {"message": "角色分配成功"}
