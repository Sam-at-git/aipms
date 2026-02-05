"""
房间管理路由

SPEC-57: 适配使用 core/services/room_service (RoomServiceV2)
保持向后兼容，可以选择使用新的领域层服务
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, RoomStatus
from app.models.schemas import (
    RoomTypeCreate, RoomTypeUpdate, RoomTypeResponse,
    RoomCreate, RoomUpdate, RoomResponse, RoomStatusUpdate
)
from app.services.room_service import RoomService

# 导入新的 RoomServiceV2 (SPEC-57)
try:
    from core.services.room_service import RoomServiceV2, get_room_service_v2
    CORE_ROOM_SERVICE_AVAILABLE = True
except ImportError:
    CORE_ROOM_SERVICE_AVAILABLE = False

from app.security.auth import get_current_user, require_manager, require_receptionist_or_manager

router = APIRouter(prefix="/rooms", tags=["房间管理"])


# 服务工厂函数 - 可以选择使用 RoomServiceV2
def get_room_service(db: Session):
    """获取房间服务实例"""
    if CORE_ROOM_SERVICE_AVAILABLE:
        # 使用新的 RoomServiceV2 (core/services/room_service.py)
        return get_room_service_v2(db)
    else:
        # 回退到原有 RoomService
        return RoomService(db)


# ============== 房型管理 ==============

@router.get("/types", response_model=List[RoomTypeResponse])
def list_room_types(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取所有房型"""
    service = get_room_service(db)
    room_types = service.get_room_types()
    result = []
    for rt in room_types:
        data = service.get_room_type_with_count(rt.id)
        result.append(RoomTypeResponse(**data))
    return result


@router.post("/types", response_model=RoomTypeResponse)
def create_room_type(
    data: RoomTypeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """创建房型"""
    service = get_room_service(db)
    try:
        room_type = service.create_room_type(data)
        rt_data = service.get_room_type_with_count(room_type.id)
        return RoomTypeResponse(**rt_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/types/{room_type_id}", response_model=RoomTypeResponse)
def update_room_type(
    room_type_id: int,
    data: RoomTypeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """更新房型"""
    service = get_room_service(db)
    try:
        room_type = service.update_room_type(room_type_id, data)
        rt_data = service.get_room_type_with_count(room_type.id)
        return RoomTypeResponse(**rt_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/types/{room_type_id}")
def delete_room_type(
    room_type_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """删除房型"""
    service = get_room_service(db)
    try:
        service.delete_room_type(room_type_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============== 房间管理 ==============

@router.get("", response_model=List[RoomResponse])
def list_rooms(
    floor: Optional[int] = None,
    room_type_id: Optional[int] = None,
    status: Optional[RoomStatus] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取房间列表"""
    service = get_room_service(db)
    rooms = service.get_rooms(floor, room_type_id, status, is_active)
    result = []
    for room in rooms:
        room_data = service.get_room_with_guest(room.id)
        result.append(RoomResponse(**room_data))
    return result


@router.get("/status-summary")
def get_room_status_summary(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取房态统计"""
    service = get_room_service(db)
    return service.get_room_status_summary()


@router.get("/available")
def get_available_rooms(
    check_in_date: date,
    check_out_date: date,
    room_type_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取可用房间"""
    service = get_room_service(db)
    rooms = service.get_available_rooms(check_in_date, check_out_date, room_type_id)
    return [service.get_room_with_guest(r.id) for r in rooms]


@router.get("/availability")
def get_room_availability(
    check_in_date: date,
    check_out_date: date,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """按房型统计可用房间数"""
    service = get_room_service(db)
    return service.get_availability_by_room_type(check_in_date, check_out_date)


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取房间详情"""
    service = get_room_service(db)
    room_data = service.get_room_with_guest(room_id)
    if not room_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
    return RoomResponse(**room_data)


@router.post("", response_model=RoomResponse)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """创建房间"""
    service = get_room_service(db)
    try:
        room = service.create_room(data)
        room_data = service.get_room_with_guest(room.id)
        return RoomResponse(**room_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """更新房间"""
    service = get_room_service(db)
    try:
        room = service.update_room(room_id, data)
        room_data = service.get_room_with_guest(room.id)
        return RoomResponse(**room_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{room_id}/status")
def update_room_status(
    room_id: int,
    data: RoomStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """更新房间状态"""
    service = get_room_service(db)
    try:
        room = service.update_room_status(room_id, data.status)
        return {"message": "状态更新成功", "status": room.status}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """删除房间"""
    service = get_room_service(db)
    try:
        service.delete_room(room_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
