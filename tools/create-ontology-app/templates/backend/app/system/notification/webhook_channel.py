"""
Webhook 通知渠道 — 通用 HTTP 回调（支持钉钉/飞书/企微机器人等）
"""
import logging
from typing import Dict, Optional

import httpx

from core.notification.channel import INotificationChannel

logger = logging.getLogger(__name__)


class WebhookChannel(INotificationChannel):
    """通用 Webhook 通知渠道"""

    def __init__(
        self,
        webhook_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout

    def send(
        self,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """发送 Webhook 通知

        Args:
            recipient: 接收标识（可用于路由或日志）
            subject: 通知标题
            content: 通知内容
            extra: 可选参数 (webhook_url 覆盖, payload_template 等)
        """
        extra = extra or {}
        url = extra.get("webhook_url", self.webhook_url)
        if not url:
            logger.error("Webhook URL not configured")
            return False

        payload = extra.get("payload") or {
            "msgtype": "text",
            "text": {
                "content": f"[{subject}]\n{content}",
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self.headers)
                resp.raise_for_status()
            logger.info(f"Webhook sent to {url}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook to {url}: {e}")
            return False

    def get_channel_type(self) -> str:
        return "webhook"
