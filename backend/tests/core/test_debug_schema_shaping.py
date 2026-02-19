"""
tests/core/test_debug_schema_shaping.py

Tests for SPEC-P07: Schema shaping metadata storage in DebugLogger.
"""
import tempfile
import os
import pytest
from unittest.mock import MagicMock

from core.ai.debug_logger import DebugLogger


@pytest.fixture
def debug_logger():
    """Create a DebugLogger with a temp file DB."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    logger = DebugLogger(db_path=path)
    yield logger
    try:
        os.unlink(path)
    except OSError:
        pass


def _fake_user(user_id=1, role="manager"):
    """Create a fake user object with id and role attributes."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    return user


class TestSchemaShapingStorage:

    def test_session_stores_schema_shaping(self, debug_logger):
        """schema_shaping data is correctly stored and retrieved."""
        session_id = debug_logger.create_session(
            input_message="帮客人办入住",
            user=_fake_user(1, "manager"),
        )

        shaping_data = {
            "strategy": "inference",
            "actions_injected": 8,
            "entities_injected": 4,
            "include_query_schema": False,
            "metadata": {"fallback_chain": []},
        }
        result = debug_logger.update_schema_shaping(session_id, shaping_data)
        assert result is True

        # Retrieve and verify
        session = debug_logger.get_session(session_id)
        assert session is not None
        session_dict = session.to_dict()
        assert session_dict["schema_shaping"] is not None
        assert session_dict["schema_shaping"]["strategy"] == "inference"
        assert session_dict["schema_shaping"]["actions_injected"] == 8
        assert session_dict["schema_shaping"]["entities_injected"] == 4
        assert session_dict["schema_shaping"]["include_query_schema"] is False

    def test_session_without_schema_shaping(self, debug_logger):
        """Sessions without schema shaping have null field."""
        session_id = debug_logger.create_session(
            input_message="test",
            user=_fake_user(1, "cleaner"),
        )
        session = debug_logger.get_session(session_id)
        assert session is not None
        session_dict = session.to_dict()
        assert session_dict["schema_shaping"] is None

    def test_schema_shaping_discovery_strategy(self, debug_logger):
        """Discovery strategy metadata includes indexed_actions."""
        session_id = debug_logger.create_session(
            input_message="入住",
            user=_fake_user(1, "manager"),
        )

        shaping_data = {
            "strategy": "discovery",
            "actions_injected": 0,
            "entities_injected": None,
            "include_query_schema": True,
            "metadata": {"indexed_actions": 29},
        }
        debug_logger.update_schema_shaping(session_id, shaping_data)

        session = debug_logger.get_session(session_id)
        sd = session.to_dict()["schema_shaping"]
        assert sd["strategy"] == "discovery"
        assert sd["actions_injected"] == 0
        assert sd["metadata"]["indexed_actions"] == 29

    def test_schema_shaping_full_strategy_with_fallback(self, debug_logger):
        """Full strategy with fallback chain is stored."""
        session_id = debug_logger.create_session(
            input_message="test",
            user=_fake_user(1, "unknown"),
        )

        shaping_data = {
            "strategy": "full",
            "actions_injected": None,
            "entities_injected": None,
            "include_query_schema": True,
            "metadata": {"fallback_chain": ["discovery_unavailable", "inference_failed"]},
        }
        debug_logger.update_schema_shaping(session_id, shaping_data)

        session = debug_logger.get_session(session_id)
        sd = session.to_dict()["schema_shaping"]
        assert sd["strategy"] == "full"
        assert "discovery_unavailable" in sd["metadata"]["fallback_chain"]
        assert "inference_failed" in sd["metadata"]["fallback_chain"]

    def test_update_schema_shaping_empty_session_id(self, debug_logger):
        """Empty session_id returns False."""
        result = debug_logger.update_schema_shaping("", {"strategy": "full"})
        assert result is False

    def test_update_schema_shaping_nonexistent_session(self, debug_logger):
        """Non-existent session returns False."""
        result = debug_logger.update_schema_shaping(
            "nonexistent-id", {"strategy": "full"}
        )
        assert result is False
