"""
Tests for core/ai/debug_logger.py

DebugLogger comprehensive test suite covering:
- Session creation and management
- Attempt logging
- Query methods (get, list, filter)
- Cleanup and statistics
- Edge cases and error handling
"""
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from core.ai.debug_logger import (
    DebugLogger,
    DebugSession,
    AttemptLog,
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_db():
    """Temporary database path that is cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def memory_db():
    """In-memory database for fast tests."""
    return ":memory:"


@pytest.fixture
def mock_user():
    """Mock user object."""
    user = Mock()
    user.id = 123
    user.role = Mock()
    user.role.value = "receptionist"
    return user


@pytest.fixture
def logger(temp_db):
    """DebugLogger instance with temp database."""
    return DebugLogger(temp_db)


@pytest.fixture
def logger_memory(memory_db):
    """DebugLogger instance with in-memory database."""
    return DebugLogger(memory_db)


# ==================== Test Database Initialization ====================

class TestDebugLoggerInit:
    """Test DebugLogger initialization and database setup."""

    def test_init_with_temp_path(self, temp_db):
        """Test initialization with temporary file path."""
        logger = DebugLogger(temp_db)
        assert logger.db_path == temp_db
        assert os.path.exists(temp_db)

    def test_init_with_memory(self, memory_db):
        """Test initialization with in-memory database."""
        logger = DebugLogger(memory_db)
        assert logger.db_path == memory_db

    def test_init_creates_tables(self, logger):
        """Test that initialization creates required tables."""
        conn = logger._get_conn()
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('debug_sessions', 'attempt_logs')
        """)
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        assert "debug_sessions" in tables
        assert "attempt_logs" in tables

    def test_init_creates_indexes(self, logger):
        """Test that initialization creates required indexes."""
        conn = logger._get_conn()
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index'
            AND name IN (
                'idx_debug_sessions_timestamp',
                'idx_debug_sessions_user',
                'idx_debug_sessions_status',
                'idx_attempt_logs_session'
            )
        """)
        indexes = [row["name"] for row in cursor.fetchall()]
        conn.close()

        assert "idx_debug_sessions_timestamp" in indexes
        assert "idx_debug_sessions_user" in indexes
        assert "idx_debug_sessions_status" in indexes
        assert "idx_attempt_logs_session" in indexes


# ==================== Test Session Creation ====================

class TestSessionCreation:
    """Test session creation and basic operations."""

    def test_create_session_returns_uuid(self, logger):
        """Test that create_session returns a valid UUID."""
        session_id = logger.create_session("Test message")
        assert isinstance(session_id, str)
        # Valid UUID format
        uuid.UUID(session_id)

    def test_create_session_with_user(self, logger, mock_user):
        """Test session creation with user information."""
        session_id = logger.create_session("Test message", mock_user)
        session = logger.get_session(session_id)

        assert session is not None
        assert session.user_id == 123
        assert session.user_role == "receptionist"

    def test_create_session_without_user(self, logger):
        """Test session creation without user information."""
        session_id = logger.create_session("Test message")
        session = logger.get_session(session_id)

        assert session is not None
        assert session.user_id is None
        assert session.user_role is None

    def test_create_session_stores_input_message(self, logger):
        """Test that input message is stored correctly."""
        message = "查询在住客人"
        session_id = logger.create_session(message)
        session = logger.get_session(session_id)

        assert session.input_message == message

    def test_create_session_initial_status(self, logger):
        """Test that new sessions have 'pending' status."""
        session_id = logger.create_session("Test")
        session = logger.get_session(session_id)

        assert session.status == "pending"

    def test_create_session_stores_timestamp(self, logger):
        """Test that session timestamp is set correctly."""
        before = datetime.now()
        session_id = logger.create_session("Test")
        after = datetime.now()

        session = logger.get_session(session_id)
        # session.timestamp is a datetime because from_row parses the ISO string
        timestamp = session.timestamp

        assert before <= timestamp <= after


# ==================== Test Session Updates ====================

class TestSessionUpdates:
    """Test session update operations."""

    def test_update_retrieval(self, logger):
        """Test updating session with retrieval data."""
        session_id = logger.create_session("Test")

        schema = {"entities": ["Guest", "Room"]}
        tools = [{"name": "query", "parameters": {}}]

        result = logger.update_session_retrieval(session_id, schema, tools)
        assert result is True

        session = logger.get_session(session_id)
        assert json.loads(session.retrieved_schema) == schema
        assert json.loads(session.retrieved_tools) == tools

    def test_update_retrieval_partial(self, logger):
        """Test updating only schema or only tools."""
        session_id = logger.create_session("Test")

        logger.update_session_retrieval(session_id, retrieved_schema={"entities": ["Guest"]})
        session = logger.get_session(session_id)
        assert json.loads(session.retrieved_schema) == {"entities": ["Guest"]}
        assert session.retrieved_tools is None

    def test_update_retrieval_nonexistent_session(self, logger):
        """Test updating retrieval for non-existent session."""
        result = logger.update_session_retrieval("fake-id", {}, [])
        assert result is False

    def test_update_llm(self, logger):
        """Test updating session with LLM interaction data."""
        session_id = logger.create_session("Test")

        prompt = "查询房间状态"
        response = '{"action": "ontology_query", ...}'
        tokens = 500
        model = "deepseek-chat"

        result = logger.update_session_llm(session_id, prompt, response, tokens, model)
        assert result is True

        session = logger.get_session(session_id)
        assert session.llm_prompt == prompt
        assert session.llm_response == response
        assert session.llm_tokens_used == tokens
        assert session.llm_model == model

    def test_update_llm_nonexistent_session(self, logger):
        """Test updating LLM for non-existent session."""
        result = logger.update_session_llm("fake-id", "prompt", "response", 100, "model")
        assert result is False


# ==================== Test Session Completion ====================

class TestSessionCompletion:
    """Test session completion operations."""

    def test_complete_session_success(self, logger):
        """Test completing session with success status."""
        session_id = logger.create_session("Test")

        result = {"rows": [{"id": 1, "name": "Room 101"}]}
        success = logger.complete_session(session_id, result, status="success")

        assert success is True

        session = logger.get_session(session_id)
        assert session.status == "success"
        assert json.loads(session.final_result) == result

    def test_complete_session_error(self, logger):
        """Test completing session with error status."""
        session_id = logger.create_session("Test")

        errors = [{"type": "validation_error", "message": "Invalid input"}]
        success = logger.complete_session(
            session_id,
            result=None,
            status="error",
            errors=errors
        )

        assert success is True

        session = logger.get_session(session_id)
        assert session.status == "error"
        assert json.loads(session.errors) == errors

    def test_complete_session_with_execution_time(self, logger):
        """Test completing session with execution time."""
        session_id = logger.create_session("Test")

        success = logger.complete_session(
            session_id,
            result={"status": "ok"},
            status="success",
            execution_time_ms=1500
        )

        assert success is True

        session = logger.get_session(session_id)
        assert session.execution_time_ms == 1500

    def test_complete_session_with_actions(self, logger):
        """Test completing session with executed actions list."""
        session_id = logger.create_session("Test")

        actions = [
            {"action": "ontology_query", "status": "success"},
            {"action": "checkout", "status": "failed"}
        ]

        success = logger.complete_session(
            session_id,
            result={"done": True},
            status="partial",
            actions_executed=actions
        )

        assert success is True

        session = logger.get_session(session_id)
        assert json.loads(session.actions_executed) == actions
        assert session.status == "partial"


# ==================== Test Attempt Logging ====================

class TestAttemptLogging:
    """Test attempt logging operations."""

    def test_log_attempt_success(self, logger):
        """Test logging a successful attempt."""
        session_id = logger.create_session("Test")

        params = {"entity": "Guest", "fields": ["name"]}
        result = {"rows": [{"name": "Alice"}]}

        attempt_id = logger.log_attempt(
            session_id,
            action_name="ontology_query",
            params=params,
            success=True,
            result=result
        )

        assert attempt_id is not None
        uuid.UUID(attempt_id)  # Valid UUID

        attempt = logger.get_attempt(attempt_id)
        assert attempt.session_id == session_id
        assert attempt.action_name == "ontology_query"
        assert attempt.success is True
        assert json.loads(attempt.params) == params
        assert json.loads(attempt.result) == result

    def test_log_attempt_failure(self, logger):
        """Test logging a failed attempt with error."""
        session_id = logger.create_session("Test")

        params = {"entity": "InvalidEntity"}
        error = {"type": "not_found", "message": "Entity not found"}

        attempt_id = logger.log_attempt(
            session_id,
            action_name="ontology_query",
            params=params,
            success=False,
            error=error
        )

        attempt = logger.get_attempt(attempt_id)
        assert attempt.success is False
        assert json.loads(attempt.error) == error
        assert attempt.result is None

    def test_log_attempt_auto_increments_number(self, logger):
        """Test that attempt numbers auto-increment."""
        session_id = logger.create_session("Test")

        id1 = logger.log_attempt(session_id, "action1", {}, True)
        id2 = logger.log_attempt(session_id, "action2", {}, True)
        id3 = logger.log_attempt(session_id, "action3", {}, True)

        attempt1 = logger.get_attempt(id1)
        attempt2 = logger.get_attempt(id2)
        attempt3 = logger.get_attempt(id3)

        assert attempt1.attempt_number == 0
        assert attempt2.attempt_number == 1
        assert attempt3.attempt_number == 2

    def test_log_attempt_custom_number(self, logger):
        """Test logging attempt with custom attempt number."""
        session_id = logger.create_session("Test")

        attempt_id = logger.log_attempt(
            session_id,
            "test_action",
            {},
            True,
            attempt_number=5
        )

        attempt = logger.get_attempt(attempt_id)
        assert attempt.attempt_number == 5

    def test_log_attempt_nonexistent_session(self, logger):
        """Test logging attempt for non-existent session."""
        attempt_id = logger.log_attempt(
            "fake-session-id",
            "test_action",
            {},
            True
        )

        assert attempt_id is None

    def test_get_attempts_for_session(self, logger):
        """Test retrieving all attempts for a session."""
        session_id = logger.create_session("Test")

        logger.log_attempt(session_id, "action1", {}, True)
        logger.log_attempt(session_id, "action2", {}, False)
        logger.log_attempt(session_id, "action3", {}, True)

        attempts = logger.get_attempts(session_id)

        assert len(attempts) == 3
        assert attempts[0].attempt_number == 0
        assert attempts[1].attempt_number == 1
        assert attempts[2].attempt_number == 2

    def test_get_attempts_empty_session(self, logger):
        """Test getting attempts for session with no attempts."""
        session_id = logger.create_session("Test")
        attempts = logger.get_attempts(session_id)
        assert attempts == []


# ==================== Test Query Methods ====================

class TestQueryMethods:
    """Test query methods for retrieving sessions and attempts."""

    def test_get_session_found(self, logger):
        """Test getting an existing session."""
        session_id = logger.create_session("Test")
        session = logger.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id
        assert session.input_message == "Test"

    def test_get_session_not_found(self, logger):
        """Test getting a non-existent session."""
        session = logger.get_session("fake-id")
        assert session is None

    def test_list_sessions_all(self, logger):
        """Test listing all sessions."""
        logger.create_session("Message 1")
        logger.create_session("Message 2")
        logger.create_session("Message 3")

        sessions = logger.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_with_limit(self, logger):
        """Test listing sessions with limit."""
        for i in range(10):
            logger.create_session(f"Message {i}")

        sessions = logger.list_sessions(limit=5)
        assert len(sessions) == 5

    def test_list_sessions_with_offset(self, logger):
        """Test listing sessions with offset."""
        for i in range(10):
            logger.create_session(f"Message {i}")

        sessions = logger.list_sessions(limit=5, offset=5)
        assert len(sessions) == 5

    def test_list_sessions_ordering(self, logger):
        """Test that sessions are ordered by timestamp DESC."""
        id1 = logger.create_session("First")
        id2 = logger.create_session("Second")
        id3 = logger.create_session("Third")

        sessions = logger.list_sessions()

        # Most recent first
        assert sessions[0].session_id == id3
        assert sessions[1].session_id == id2
        assert sessions[2].session_id == id1

    def test_list_sessions_filter_by_user_id(self, logger, mock_user):
        """Test filtering sessions by user ID."""
        logger.create_session("User 1 message", mock_user)

        other_user = Mock()
        other_user.id = 456
        other_user.role = Mock()
        other_user.role.value = "manager"
        logger.create_session("User 2 message", other_user)

        sessions = logger.list_sessions(user_id=123)
        assert len(sessions) == 1
        assert sessions[0].user_id == 123

    def test_list_sessions_filter_by_status(self, logger):
        """Test filtering sessions by status."""
        s1 = logger.create_session("Success session")
        s2 = logger.create_session("Error session")
        s3 = logger.create_session("Another success")

        logger.complete_session(s1, {"ok": True}, "success")
        logger.complete_session(s2, None, "error")
        logger.complete_session(s3, {"ok": True}, "success")

        sessions = logger.list_sessions(status="success")
        assert len(sessions) == 2

        error_sessions = logger.list_sessions(status="error")
        assert len(error_sessions) == 1

    def test_get_attempt_found(self, logger):
        """Test getting an existing attempt."""
        session_id = logger.create_session("Test")
        attempt_id = logger.log_attempt(session_id, "test_action", {}, True)

        attempt = logger.get_attempt(attempt_id)
        assert attempt is not None
        assert attempt.attempt_id == attempt_id

    def test_get_attempt_not_found(self, logger):
        """Test getting a non-existent attempt."""
        attempt = logger.get_attempt("fake-attempt-id")
        assert attempt is None


# ==================== Test Session Deletion ====================

class TestSessionDeletion:
    """Test session deletion operations."""

    def test_delete_session(self, logger):
        """Test deleting a session."""
        session_id = logger.create_session("Test")

        # Verify it exists
        assert logger.get_session(session_id) is not None

        # Delete it
        result = logger.delete_session(session_id)
        assert result is True

        # Verify it's gone
        assert logger.get_session(session_id) is None

    def test_delete_session_with_attempts(self, logger):
        """Test that deleting a session also deletes its attempts."""
        session_id = logger.create_session("Test")
        logger.log_attempt(session_id, "action1", {}, True)
        logger.log_attempt(session_id, "action2", {}, True)

        # Verify attempts exist
        assert len(logger.get_attempts(session_id)) == 2

        # Delete session
        logger.delete_session(session_id)

        # Verify attempts are also deleted
        assert len(logger.get_attempts(session_id)) == 0

    def test_delete_nonexistent_session(self, logger):
        """Test deleting a non-existent session."""
        result = logger.delete_session("fake-id")
        assert result is False


# ==================== Test Cleanup ====================

class TestCleanup:
    """Test cleanup operations."""

    def test_cleanup_old_sessions(self, logger):
        """Test cleaning up old sessions."""
        # Create a session
        session_id = logger.create_session("Old session")

        # Manually set timestamp to old date
        conn = logger._get_conn()
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        conn.execute(
            "UPDATE debug_sessions SET timestamp = ? WHERE id = ?",
            (old_date, session_id)
        )
        conn.commit()
        conn.close()

        # Run cleanup
        deleted = logger.cleanup_old_sessions(days=30)

        assert deleted == 1
        assert logger.get_session(session_id) is None

    def test_cleanup_keeps_recent_sessions(self, logger):
        """Test that cleanup keeps recent sessions."""
        session_id = logger.create_session("Recent session")

        deleted = logger.cleanup_old_sessions(days=30)

        assert deleted == 0
        assert logger.get_session(session_id) is not None

    def test_cleanup_custom_retention(self, logger):
        """Test cleanup with custom retention days."""
        session_id = logger.create_session("Old session")

        conn = logger._get_conn()
        old_date = (datetime.now() - timedelta(days=15)).isoformat()
        conn.execute(
            "UPDATE debug_sessions SET timestamp = ? WHERE id = ?",
            (old_date, session_id)
        )
        conn.commit()
        conn.close()

        # Clean up after 10 days
        deleted = logger.cleanup_old_sessions(days=10)

        assert deleted == 1


# ==================== Test Statistics ====================

class TestStatistics:
    """Test statistics methods."""

    def test_get_statistics(self, logger):
        """Test getting debug logger statistics."""
        # Create some sessions
        s1 = logger.create_session("Success")
        s2 = logger.create_session("Error")
        s3 = logger.create_session("Pending")

        logger.log_attempt(s1, "action", {}, True)
        logger.log_attempt(s1, "action", {}, True)
        logger.log_attempt(s2, "action", {}, False)

        logger.complete_session(s1, {"ok": True}, "success")
        logger.complete_session(s2, None, "error")
        # s3 left as pending

        stats = logger.get_statistics()

        assert stats["total_sessions"] == 3
        assert stats["total_attempts"] == 3
        assert stats["status_counts"]["success"] == 1
        assert stats["status_counts"]["error"] == 1
        assert stats["status_counts"]["pending"] == 1

    def test_get_statistics_empty(self, logger):
        """Test statistics when logger is empty."""
        stats = logger.get_statistics()

        assert stats["total_sessions"] == 0
        assert stats["total_attempts"] == 0
        assert stats["status_counts"] == {}


# ==================== Test Export ====================

class TestExport:
    """Test export functionality."""

    def test_export_session(self, logger):
        """Test exporting a complete session."""
        session_id = logger.create_session("Test message")

        logger.update_session_llm(session_id, "prompt", "response", 100, "model")

        attempt_id = logger.log_attempt(
            session_id,
            "test_action",
            {"param": "value"},
            True,
            result={"status": "ok"}
        )

        logger.complete_session(session_id, {"done": True}, "success")

        exported = logger.export_session(session_id)

        assert exported is not None
        assert "session" in exported
        assert "attempts" in exported

        assert exported["session"]["input_message"] == "Test message"
        assert exported["session"]["status"] == "success"
        assert len(exported["attempts"]) == 1
        assert exported["attempts"][0]["action_name"] == "test_action"

    def test_export_nonexistent_session(self, logger):
        """Test exporting a non-existent session."""
        exported = logger.export_session("fake-id")
        assert exported is None


# ==================== Test Data Models ====================

class TestDebugSession:
    """Test DebugSession dataclass methods."""

    def test_from_row(self):
        """Test creating DebugSession from database row."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT 'test-id' as id, '2026-02-07T12:00:00' as timestamp,
                   123 as user_id, 'receptionist' as user_role,
                   'Test message' as input_message, 'pending' as status,
                   NULL as retrieved_schema, NULL as retrieved_tools,
                   NULL as llm_prompt, NULL as llm_response,
                   NULL as llm_tokens_used, NULL as llm_model,
                   NULL as actions_executed, NULL as execution_time_ms,
                   NULL as final_result, NULL as errors, NULL as metadata
        """).fetchone()

        session = DebugSession.from_row(row)

        assert session.session_id == "test-id"
        assert session.user_id == 123
        assert session.user_role == "receptionist"
        assert session.input_message == "Test message"

    def test_to_dict(self, temp_db):
        """Test converting DebugSession to dictionary."""
        logger = DebugLogger(temp_db)
        session_id = logger.create_session("Test")
        session = logger.get_session(session_id)

        data = session.to_dict()

        assert data["session_id"] == session_id
        assert data["input_message"] == "Test"
        assert isinstance(data["timestamp"], str)
        assert data["retrieved_schema"] is None


class TestAttemptLog:
    """Test AttemptLog dataclass methods."""

    def test_from_row(self):
        """Test creating AttemptLog from database row."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT 'attempt-id' as attempt_id, 'session-id' as session_id,
                   0 as attempt_number, 'test_action' as action_name,
                   '{"param": "value"}' as params, 1 as success,
                   NULL as error, '{"result": "ok"}' as result,
                   '2026-02-07T12:00:00' as timestamp
        """).fetchone()

        attempt = AttemptLog.from_row(row)

        assert attempt.attempt_id == "attempt-id"
        assert attempt.session_id == "session-id"
        assert attempt.attempt_number == 0
        assert attempt.success is True
        assert json.loads(attempt.params) == {"param": "value"}

    def test_to_dict(self, temp_db):
        """Test converting AttemptLog to dictionary."""
        logger = DebugLogger(temp_db)
        session_id = logger.create_session("Test")
        attempt_id = logger.log_attempt(
            session_id,
            "test_action",
            {"param": "value"},
            True,
            result={"ok": True}
        )

        attempt = logger.get_attempt(attempt_id)
        data = attempt.to_dict()

        assert data["attempt_id"] == attempt_id
        assert data["action_name"] == "test_action"
        assert data["params"] == {"param": "value"}
        assert data["result"] == {"ok": True}


# ==================== Test Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_json_fields(self, logger):
        """Test handling of empty JSON fields."""
        session_id = logger.create_session("Test")

        # Update with empty dicts/lists
        logger.update_session_retrieval(session_id, {}, [])
        logger.complete_session(
            session_id,
            result={},
            status="success",
            actions_executed=[],
            errors=[]
        )

        session = logger.get_session(session_id)

        assert json.loads(session.retrieved_schema) == {}
        assert json.loads(session.retrieved_tools) == []
        assert json.loads(session.final_result) == {}

    def test_large_json_data(self, logger):
        """Test handling of large JSON data."""
        session_id = logger.create_session("Test")

        large_schema = {
            "entities": [f"Entity{i}" for i in range(1000)],
            "fields": {f"field{i}": f"value{i}" for i in range(1000)}
        }

        logger.update_session_retrieval(session_id, large_schema)
        session = logger.get_session(session_id)

        parsed = json.loads(session.retrieved_schema)
        assert len(parsed["entities"]) == 1000

    def test_unicode_content(self, logger):
        """Test handling of unicode content."""
        message = "测试中文消息 🏨"
        session_id = logger.create_session(message)

        session = logger.get_session(session_id)
        assert session.input_message == message

    def test_special_characters_in_params(self, logger):
        """Test handling of special characters in parameters."""
        session_id = logger.create_session("Test")

        params = {
            "query": "SELECT * FROM 'table'; DROP TABLE--",
            "path": "../../../etc/passwd",
            "script": "<script>alert('xss')</script>"
        }

        attempt_id = logger.log_attempt(session_id, "test", params, True)

        attempt = logger.get_attempt(attempt_id)
        assert json.loads(attempt.params) == params

    def test_null_values_in_db(self, logger):
        """Test that NULL values are handled correctly."""
        session_id = logger.create_session("Test")

        session = logger.get_session(session_id)
        assert session.retrieved_schema is None
        assert session.llm_prompt is None
        assert session.final_result is None
        assert session.errors is None

    def test_concurrent_session_creation(self, logger):
        """Test creating multiple sessions concurrently."""
        import threading

        session_ids = []

        def create_session(msg):
            sid = logger.create_session(msg)
            session_ids.append(sid)

        threads = [
            threading.Thread(target=create_session, args=(f"Message {i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(session_ids) == 10
        assert len(set(session_ids)) == 10  # All unique
