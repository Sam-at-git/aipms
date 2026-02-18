"""
安全事件路由
提供安全事件查询、统计、告警管理API
"""
from datetime import datetime, timedelta, date, UTC
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from app.database import get_db
from app.hotel.models.ontology import Employee
from app.models.security_events import SecurityEventType, SecurityEventSeverity
from app.services.security_event_service import security_event_service
from app.services.alert_service import alert_service
from app.security.auth import get_current_user, require_sysadmin

router = APIRouter(prefix="/security", tags=["安全管理"])


@router.get("/events")
async def list_security_events(
    event_type: Optional[str] = Query(None, description="事件类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    hours: int = Query(24, ge=1, le=720, description="时间范围（小时）"),
    unacknowledged_only: bool = Query(False, description="仅未确认"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取安全事件列表"""
    start_time = datetime.now(UTC) - timedelta(hours=hours)

    # 转换枚举
    event_type_enum = None
    if event_type:
        try:
            event_type_enum = SecurityEventType(event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的事件类型: {event_type}")

    severity_enum = None
    if severity:
        try:
            severity_enum = SecurityEventSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的严重程度: {severity}")

    events = security_event_service.get_events(
        db,
        event_type=event_type_enum,
        severity=severity_enum,
        user_id=user_id,
        start_time=start_time,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
        offset=offset
    )

    return [security_event_service.to_response(e) for e in events]


@router.get("/events/{event_id}")
async def get_security_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取安全事件详情"""
    event = security_event_service.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return security_event_service.to_response(event)


@router.get("/statistics")
async def get_security_statistics(
    hours: int = Query(24, ge=1, le=720, description="统计时间范围（小时）"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取安全事件统计"""
    return security_event_service.get_statistics(db, hours)


@router.get("/alerts")
async def get_active_alerts(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取活跃告警（未确认的高危事件）"""
    return alert_service.get_active_alerts(db)


@router.get("/alerts/summary")
async def get_alert_summary(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取告警摘要"""
    return alert_service.get_alert_summary(db)


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """确认安全事件"""
    event = security_event_service.acknowledge_event(db, event_id, current_user.id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    db.commit()
    return security_event_service.to_response(event)


@router.post("/events/bulk-acknowledge")
async def bulk_acknowledge_events(
    event_ids: List[int],
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """批量确认安全事件"""
    count = security_event_service.bulk_acknowledge(db, event_ids, current_user.id)
    db.commit()
    return {"acknowledged_count": count}


@router.get("/user/{user_id}/history")
async def get_user_security_history(
    user_id: int,
    days: int = Query(30, ge=1, le=365, description="历史天数"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取用户安全事件历史"""
    events = security_event_service.get_user_security_history(db, user_id, days, limit)
    return [security_event_service.to_response(e) for e in events]


@router.get("/high-severity")
async def get_high_severity_events(
    hours: int = Query(24, ge=1, le=168, description="时间范围（小时）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin)
):
    """获取高危事件列表"""
    events = security_event_service.get_recent_high_severity_events(db, hours, limit)
    return [security_event_service.to_response(e) for e in events]


@router.get("/event-types")
async def get_event_types(
    current_user: Employee = Depends(require_sysadmin)
):
    """获取所有事件类型"""
    from app.models.security_events import EVENT_TYPE_DESCRIPTIONS
    return [
        {"value": et.value, "label": EVENT_TYPE_DESCRIPTIONS.get(et, et.value)}
        for et in SecurityEventType
    ]


@router.get("/severity-levels")
async def get_severity_levels(
    current_user: Employee = Depends(require_sysadmin)
):
    """获取所有严重程度级别"""
    from app.models.security_events import SEVERITY_DESCRIPTIONS
    return [
        {"value": sv.value, "label": SEVERITY_DESCRIPTIONS.get(sv, sv.value)}
        for sv in SecurityEventSeverity
    ]


@router.get("/trend")
async def get_event_trend(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """获取安全事件趋势（SE-2）— 按天/severity 分层"""
    from app.models.security_events import SecurityEventModel
    start_date = date.today() - timedelta(days=days)

    results = db.query(
        cast(SecurityEventModel.timestamp, Date).label('day'),
        SecurityEventModel.severity,
        func.count(SecurityEventModel.id).label('count'),
    ).filter(
        SecurityEventModel.timestamp >= datetime.combine(start_date, datetime.min.time())
    ).group_by(
        cast(SecurityEventModel.timestamp, Date),
        SecurityEventModel.severity,
    ).order_by(
        cast(SecurityEventModel.timestamp, Date),
    ).all()

    data: Dict[str, Dict[str, int]] = {}
    for r in results:
        day_str = str(r.day)
        if day_str not in data:
            data[day_str] = {"low": 0, "medium": 0, "high": 0, "critical": 0, "total": 0}
        data[day_str][r.severity] = r.count
        data[day_str]["total"] += r.count

    return {
        "days": days,
        "data": [{"day": day, **counts} for day, counts in sorted(data.items())],
    }


@router.get("/risk-scores")
async def get_user_risk_scores(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
) -> List[Dict[str, Any]]:
    """获取用户风险评分（SE-3）— 基于事件频率和严重程度"""
    from app.models.security_events import SecurityEventModel
    start_date = date.today() - timedelta(days=days)

    SEVERITY_WEIGHTS = {"low": 1, "medium": 3, "high": 7, "critical": 15}

    results = db.query(
        SecurityEventModel.user_id,
        SecurityEventModel.user_name,
        SecurityEventModel.severity,
        func.count(SecurityEventModel.id).label('count'),
    ).filter(
        SecurityEventModel.timestamp >= datetime.combine(start_date, datetime.min.time()),
        SecurityEventModel.user_id.isnot(None),
    ).group_by(
        SecurityEventModel.user_id,
        SecurityEventModel.user_name,
        SecurityEventModel.severity,
    ).all()

    user_scores: Dict[int, Dict[str, Any]] = {}
    for r in results:
        if r.user_id not in user_scores:
            user_scores[r.user_id] = {
                "user_id": r.user_id,
                "user_name": r.user_name or f"User {r.user_id}",
                "score": 0,
                "event_count": 0,
                "breakdown": {},
            }
        weight = SEVERITY_WEIGHTS.get(r.severity, 1)
        user_scores[r.user_id]["score"] += r.count * weight
        user_scores[r.user_id]["event_count"] += r.count
        user_scores[r.user_id]["breakdown"][r.severity] = r.count

    scored = sorted(user_scores.values(), key=lambda x: x["score"], reverse=True)
    return scored
