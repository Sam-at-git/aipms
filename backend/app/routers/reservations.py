"""
预订管理路由
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, ReservationStatus
from app.models.schemas import (
    ReservationCreate, ReservationUpdate, ReservationCancel, ReservationResponse
)
from app.services.reservation_service import ReservationService
from app.security.auth import get_current_user, require_receptionist_or_manager

router = APIRouter(prefix="/reservations", tags=["预订管理"])


@router.get("", response_model=List[ReservationResponse])
def list_reservations(
    status: Optional[ReservationStatus] = None,
    check_in_date: Optional[date] = None,
    guest_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取预订列表"""
    service = ReservationService(db)
    reservations = service.get_reservations(status, check_in_date, guest_name)
    return [ReservationResponse(**service.get_reservation_detail(r.id)) for r in reservations]


@router.get("/search")
def search_reservations(
    keyword: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """搜索预订"""
    service = ReservationService(db)
    reservations = service.search_reservations(keyword)
    return [service.get_reservation_detail(r.id) for r in reservations]


@router.get("/today-arrivals")
def get_today_arrivals(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取今日预抵"""
    service = ReservationService(db)
    reservations = service.get_today_arrivals()
    return [service.get_reservation_detail(r.id) for r in reservations]


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取预订详情"""
    service = ReservationService(db)
    detail = service.get_reservation_detail(reservation_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预订不存在")
    return ReservationResponse(**detail)


@router.post("", response_model=ReservationResponse)
def create_reservation(
    data: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """创建预订"""
    service = ReservationService(db)
    try:
        reservation = service.create_reservation(data, current_user.id)
        detail = service.get_reservation_detail(reservation.id)
        return ReservationResponse(**detail)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{reservation_id}", response_model=ReservationResponse)
def update_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """更新预订"""
    service = ReservationService(db)
    try:
        reservation = service.update_reservation(reservation_id, data)
        detail = service.get_reservation_detail(reservation.id)
        return ReservationResponse(**detail)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    data: ReservationCancel,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """取消预订"""
    service = ReservationService(db)
    try:
        reservation = service.cancel_reservation(reservation_id, data)
        return {"message": "预订已取消", "reservation_id": reservation.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/no-show")
def mark_no_show(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """标记未到"""
    service = ReservationService(db)
    try:
        reservation = service.mark_no_show(reservation_id)
        return {"message": "已标记为未到", "reservation_id": reservation.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
