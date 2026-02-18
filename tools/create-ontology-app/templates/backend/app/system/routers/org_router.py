"""
组织机构 API 路由
前缀: /api/system/departments, /api/system/positions
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.hotel.models.ontology import Employee
from app.security.auth import get_current_user, require_manager
from app.system.schemas import (
    DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentTreeResponse,
    PositionCreate, PositionUpdate, PositionResponse,
)
from app.system.services.org_service import OrgService

dept_router = APIRouter(prefix="/system/departments", tags=["组织机构-部门"])
pos_router = APIRouter(prefix="/system/positions", tags=["组织机构-岗位"])


# =============== Department endpoints ===============

@dept_router.get("", response_model=List[DepartmentResponse])
def list_departments(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取部门列表（扁平）"""
    service = OrgService(db)
    return service.get_departments(is_active=is_active)


@dept_router.get("/tree")
def get_department_tree(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取部门树形结构"""
    service = OrgService(db)
    return service.get_department_tree()


@dept_router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取部门详情"""
    service = OrgService(db)
    dept = service.get_department_by_id(dept_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
    return dept


@dept_router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建部门（需要经理权限）"""
    service = OrgService(db)
    try:
        return service.create_department(
            code=data.code, name=data.name,
            parent_id=data.parent_id, leader_id=data.leader_id,
            sort_order=data.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@dept_router.put("/{dept_id}", response_model=DepartmentResponse)
def update_department(
    dept_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新部门"""
    service = OrgService(db)
    try:
        return service.update_department(dept_id, **data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@dept_router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除部门"""
    service = OrgService(db)
    try:
        service.delete_department(dept_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============== Position endpoints ===============

@pos_router.get("", response_model=List[PositionResponse])
def list_positions(
    department_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取岗位列表"""
    service = OrgService(db)
    return service.get_positions(department_id=department_id, is_active=is_active)


@pos_router.get("/{pos_id}", response_model=PositionResponse)
def get_position(
    pos_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取岗位详情"""
    service = OrgService(db)
    pos = service.get_position_by_id(pos_id)
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")
    return pos


@pos_router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
def create_position(
    data: PositionCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建岗位（需要经理权限）"""
    service = OrgService(db)
    try:
        return service.create_position(
            code=data.code, name=data.name,
            department_id=data.department_id, sort_order=data.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@pos_router.put("/{pos_id}", response_model=PositionResponse)
def update_position(
    pos_id: int,
    data: PositionUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新岗位"""
    service = OrgService(db)
    try:
        return service.update_position(pos_id, **data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@pos_router.delete("/{pos_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(
    pos_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除岗位"""
    service = OrgService(db)
    try:
        service.delete_position(pos_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
