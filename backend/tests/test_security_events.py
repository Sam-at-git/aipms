"""
Tests for security events service and API
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.ontology import Employee, EmployeeRole
from app.models.security_events import (
    SecurityEventModel, SecurityEventType, SecurityEventSeverity,
    ALERT_THRESHOLDS
)
from app.services.security_event_service import SecurityEventService
from app.security.auth import get_password_hash


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def security_service():
    """Create security event service instance"""
    # Use a mock event publisher to avoid side effects
    published_events = []

    def mock_publisher(event):
        published_events.append(event)

    service = SecurityEventService(event_publisher=mock_publisher)
    service._published_events = published_events
    return service


@pytest.fixture
def manager_user(db):
    """Create a manager user for testing"""
    user = Employee(
        username="test_manager",
        password_hash=get_password_hash("password123"),
        name="Test Manager",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestSecurityEventService:
    """Tests for SecurityEventService"""

    def test_record_event(self, db, security_service):
        """Test recording a security event"""
        event = security_service.record_event(
            db,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            description="User logged in successfully",
            severity=SecurityEventSeverity.LOW,
            source_ip="192.168.1.1",
            user_id=1,
            user_name="Test User"
        )
        db.commit()

        assert event.id is not None
        assert event.event_type == SecurityEventType.LOGIN_SUCCESS.value
        assert event.severity == SecurityEventSeverity.LOW.value
        assert event.description == "User logged in successfully"
        assert event.source_ip == "192.168.1.1"
        assert event.user_id == 1

    def test_record_login_failure(self, db, security_service):
        """Test recording login failure event"""
        event = security_service.record_event(
            db,
            event_type=SecurityEventType.LOGIN_FAILED,
            description="Login failed for user testuser",
            severity=SecurityEventSeverity.LOW,
            source_ip="10.0.0.1",
            details={"username": "testuser"}
        )
        db.commit()

        assert event.event_type == SecurityEventType.LOGIN_FAILED.value
        assert "username" in event.details

    def test_escalation_on_multiple_failures(self, db, security_service):
        """Test that multiple login failures trigger escalation"""
        # Record multiple login failures within the threshold window
        threshold = ALERT_THRESHOLDS[SecurityEventType.LOGIN_FAILED]

        for i in range(threshold["count"]):
            security_service.record_event(
                db,
                event_type=SecurityEventType.LOGIN_FAILED,
                description=f"Login failure {i + 1}",
                severity=SecurityEventSeverity.LOW,
                user_id=1,
                user_name="Test User"
            )
        db.commit()

        # Check that an escalated event was created
        escalated_events = db.query(SecurityEventModel).filter(
            SecurityEventModel.event_type == SecurityEventType.MULTIPLE_LOGIN_FAILURES.value
        ).all()

        assert len(escalated_events) >= 1
        assert escalated_events[0].severity == SecurityEventSeverity.HIGH.value

    def test_get_events(self, db, security_service):
        """Test retrieving security events"""
        # Create some events
        for i in range(5):
            security_service.record_event(
                db,
                event_type=SecurityEventType.LOGIN_SUCCESS,
                description=f"Login {i}",
                severity=SecurityEventSeverity.LOW
            )
        db.commit()

        events = security_service.get_events(db, limit=10)
        assert len(events) == 5

    def test_get_events_filter_by_type(self, db, security_service):
        """Test filtering events by type"""
        security_service.record_event(db, SecurityEventType.LOGIN_SUCCESS, "Success 1")
        security_service.record_event(db, SecurityEventType.LOGIN_FAILED, "Failure 1")
        security_service.record_event(db, SecurityEventType.LOGIN_SUCCESS, "Success 2")
        db.commit()

        events = security_service.get_events(
            db,
            event_type=SecurityEventType.LOGIN_SUCCESS
        )
        assert len(events) == 2
        assert all(e.event_type == SecurityEventType.LOGIN_SUCCESS.value for e in events)

    def test_get_events_filter_by_severity(self, db, security_service):
        """Test filtering events by severity"""
        security_service.record_event(
            db, SecurityEventType.LOGIN_SUCCESS, "Low event",
            severity=SecurityEventSeverity.LOW
        )
        security_service.record_event(
            db, SecurityEventType.UNAUTHORIZED_ACCESS, "High event",
            severity=SecurityEventSeverity.HIGH
        )
        db.commit()

        events = security_service.get_events(
            db,
            severity=SecurityEventSeverity.HIGH
        )
        assert len(events) == 1
        assert events[0].severity == SecurityEventSeverity.HIGH.value

    def test_acknowledge_event(self, db, security_service, manager_user):
        """Test acknowledging a security event"""
        event = security_service.record_event(
            db,
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            description="Unauthorized access attempt",
            severity=SecurityEventSeverity.HIGH
        )
        db.commit()

        # Acknowledge the event
        acknowledged = security_service.acknowledge_event(db, event.id, manager_user.id)
        db.commit()

        assert acknowledged.is_acknowledged is True
        assert acknowledged.acknowledged_by == manager_user.id
        assert acknowledged.acknowledged_at is not None

    def test_get_statistics(self, db, security_service):
        """Test getting security statistics"""
        # Create events of different types and severities
        security_service.record_event(
            db, SecurityEventType.LOGIN_SUCCESS, "Success",
            severity=SecurityEventSeverity.LOW
        )
        security_service.record_event(
            db, SecurityEventType.LOGIN_FAILED, "Failure",
            severity=SecurityEventSeverity.LOW
        )
        security_service.record_event(
            db, SecurityEventType.UNAUTHORIZED_ACCESS, "Unauthorized",
            severity=SecurityEventSeverity.HIGH
        )
        db.commit()

        stats = security_service.get_statistics(db, hours=24)

        assert stats["total"] == 3
        assert stats["unacknowledged"] == 3
        assert SecurityEventType.LOGIN_SUCCESS.value in stats["by_type"]
        assert SecurityEventSeverity.HIGH.value in stats["by_severity"]

    def test_get_recent_high_severity_events(self, db, security_service):
        """Test retrieving recent high severity events"""
        security_service.record_event(
            db, SecurityEventType.LOGIN_SUCCESS, "Low event",
            severity=SecurityEventSeverity.LOW
        )
        security_service.record_event(
            db, SecurityEventType.UNAUTHORIZED_ACCESS, "High event",
            severity=SecurityEventSeverity.HIGH
        )
        security_service.record_event(
            db, SecurityEventType.ROLE_ESCALATION_ATTEMPT, "Critical event",
            severity=SecurityEventSeverity.CRITICAL
        )
        db.commit()

        events = security_service.get_recent_high_severity_events(db, hours=24, limit=10)

        assert len(events) == 2
        severities = [e.severity for e in events]
        assert SecurityEventSeverity.LOW.value not in severities

    def test_bulk_acknowledge(self, db, security_service, manager_user):
        """Test bulk acknowledging events"""
        event1 = security_service.record_event(db, SecurityEventType.LOGIN_FAILED, "Event 1")
        event2 = security_service.record_event(db, SecurityEventType.LOGIN_FAILED, "Event 2")
        event3 = security_service.record_event(db, SecurityEventType.LOGIN_FAILED, "Event 3")
        db.commit()

        count = security_service.bulk_acknowledge(
            db,
            [event1.id, event2.id],
            manager_user.id
        )
        db.commit()

        assert count == 2

        # Verify events are acknowledged
        db.refresh(event1)
        db.refresh(event2)
        db.refresh(event3)

        assert event1.is_acknowledged is True
        assert event2.is_acknowledged is True
        assert event3.is_acknowledged is False

    def test_get_user_security_history(self, db, security_service, manager_user):
        """Test getting user security history"""
        # Create events for specific user
        security_service.record_event(
            db, SecurityEventType.LOGIN_SUCCESS, "User login",
            user_id=manager_user.id, user_name=manager_user.name
        )
        security_service.record_event(
            db, SecurityEventType.PASSWORD_CHANGED, "Password changed",
            user_id=manager_user.id, user_name=manager_user.name
        )
        # Create event for different user
        security_service.record_event(
            db, SecurityEventType.LOGIN_SUCCESS, "Other user",
            user_id=999, user_name="Other"
        )
        db.commit()

        history = security_service.get_user_security_history(
            db, manager_user.id, days=30, limit=50
        )

        assert len(history) == 2
        assert all(e.user_id == manager_user.id for e in history)

    def test_to_response_format(self, db, security_service):
        """Test event to response format conversion"""
        event = security_service.record_event(
            db,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            description="Test event",
            severity=SecurityEventSeverity.LOW,
            source_ip="10.0.0.1",
            user_id=1,
            user_name="Test",
            details={"key": "value"}
        )
        db.commit()

        response = security_service.to_response(event)

        assert "id" in response
        assert "event_type" in response
        assert "severity" in response
        assert "timestamp" in response
        assert response["details"] == {"key": "value"}
        assert response["is_acknowledged"] is False


class TestSecurityEventModel:
    """Tests for SecurityEventModel ORM"""

    def test_create_event(self, db):
        """Test creating security event directly"""
        event = SecurityEventModel(
            event_type=SecurityEventType.LOGIN_SUCCESS.value,
            severity=SecurityEventSeverity.LOW.value,
            timestamp=datetime.utcnow(),
            description="Direct creation test"
        )
        db.add(event)
        db.commit()

        assert event.id is not None
        assert event.is_acknowledged is False

    def test_event_ordering(self, db):
        """Test that events are ordered by timestamp descending"""
        for i in range(3):
            event = SecurityEventModel(
                event_type=SecurityEventType.LOGIN_SUCCESS.value,
                severity=SecurityEventSeverity.LOW.value,
                timestamp=datetime.utcnow() - timedelta(hours=i),
                description=f"Event {i}"
            )
            db.add(event)
        db.commit()

        events = db.query(SecurityEventModel).order_by(
            SecurityEventModel.timestamp.desc()
        ).all()

        # Most recent first
        assert events[0].description == "Event 0"
        assert events[2].description == "Event 2"


class TestAlertThresholds:
    """Tests for alert threshold configuration"""

    def test_login_failure_threshold_exists(self):
        """Test that login failure threshold is configured"""
        assert SecurityEventType.LOGIN_FAILED in ALERT_THRESHOLDS
        threshold = ALERT_THRESHOLDS[SecurityEventType.LOGIN_FAILED]
        assert "count" in threshold
        assert "window_minutes" in threshold
        assert "escalate_to" in threshold

    def test_unauthorized_access_threshold_exists(self):
        """Test that unauthorized access threshold is configured"""
        assert SecurityEventType.UNAUTHORIZED_ACCESS in ALERT_THRESHOLDS
        threshold = ALERT_THRESHOLDS[SecurityEventType.UNAUTHORIZED_ACCESS]
        assert threshold["severity"] == SecurityEventSeverity.HIGH
