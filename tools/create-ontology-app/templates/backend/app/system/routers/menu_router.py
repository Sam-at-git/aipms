"""
菜单管理 API 路由
前缀: /api/system/menus
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import get_current_user, require_manager
from app.system.schemas import MenuCreate, MenuUpdate, MenuResponse
from app.system.services.menu_service import MenuService

router = APIRouter(prefix="/system/menus", tags=["菜单管理"])


@router.get("", response_model=List[MenuResponse])
def list_menus(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取全部菜单列表（扁平）"""
    service = MenuService(db)
    return [MenuResponse.model_validate(m) for m in service.get_menus(include_inactive=True)]


@router.get("/tree")
def get_menu_tree(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取完整菜单树（管理用）"""
    service = MenuService(db)
    return service.get_menu_tree(include_buttons=True)


@router.get("/user")
def get_user_menus(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取当前用户可见菜单树"""
    service = MenuService(db)
    is_sysadmin = current_user.role == EmployeeRole.SYSADMIN

    # Get user permissions
    from core.security.permission import permission_provider_registry
    if permission_provider_registry.has_provider():
        user_perms = permission_provider_registry.get_user_permissions(current_user.id)
    else:
        user_perms = set()

    return service.get_user_menu_tree(user_perms, is_sysadmin=is_sysadmin)


@router.post("", response_model=MenuResponse, status_code=201)
def create_menu(
    data: MenuCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建菜单"""
    service = MenuService(db)
    try:
        menu = service.create_menu(
            code=data.code, name=data.name, menu_type=data.menu_type,
            parent_id=data.parent_id, path=data.path, icon=data.icon,
            component=data.component, permission_code=data.permission_code,
            is_visible=data.is_visible, sort_order=data.sort_order,
        )
        db.commit()
        return MenuResponse.model_validate(menu)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: int,
    data: MenuUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新菜单"""
    service = MenuService(db)
    try:
        updates = data.model_dump(exclude_unset=True)
        menu = service.update_menu(menu_id, **updates)
        db.commit()
        return MenuResponse.model_validate(menu)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{menu_id}", status_code=204)
def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除菜单"""
    service = MenuService(db)
    try:
        service.delete_menu(menu_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
