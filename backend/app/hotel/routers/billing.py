"""
账单管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.hotel.models.ontology import Employee
from app.hotel.models.schemas import PaymentCreate, BillAdjustment, BillResponse
from app.hotel.services.billing_service import BillingService
from app.security.auth import get_current_user, require_manager, require_receptionist_or_manager

router = APIRouter(prefix="/billing", tags=["账单管理"])


@router.get("/bill/{bill_id}", response_model=BillResponse)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取账单详情"""
    service = BillingService(db)
    detail = service.get_bill_detail(bill_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账单不存在")
    return BillResponse(**detail)


@router.get("/stay/{stay_record_id}", response_model=BillResponse)
def get_bill_by_stay(
    stay_record_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """根据住宿记录获取账单"""
    service = BillingService(db)
    bill = service.get_bill_by_stay(stay_record_id)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账单不存在")
    return BillResponse(**service.get_bill_detail(bill.id))


@router.post("/payment")
def add_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_receptionist_or_manager)
):
    """添加支付记录"""
    service = BillingService(db)
    try:
        payment = service.add_payment(data, current_user.id)
        return {
            "message": "支付记录已添加",
            "payment_id": payment.id,
            "amount": payment.amount
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/adjust")
def adjust_bill(
    data: BillAdjustment,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """调整账单金额（仅经理）"""
    service = BillingService(db)
    try:
        bill = service.adjust_bill(data, current_user.id)
        return {
            "message": "账单已调整",
            "bill_id": bill.id,
            "adjustment_amount": bill.adjustment_amount
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
