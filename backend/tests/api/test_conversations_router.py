"""
Tests for app/routers/conversations.py — conversation history endpoints.

Covers:
- GET /conversations/messages — paginated messages
- GET /conversations/messages/date/{date_str} — messages by date
- GET /conversations/search — search messages
- GET /conversations/dates — available dates
- GET /conversations/admin/users — admin list users (sysadmin only)
- GET /conversations/admin/user/{id}/dates — admin user dates
- GET /conversations/admin/user/{id}/messages — admin user messages with filters
- GET /conversations/admin/statistics — admin statistics
- GET /conversations/admin/export — export messages (JSON and CSV)
"""
import shutil
import tempfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.hotel.models.ontology import Employee, EmployeeRole
from app.main import app
from app.routers.conversations import get_conversation_service
from app.security.auth import create_access_token, get_password_hash
from app.services.conversation_service import ConversationMessage, ConversationService


# ==================== Fixtures ====================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for conversation data."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def conv_service(temp_dir):
    """ConversationService backed by temp dir."""
    return ConversationService(base_dir=temp_dir)


@pytest.fixture
def manager_user(db_session):
    user = Employee(
        username="mgr_conv",
        password_hash=get_password_hash("123456"),
        name="Conv Manager",
        role=EmployeeRole.MANAGER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def manager_token(manager_user):
    return create_access_token(manager_user.id, manager_user.role)


@pytest.fixture
def manager_auth_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def sysadmin_user(db_session):
    user = Employee(
        username="admin_conv",
        password_hash=get_password_hash("123456"),
        name="Conv Admin",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sysadmin_token(sysadmin_user):
    return create_access_token(sysadmin_user.id, sysadmin_user.role)


@pytest.fixture
def sysadmin_auth_headers(sysadmin_token):
    return {"Authorization": f"Bearer {sysadmin_token}"}


@pytest.fixture(autouse=True)
def _override_conv_service(conv_service):
    """Override the conversation service dependency for all tests."""
    app.dependency_overrides[get_conversation_service] = lambda: conv_service
    yield
    app.dependency_overrides.pop(get_conversation_service, None)


def _seed_messages(service, user_id, count=4, topic_id=None):
    """Helper to seed message pairs for a user."""
    for i in range(count):
        service.save_message_pair(
            user_id=user_id,
            user_content=f"question {i}",
            assistant_content=f"answer {i}",
            topic_id=topic_id,
        )


# ==================== GET /conversations/messages ====================


class TestGetMessages:

    def test_no_auth(self, client):
        resp = client.get("/conversations/messages")
        assert resp.status_code in (401, 403)

    def test_empty_history(self, client, manager_auth_headers):
        resp = client.get("/conversations/messages", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["has_more"] is False

    def test_returns_messages(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=2)
        resp = client.get("/conversations/messages", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # 2 pairs = 4 messages
        assert len(data["messages"]) == 4
        assert data["has_more"] is False

    def test_limit_param(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=5)
        resp = client.get(
            "/conversations/messages",
            params={"limit": 3},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 3
        assert data["has_more"] is True

    def test_before_param(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=2)
        # Get all messages first
        resp1 = client.get("/conversations/messages", headers=manager_auth_headers)
        msgs = resp1.json()["messages"]
        assert len(msgs) >= 2

        # Use a timestamp that is before the latest message
        last_ts = msgs[-1]["timestamp"]
        resp2 = client.get(
            "/conversations/messages",
            params={"before": last_ts},
            headers=manager_auth_headers,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        # Messages before the last timestamp should be fewer
        for m in data["messages"]:
            assert m["timestamp"] < last_ts

    def test_oldest_timestamp(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=1)
        resp = client.get("/conversations/messages", headers=manager_auth_headers)
        data = resp.json()
        assert data["oldest_timestamp"] is not None


# ==================== GET /conversations/messages/date/{date_str} ====================


class TestGetMessagesByDate:

    def test_valid_date_with_messages(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=1)
        today = datetime.now().strftime("%Y-%m-%d")
        resp = client.get(
            f"/conversations/messages/date/{today}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # 1 pair = 2 messages

    def test_valid_date_no_messages(self, client, manager_auth_headers):
        resp = client.get(
            "/conversations/messages/date/2020-01-01",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_invalid_date_format(self, client, manager_auth_headers):
        resp = client.get(
            "/conversations/messages/date/not-a-date",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_no_auth(self, client):
        resp = client.get("/conversations/messages/date/2025-01-01")
        assert resp.status_code in (401, 403)


# ==================== GET /conversations/search ====================


class TestSearchMessages:

    def test_search_finds_match(self, client, manager_auth_headers, conv_service, manager_user):
        conv_service.save_message_pair(
            user_id=manager_user.id,
            user_content="I need a luxury room",
            assistant_content="Sure, room 501 is available",
        )
        resp = client.get(
            "/conversations/search",
            params={"keyword": "luxury"},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("luxury" in m["content"].lower() for m in data["messages"])

    def test_search_no_match(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=1)
        resp = client.get(
            "/conversations/search",
            params={"keyword": "nonexistent_xyz"},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_search_with_date_range(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=1)
        today = datetime.now().strftime("%Y-%m-%d")
        resp = client.get(
            "/conversations/search",
            params={
                "keyword": "question",
                "start_date": today,
                "end_date": today,
            },
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_requires_keyword(self, client, manager_auth_headers):
        resp = client.get("/conversations/search", headers=manager_auth_headers)
        assert resp.status_code == 422  # missing required param

    def test_search_limit(self, client, manager_auth_headers, conv_service, manager_user):
        # Seed many messages
        for i in range(10):
            conv_service.save_message_pair(
                user_id=manager_user.id,
                user_content=f"repeated keyword message {i}",
                assistant_content=f"reply to keyword {i}",
            )
        resp = client.get(
            "/conversations/search",
            params={"keyword": "keyword", "limit": 3},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 3

    def test_search_no_auth(self, client):
        resp = client.get("/conversations/search", params={"keyword": "test"})
        assert resp.status_code in (401, 403)


# ==================== GET /conversations/dates ====================


class TestGetAvailableDates:

    def test_no_dates(self, client, manager_auth_headers):
        resp = client.get("/conversations/dates", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["dates"] == []

    def test_with_dates(self, client, manager_auth_headers, conv_service, manager_user):
        _seed_messages(conv_service, manager_user.id, count=1)
        resp = client.get("/conversations/dates", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dates"]) >= 1
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in data["dates"]

    def test_no_auth(self, client):
        resp = client.get("/conversations/dates")
        assert resp.status_code in (401, 403)


# ==================== Admin Endpoints ====================


class TestAdminGetUsers:

    def test_requires_sysadmin(self, client, manager_auth_headers):
        resp = client.get("/conversations/admin/users", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_list_users(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=100, user_content="hi", assistant_content="hello")
        conv_service.save_message_pair(user_id=200, user_content="hi", assistant_content="hello")
        resp = client.get("/conversations/admin/users", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        user_ids = [u["user_id"] for u in data["users"]]
        assert 100 in user_ids
        assert 200 in user_ids

    def test_empty_users(self, client, sysadmin_auth_headers):
        resp = client.get("/conversations/admin/users", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["users"] == []


class TestAdminGetUserDates:

    def test_requires_sysadmin(self, client, manager_auth_headers):
        resp = client.get("/conversations/admin/user/1/dates", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_get_user_dates(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=50, user_content="hi", assistant_content="hello")
        resp = client.get("/conversations/admin/user/50/dates", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dates"]) >= 1


class TestAdminGetUserMessages:

    def test_requires_sysadmin(self, client, manager_auth_headers):
        resp = client.get("/conversations/admin/user/1/messages", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_get_messages_default(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=60, user_content="hi", assistant_content="hello")
        resp = client.get("/conversations/admin/user/60/messages", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2

    def test_get_messages_by_date_str(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=61, user_content="hi", assistant_content="hello")
        today = datetime.now().strftime("%Y-%m-%d")
        resp = client.get(
            "/conversations/admin/user/61/messages",
            params={"date_str": today},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2

    def test_get_messages_by_keyword(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(
            user_id=62,
            user_content="luxury room needed",
            assistant_content="Room 501 available",
        )
        resp = client.get(
            "/conversations/admin/user/62/messages",
            params={"keyword": "luxury"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) >= 1

    def test_get_messages_with_keyword_and_date(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(
            user_id=63,
            user_content="search term special",
            assistant_content="found it",
        )
        today = datetime.now().strftime("%Y-%m-%d")
        resp = client.get(
            "/conversations/admin/user/63/messages",
            params={"keyword": "special", "date_str": today},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) >= 1

    def test_get_messages_empty_user(self, client, sysadmin_auth_headers):
        resp = client.get("/conversations/admin/user/9999/messages", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []

    def test_oldest_timestamp_present(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=70, user_content="x", assistant_content="y")
        resp = client.get("/conversations/admin/user/70/messages", headers=sysadmin_auth_headers)
        data = resp.json()
        assert data["oldest_timestamp"] is not None

    def test_has_more_is_false(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=71, user_content="x", assistant_content="y")
        resp = client.get("/conversations/admin/user/71/messages", headers=sysadmin_auth_headers)
        data = resp.json()
        assert data["has_more"] is False


class TestAdminStatistics:

    def test_requires_sysadmin(self, client, manager_auth_headers):
        resp = client.get("/conversations/admin/statistics", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_returns_statistics(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=80, user_content="hi", assistant_content="hello")
        resp = client.get("/conversations/admin/statistics", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_messages" in data
        assert "today_messages" in data
        assert "user_count" in data
        assert "action_distribution" in data
        assert data["total_messages"] >= 2
        assert data["user_count"] >= 1

    def test_statistics_empty(self, client, sysadmin_auth_headers):
        resp = client.get("/conversations/admin/statistics", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_messages"] == 0


# ==================== Admin Export ====================


class TestAdminExport:

    def test_requires_sysadmin(self, client, manager_auth_headers):
        resp = client.get(
            "/conversations/admin/export",
            params={"user_id": 1},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 403

    def test_export_json(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=90, user_content="hi", assistant_content="hello")
        resp = client.get(
            "/conversations/admin/export",
            params={"user_id": 90, "format": "json"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 90
        assert data["count"] >= 2
        assert isinstance(data["messages"], list)

    def test_export_csv(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=91, user_content="csv test", assistant_content="csv reply")
        resp = client.get(
            "/conversations/admin/export",
            params={"user_id": 91, "format": "csv"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        assert "id" in content
        assert "timestamp" in content
        assert "csv test" in content

    def test_export_csv_attachment_header(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=92, user_content="x", assistant_content="y")
        resp = client.get(
            "/conversations/admin/export",
            params={"user_id": 92, "format": "csv"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "chat_user_92" in disposition

    def test_export_json_empty(self, client, sysadmin_auth_headers):
        resp = client.get(
            "/conversations/admin/export",
            params={"user_id": 9999, "format": "json"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_export_with_date_range(self, client, sysadmin_auth_headers, conv_service):
        conv_service.save_message_pair(user_id=93, user_content="date test", assistant_content="reply")
        today = datetime.now().strftime("%Y-%m-%d")
        resp = client.get(
            "/conversations/admin/export",
            params={
                "user_id": 93,
                "format": "json",
                "start_date": today,
                "end_date": today,
            },
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2

    def test_export_requires_user_id(self, client, sysadmin_auth_headers):
        resp = client.get(
            "/conversations/admin/export",
            params={"format": "json"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 422  # user_id is required
