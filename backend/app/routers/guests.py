"""
客人管理路由 (包含CRM功能)

SPEC-58: 适配使用 core/services/guest_service (GuestServiceV2)
保持向后兼容，可以选择使用新的领域层服务
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, GuestTier
from app.models.schemas import GuestCreate, GuestUpdate, GuestResponse, GuestDetailResponse
from app.services.guest_service import GuestService

# 导入新的 GuestServiceV2 (SPEC-58)
try:
    from app.services.guest_service_v2 import GuestServiceV2
    CORE_GUEST_SERVICE_AVAILABLE = True
except ImportError:
    CORE_GUEST_SERVICE_AVAILABLE = False

from app.security.auth import get_current_user, require_manager, require_receptionist_or_manager

router = APIRouter(prefix="/guests", tags=["客人管理"])


# 服务工厂函数 - 可以选择使用 GuestServiceV2
def get_guest_service(db: Session):
    """获取客人服务实例"""
    if CORE_GUEST_SERVICE_AVAILABLE:
        # 使用新的 GuestServiceV2 (core/services/guest_service.py)
        return GuestServiceV2(db)
    else:
        # 回退到原有 GuestService
        return GuestService(db)


@router.get("/", response_model=List[GuestResponse])
def list_guests(
    search: Optional[str] = None,
    tier: Optional[GuestTier] = None,
    is_blacklisted: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取客人列表"""
    service = get_guest_service(db)
    guests = service.get_guests(search=search, tier=tier, is_blacklisted=is_blacklisted, limit=limit)

    return [
        GuestResponse(
            id=g.id,
            name=g.name,
            id_type=g.id_type,
            id_number=g.id_number,
            phone=g.phone,
            email=g.email,
            preferences=g.preferences,
            tier=g.tier,
            total_stays=g.total_stays or 0,
            total_amount=g.total_amount or 0,
            is_blacklisted=g.is_blacklisted or False,
            blacklist_reason=g.blacklist_reason,
            notes=g.notes,
            created_at=g.created_at,
            updated_at=g.updated_at
        )
        for g in guests
    ]


@router.get("/{guest_id}", response_model=GuestDetailResponse)
def get_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取客人详情"""
    service = get_guest_service(db)
    guest = service.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客人不存在")

    stats = service.get_guest_stats(guest_id)

    return GuestDetailResponse(
        id=guest.id,
        name=guest.name,
        id_type=guest.id_type,
        id_number=guest.id_number,
        phone=guest.phone,
        email=guest.email,
        preferences=guest.preferences,
        tier=guest.tier,
        total_stays=guest.total_stays or 0,
        total_amount=guest.total_amount or 0,
        is_blacklisted=guest.is_blacklisted or False,
        blacklist_reason=guest.blacklist_reason,
        notes=guest.notes,
        created_at=guest.created_at,
        updated_at=guest.updated_at,
        reservation_count=stats["reservation_count"],
        last_stay_date=stats["last_stay_date"],
        last_room_type=stats["last_room_type"]
    )


@router.post("/", response_model=GuestResponse)
def create_guest(
    data: GuestCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """创建客人"""
    service = get_guest_service(db)
    try:
        guest = service.create_guest(data)
        return GuestResponse(
            id=guest.id,
            name=guest.name,
            id_type=guest.id_type,
            id_number=guest.id_number,
            phone=guest.phone,
            email=guest.email,
            preferences=guest.preferences,
            tier=guest.tier,
            total_stays=guest.total_stays or 0,
            total_amount=guest.total_amount or 0,
            is_blacklisted=guest.is_blacklisted or False,
            blacklist_reason=guest.blacklist_reason,
            notes=guest.notes,
            created_at=guest.created_at,
            updated_at=guest.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{guest_id}", response_model=GuestResponse)
def update_guest(
    guest_id: int,
    data: GuestUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """更新客人信息"""
    service = get_guest_service(db)
    try:
        guest = service.update_guest(guest_id, data)
        return GuestResponse(
            id=guest.id,
            name=guest.name,
            id_type=guest.id_type,
            id_number=guest.id_number,
            phone=guest.phone,
            email=guest.email,
            preferences=guest.preferences,
            tier=guest.tier,
            total_stays=guest.total_stays or 0,
            total_amount=guest.total_amount or 0,
            is_blacklisted=guest.is_blacklisted or False,
            blacklist_reason=guest.blacklist_reason,
            notes=guest.notes,
            created_at=guest.created_at,
            updated_at=guest.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{guest_id}/stay-history")
def get_stay_history(
    guest_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取客人入住历史"""
    service = get_guest_service(db)
    return service.get_guest_stay_history(guest_id, limit)


@router.get("/{guest_id}/reservation-history")
def get_reservation_history(
    guest_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取客人预订历史"""
    service = get_guest_service(db)
    return service.get_guest_reservation_history(guest_id, limit)


@router.put("/{guest_id}/tier")
def update_guest_tier(
    guest_id: int,
    tier: GuestTier,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """更新客人等级"""
    service = get_guest_service(db)
    try:
        guest = service.update_tier(guest_id, tier)
        return {"message": f"客人等级已更新为 {tier.value}"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{guest_id}/blacklist")
def toggle_blacklist(
    guest_id: int,
    is_blacklisted: bool = Query(...),
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """设置黑名单状态"""
    service = get_guest_service(db)
    try:
        if is_blacklisted:
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="添加到黑名单必须提供原因"
                )
            service.add_to_blacklist(guest_id, reason)
            return {"message": "已添加到黑名单"}
        else:
            service.remove_from_blacklist(guest_id)
            return {"message": "已从黑名单移除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{guest_id}/preferences")
def update_preferences(
    guest_id: int,
    preferences: dict,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """更新客人偏好"""
    service = get_guest_service(db)
    try:
        service.update_preferences(guest_id, preferences)
        return {"message": "偏好已更新"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{guest_id}/stats")
def get_guest_stats(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取客人统计信息"""
    service = get_guest_service(db)
    try:
        return service.get_guest_stats(guest_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
