"""
通知渠道实现 — 站内消息、邮件、Webhook
"""
from app.system.notification.internal_channel import InternalChannel
from app.system.notification.email_channel import EmailChannel
from app.system.notification.webhook_channel import WebhookChannel

__all__ = ["InternalChannel", "EmailChannel", "WebhookChannel"]
