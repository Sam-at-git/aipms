"""
Comprehensive tests for AlertService.

Tests initialization, event handling, alert triggering,
active alerts retrieval, and alert summary.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch, call

from app.services.alert_service import AlertService, alert_service, register_alert_handlers
from app.services.event_bus import Event, EventBus
from app.models.security_events import (
    SecurityEventSeverity,
    SecurityEventModel,
)


@pytest.fixture
def fresh_alert_service():
    """Create a fresh AlertService instance (not the global singleton)."""
    svc = AlertService()
    svc._initialized = False
    return svc


@pytest.fixture
def mock_event_bus():
    """Mock the event_bus used by AlertService."""
    with patch("app.services.alert_service.event_bus") as mock_bus:
        yield mock_bus


# ========== initialize ==========


class TestInitialize:
    """Tests for AlertService.initialize()."""

    def test_subscribes_to_security_events(self, fresh_alert_service, mock_event_bus):
        fresh_alert_service.initialize()
        mock_event_bus.subscribe.assert_called_once_with(
            "security.event_recorded",
            fresh_alert_service._handle_security_event,
        )
        assert fresh_alert_service._initialized is True

    def test_idempotent(self, fresh_alert_service, mock_event_bus):
        """Calling initialize() twice should only subscribe once."""
        fresh_alert_service.initialize()
        fresh_alert_service.initialize()
        assert mock_event_bus.subscribe.call_count == 1

    def test_register_alert_handlers_function(self, mock_event_bus):
        """Test the module-level convenience function."""
        # Reset global singleton
        original_initialized = alert_service._initialized
        alert_service._initialized = False
        try:
            register_alert_handlers()
            assert alert_service._initialized is True
        finally:
            alert_service._initialized = original_initialized


# ========== _handle_security_event ==========


class TestHandleSecurityEvent:
    """Tests for _handle_security_event()."""

    def test_triggers_alert_for_high_severity(self, fresh_alert_service):
        with patch.object(fresh_alert_service, "_trigger_alert") as mock_trigger:
            event = Event(
                event_type="security.event_recorded",
                timestamp=datetime.now(UTC),
                data={
                    "severity": SecurityEventSeverity.HIGH.value,
                    "event_type": "unauthorized_access",
                    "description": "Unauthorized access attempt",
                    "user_name": "attacker",
                    "source_ip": "10.0.0.1",
                },
                source="test",
            )
            fresh_alert_service._handle_security_event(event)
            mock_trigger.assert_called_once_with(event.data)

    def test_triggers_alert_for_critical_severity(self, fresh_alert_service):
        with patch.object(fresh_alert_service, "_trigger_alert") as mock_trigger:
            event = Event(
                event_type="security.event_recorded",
                timestamp=datetime.now(UTC),
                data={
                    "severity": SecurityEventSeverity.CRITICAL.value,
                    "event_type": "role_escalation_attempt",
                    "description": "Critical breach",
                },
                source="test",
            )
            fresh_alert_service._handle_security_event(event)
            mock_trigger.assert_called_once()

    def test_ignores_low_severity(self, fresh_alert_service):
        with patch.object(fresh_alert_service, "_trigger_alert") as mock_trigger:
            event = Event(
                event_type="security.event_recorded",
                timestamp=datetime.now(UTC),
                data={
                    "severity": SecurityEventSeverity.LOW.value,
                    "event_type": "login_success",
                    "description": "Normal login",
                },
                source="test",
            )
            fresh_alert_service._handle_security_event(event)
            mock_trigger.assert_not_called()

    def test_ignores_medium_severity(self, fresh_alert_service):
        with patch.object(fresh_alert_service, "_trigger_alert") as mock_trigger:
            event = Event(
                event_type="security.event_recorded",
                timestamp=datetime.now(UTC),
                data={
                    "severity": SecurityEventSeverity.MEDIUM.value,
                    "event_type": "sensitive_data_access",
                    "description": "Data accessed",
                },
                source="test",
            )
            fresh_alert_service._handle_security_event(event)
            mock_trigger.assert_not_called()


# ========== _trigger_alert ==========


class TestTriggerAlert:
    """Tests for _trigger_alert()."""

    def test_publishes_alert_event_for_high(self, fresh_alert_service, mock_event_bus):
        security_event = {
            "severity": SecurityEventSeverity.HIGH.value,
            "event_type": "unauthorized_access",
            "description": "Attempt detected",
            "user_name": "user1",
            "source_ip": "192.168.1.1",
        }
        fresh_alert_service._trigger_alert(security_event)

        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.event_type == "alert.triggered"
        assert published_event.data["alert_type"] == "security"
        assert published_event.data["priority"] == "high"
        assert published_event.data["security_event"] == security_event

    def test_publishes_alert_event_for_critical(self, fresh_alert_service, mock_event_bus):
        security_event = {
            "severity": SecurityEventSeverity.CRITICAL.value,
            "event_type": "role_escalation_attempt",
            "description": "Critical breach",
            "user_name": "attacker",
            "source_ip": "10.0.0.1",
        }
        fresh_alert_service._trigger_alert(security_event)

        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.data["priority"] == "critical"

    def test_handles_missing_fields_gracefully(self, fresh_alert_service, mock_event_bus):
        """Event data with missing optional fields should not crash."""
        security_event = {
            "severity": "unknown",
        }
        fresh_alert_service._trigger_alert(security_event)
        mock_event_bus.publish.assert_called_once()

    def test_logs_critical_message(self, fresh_alert_service, mock_event_bus, caplog):
        import logging
        with caplog.at_level(logging.CRITICAL):
            security_event = {
                "severity": SecurityEventSeverity.HIGH.value,
                "event_type": "unauthorized_access",
                "description": "Test alert",
                "user_name": "tester",
                "source_ip": "127.0.0.1",
            }
            fresh_alert_service._trigger_alert(security_event)
        assert "SECURITY ALERT" in caplog.text


# ========== get_active_alerts ==========


class TestGetActiveAlerts:
    """Tests for get_active_alerts()."""

    def test_returns_high_severity_unacknowledged(self, fresh_alert_service, db_session):
        """Test that only high/critical unacknowledged events are returned."""
        # Create security events directly in DB
        high_event = SecurityEventModel(
            event_type="unauthorized_access",
            severity=SecurityEventSeverity.HIGH.value,
            timestamp=datetime.now(UTC),
            description="High severity event",
            is_acknowledged=False,
        )
        low_event = SecurityEventModel(
            event_type="login_success",
            severity=SecurityEventSeverity.LOW.value,
            timestamp=datetime.now(UTC),
            description="Low severity event",
            is_acknowledged=False,
        )
        critical_event = SecurityEventModel(
            event_type="role_escalation_attempt",
            severity=SecurityEventSeverity.CRITICAL.value,
            timestamp=datetime.now(UTC),
            description="Critical event",
            is_acknowledged=False,
        )
        acknowledged_high = SecurityEventModel(
            event_type="unauthorized_access",
            severity=SecurityEventSeverity.HIGH.value,
            timestamp=datetime.now(UTC),
            description="Already acknowledged",
            is_acknowledged=True,
        )
        db_session.add_all([high_event, low_event, critical_event, acknowledged_high])
        db_session.commit()

        with patch("app.services.security_event_service.security_event_service") as mock_ses:
            # Mock get_events to return unacknowledged events
            mock_ses.get_events.return_value = [high_event, low_event, critical_event]
            mock_ses.to_response.side_effect = lambda e: {
                "id": e.id,
                "severity": e.severity,
                "event_type": e.event_type,
                "description": e.description,
            }

            alerts = fresh_alert_service.get_active_alerts(db_session)

        # Should only include high and critical events
        assert len(alerts) == 2
        severities = {a["severity"] for a in alerts}
        assert SecurityEventSeverity.LOW.value not in severities

    def test_empty_when_no_events(self, fresh_alert_service, db_session):
        with patch("app.services.security_event_service.security_event_service") as mock_ses:
            mock_ses.get_events.return_value = []
            alerts = fresh_alert_service.get_active_alerts(db_session)
        assert alerts == []


# ========== get_alert_summary ==========


class TestGetAlertSummary:
    """Tests for get_alert_summary()."""

    def test_returns_summary_dict(self, fresh_alert_service, db_session):
        with patch("app.services.security_event_service.security_event_service") as mock_ses:
            mock_ses.get_statistics.return_value = {
                "total": 10,
                "unacknowledged": 3,
                "by_type": {"unauthorized_access": 5, "login_failed": 5},
                "by_severity": {
                    SecurityEventSeverity.HIGH.value: 4,
                    SecurityEventSeverity.CRITICAL.value: 2,
                    SecurityEventSeverity.LOW.value: 4,
                },
                "time_range_hours": 24,
            }

            summary = fresh_alert_service.get_alert_summary(db_session)

        assert summary["total_alerts"] == 6  # 4 high + 2 critical
        assert summary["critical"] == 2
        assert summary["high"] == 4
        assert summary["unacknowledged"] == 3
        assert summary["time_range_hours"] == 24

    def test_zero_counts(self, fresh_alert_service, db_session):
        with patch("app.services.security_event_service.security_event_service") as mock_ses:
            mock_ses.get_statistics.return_value = {
                "total": 0,
                "unacknowledged": 0,
                "by_type": {},
                "by_severity": {},
                "time_range_hours": 24,
            }
            summary = fresh_alert_service.get_alert_summary(db_session)

        assert summary["total_alerts"] == 0
        assert summary["critical"] == 0
        assert summary["high"] == 0

    def test_missing_severity_keys(self, fresh_alert_service, db_session):
        """If by_severity doesn't have high/critical keys, should default to 0."""
        with patch("app.services.security_event_service.security_event_service") as mock_ses:
            mock_ses.get_statistics.return_value = {
                "total": 5,
                "unacknowledged": 1,
                "by_type": {"login_success": 5},
                "by_severity": {SecurityEventSeverity.LOW.value: 5},
                "time_range_hours": 24,
            }
            summary = fresh_alert_service.get_alert_summary(db_session)

        assert summary["total_alerts"] == 0
        assert summary["critical"] == 0
        assert summary["high"] == 0
