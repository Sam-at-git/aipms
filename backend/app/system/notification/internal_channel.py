"""
站内消息通知渠道 — 通过 MessageService 发送站内消息
"""
import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from core.notification.channel import INotificationChannel

logger = logging.getLogger(__name__)


class InternalChannel(INotificationChannel):
    """站内消息渠道"""

    def __init__(self, db_factory=None):
        self._db_factory = db_factory

    def send(
        self,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """发送站内消息

        Args:
            recipient: 接收者用户 ID（字符串形式）
            subject: 消息标题
            content: 消息内容
            extra: 可选扩展参数 (msg_type, sender_id 等)
        """
        try:
            from app.system.services.message_service import MessageService
            from app.database import SessionLocal

            db = SessionLocal() if self._db_factory is None else self._db_factory()
            try:
                service = MessageService(db)
                msg_type = (extra or {}).get("msg_type", "system")
                sender_id = (extra or {}).get("sender_id")
                service.send_message(
                    sender_id=sender_id,
                    recipient_id=int(recipient),
                    title=subject,
                    content=content,
                    msg_type=msg_type,
                )
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to send internal message to {recipient}: {e}")
            return False

    def get_channel_type(self) -> str:
        return "internal"
