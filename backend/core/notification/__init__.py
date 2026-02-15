"""
通知渠道抽象层 — 仅定义接口，app 层实现具体渠道
"""
from core.notification.channel import INotificationChannel, NotificationChannelRegistry

__all__ = ["INotificationChannel", "NotificationChannelRegistry"]
