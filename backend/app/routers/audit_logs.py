"""
审计日志路由
"""
import csv
import io
from typing import Any, Dict, List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, SystemLog
from app.services.audit_service import AuditService
from app.security.auth import get_current_user, require_sysadmin, require_permission
from app.security.permissions import AUDIT_READ

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("/summary")
def get_action_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(AUDIT_READ))
):
    """获取操作统计摘要"""
    service = AuditService(db)
    return service.get_action_summary(days)


@router.get("/trend")
def get_daily_trend(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(AUDIT_READ)),
) -> Dict[str, Any]:
    """获取每日操作量趋势（A-2）"""
    service = AuditService(db)
    data = service.get_daily_trend(days)
    return {"days": days, "data": data}


@router.get("/export")
def export_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    operator_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = Query(default="json", description="json or csv"),
    limit: int = Query(default=1000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(AUDIT_READ)),
):
    """导出审计日志（A-1）"""
    service = AuditService(db)

    start = datetime.fromisoformat(start_date).date() if start_date else None
    end = datetime.fromisoformat(end_date).date() if end_date else None

    logs = service.get_logs(
        action=action,
        entity_type=entity_type,
        operator_id=operator_id,
        start_date=start,
        end_date=end,
        limit=limit,
    )

    rows = [
        {
            "id": log.id,
            "operator_id": log.operator_id,
            "operator_name": log.operator.name if log.operator else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "operator_id", "operator_name", "action", "entity_type", "entity_id", "ip_address", "created_at"])
        for r in rows:
            writer.writerow([r["id"], r["operator_id"], r["operator_name"], r["action"], r["entity_type"], r["entity_id"], r["ip_address"], r["created_at"]])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )

    return {"count": len(rows), "logs": rows}


@router.get("/")
def list_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    operator_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(AUDIT_READ))
):
    """获取审计日志列表"""
    service = AuditService(db)

    # 转换日期字符串
    start = None
    end = None
    if start_date:
        start = datetime.fromisoformat(start_date).date()
    if end_date:
        end = datetime.fromisoformat(end_date).date()

    logs = service.get_logs(
        action=action,
        entity_type=entity_type,
        operator_id=operator_id,
        start_date=start,
        end_date=end,
        limit=limit
    )

    return [
        {
            "id": log.id,
            "operator_id": log.operator_id,
            "operator_name": log.operator.name if log.operator else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "ip_address": log.ip_address,
            "created_at": log.created_at
        }
        for log in logs
    ]


@router.get("/{log_id}")
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(AUDIT_READ))
):
    """获取单条日志详情"""
    service = AuditService(db)
    log = service.get_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志不存在")

    return {
        "id": log.id,
        "operator_id": log.operator_id,
        "operator_name": log.operator.name if log.operator else None,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "old_value": log.old_value,
        "new_value": log.new_value,
        "ip_address": log.ip_address,
        "created_at": log.created_at
    }


@router.get("/entity/{entity_type}/{entity_id}")
def get_entity_logs(
    entity_type: str,
    entity_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """获取特定实体的操作日志"""
    service = AuditService(db)
    logs = service.get_logs_by_entity(entity_type, entity_id, limit)

    return [
        {
            "id": log.id,
            "operator_id": log.operator_id,
            "operator_name": log.operator.name if log.operator else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "created_at": log.created_at
        }
        for log in logs
    ]
