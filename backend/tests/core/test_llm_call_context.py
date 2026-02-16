"""
Tests for LLMCallContext (SPEC-31).
"""
import threading
import pytest
from core.ai.llm_call_context import LLMCallContext


class TestLLMCallContextLifecycle:
    def setup_method(self):
        """Ensure clean state before each test."""
        LLMCallContext.end_session()

    def test_no_active_session(self):
        assert LLMCallContext.get_current() is None

    def test_begin_and_get(self):
        LLMCallContext.begin_session("sess-1", "mock_logger")
        ctx = LLMCallContext.get_current()
        assert ctx is not None
        assert ctx["session_id"] == "sess-1"
        assert ctx["debug_logger"] == "mock_logger"
        assert ctx["sequence"] == 0
        assert ctx["ooda_phase"] is None
        assert ctx["call_type"] is None
        LLMCallContext.end_session()

    def test_before_call_sets_phase(self):
        LLMCallContext.begin_session("sess-1", "mock_logger")
        LLMCallContext.before_call("orient", "topic_relevance")
        ctx = LLMCallContext.get_current()
        assert ctx["ooda_phase"] == "orient"
        assert ctx["call_type"] == "topic_relevance"
        LLMCallContext.end_session()

    def test_next_sequence_increments(self):
        LLMCallContext.begin_session("sess-1", "mock_logger")
        assert LLMCallContext.next_sequence() == 0
        assert LLMCallContext.next_sequence() == 1
        assert LLMCallContext.next_sequence() == 2
        LLMCallContext.end_session()

    def test_end_session_clears(self):
        LLMCallContext.begin_session("sess-1", "mock_logger")
        LLMCallContext.before_call("decide", "chat")
        LLMCallContext.next_sequence()
        LLMCallContext.end_session()

        assert LLMCallContext.get_current() is None

    def test_multiple_sessions(self):
        LLMCallContext.begin_session("sess-1", "logger1")
        LLMCallContext.next_sequence()
        LLMCallContext.end_session()

        LLMCallContext.begin_session("sess-2", "logger2")
        ctx = LLMCallContext.get_current()
        assert ctx["session_id"] == "sess-2"
        assert ctx["sequence"] == 0  # Reset
        LLMCallContext.end_session()


class TestThreadIsolation:
    def test_separate_threads_have_separate_contexts(self):
        results = {}

        def thread_fn(thread_id, session_id):
            LLMCallContext.begin_session(session_id, f"logger_{thread_id}")
            LLMCallContext.before_call("decide", "chat")
            seq = LLMCallContext.next_sequence()
            ctx = LLMCallContext.get_current()
            results[thread_id] = {
                "session_id": ctx["session_id"],
                "sequence": seq,
            }
            LLMCallContext.end_session()

        t1 = threading.Thread(target=thread_fn, args=(1, "sess-A"))
        t2 = threading.Thread(target=thread_fn, args=(2, "sess-B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results[1]["session_id"] == "sess-A"
        assert results[2]["session_id"] == "sess-B"
        assert results[1]["sequence"] == 0
        assert results[2]["sequence"] == 0
