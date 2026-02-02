"""
退房管理路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import CheckOutRequest, StayRecordResponse
from app.services.checkout_service import CheckOutService
from app.services.checkin_service import CheckInService
from app.security.auth import get_current_user, require_receptionist_or_manager

router = APIRouter(prefix="/checkout", tags=["退房管理"])


@router.post("")
def check_out(
    data: CheckOutRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """退房"""
    service = CheckOutService(db)
    try:
        stay = service.check_out(data, current_user.id)
        return {"message": "退房成功", "stay_record_id": stay.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/batch")
def batch_check_out(
    stay_record_ids: List[int],
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """批量退房"""
    service = CheckOutService(db)
    results = service.batch_check_out(stay_record_ids, current_user.id)
    return {"results": results}


@router.get("/today-expected")
def get_today_expected_checkouts(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """今日预计退房"""
    service = CheckOutService(db)
    checkin_service = CheckInService(db)
    stays = service.get_today_expected_checkouts()
    return [checkin_service.get_stay_detail(s.id) for s in stays]


@router.get("/overdue")
def get_overdue_stays(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """逾期未退房"""
    service = CheckOutService(db)
    checkin_service = CheckInService(db)
    stays = service.get_overdue_stays()
    return [checkin_service.get_stay_detail(s.id) for s in stays]
