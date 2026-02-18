"""
告警服务
监听安全事件并在达到阈值时触发告警
"""
from datetime import datetime, UTC
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import logging

from app.models.security_events import SecurityEventSeverity
from app.services.event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class AlertService:
    """告警服务"""

    def __init__(self):
        self._initialized = False

    def initialize(self):
        """初始化告警服务，订阅安全事件"""
        if self._initialized:
            return

        # 订阅安全事件
        event_bus.subscribe("security.event_recorded", self._handle_security_event)
        self._initialized = True
        logger.info("AlertService initialized and subscribed to security events")

    def _handle_security_event(self, event: Event):
        """处理安全事件"""
        security_event = event.data
        severity = security_event.get('severity')

        # 高危和紧急事件触发告警
        if severity in [SecurityEventSeverity.HIGH.value, SecurityEventSeverity.CRITICAL.value]:
            self._trigger_alert(security_event)

    def _trigger_alert(self, security_event: dict):
        """触发告警"""
        severity = security_event.get('severity', 'unknown')
        event_type = security_event.get('event_type', 'unknown')
        description = security_event.get('description', '')
        user_name = security_event.get('user_name', 'unknown')
        source_ip = security_event.get('source_ip', 'unknown')

        # 记录到日志
        logger.critical(
            f"SECURITY ALERT: [{severity.upper()}] {event_type} - {description} "
            f"(User: {user_name}, IP: {source_ip})"
        )

        # 发布告警事件（供WebSocket推送或其他通知渠道）
        event_bus.publish(Event(
            event_type="alert.triggered",
            timestamp=datetime.now(UTC),
            data={
                "alert_type": "security",
                "security_event": security_event,
                "notification_channels": ["log", "websocket"],
                "priority": "high" if severity == SecurityEventSeverity.HIGH.value else "critical"
            },
            source="alert_service"
        ))

    def get_active_alerts(self, db: Session) -> List[Dict[str, Any]]:
        """获取当前活跃告警（未确认的高危事件）"""
        from app.services.security_event_service import security_event_service

        events = security_event_service.get_events(
            db,
            unacknowledged_only=True,
            limit=50
        )

        # 只返回高危和紧急事件
        high_severity = [SecurityEventSeverity.HIGH.value, SecurityEventSeverity.CRITICAL.value]
        alerts = []

        for event in events:
            if event.severity in high_severity:
                alerts.append(security_event_service.to_response(event))

        return alerts

    def get_alert_summary(self, db: Session) -> Dict[str, Any]:
        """获取告警摘要"""
        from app.services.security_event_service import security_event_service

        stats = security_event_service.get_statistics(db, hours=24)

        high_count = stats['by_severity'].get(SecurityEventSeverity.HIGH.value, 0)
        critical_count = stats['by_severity'].get(SecurityEventSeverity.CRITICAL.value, 0)

        return {
            "total_alerts": high_count + critical_count,
            "critical": critical_count,
            "high": high_count,
            "unacknowledged": stats['unacknowledged'],
            "time_range_hours": 24
        }


# 全局实例
alert_service = AlertService()


def register_alert_handlers():
    """注册告警处理器（在应用启动时调用）"""
    alert_service.initialize()
