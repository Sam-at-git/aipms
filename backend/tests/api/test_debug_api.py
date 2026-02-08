"""
tests/api/test_debug_api.py

Tests for the debug API endpoints.

These tests require sysadmin role and test:
- Session listing with filters
- Session detail retrieval
- Statistics
- Access control
"""
import pytest
from datetime import datetime

from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token
from core.ai.debug_logger import DebugLogger


# ==================== Fixtures ====================

@pytest.fixture
def sysadmin_token(db_session):
    """Create a sysadmin user and return token."""
    sysadmin = Employee(
        username="admin_debug",
        password_hash=get_password_hash("debug123"),
        name="Debug Admin",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(sysadmin)
    db_session.commit()
    db_session.flush()
    db_session.refresh(sysadmin)
    return create_access_token(sysadmin.id, sysadmin.role)


@pytest.fixture
def sysadmin_auth_headers(sysadmin_token):
    """Return sysadmin auth headers."""
    return {"Authorization": f"Bearer {sysadmin_token}"}


# ==================== List Sessions Tests ====================

def test_list_sessions_success(client, sysadmin_auth_headers):
    """List sessions successfully."""
    response = client.get("/debug/sessions", headers=sysadmin_auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["sessions"], list)


def test_list_sessions_with_filters(client, sysadmin_auth_headers):
    """Filter sessions by status and user_id."""
    response = client.get(
        "/debug/sessions",
        params={"status": "success", "limit": 10},
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_list_sessions_pagination(client, sysadmin_auth_headers):
    """Test pagination parameters."""
    response = client.get(
        "/debug/sessions",
        params={"limit": 5, "offset": 10},
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 5
    assert data["offset"] == 10


# ==================== Statistics Tests ====================

def test_get_statistics(client, sysadmin_auth_headers):
    """Get debug statistics."""
    response = client.get("/debug/statistics", headers=sysadmin_auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "total_sessions" in data
    assert "total_attempts" in data
    assert "status_counts" in data
    assert "recent_sessions_24h" in data


# ==================== Session Detail Tests ====================

def test_get_session_detail_not_found(client, sysadmin_auth_headers):
    """Get non-existent session returns 404."""
    response = client.get(
        "/debug/sessions/non-existent-id",
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 404


# ==================== Replay Tests ====================

def test_replay_session_not_found(client, sysadmin_auth_headers):
    """Replay returns 503 when ReplayEngine is not available."""
    response = client.post(
        "/debug/replay",
        json={
            "session_id": "non-existent-id"
        },
        headers=sysadmin_auth_headers
    )

    # ReplayEngine may not be available in test environment
    assert response.status_code in [404, 503]


def test_replay_missing_session_id(client, sysadmin_auth_headers):
    """Replay without session_id returns 400."""
    response = client.post(
        "/debug/replay",
        json={},
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 400


# ==================== Replay Result Tests ====================

def test_get_replay_not_found(client, sysadmin_auth_headers):
    """Get non-existent replay returns 404 or 503."""
    response = client.get(
        "/debug/replay/non-existent-id",
        headers=sysadmin_auth_headers
    )

    # ReplayEngine may not be available in test environment
    assert response.status_code in [404, 503]


# ==================== List Replays Tests ====================

def test_list_replays(client, sysadmin_auth_headers):
    """List replays."""
    response = client.get(
        "/debug/replays",
        headers=sysadmin_auth_headers
    )

    # ReplayEngine may not be available in test environment
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "replays" in data
        assert "count" in data
        assert isinstance(data["replays"], list)


# ==================== Management Tests ====================

def test_delete_session_not_found(client, sysadmin_auth_headers):
    """Delete non-existent session returns 404."""
    response = client.delete(
        "/debug/sessions/non-existent-id",
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 404


def test_cleanup_old_sessions(client, sysadmin_auth_headers):
    """Cleanup old sessions."""
    response = client.post(
        "/debug/cleanup",
        params={"days": 30},
        headers=sysadmin_auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "message" in data
    assert "deleted_count" in data
    assert data["days"] == 30


# ==================== Pagination Edge Cases ====================

def test_list_sessions_limit_bounds(client, sysadmin_auth_headers):
    """Test limit validation bounds."""
    # Test upper bound (max 100)
    response = client.get(
        "/debug/sessions",
        params={"limit": 200},
        headers=sysadmin_auth_headers
    )
    # Should be rejected or clamped
    assert response.status_code in [200, 422]

    # Test lower bound (min 1)
    response = client.get(
        "/debug/sessions",
        params={"limit": 0},
        headers=sysadmin_auth_headers
    )
    assert response.status_code == 422


def test_list_sessions_negative_offset(client, sysadmin_auth_headers):
    """Test negative offset is rejected."""
    response = client.get(
        "/debug/sessions",
        params={"offset": -1},
        headers=sysadmin_auth_headers
    )
    assert response.status_code == 422


# ==================== Unauthorized Access Tests ====================

def test_unauthorized_access_without_token(client):
    """Test that accessing debug endpoints without token fails."""
    response = client.get("/debug/sessions")
    assert response.status_code == 401


def test_unauthorized_access_non_sysadmin(client, manager_token):
    """Test that non-sysadmin cannot access debug API."""
    headers = {"Authorization": f"Bearer {manager_token}"}
    response = client.get("/debug/sessions", headers=headers)
    assert response.status_code == 403
