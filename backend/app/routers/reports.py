"""
报表路由
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import DashboardStats
from app.services.report_service import ReportService
from app.security.auth import get_current_user, require_manager, require_permission
from app.security.permissions import REPORT_READ

router = APIRouter(prefix="/reports", tags=["统计报表"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取仪表盘数据"""
    service = ReportService(db)
    return DashboardStats(**service.get_dashboard_stats())


@router.get("/occupancy")
def get_occupancy_report(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=7)),
    end_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(REPORT_READ))
):
    """获取入住率报表"""
    service = ReportService(db)
    return service.get_occupancy_report(start_date, end_date)


@router.get("/revenue")
def get_revenue_report(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=7)),
    end_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(REPORT_READ))
):
    """获取营收报表"""
    service = ReportService(db)
    return service.get_revenue_report(start_date, end_date)


@router.get("/room-types")
def get_room_type_report(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(REPORT_READ))
):
    """获取房型销售统计"""
    service = ReportService(db)
    return service.get_room_type_report(start_date, end_date)
