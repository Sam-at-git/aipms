"""
安全事件服务
负责记录、检测、查询和管理安全事件
"""
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import logging

from app.models.security_events import (
    SecurityEventModel, SecurityEvent, SecurityEventType,
    SecurityEventSeverity, ALERT_THRESHOLDS, SecurityStatistics
)
from app.services.event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class SecurityEventService:
    """安全事件服务"""

    def __init__(self, db: Session = None, event_publisher=None):
        self.db = db
        self._publish_event = event_publisher or event_bus.publish

    def record_event(
        self,
        db: Session,
        event_type: SecurityEventType,
        description: str,
        severity: SecurityEventSeverity = SecurityEventSeverity.LOW,
        source_ip: str = None,
        user_id: int = None,
        user_name: str = None,
        details: dict = None
    ) -> SecurityEventModel:
        """记录安全事件"""
        event = SecurityEventModel(
            event_type=event_type.value,
            severity=severity.value,
            timestamp=datetime.now(UTC),
            source_ip=source_ip,
            user_id=user_id,
            user_name=user_name,
            description=description,
            details=json.dumps(details or {}, ensure_ascii=False)
        )

        db.add(event)
        db.flush()  # 获取ID但不提交，让调用者决定何时提交

        # 检查是否需要升级告警
        self._check_escalation(db, event, event_type, user_id)

        # 发布安全事件到事件总线
        self._publish_event(Event(
            event_type="security.event_recorded",
            timestamp=datetime.now(UTC),
            data={
                "id": event.id,
                "event_type": event_type.value,
                "severity": severity.value,
                "description": description,
                "user_id": user_id,
                "user_name": user_name,
                "source_ip": source_ip,
                "details": details or {}
            },
            source="security_event_service"
        ))

        logger.warning(f"Security event: [{severity.value}] {event_type.value} - {description}")
        return event

    def _check_escalation(
        self,
        db: Session,
        event: SecurityEventModel,
        event_type: SecurityEventType,
        user_id: int = None
    ):
        """检查是否需要升级告警"""
        threshold = ALERT_THRESHOLDS.get(event_type)
        if not threshold:
            return

        # 查询时间窗口内的相同类型事件
        window_start = datetime.now(UTC) - timedelta(minutes=threshold['window_minutes'])

        query = db.query(SecurityEventModel).filter(
            SecurityEventModel.event_type == event_type.value,
            SecurityEventModel.timestamp >= window_start
        )

        if user_id:
            query = query.filter(SecurityEventModel.user_id == user_id)

        count = query.count()

        if count >= threshold['count']:
            # 触发升级
            if 'escalate_to' in threshold:
                escalate_severity = threshold.get('escalate_severity', SecurityEventSeverity.HIGH)
                self.record_event(
                    db,
                    event_type=threshold['escalate_to'],
                    description=f"检测到连续{count}次 {event_type.value} 事件",
                    severity=escalate_severity,
                    user_id=user_id,
                    user_name=event.user_name,
                    source_ip=event.source_ip,
                    details={
                        "trigger_event_id": event.id,
                        "count": count,
                        "window_minutes": threshold['window_minutes']
                    }
                )

    def get_events(
        self,
        db: Session,
        event_type: SecurityEventType = None,
        severity: SecurityEventSeverity = None,
        user_id: int = None,
        start_time: datetime = None,
        end_time: datetime = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityEventModel]:
        """查询安全事件"""
        query = db.query(SecurityEventModel)

        if event_type:
            query = query.filter(SecurityEventModel.event_type == event_type.value)
        if severity:
            query = query.filter(SecurityEventModel.severity == severity.value)
        if user_id:
            query = query.filter(SecurityEventModel.user_id == user_id)
        if start_time:
            query = query.filter(SecurityEventModel.timestamp >= start_time)
        if end_time:
            query = query.filter(SecurityEventModel.timestamp <= end_time)
        if unacknowledged_only:
            query = query.filter(SecurityEventModel.is_acknowledged == False)

        return query.order_by(SecurityEventModel.timestamp.desc()).offset(offset).limit(limit).all()

    def get_event_by_id(self, db: Session, event_id: int) -> Optional[SecurityEventModel]:
        """根据ID获取安全事件"""
        return db.query(SecurityEventModel).filter(SecurityEventModel.id == event_id).first()

    def acknowledge_event(
        self,
        db: Session,
        event_id: int,
        acknowledged_by: int
    ) -> Optional[SecurityEventModel]:
        """确认安全事件"""
        event = db.query(SecurityEventModel).filter(SecurityEventModel.id == event_id).first()
        if event:
            event.is_acknowledged = True
            event.acknowledged_by = acknowledged_by
            event.acknowledged_at = datetime.now(UTC)

            # 发布确认事件
            self._publish_event(Event(
                event_type="security.event_acknowledged",
                timestamp=datetime.now(UTC),
                data={
                    "event_id": event_id,
                    "acknowledged_by": acknowledged_by
                },
                source="security_event_service"
            ))

        return event

    def bulk_acknowledge(
        self,
        db: Session,
        event_ids: List[int],
        acknowledged_by: int
    ) -> int:
        """批量确认安全事件"""
        count = db.query(SecurityEventModel).filter(
            SecurityEventModel.id.in_(event_ids),
            SecurityEventModel.is_acknowledged == False
        ).update({
            SecurityEventModel.is_acknowledged: True,
            SecurityEventModel.acknowledged_by: acknowledged_by,
            SecurityEventModel.acknowledged_at: datetime.now(UTC)
        }, synchronize_session=False)

        return count

    def get_statistics(self, db: Session, hours: int = 24) -> Dict[str, Any]:
        """获取安全事件统计"""
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        events = db.query(SecurityEventModel).filter(
            SecurityEventModel.timestamp >= start_time
        ).all()

        by_type = {}
        by_severity = {}
        unacknowledged = 0

        for event in events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
            if not event.is_acknowledged:
                unacknowledged += 1

        return {
            "total": len(events),
            "unacknowledged": unacknowledged,
            "by_type": by_type,
            "by_severity": by_severity,
            "time_range_hours": hours
        }

    def get_recent_high_severity_events(
        self,
        db: Session,
        hours: int = 24,
        limit: int = 20
    ) -> List[SecurityEventModel]:
        """获取最近的高危事件"""
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        return db.query(SecurityEventModel).filter(
            SecurityEventModel.timestamp >= start_time,
            SecurityEventModel.severity.in_([
                SecurityEventSeverity.HIGH.value,
                SecurityEventSeverity.CRITICAL.value
            ])
        ).order_by(SecurityEventModel.timestamp.desc()).limit(limit).all()

    def get_user_security_history(
        self,
        db: Session,
        user_id: int,
        days: int = 30,
        limit: int = 50
    ) -> List[SecurityEventModel]:
        """获取用户的安全事件历史"""
        start_time = datetime.now(UTC) - timedelta(days=days)

        return db.query(SecurityEventModel).filter(
            SecurityEventModel.user_id == user_id,
            SecurityEventModel.timestamp >= start_time
        ).order_by(SecurityEventModel.timestamp.desc()).limit(limit).all()

    def cleanup_old_events(self, db: Session, days: int = 90) -> int:
        """清理旧的安全事件（保留指定天数内的事件）"""
        cutoff_time = datetime.now(UTC) - timedelta(days=days)

        count = db.query(SecurityEventModel).filter(
            SecurityEventModel.timestamp < cutoff_time
        ).delete(synchronize_session=False)

        logger.info(f"Cleaned up {count} security events older than {days} days")
        return count

    def to_response(self, event: SecurityEventModel) -> Dict[str, Any]:
        """将数据库模型转换为响应格式"""
        return {
            "id": event.id,
            "event_type": event.event_type,
            "severity": event.severity,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "source_ip": event.source_ip,
            "user_id": event.user_id,
            "user_name": event.user_name,
            "description": event.description,
            "details": json.loads(event.details) if event.details else {},
            "is_acknowledged": event.is_acknowledged,
            "acknowledged_by": event.acknowledged_by,
            "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None
        }


# 全局实例
security_event_service = SecurityEventService()
