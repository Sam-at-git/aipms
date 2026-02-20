"""
价格管理路由
"""
from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import RatePlanCreate, RatePlanUpdate, RatePlanResponse
from app.services.price_service import PriceService
from app.security.auth import get_current_user, require_manager, require_permission
from app.security.permissions import PRICE_READ, PRICE_WRITE

router = APIRouter(prefix="/prices", tags=["价格管理"])


@router.get("/rate-plans", response_model=List[RatePlanResponse])
def list_rate_plans(
    room_type_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取价格策略列表"""
    service = PriceService(db)
    plans = service.get_rate_plans(room_type_id, is_active)
    result = []
    for p in plans:
        result.append(RatePlanResponse(
            id=p.id,
            name=p.name,
            room_type_id=p.room_type_id,
            room_type_name=p.room_type.name,
            start_date=p.start_date,
            end_date=p.end_date,
            price=p.price,
            priority=p.priority,
            is_weekend=p.is_weekend,
            is_active=p.is_active,
            created_at=p.created_at
        ))
    return result


@router.get("/rate-plans/{rate_plan_id}", response_model=RatePlanResponse)
def get_rate_plan(
    rate_plan_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取价格策略详情"""
    service = PriceService(db)
    plan = service.get_rate_plan(rate_plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="价格策略不存在")
    return RatePlanResponse(
        id=plan.id,
        name=plan.name,
        room_type_id=plan.room_type_id,
        room_type_name=plan.room_type.name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        price=plan.price,
        priority=plan.priority,
        is_weekend=plan.is_weekend,
        is_active=plan.is_active,
        created_at=plan.created_at
    )


@router.post("/rate-plans", response_model=RatePlanResponse)
def create_rate_plan(
    data: RatePlanCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(PRICE_WRITE))
):
    """创建价格策略"""
    service = PriceService(db)
    try:
        plan = service.create_rate_plan(data, current_user.id)
        return RatePlanResponse(
            id=plan.id,
            name=plan.name,
            room_type_id=plan.room_type_id,
            room_type_name=plan.room_type.name,
            start_date=plan.start_date,
            end_date=plan.end_date,
            price=plan.price,
            priority=plan.priority,
            is_weekend=plan.is_weekend,
            is_active=plan.is_active,
            created_at=plan.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/rate-plans/{rate_plan_id}", response_model=RatePlanResponse)
def update_rate_plan(
    rate_plan_id: int,
    data: RatePlanUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(PRICE_WRITE))
):
    """更新价格策略"""
    service = PriceService(db)
    try:
        plan = service.update_rate_plan(rate_plan_id, data)
        return RatePlanResponse(
            id=plan.id,
            name=plan.name,
            room_type_id=plan.room_type_id,
            room_type_name=plan.room_type.name,
            start_date=plan.start_date,
            end_date=plan.end_date,
            price=plan.price,
            priority=plan.priority,
            is_weekend=plan.is_weekend,
            is_active=plan.is_active,
            created_at=plan.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/rate-plans/{rate_plan_id}")
def delete_rate_plan(
    rate_plan_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(PRICE_WRITE))
):
    """删除价格策略"""
    service = PriceService(db)
    try:
        service.delete_rate_plan(rate_plan_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/calendar")
def get_price_calendar(
    room_type_id: int,
    start_date: date = Query(default_factory=date.today),
    end_date: date = Query(default_factory=lambda: date.today() + timedelta(days=30)),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取价格日历"""
    service = PriceService(db)
    return service.get_price_calendar(room_type_id, start_date, end_date)


@router.get("/calculate")
def calculate_price(
    room_type_id: int,
    check_in_date: date,
    check_out_date: date,
    room_count: int = 1,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """计算房费"""
    service = PriceService(db)
    try:
        total = service.calculate_total_price(room_type_id, check_in_date, check_out_date, room_count)
        nights = (check_out_date - check_in_date).days
        return {
            "room_type_id": room_type_id,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "nights": nights,
            "room_count": room_count,
            "total_amount": total
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
