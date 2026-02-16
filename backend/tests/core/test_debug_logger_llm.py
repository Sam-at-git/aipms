"""
Tests for DebugLogger LLM interaction tracking (SPEC-30).
"""
import os
import tempfile
import pytest
from core.ai.debug_logger import DebugLogger, LLMInteraction


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
def debug_logger(temp_db):
    """Create a DebugLogger with temp file DB for testing."""
    return DebugLogger(db_path=temp_db)


@pytest.fixture
def session_id(debug_logger):
    """Create a test session and return its ID."""
    return debug_logger.create_session(input_message="test query")


class TestLLMInteractionDataclass:
    def test_to_dict(self):
        interaction = LLMInteraction(
            interaction_id="int-1",
            session_id="sess-1",
            sequence_number=0,
            ooda_phase="orient",
            call_type="topic_relevance",
            started_at="2025-01-01T00:00:00",
            ended_at="2025-01-01T00:00:01",
            latency_ms=333,
            model="deepseek-chat",
            prompt='[{"role": "user", "content": "test"}]',
            response="continuation",
            tokens_input=100,
            tokens_output=5,
            tokens_total=105,
            temperature=0.0,
            success=True,
        )
        d = interaction.to_dict()
        assert d["interaction_id"] == "int-1"
        assert d["ooda_phase"] == "orient"
        assert d["call_type"] == "topic_relevance"
        assert d["latency_ms"] == 333
        assert d["tokens_total"] == 105
        assert d["success"] is True
        assert d["error"] is None


class TestLogLLMInteraction:
    def test_log_and_get(self, debug_logger, session_id):
        iid = debug_logger.log_llm_interaction(
            session_id=session_id,
            sequence_number=0,
            ooda_phase="orient",
            call_type="topic_relevance",
            started_at="2025-01-01T00:00:00",
            ended_at="2025-01-01T00:00:01",
            latency_ms=333,
            model="deepseek-chat",
            prompt="test prompt",
            response="continuation",
            tokens_input=100,
            tokens_output=5,
            tokens_total=105,
            temperature=0.0,
        )
        assert iid is not None

        interactions = debug_logger.get_llm_interactions(session_id)
        assert len(interactions) == 1
        assert interactions[0].ooda_phase == "orient"
        assert interactions[0].call_type == "topic_relevance"
        assert interactions[0].latency_ms == 333

    def test_ordering_by_sequence(self, debug_logger, session_id):
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=2,
            ooda_phase="act", call_type="format_result",
            started_at="2025-01-01T00:00:03", ended_at="2025-01-01T00:00:04",
            latency_ms=120,
        )
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=0,
            ooda_phase="orient", call_type="topic_relevance",
            started_at="2025-01-01T00:00:00", ended_at="2025-01-01T00:00:01",
            latency_ms=333,
        )
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=1,
            ooda_phase="decide", call_type="chat",
            started_at="2025-01-01T00:00:01", ended_at="2025-01-01T00:00:03",
            latency_ms=850,
        )

        interactions = debug_logger.get_llm_interactions(session_id)
        assert len(interactions) == 3
        assert [i.sequence_number for i in interactions] == [0, 1, 2]
        assert [i.ooda_phase for i in interactions] == ["orient", "decide", "act"]

    def test_empty_session(self, debug_logger, session_id):
        interactions = debug_logger.get_llm_interactions(session_id)
        assert interactions == []

    def test_error_interaction(self, debug_logger, session_id):
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=0,
            ooda_phase="decide", call_type="chat",
            started_at="2025-01-01T00:00:00", ended_at="2025-01-01T00:00:01",
            latency_ms=100,
            success=False,
            error="Connection timeout",
        )

        interactions = debug_logger.get_llm_interactions(session_id)
        assert len(interactions) == 1
        assert interactions[0].success is False
        assert interactions[0].error == "Connection timeout"


class TestCascadeDelete:
    def test_delete_session_deletes_interactions(self, debug_logger, session_id):
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=0,
            ooda_phase="orient", call_type="topic_relevance",
            started_at="2025-01-01T00:00:00", ended_at="2025-01-01T00:00:01",
            latency_ms=100,
        )
        debug_logger.log_llm_interaction(
            session_id=session_id, sequence_number=1,
            ooda_phase="decide", call_type="chat",
            started_at="2025-01-01T00:00:01", ended_at="2025-01-01T00:00:02",
            latency_ms=200,
        )

        assert len(debug_logger.get_llm_interactions(session_id)) == 2
        debug_logger.delete_session(session_id)
        assert len(debug_logger.get_llm_interactions(session_id)) == 0

    def test_cleanup_old_sessions_deletes_interactions(self, debug_logger):
        # Create a session with interactions
        sid = debug_logger.create_session(input_message="old query")
        debug_logger.log_llm_interaction(
            session_id=sid, sequence_number=0,
            ooda_phase="decide", call_type="chat",
            started_at="2025-01-01T00:00:00", ended_at="2025-01-01T00:00:01",
            latency_ms=100,
        )

        # Manually backdate the session
        conn = debug_logger._get_conn()
        try:
            conn.execute(
                "UPDATE debug_sessions SET timestamp = '2020-01-01T00:00:00' WHERE id = ?",
                (sid,)
            )
            conn.commit()
        finally:
            conn.close()

        # Clean up old sessions (older than 1 day)
        deleted = debug_logger.cleanup_old_sessions(days=1)
        assert deleted >= 1
        assert len(debug_logger.get_llm_interactions(sid)) == 0
