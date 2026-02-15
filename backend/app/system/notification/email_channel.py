"""
邮件通知渠道 — SMTP 发送邮件
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

from core.notification.channel import INotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(INotificationChannel):
    """SMTP 邮件通知渠道"""

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        sender_email: str = "",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_email = sender_email or smtp_user
        self.use_tls = use_tls

    def send(
        self,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """发送邮件

        Args:
            recipient: 收件人邮箱地址
            subject: 邮件标题
            content: 邮件内容（支持 HTML）
            extra: 可选参数 (content_type: 'html'|'plain', cc, bcc)
        """
        try:
            extra = extra or {}
            content_type = extra.get("content_type", "plain")

            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = recipient
            msg["Subject"] = subject

            if cc := extra.get("cc"):
                msg["Cc"] = cc
            msg.attach(MIMEText(content, content_type, "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {recipient}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False

    def get_channel_type(self) -> str:
        return "email"
