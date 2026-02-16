"""
core/ai/llm_call_context.py

Thread-local storage for passing debug session context to LLM call sites.

This allows the LLM service interceptor to know which session and OODA phase
a given LLM call belongs to, without threading the context through every
function signature.
"""
import threading
from typing import Optional, Dict, Any


class LLMCallContext:
    """Thread-local storage for debug session context."""

    _local = threading.local()

    @classmethod
    def begin_session(cls, session_id: str, debug_logger) -> None:
        """
        Called at the start of process_message() to set up context.

        Args:
            session_id: The debug session ID
            debug_logger: DebugLogger instance for recording interactions
        """
        cls._local.session_id = session_id
        cls._local.debug_logger = debug_logger
        cls._local.sequence = 0
        cls._local.ooda_phase = None
        cls._local.call_type = None

    @classmethod
    def before_call(cls, ooda_phase: str, call_type: str) -> None:
        """
        Called before each LLM API call to set phase info.

        Args:
            ooda_phase: Current OODA phase ('orient', 'decide', 'act')
            call_type: Type of LLM call ('topic_relevance', 'chat', 'extract_params',
                       'parse_followup', 'format_result')
        """
        cls._local.ooda_phase = ooda_phase
        cls._local.call_type = call_type

    @classmethod
    def get_current(cls) -> Optional[Dict[str, Any]]:
        """
        Get the current context, or None if no session is active.

        Returns:
            Dict with session_id, ooda_phase, call_type, debug_logger, sequence
            or None if not in a session.
        """
        session_id = getattr(cls._local, 'session_id', None)
        if session_id is None:
            return None

        return {
            'session_id': session_id,
            'ooda_phase': getattr(cls._local, 'ooda_phase', None),
            'call_type': getattr(cls._local, 'call_type', None),
            'debug_logger': getattr(cls._local, 'debug_logger', None),
            'sequence': getattr(cls._local, 'sequence', 0),
        }

    @classmethod
    def next_sequence(cls) -> int:
        """
        Increment and return the next sequence number.

        Returns:
            The next sequence number (0-based)
        """
        current = getattr(cls._local, 'sequence', 0)
        cls._local.sequence = current + 1
        return current

    @classmethod
    def end_session(cls) -> None:
        """Called at the end of process_message() to clean up context."""
        cls._local.session_id = None
        cls._local.debug_logger = None
        cls._local.sequence = 0
        cls._local.ooda_phase = None
        cls._local.call_type = None


__all__ = ["LLMCallContext"]
