"""
数据字典 API 路由
前缀: /api/system/dicts
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ontology import Employee
from app.security.auth import get_current_user, require_manager
from app.system.schemas import (
    DictTypeCreate, DictTypeUpdate, DictTypeResponse,
    DictItemCreate, DictItemUpdate, DictItemResponse,
)
from app.system.services.dict_service import DictService

router = APIRouter(prefix="/system/dicts", tags=["数据字典"])


# ---- DictType endpoints ----

@router.get("", response_model=List[DictTypeResponse])
def list_dict_types(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取字典类型列表"""
    service = DictService(db)
    types = service.get_dict_types(is_active=is_active)
    result = []
    for t in types:
        resp = DictTypeResponse.model_validate(t)
        resp.item_count = len(t.items) if t.items else 0
        result.append(resp)
    return result


@router.get("/{type_id}", response_model=DictTypeResponse)
def get_dict_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取字典类型详情"""
    service = DictService(db)
    dict_type = service.get_dict_type_by_id(type_id)
    if not dict_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字典类型不存在")
    resp = DictTypeResponse.model_validate(dict_type)
    resp.item_count = len(dict_type.items) if dict_type.items else 0
    return resp


@router.post("", response_model=DictTypeResponse, status_code=status.HTTP_201_CREATED)
def create_dict_type(
    data: DictTypeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建字典类型（需要经理权限）"""
    service = DictService(db)
    try:
        dict_type = service.create_dict_type(
            code=data.code, name=data.name,
            description=data.description, is_system=data.is_system,
        )
        return DictTypeResponse.model_validate(dict_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{type_id}", response_model=DictTypeResponse)
def update_dict_type(
    type_id: int,
    data: DictTypeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新字典类型（需要经理权限）"""
    service = DictService(db)
    try:
        dict_type = service.update_dict_type(type_id, **data.model_dump(exclude_unset=True))
        resp = DictTypeResponse.model_validate(dict_type)
        resp.item_count = len(dict_type.items) if dict_type.items else 0
        return resp
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{type_id}")
def delete_dict_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除字典类型（需要经理权限，系统内置不可删除）"""
    service = DictService(db)
    try:
        service.delete_dict_type(type_id)
        return {"success": True, "message": "字典类型已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---- DictItem endpoints ----

@router.get("/{type_id}/items", response_model=List[DictItemResponse])
def list_dict_items(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取字典项列表"""
    service = DictService(db)
    items = service.get_items_by_type_id(type_id)
    return [DictItemResponse.model_validate(item) for item in items]


@router.get("/code/{type_code}/items", response_model=List[DictItemResponse])
def list_dict_items_by_code(
    type_code: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """按字典类型编码获取字典项列表"""
    service = DictService(db)
    try:
        items = service.get_items_by_type_code(type_code)
        return [DictItemResponse.model_validate(item) for item in items]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{type_id}/items", response_model=DictItemResponse, status_code=status.HTTP_201_CREATED)
def create_dict_item(
    type_id: int,
    data: DictItemCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建字典项（需要经理权限）"""
    service = DictService(db)
    try:
        item = service.create_dict_item(
            dict_type_id=type_id, label=data.label, value=data.value,
            color=data.color, extra=data.extra,
            sort_order=data.sort_order, is_default=data.is_default,
        )
        return DictItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/items/{item_id}", response_model=DictItemResponse)
def update_dict_item(
    item_id: int,
    data: DictItemUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新字典项（需要经理权限）"""
    service = DictService(db)
    try:
        item = service.update_dict_item(item_id, **data.model_dump(exclude_unset=True))
        return DictItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/items/{item_id}")
def delete_dict_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除字典项（需要经理权限）"""
    service = DictService(db)
    try:
        service.delete_dict_item(item_id)
        return {"success": True, "message": "字典项已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
