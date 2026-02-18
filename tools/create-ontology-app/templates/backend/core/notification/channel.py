"""
Notification channel interface - domain-agnostic notification abstraction.

The app layer implements INotificationChannel to connect to specific
channels (in-app messages, email, webhooks, etc.).
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import threading


class INotificationChannel(ABC):
    """Notification channel interface."""

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """Send a notification.

        Args:
            recipient: Recipient identifier (user ID, email, phone, etc.)
            subject: Notification subject
            content: Notification content
            extra: Extra parameters (e.g., template variables, priority)

        Returns:
            True if the notification was sent successfully.
        """

    @abstractmethod
    def get_channel_type(self) -> str:
        """Return the channel type identifier, e.g. 'internal', 'email', 'sms', 'webhook'."""


class NotificationChannelRegistry:
    """Notification channel registry - singleton.

    The app layer registers implementations at startup:
        registry = NotificationChannelRegistry()
        registry.register(InternalChannel(db))
        registry.register(EmailChannel(smtp_config))
    """

    _instance: Optional["NotificationChannelRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "NotificationChannelRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._channels: Dict[str, INotificationChannel] = {}
        return cls._instance

    def register(self, channel: INotificationChannel) -> None:
        """Register a notification channel."""
        self._channels[channel.get_channel_type()] = channel

    def get_channel(self, channel_type: str) -> Optional[INotificationChannel]:
        """Get a channel by type."""
        return self._channels.get(channel_type)

    def get_all_channels(self) -> List[INotificationChannel]:
        """Get all registered channels."""
        return list(self._channels.values())

    def send(
        self,
        channel_type: str,
        recipient: str,
        subject: str,
        content: str,
        extra: Optional[Dict] = None,
    ) -> bool:
        """Send a notification via the specified channel."""
        channel = self.get_channel(channel_type)
        if channel is None:
            return False
        return channel.send(recipient, subject, content, extra)

    def clear(self) -> None:
        """Clear all channels (for testing)."""
        self._channels.clear()


__all__ = [
    "INotificationChannel",
    "NotificationChannelRegistry",
]
