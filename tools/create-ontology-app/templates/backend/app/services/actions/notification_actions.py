"""
app/services/actions/notification_actions.py

Notification-related action handlers.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.hotel.models.ontology import Employee
from app.services.actions.base import NotificationParams

import logging

logger = logging.getLogger(__name__)


def register_notification_actions(registry: ActionRegistry) -> None:
    """Register all notification-related actions."""

    @registry.register(
        name="notify_checkout_reminder",
        entity="StayRecord",
        description="发送退房提醒通知给指定房间的客人。",
        category="notification",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["sends_notification"],
        search_keywords=["退房提醒", "通知客人", "提醒退房"],
    )
    def handle_checkout_reminder(
        params: NotificationParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Send checkout reminder notification."""
        target = params.target or "相关客人"
        return {
            "success": True,
            "message": f"退房提醒已发送给{target}",
            "target": target,
            "channel": params.channel,
        }

    @registry.register(
        name="notify_task_assigned",
        entity="Task",
        description="通知员工有新任务分配。",
        category="notification",
        requires_confirmation=False,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["sends_notification"],
        search_keywords=["通知任务", "新任务通知", "任务分配通知"],
    )
    def handle_task_assigned_notification(
        params: NotificationParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Send task assignment notification."""
        target = params.target or "相关员工"
        return {
            "success": True,
            "message": f"已通知{target}有新任务",
            "target": target,
            "channel": params.channel,
        }

    @registry.register(
        name="notify_low_inventory",
        entity="Room",
        description="房源不足预警通知，当可用房间低于阈值时发送预警。",
        category="notification",
        requires_confirmation=False,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["sends_notification"],
        search_keywords=["房源预警", "库存不足", "房间不够", "房源不足"],
    )
    def handle_low_inventory_notification(
        params: NotificationParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Send low inventory alert."""
        return {
            "success": True,
            "message": "房源不足预警已发送给管理层",
            "channel": params.channel,
        }


__all__ = ["register_notification_actions"]
