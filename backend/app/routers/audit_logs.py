"""
审计日志路由
"""
from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, SystemLog
from app.services.audit_service import AuditService
from app.security.auth import get_current_user, require_sysadmin

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("/summary")
def get_action_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取操作统计摘要"""
    service = AuditService(db)
    return service.get_action_summary(days)


@router.get("/")
def list_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    operator_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
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
    current_user: Employee = Depends(require_sysadmin)
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
