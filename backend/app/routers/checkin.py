"""
入住管理路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import (
    CheckInFromReservation, WalkInCheckIn, ExtendStay, ChangeRoom, StayRecordResponse
)
from app.services.checkin_service import CheckInService
from app.security.auth import get_current_user, require_receptionist_or_manager

router = APIRouter(prefix="/checkin", tags=["入住管理"])


@router.get("/active-stays", response_model=List[StayRecordResponse])
def list_active_stays(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取所有在住记录"""
    service = CheckInService(db)
    stays = service.get_active_stays()
    return [StayRecordResponse(**service.get_stay_detail(s.id)) for s in stays]


@router.get("/search")
def search_active_stays(
    keyword: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """搜索在住客人"""
    service = CheckInService(db)
    stays = service.search_active_stays(keyword)
    return [service.get_stay_detail(s.id) for s in stays]


@router.get("/stay/{stay_record_id}", response_model=StayRecordResponse)
def get_stay_record(
    stay_record_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取住宿记录详情"""
    service = CheckInService(db)
    detail = service.get_stay_detail(stay_record_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="住宿记录不存在")
    return StayRecordResponse(**detail)


@router.post("/from-reservation", response_model=StayRecordResponse)
def check_in_from_reservation(
    data: CheckInFromReservation,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """预订入住"""
    service = CheckInService(db)
    try:
        stay = service.check_in_from_reservation(data, current_user.id)
        return StayRecordResponse(**service.get_stay_detail(stay.id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/walk-in", response_model=StayRecordResponse)
def walk_in_check_in(
    data: WalkInCheckIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """散客入住"""
    service = CheckInService(db)
    try:
        stay = service.walk_in_check_in(data, current_user.id)
        return StayRecordResponse(**service.get_stay_detail(stay.id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/stay/{stay_record_id}/extend")
def extend_stay(
    stay_record_id: int,
    data: ExtendStay,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """续住"""
    service = CheckInService(db)
    try:
        stay = service.extend_stay(stay_record_id, data)
        return {"message": "续住成功", "new_check_out_date": stay.expected_check_out}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/stay/{stay_record_id}/change-room")
def change_room(
    stay_record_id: int,
    data: ChangeRoom,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """换房"""
    service = CheckInService(db)
    try:
        stay = service.change_room(stay_record_id, data, current_user.id)
        return {"message": "换房成功", "new_room_number": stay.room.room_number}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
