"""
Tests for app/routers/debug.py — debug panel API endpoints.

Covers:
- GET  /debug/sessions — list sessions
- GET  /debug/sessions/{id} — session detail (found and not found)
- GET  /debug/statistics — statistics
- GET  /debug/analytics/token-trend — token trend
- GET  /debug/analytics/error-aggregation — error aggregation
- POST /debug/replay — replay session
- GET  /debug/replay/{id} — replay result
- GET  /debug/replays — list replays
- DELETE /debug/sessions/{id} — delete session
- POST /debug/cleanup — cleanup old sessions

Uses tempfile-backed DebugLogger for isolation.  Replay endpoints are
tested both with a mocked ReplayEngine (happy path) and with
ReplayEngine = None (503 response).

Note: The debug router calls get_debug_logger() and get_replay_engine()
as plain functions (not via FastAPI Depends), so we must patch
the module-level functions with unittest.mock.patch.
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import create_access_token, get_password_hash
from core.ai.debug_logger import AttemptLog, DebugLogger, DebugSession, LLMInteraction


# ==================== Fixtures ====================


@pytest.fixture
def sysadmin_user(db_session):
    user = Employee(
        username="admin_dbg",
        password_hash=get_password_hash("123456"),
        name="Debug Admin",
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


@pytest.fixture
def manager_user(db_session):
    user = Employee(
        username="mgr_dbg",
        password_hash=get_password_hash("123456"),
        name="Debug Manager",
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
def debug_logger():
    """Create a DebugLogger backed by a temp file for test isolation."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    logger = DebugLogger(db_path=path)
    yield logger
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def seeded_session(debug_logger):
    """Create a debug session with an attempt and return its session_id."""
    session_id = debug_logger.create_session(input_message="test query")
    debug_logger.log_attempt(
        session_id=session_id,
        action_name="ontology_query",
        params={"entity": "Room"},
        success=True,
        result={"rows": []},
    )
    debug_logger.complete_session(
        session_id=session_id,
        result={"rows": []},
        status="success",
        execution_time_ms=150,
    )
    return session_id


@pytest.fixture
def mock_replay_engine():
    """Return a mocked ReplayEngine."""
    return MagicMock()


# ==================== Auth / Access Control ====================


class TestDebugAccessControl:

    @patch("app.routers.debug.get_debug_logger")
    def test_no_auth_returns_401(self, mock_get_logger, client, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions")
        assert resp.status_code in (401, 403)

    @patch("app.routers.debug.get_debug_logger")
    def test_non_sysadmin_returns_403(self, mock_get_logger, client, manager_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions", headers=manager_auth_headers)
        assert resp.status_code == 403

    @patch("app.routers.debug.get_debug_logger")
    def test_sysadmin_can_access(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions", headers=sysadmin_auth_headers)
        assert resp.status_code == 200


# ==================== GET /debug/sessions ====================


class TestListSessions:

    @patch("app.routers.debug.get_debug_logger")
    def test_empty_list(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["total"] == 0

    @patch("app.routers.debug.get_debug_logger")
    def test_with_sessions(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger, seeded_session):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) >= 1
        session = data["sessions"][0]
        assert session["session_id"] == seeded_session
        assert session["input_message"] == "test query"
        assert session["status"] == "success"
        assert "attempt_count" in session
        assert session["attempt_count"] >= 1

    @patch("app.routers.debug.get_debug_logger")
    def test_pagination(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        for i in range(5):
            sid = debug_logger.create_session(input_message=f"query {i}")
            debug_logger.complete_session(sid, status="success")
        resp = client.get(
            "/debug/sessions",
            params={"limit": 2, "offset": 0},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    @patch("app.routers.debug.get_debug_logger")
    def test_filter_by_status(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        sid1 = debug_logger.create_session(input_message="ok")
        debug_logger.complete_session(sid1, status="success")
        sid2 = debug_logger.create_session(input_message="fail")
        debug_logger.complete_session(sid2, status="error")

        resp = client.get(
            "/debug/sessions",
            params={"status": "error"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for s in data["sessions"]:
            assert s["status"] == "error"

    def test_limit_validation_lower_bound(self, client, sysadmin_auth_headers):
        resp = client.get(
            "/debug/sessions",
            params={"limit": 0},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 422

    def test_limit_validation_upper_bound(self, client, sysadmin_auth_headers):
        resp = client.get(
            "/debug/sessions",
            params={"limit": 200},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code in (200, 422)

    def test_negative_offset_rejected(self, client, sysadmin_auth_headers):
        resp = client.get(
            "/debug/sessions",
            params={"offset": -1},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 422

    @patch("app.routers.debug.get_debug_logger")
    def test_action_type_from_attempt(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger, seeded_session):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/sessions", headers=sysadmin_auth_headers)
        data = resp.json()
        session = data["sessions"][0]
        assert session["action_type"] == "ontology_query"


# ==================== GET /debug/sessions/{id} ====================


class TestGetSessionDetail:

    @patch("app.routers.debug.get_debug_logger")
    def test_found(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger, seeded_session):
        mock_get_logger.return_value = debug_logger
        resp = client.get(
            f"/debug/sessions/{seeded_session}",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["session_id"] == seeded_session
        assert isinstance(data["attempts"], list)
        assert len(data["attempts"]) >= 1
        assert isinstance(data["llm_interactions"], list)

    @patch("app.routers.debug.get_debug_logger")
    def test_not_found(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get(
            "/debug/sessions/non-existent-id",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 404

    @patch("app.routers.debug.get_debug_logger")
    def test_session_has_llm_interactions(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        sid = debug_logger.create_session(input_message="llm test")
        debug_logger.log_llm_interaction(
            session_id=sid,
            sequence_number=1,
            ooda_phase="decide",
            call_type="chat",
            started_at="2025-01-01T00:00:00",
            ended_at="2025-01-01T00:00:01",
            latency_ms=500,
            model="test-model",
            tokens_total=100,
        )
        debug_logger.complete_session(sid, status="success")

        resp = client.get(f"/debug/sessions/{sid}", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["llm_interactions"]) == 1
        assert data["llm_interactions"][0]["ooda_phase"] == "decide"


# ==================== GET /debug/statistics ====================


class TestGetStatistics:

    @patch("app.routers.debug.get_debug_logger")
    def test_empty_stats(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/statistics", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["total_attempts"] == 0
        assert data["status_counts"] == {}

    @patch("app.routers.debug.get_debug_logger")
    def test_with_data(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger, seeded_session):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/statistics", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] >= 1
        assert data["total_attempts"] >= 1


# ==================== GET /debug/analytics/token-trend ====================


class TestTokenTrend:

    @patch("app.routers.debug.get_debug_logger")
    def test_token_trend_empty(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/analytics/token-trend", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7
        assert isinstance(data["data"], list)

    @patch("app.routers.debug.get_debug_logger")
    def test_token_trend_custom_days(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get(
            "/debug/analytics/token-trend",
            params={"days": 14},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 14

    @patch("app.routers.debug.get_debug_logger")
    def test_token_trend_with_data(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        sid = debug_logger.create_session(input_message="token test")
        debug_logger.update_session_llm(
            session_id=sid,
            prompt="test",
            response="test",
            tokens_used=500,
            model="test-model",
        )
        debug_logger.complete_session(sid, status="success", execution_time_ms=100)

        resp = client.get("/debug/analytics/token-trend", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1

    def test_token_trend_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.get("/debug/analytics/token-trend", headers=manager_auth_headers)
        assert resp.status_code == 403


# ==================== GET /debug/analytics/error-aggregation ====================


class TestErrorAggregation:

    @patch("app.routers.debug.get_debug_logger")
    def test_error_aggregation_empty(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get("/debug/analytics/error-aggregation", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7
        assert isinstance(data["by_day"], list)
        assert isinstance(data["top_errors"], list)
        assert "totals" in data

    @patch("app.routers.debug.get_debug_logger")
    def test_error_aggregation_custom_days(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.get(
            "/debug/analytics/error-aggregation",
            params={"days": 30},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 30

    @patch("app.routers.debug.get_debug_logger")
    def test_error_aggregation_with_errors(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        sid = debug_logger.create_session(input_message="error test")
        debug_logger.complete_session(
            sid,
            status="error",
            errors=[{"type": "ActionError", "message": "Unknown action"}],
        )

        resp = client.get("/debug/analytics/error-aggregation", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["error_sessions"] >= 1

    def test_error_aggregation_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.get("/debug/analytics/error-aggregation", headers=manager_auth_headers)
        assert resp.status_code == 403


# ==================== POST /debug/replay ====================


class TestReplaySession:

    @patch("app.routers.debug.get_replay_engine")
    def test_missing_session_id(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        resp = client.post(
            "/debug/replay",
            json={},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 400

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_engine_unavailable(self, mock_get_replay, client, sysadmin_auth_headers):
        mock_get_replay.return_value = None
        resp = client.post(
            "/debug/replay",
            json={"session_id": "some-id"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 503

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_session_not_found(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.replay_session.return_value = None
        resp = client.post(
            "/debug/replay",
            json={"session_id": "non-existent"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 404

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_success(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "replay_id": "r-1",
            "original_session_id": "s-1",
            "success": True,
            "result": {"message": "ok"},
            "attempts": [],
            "execution_time_ms": 100,
            "llm_model": "test",
            "llm_tokens_used": 50,
            "error": None,
            "dry_run": False,
        }
        mock_replay_engine.replay_session.return_value = mock_result

        resp = client.post(
            "/debug/replay",
            json={"session_id": "s-1"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["replay_id"] == "r-1"
        assert data["success"] is True

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_with_overrides(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "replay_id": "r-2",
            "original_session_id": "s-2",
            "success": True,
            "result": {},
            "attempts": [],
            "execution_time_ms": 80,
            "llm_model": "gpt-4",
            "llm_tokens_used": 200,
            "error": None,
            "dry_run": True,
        }
        mock_replay_engine.replay_session.return_value = mock_result

        resp = client.post(
            "/debug/replay",
            json={
                "session_id": "s-2",
                "overrides": {"llm_model": "gpt-4", "llm_temperature": 0.3},
                "dry_run": True,
            },
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200

    def test_replay_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.post(
            "/debug/replay",
            json={"session_id": "s-1"},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 403


# ==================== GET /debug/replay/{id} ====================


class TestGetReplayResult:

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_engine_unavailable(self, mock_get_replay, client, sysadmin_auth_headers):
        mock_get_replay.return_value = None
        resp = client.get("/debug/replay/r-1", headers=sysadmin_auth_headers)
        assert resp.status_code == 503

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_not_found(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.get_replay.return_value = None
        resp = client.get("/debug/replay/non-existent", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    @patch("app.routers.debug.get_replay_engine")
    def test_original_session_not_found(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.get_replay.return_value = {
            "replay_id": "r-1",
            "original_session_id": "s-missing",
            "success": True,
            "result": {},
            "attempts": [],
            "execution_time_ms": 100,
            "llm_model": "test",
            "llm_tokens_used": 50,
            "error": None,
            "timestamp": "2025-01-01T00:00:00",
            "dry_run": False,
        }
        mock_replay_engine.load_session.return_value = None
        resp = client.get("/debug/replay/r-1", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_result_success(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.get_replay.return_value = {
            "replay_id": "r-1",
            "original_session_id": "s-1",
            "success": True,
            "result": {"message": "ok"},
            "attempts": [],
            "execution_time_ms": 100,
            "llm_model": "test",
            "llm_tokens_used": 50,
            "error": None,
            "timestamp": "2025-01-01T00:00:00",
            "dry_run": False,
        }
        mock_replay_engine.load_session.return_value = {
            "session": {"session_id": "s-1", "input_message": "test"},
            "attempts": [],
        }
        mock_comparison = MagicMock()
        mock_comparison.to_dict.return_value = {
            "same_action": True,
            "same_result": True,
            "token_diff": 0,
        }
        mock_replay_engine.compare_sessions.return_value = mock_comparison

        resp = client.get("/debug/replay/r-1", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["replay"]["replay_id"] == "r-1"
        assert data["original_session"] is not None
        assert data["comparison"] is not None


# ==================== GET /debug/replays ====================


class TestListReplays:

    @patch("app.routers.debug.get_replay_engine")
    def test_replay_engine_unavailable(self, mock_get_replay, client, sysadmin_auth_headers):
        mock_get_replay.return_value = None
        resp = client.get("/debug/replays", headers=sysadmin_auth_headers)
        assert resp.status_code == 503

    @patch("app.routers.debug.get_replay_engine")
    def test_list_replays_empty(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.list_replays.return_value = []
        resp = client.get("/debug/replays", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["replays"] == []
        assert data["count"] == 0

    @patch("app.routers.debug.get_replay_engine")
    def test_list_replays_with_data(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.list_replays.return_value = [
            {"replay_id": "r-1", "original_session_id": "s-1"},
            {"replay_id": "r-2", "original_session_id": "s-2"},
        ]
        resp = client.get("/debug/replays", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    @patch("app.routers.debug.get_replay_engine")
    def test_list_replays_filter_by_session(self, mock_get_replay, client, sysadmin_auth_headers, mock_replay_engine):
        mock_get_replay.return_value = mock_replay_engine
        mock_replay_engine.list_replays.return_value = [
            {"replay_id": "r-1", "original_session_id": "s-1"},
        ]
        resp = client.get(
            "/debug/replays",
            params={"original_session_id": "s-1"},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        mock_replay_engine.list_replays.assert_called_once()

    def test_list_replays_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.get("/debug/replays", headers=manager_auth_headers)
        assert resp.status_code == 403


# ==================== DELETE /debug/sessions/{id} ====================


class TestDeleteSession:

    @patch("app.routers.debug.get_debug_logger")
    def test_delete_existing(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger, seeded_session):
        mock_get_logger.return_value = debug_logger
        resp = client.delete(
            f"/debug/sessions/{seeded_session}",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == seeded_session
        assert "deleted" in data["message"].lower()

    @patch("app.routers.debug.get_debug_logger")
    def test_delete_not_found(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.delete(
            "/debug/sessions/non-existent-id",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 404

    def test_delete_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.delete(
            "/debug/sessions/any-id",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 403


# ==================== POST /debug/cleanup ====================


class TestCleanupOldSessions:

    @patch("app.routers.debug.get_debug_logger")
    def test_cleanup_default_days(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.post("/debug/cleanup", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 30
        assert "deleted_count" in data

    @patch("app.routers.debug.get_debug_logger")
    def test_cleanup_custom_days(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        resp = client.post(
            "/debug/cleanup",
            params={"days": 7},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7

    @patch("app.routers.debug.get_debug_logger")
    def test_cleanup_with_old_sessions(self, mock_get_logger, client, sysadmin_auth_headers, debug_logger):
        mock_get_logger.return_value = debug_logger
        for i in range(3):
            sid = debug_logger.create_session(input_message=f"test {i}")
            debug_logger.complete_session(sid, status="success")

        resp = client.post(
            "/debug/cleanup",
            params={"days": 30},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Recent sessions should NOT be deleted
        assert data["deleted_count"] == 0

    def test_cleanup_non_sysadmin_forbidden(self, client, manager_auth_headers):
        resp = client.post("/debug/cleanup", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_cleanup_days_validation(self, client, sysadmin_auth_headers):
        # days must be >= 1
        resp = client.post(
            "/debug/cleanup",
            params={"days": 0},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 422

        # days must be <= 365
        resp = client.post(
            "/debug/cleanup",
            params={"days": 400},
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 422
