"""
Notification channel tests.

Covers:
- EmailChannel: send success, send failure, get_channel_type, TLS toggle, login
- InternalChannel: send success, send failure, get_channel_type, db_factory usage
- WebhookChannel: send success, send failure, no URL, custom payload, get_channel_type
- Module __init__.py: imports all channels
"""
import smtplib
from unittest.mock import MagicMock, patch, call

import pytest

from app.system.notification import InternalChannel, EmailChannel, WebhookChannel
from app.system.notification.email_channel import EmailChannel as EmailChannelDirect
from app.system.notification.internal_channel import InternalChannel as InternalChannelDirect
from app.system.notification.webhook_channel import WebhookChannel as WebhookChannelDirect


# ── EmailChannel Tests ────────────────────────────────────


class TestEmailChannel:
    """Test EmailChannel.send() with mocked SMTP."""

    def test_get_channel_type(self):
        ch = EmailChannel()
        assert ch.get_channel_type() == "email"

    def test_send_success_with_tls_and_login(self):
        ch = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="secret",
            sender_email="noreply@example.com",
            use_tls=True,
        )
        mock_server = MagicMock()
        with patch("app.system.notification.email_channel.smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

            result = ch.send(
                recipient="recipient@example.com",
                subject="Test Subject",
                content="Hello, world!",
            )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.send_message.assert_called_once()

    def test_send_success_without_tls_and_login(self):
        ch = EmailChannel(
            smtp_host="localhost",
            smtp_port=25,
            smtp_user="",
            smtp_password="",
            sender_email="no-auth@example.com",
            use_tls=False,
        )
        mock_server = MagicMock()
        with patch("app.system.notification.email_channel.smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

            result = ch.send(
                recipient="user@example.com",
                subject="Plain",
                content="No TLS",
            )

        assert result is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()

    def test_send_with_html_content_and_cc(self):
        ch = EmailChannel(smtp_host="localhost", smtp_user="u", smtp_password="p")
        mock_server = MagicMock()
        with patch("app.system.notification.email_channel.smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

            result = ch.send(
                recipient="to@example.com",
                subject="HTML Email",
                content="<h1>Hello</h1>",
                extra={"content_type": "html", "cc": "cc@example.com"},
            )

        assert result is True

    def test_send_failure(self):
        ch = EmailChannel(smtp_host="bad-host", smtp_port=587)
        with patch("app.system.notification.email_channel.smtplib.SMTP") as MockSMTP:
            MockSMTP.side_effect = smtplib.SMTPException("Connection refused")

            result = ch.send(
                recipient="user@example.com",
                subject="Fail",
                content="Will fail",
            )

        assert result is False

    def test_sender_email_defaults_to_smtp_user(self):
        ch = EmailChannel(smtp_user="user@mail.com")
        assert ch.sender_email == "user@mail.com"


# ── InternalChannel Tests ─────────────────────────────────


class TestInternalChannel:
    """Test InternalChannel.send() with mocked MessageService."""

    def test_get_channel_type(self):
        ch = InternalChannel()
        assert ch.get_channel_type() == "internal"

    def test_send_success_with_db_factory(self):
        mock_db = MagicMock()
        mock_service = MagicMock()

        with patch(
            "app.system.services.message_service.MessageService",
            return_value=mock_service,
        ):
            ch = InternalChannel(db_factory=lambda: mock_db)
            result = ch.send(
                recipient="42",
                subject="New Task",
                content="You have a cleaning task",
                extra={"msg_type": "business", "sender_id": 1},
            )

        assert result is True
        mock_db.close.assert_called_once()

    def test_send_success_default_msg_type(self):
        mock_db = MagicMock()
        mock_service = MagicMock()

        with patch(
            "app.system.services.message_service.MessageService",
            return_value=mock_service,
        ):
            ch = InternalChannel(db_factory=lambda: mock_db)
            result = ch.send(
                recipient="10",
                subject="System Alert",
                content="Alert content",
            )

        assert result is True

    def test_send_failure_on_exception(self):
        """When db_factory raises, send returns False."""
        def bad_factory():
            raise RuntimeError("DB error")

        ch = InternalChannel(db_factory=bad_factory)
        result = ch.send(
            recipient="1",
            subject="Fail",
            content="Will fail",
        )
        assert result is False

    def test_send_uses_session_local_when_no_factory(self):
        """When db_factory is None, fallback to SessionLocal."""
        mock_db = MagicMock()
        mock_service = MagicMock()

        with patch(
            "app.database.SessionLocal",
            return_value=mock_db,
        ), patch(
            "app.system.services.message_service.MessageService",
            return_value=mock_service,
        ):
            ch = InternalChannel(db_factory=None)
            result = ch.send(
                recipient="5",
                subject="Test",
                content="Content",
            )

        assert result is True
        mock_db.close.assert_called_once()


# ── WebhookChannel Tests ──────────────────────────────────


class TestWebhookChannel:
    """Test WebhookChannel.send() with mocked httpx."""

    def test_get_channel_type(self):
        ch = WebhookChannel()
        assert ch.get_channel_type() == "webhook"

    def test_send_success(self):
        ch = WebhookChannel(webhook_url="https://hooks.example.com/notify")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("app.system.notification.webhook_channel.httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = ch.send(
                recipient="channel_123",
                subject="New Alert",
                content="Room 101 needs cleaning",
            )

        assert result is True
        mock_client.post.assert_called_once()
        # Verify default payload structure
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["msgtype"] == "text"
        assert "New Alert" in payload["text"]["content"]

    def test_send_with_custom_payload(self):
        ch = WebhookChannel(webhook_url="https://hooks.example.com/notify")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("app.system.notification.webhook_channel.httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            custom_payload = {"type": "custom", "body": "data"}
            result = ch.send(
                recipient="x",
                subject="Sub",
                content="Con",
                extra={"payload": custom_payload},
            )

        assert result is True
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload == custom_payload

    def test_send_with_url_override(self):
        ch = WebhookChannel(webhook_url="https://default.example.com")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        with patch("app.system.notification.webhook_channel.httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = ch.send(
                recipient="x",
                subject="Sub",
                content="Con",
                extra={"webhook_url": "https://override.example.com"},
            )

        assert result is True
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://override.example.com"

    def test_send_no_url_configured(self):
        ch = WebhookChannel(webhook_url="")
        result = ch.send(
            recipient="x",
            subject="No URL",
            content="Will fail",
        )
        assert result is False

    def test_send_http_error(self):
        ch = WebhookChannel(webhook_url="https://hooks.example.com/bad")

        with patch("app.system.notification.webhook_channel.httpx.Client") as MockClient:
            MockClient.side_effect = Exception("Connection error")

            result = ch.send(
                recipient="x",
                subject="Error",
                content="Will fail",
            )

        assert result is False

    def test_custom_headers_and_timeout(self):
        custom_headers = {"Authorization": "Bearer token123"}
        ch = WebhookChannel(
            webhook_url="https://api.example.com",
            headers=custom_headers,
            timeout=5.0,
        )
        assert ch.headers == custom_headers
        assert ch.timeout == 5.0

    def test_default_headers(self):
        ch = WebhookChannel()
        assert ch.headers == {"Content-Type": "application/json"}


# ── Module Import Tests ───────────────────────────────────


class TestNotificationModuleInit:
    """Verify __init__.py exports all channels."""

    def test_imports(self):
        from app.system.notification import InternalChannel, EmailChannel, WebhookChannel
        assert InternalChannel is InternalChannelDirect
        assert EmailChannel is EmailChannelDirect
        assert WebhookChannel is WebhookChannelDirect
