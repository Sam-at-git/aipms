"""
通知渠道接口 — 域无关的通知抽象

app 层通过实现 INotificationChannel 来对接具体通知渠道（站内信、邮件、Webhook 等）。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class INotificationChannel(ABC):
    """通知渠道接口"""

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """发送通知

        Args:
            recipient: 接收方标识（用户ID、邮箱、手机号等，由渠道实现决定）
            subject: 通知标题
            content: 通知内容
            extra: 扩展参数（如模板变量、优先级等）

        Returns:
            是否发送成功
        """

    @abstractmethod
    def get_channel_type(self) -> str:
        """返回渠道类型标识，如 'internal', 'email', 'sms', 'webhook'"""


class NotificationChannelRegistry:
    """通知渠道注册表 — 单例模式

    app 层在 lifespan 中注册实现：
        registry = NotificationChannelRegistry()
        registry.register(InternalChannel(db))
        registry.register(EmailChannel(smtp_config))
    """

    _instance: Optional["NotificationChannelRegistry"] = None

    def __new__(cls) -> "NotificationChannelRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._channels: Dict[str, INotificationChannel] = {}
        return cls._instance

    def register(self, channel: INotificationChannel) -> None:
        """注册通知渠道"""
        self._channels[channel.get_channel_type()] = channel

    def get_channel(self, channel_type: str) -> Optional[INotificationChannel]:
        """获取指定类型的渠道"""
        return self._channels.get(channel_type)

    def get_all_channels(self) -> List[INotificationChannel]:
        """获取所有已注册渠道"""
        return list(self._channels.values())

    def send(
        self,
        channel_type: str,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """通过指定渠道发送通知"""
        channel = self.get_channel(channel_type)
        if channel is None:
            return False
        return channel.send(recipient, subject, content, extra)

    def clear(self) -> None:
        """清除所有渠道（用于测试）"""
        self._channels.clear()
