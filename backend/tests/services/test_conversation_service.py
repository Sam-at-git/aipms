"""
Comprehensive tests for ConversationService.

Tests all methods including save, retrieval, pagination, search,
statistics, export, and edge cases like invalid JSON lines.
"""
import json
import pytest
from datetime import datetime, date, timedelta

from app.services.conversation_service import (
    ConversationService,
    ConversationMessage,
    MessageContext,
    DateTimeEncoder,
)


@pytest.fixture
def service(tmp_path):
    """Create a ConversationService with tmp_path storage."""
    return ConversationService(base_dir=str(tmp_path))


@pytest.fixture
def populated_service(service):
    """Service pre-loaded with several message pairs across topics."""
    service.save_message_pair(
        user_id=1,
        user_content="Hello",
        assistant_content="Hi there!",
        topic_id="topic-a",
        actions=[{"action_type": "greet"}],
    )
    service.save_message_pair(
        user_id=1,
        user_content="Show rooms",
        assistant_content="Here are the rooms.",
        topic_id="topic-b",
        actions=[{"action_type": "ontology_query"}],
    )
    return service


# ========== DateTimeEncoder ==========


class TestDateTimeEncoder:
    """Tests for the custom JSON encoder."""

    def test_encodes_datetime(self):
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = json.dumps({"ts": dt}, cls=DateTimeEncoder)
        assert "2025-01-15T10:30:00" in result

    def test_encodes_date(self):
        d = date(2025, 1, 15)
        result = json.dumps({"d": d}, cls=DateTimeEncoder)
        assert "2025-01-15" in result

    def test_raises_for_unsupported_type(self):
        with pytest.raises(TypeError):
            json.dumps({"x": set()}, cls=DateTimeEncoder)


# ========== ConversationMessage ==========


class TestConversationMessage:
    """Tests for message serialization / deserialization."""

    def test_to_dict_minimal(self):
        msg = ConversationMessage(
            id="m1",
            timestamp="2025-01-15T10:00:00",
            role="user",
            content="hello",
        )
        d = msg.to_dict()
        assert d["id"] == "m1"
        assert "actions" not in d
        assert "context" not in d
        assert "result_data" not in d

    def test_to_dict_full(self):
        msg = ConversationMessage(
            id="m2",
            timestamp="2025-01-15T10:00:00",
            role="assistant",
            content="hi",
            actions=[{"action_type": "greet"}],
            context=MessageContext(topic_id="t1", is_followup=True, parent_message_id="m1"),
            result_data={"key": "value"},
        )
        d = msg.to_dict()
        assert d["actions"] == [{"action_type": "greet"}]
        assert d["context"]["topic_id"] == "t1"
        assert d["context"]["is_followup"] is True
        assert d["result_data"]["key"] == "value"

    def test_from_dict_minimal(self):
        data = {
            "id": "m1",
            "timestamp": "2025-01-15T10:00:00",
            "role": "user",
            "content": "test",
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.id == "m1"
        assert msg.context is None
        assert msg.actions is None
        assert msg.result_data is None

    def test_from_dict_with_context(self):
        data = {
            "id": "m2",
            "timestamp": "2025-01-15T10:00:00",
            "role": "assistant",
            "content": "reply",
            "context": {
                "topic_id": "t1",
                "is_followup": False,
                "parent_message_id": "m1",
            },
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.context.topic_id == "t1"
        assert msg.context.parent_message_id == "m1"


# ========== save_message ==========


class TestSaveMessage:
    """Tests for save_message()."""

    def test_save_and_read_back(self, service):
        msg = ConversationMessage(
            id="msg-1",
            timestamp=datetime.now().isoformat(),
            role="user",
            content="test content",
        )
        saved = service.save_message(user_id=1, message=msg)
        assert saved.id == "msg-1"

        messages = service.get_messages_by_date(1, datetime.now().strftime("%Y-%m-%d"))
        assert len(messages) == 1
        assert messages[0].content == "test content"

    def test_auto_generates_id(self, service):
        msg = ConversationMessage(
            id="",
            timestamp=datetime.now().isoformat(),
            role="user",
            content="no id",
        )
        saved = service.save_message(user_id=1, message=msg)
        assert saved.id != ""
        assert len(saved.id) > 0

    def test_auto_generates_timestamp(self, service):
        msg = ConversationMessage(
            id="msg-auto-ts",
            timestamp="",
            role="user",
            content="no timestamp",
        )
        saved = service.save_message(user_id=1, message=msg)
        assert saved.timestamp != ""


# ========== save_message_pair ==========


class TestSaveMessagePair:
    """Tests for save_message_pair()."""

    def test_basic_pair(self, service):
        user_msg, asst_msg = service.save_message_pair(
            user_id=1,
            user_content="hi",
            assistant_content="hello",
        )
        assert user_msg.role == "user"
        assert asst_msg.role == "assistant"
        assert user_msg.content == "hi"
        assert asst_msg.content == "hello"

    def test_pair_with_topic_and_actions(self, service):
        user_msg, asst_msg = service.save_message_pair(
            user_id=1,
            user_content="query rooms",
            assistant_content="here are rooms",
            actions=[{"action_type": "ontology_query"}],
            topic_id="t1",
            is_followup=True,
            parent_message_id="parent-1",
        )
        assert user_msg.context.topic_id == "t1"
        assert user_msg.context.is_followup is True
        assert user_msg.context.parent_message_id == "parent-1"
        assert asst_msg.actions == [{"action_type": "ontology_query"}]
        assert asst_msg.context.parent_message_id == user_msg.id

    def test_pair_with_result_data(self, service):
        _, asst_msg = service.save_message_pair(
            user_id=1,
            user_content="q",
            assistant_content="a",
            result_data={"rooms": [{"number": "101"}]},
        )
        assert asst_msg.result_data == {"rooms": [{"number": "101"}]}

    def test_pair_persists(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        messages, has_more = service.get_messages(user_id=1)
        assert len(messages) == 2
        assert not has_more


# ========== get_messages ==========


class TestGetMessages:
    """Tests for get_messages() with pagination."""

    def test_empty_user(self, service):
        messages, has_more = service.get_messages(user_id=999)
        assert messages == []
        assert has_more is False

    def test_limit(self, service):
        for i in range(5):
            service.save_message_pair(
                user_id=1,
                user_content=f"q{i}",
                assistant_content=f"a{i}",
            )
        # 10 messages total, limit to 4
        messages, has_more = service.get_messages(user_id=1, limit=4)
        assert len(messages) == 4
        assert has_more is True

    def test_before_parameter(self, service):
        # Save messages with known timestamps
        now = datetime.now()
        msg1 = ConversationMessage(
            id="msg-old",
            timestamp=(now - timedelta(hours=2)).isoformat(),
            role="user",
            content="old message",
        )
        msg2 = ConversationMessage(
            id="msg-new",
            timestamp=now.isoformat(),
            role="user",
            content="new message",
        )
        service.save_message(user_id=1, message=msg1)
        service.save_message(user_id=1, message=msg2)

        # Get messages before msg2's timestamp
        messages, has_more = service.get_messages(
            user_id=1, before=now.isoformat()
        )
        assert len(messages) == 1
        assert messages[0].id == "msg-old"

    def test_returns_oldest_first(self, service):
        service.save_message_pair(
            user_id=1,
            user_content="first",
            assistant_content="reply-first",
        )
        messages, _ = service.get_messages(user_id=1)
        assert messages[0].content == "first"


# ========== get_messages_by_date ==========


class TestGetMessagesByDate:
    """Tests for get_messages_by_date()."""

    def test_returns_messages_for_date(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        today = datetime.now().strftime("%Y-%m-%d")
        messages = service.get_messages_by_date(user_id=1, date_str=today)
        assert len(messages) == 2

    def test_returns_empty_for_missing_date(self, service):
        messages = service.get_messages_by_date(user_id=1, date_str="2000-01-01")
        assert messages == []


# ========== get_context_messages ==========


class TestGetContextMessages:
    """Tests for get_context_messages()."""

    def test_empty_user(self, service):
        ctx = service.get_context_messages(user_id=999)
        assert ctx == []

    def test_without_topic_id(self, populated_service):
        ctx = populated_service.get_context_messages(user_id=1, max_rounds=2)
        # max_rounds=2 means up to 4 messages from the most recent
        assert len(ctx) == 4

    def test_with_matching_topic_id(self, populated_service):
        ctx = populated_service.get_context_messages(
            user_id=1, topic_id="topic-a", max_rounds=5
        )
        assert len(ctx) == 2
        assert ctx[0].content == "Hello"

    def test_with_nonexistent_topic_falls_back(self, populated_service):
        # topic_id doesn't match any message; falls back to recent messages
        ctx = populated_service.get_context_messages(
            user_id=1, topic_id="nonexistent", max_rounds=2
        )
        assert len(ctx) == 4

    def test_max_rounds_limits_topic_messages(self, service):
        # Create many messages with same topic
        for i in range(5):
            service.save_message_pair(
                user_id=1,
                user_content=f"q{i}",
                assistant_content=f"a{i}",
                topic_id="t1",
            )
        ctx = service.get_context_messages(user_id=1, topic_id="t1", max_rounds=2)
        assert len(ctx) == 4  # 2 rounds = 4 messages


# ========== search_messages ==========


class TestSearchMessages:
    """Tests for search_messages()."""

    def test_basic_keyword_search(self, populated_service):
        results = populated_service.search_messages(user_id=1, keyword="rooms")
        assert len(results) >= 1
        assert any("rooms" in r.content.lower() for r in results)

    def test_search_case_insensitive(self, populated_service):
        results = populated_service.search_messages(user_id=1, keyword="HELLO")
        assert len(results) >= 1

    def test_search_with_date_range(self, service, tmp_path):
        # Create messages on different dates
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        # Write yesterday's message manually
        user_dir = service._get_user_dir(1)
        yesterday_file = user_dir / f"{yesterday}.jsonl"
        old_msg = ConversationMessage(
            id="old-1",
            timestamp=f"{yesterday}T10:00:00",
            role="user",
            content="old keyword here",
        )
        with open(yesterday_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(old_msg.to_dict(), ensure_ascii=False) + "\n")

        # Today's message
        service.save_message_pair(
            user_id=1,
            user_content="new keyword here",
            assistant_content="reply",
        )

        # Search only today
        results = service.search_messages(
            user_id=1, keyword="keyword", start_date=today, end_date=today
        )
        assert all("new" in r.content or "reply" in r.content.lower() for r in results if "keyword" in r.content.lower())

        # Search only yesterday
        results_old = service.search_messages(
            user_id=1, keyword="keyword", start_date=yesterday, end_date=yesterday
        )
        assert len(results_old) == 1
        assert "old" in results_old[0].content

    def test_search_limit(self, service):
        for i in range(10):
            service.save_message_pair(
                user_id=1,
                user_content=f"searchable {i}",
                assistant_content="reply",
            )
        results = service.search_messages(user_id=1, keyword="searchable", limit=3)
        assert len(results) == 3

    def test_search_no_results(self, populated_service):
        results = populated_service.search_messages(user_id=1, keyword="zzzznonexistent")
        assert results == []

    def test_search_no_files(self, service):
        results = service.search_messages(user_id=999, keyword="anything")
        assert results == []


# ========== get_available_dates ==========


class TestGetAvailableDates:
    """Tests for get_available_dates()."""

    def test_no_history(self, service):
        dates = service.get_available_dates(user_id=999)
        assert dates == []

    def test_returns_dates(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        dates = service.get_available_dates(user_id=1)
        assert len(dates) == 1
        today = datetime.now().strftime("%Y-%m-%d")
        assert dates[0] == today

    def test_ignores_non_date_files(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        # Create a file with non-date name
        user_dir = service._get_user_dir(1)
        bad_file = user_dir / "notadate.jsonl"
        bad_file.write_text("test\n")

        dates = service.get_available_dates(user_id=1)
        assert "notadate" not in dates


# ========== get_last_active_conversation ==========


class TestGetLastActiveConversation:
    """Tests for get_last_active_conversation()."""

    def test_no_history(self, service):
        messages, date_str = service.get_last_active_conversation(user_id=999)
        assert messages == []
        assert date_str is None

    def test_returns_latest_date(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        messages, date_str = service.get_last_active_conversation(user_id=1)
        assert len(messages) == 2
        assert date_str == datetime.now().strftime("%Y-%m-%d")


# ========== get_last_message ==========


class TestGetLastMessage:
    """Tests for get_last_message()."""

    def test_no_messages(self, service):
        msg = service.get_last_message(user_id=999)
        assert msg is None

    def test_returns_last_message(self, service):
        service.save_message_pair(
            user_id=1,
            user_content="question",
            assistant_content="answer",
        )
        msg = service.get_last_message(user_id=1)
        assert msg is not None
        # The last message should be the assistant reply (newest)
        assert msg.role == "assistant"
        assert msg.content == "answer"


# ========== get_users_with_conversations ==========


class TestGetUsersWithConversations:
    """Tests for get_users_with_conversations()."""

    def test_empty(self, service):
        users = service.get_users_with_conversations()
        assert users == []

    def test_returns_sorted_ids(self, service):
        service.save_message_pair(user_id=5, user_content="q", assistant_content="a")
        service.save_message_pair(user_id=2, user_content="q", assistant_content="a")
        users = service.get_users_with_conversations()
        assert users == [2, 5]

    def test_skips_non_numeric_dirs(self, service, tmp_path):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        # Create a non-numeric directory
        (tmp_path / "not_a_number").mkdir()
        users = service.get_users_with_conversations()
        assert users == [1]

    def test_skips_empty_user_dirs(self, service, tmp_path):
        # Create a numeric dir without .jsonl files
        (tmp_path / "99").mkdir()
        users = service.get_users_with_conversations()
        assert 99 not in users

    def test_base_dir_not_exists(self, tmp_path):
        """When base_dir is removed externally."""
        svc = ConversationService(base_dir=str(tmp_path / "conversations"))
        # base_dir is created by __init__, so it does exist; remove it
        import shutil
        shutil.rmtree(str(tmp_path / "conversations"))
        users = svc.get_users_with_conversations()
        assert users == []


# ========== generate_topic_id ==========


class TestGenerateTopicId:
    """Tests for generate_topic_id()."""

    def test_returns_string(self, service):
        topic_id = service.generate_topic_id()
        assert isinstance(topic_id, str)

    def test_has_correct_length(self, service):
        topic_id = service.generate_topic_id()
        assert len(topic_id) == 8

    def test_unique(self, service):
        ids = {service.generate_topic_id() for _ in range(100)}
        assert len(ids) == 100


# ========== get_statistics ==========


class TestGetStatistics:
    """Tests for get_statistics()."""

    def test_empty_stats(self, service):
        stats = service.get_statistics()
        assert stats["total_messages"] == 0
        assert stats["today_messages"] == 0
        assert stats["user_count"] == 0
        assert stats["action_distribution"] == []

    def test_counts_messages(self, populated_service):
        stats = populated_service.get_statistics()
        assert stats["total_messages"] == 4  # 2 pairs = 4 messages
        assert stats["today_messages"] == 4
        assert stats["user_count"] == 1

    def test_action_distribution(self, populated_service):
        stats = populated_service.get_statistics()
        dist = stats["action_distribution"]
        assert len(dist) >= 1
        action_types = {entry["action_type"] for entry in dist}
        assert "greet" in action_types or "ontology_query" in action_types

    def test_multiple_users(self, service):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        service.save_message_pair(user_id=2, user_content="q", assistant_content="a")
        stats = service.get_statistics()
        assert stats["user_count"] == 2
        assert stats["total_messages"] == 4

    def test_skips_non_numeric_dirs(self, service, tmp_path):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        (tmp_path / "invalid_dir").mkdir()
        stats = service.get_statistics()
        assert stats["user_count"] == 1

    def test_base_dir_missing(self, tmp_path):
        svc = ConversationService(base_dir=str(tmp_path / "conversations"))
        import shutil
        shutil.rmtree(str(tmp_path / "conversations"))
        stats = svc.get_statistics()
        assert stats["total_messages"] == 0


# ========== export_messages ==========


class TestExportMessages:
    """Tests for export_messages()."""

    def test_export_all(self, populated_service):
        exported = populated_service.export_messages(user_id=1)
        assert len(exported) == 4
        assert all(isinstance(m, dict) for m in exported)

    def test_export_with_date_filter(self, service, tmp_path):
        # Create messages on different dates
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        user_dir = service._get_user_dir(1)
        yesterday_file = user_dir / f"{yesterday}.jsonl"
        old_msg = ConversationMessage(
            id="old-1",
            timestamp=f"{yesterday}T10:00:00",
            role="user",
            content="old",
        )
        with open(yesterday_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(old_msg.to_dict(), ensure_ascii=False) + "\n")

        service.save_message_pair(user_id=1, user_content="today", assistant_content="reply")

        today = datetime.now().strftime("%Y-%m-%d")

        # Export only today
        exported = service.export_messages(user_id=1, start_date=today, end_date=today)
        assert len(exported) == 2
        assert exported[0]["content"] == "today"

        # Export only yesterday
        exported_old = service.export_messages(user_id=1, start_date=yesterday, end_date=yesterday)
        assert len(exported_old) == 1
        assert exported_old[0]["content"] == "old"

    def test_export_empty(self, service):
        exported = service.export_messages(user_id=999)
        assert exported == []

    def test_export_ignores_invalid_filenames(self, service, tmp_path):
        service.save_message_pair(user_id=1, user_content="q", assistant_content="a")
        user_dir = service._get_user_dir(1)
        bad_file = user_dir / "badname.jsonl"
        bad_file.write_text("{}\n")
        exported = service.export_messages(user_id=1)
        # Should only include today's messages, not the bad file
        assert len(exported) == 2


# ========== _read_file ==========


class TestReadFile:
    """Tests for _read_file() with edge cases."""

    def test_nonexistent_file(self, service, tmp_path):
        from pathlib import Path
        result = service._read_file(Path(tmp_path / "nonexistent.jsonl"))
        assert result == []

    def test_empty_file(self, service, tmp_path):
        from pathlib import Path
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = service._read_file(f)
        assert result == []

    def test_invalid_json_lines_skipped(self, service, tmp_path):
        from pathlib import Path
        f = tmp_path / "bad.jsonl"
        valid_msg = json.dumps({
            "id": "m1",
            "timestamp": "2025-01-15T10:00:00",
            "role": "user",
            "content": "valid",
        })
        f.write_text(
            "not valid json\n"
            + valid_msg + "\n"
            + "{invalid json line}\n"
            + "\n"
        )
        result = service._read_file(f)
        assert len(result) == 1
        assert result[0].content == "valid"

    def test_missing_key_lines_skipped(self, service, tmp_path):
        from pathlib import Path
        f = tmp_path / "missing_key.jsonl"
        # Valid JSON but missing required keys
        f.write_text('{"id": "m1"}\n')
        result = service._read_file(f)
        assert result == []

    def test_blank_lines_skipped(self, service, tmp_path):
        from pathlib import Path
        f = tmp_path / "blanks.jsonl"
        valid_msg = json.dumps({
            "id": "m1",
            "timestamp": "2025-01-15T10:00:00",
            "role": "user",
            "content": "ok",
        })
        f.write_text(f"\n\n{valid_msg}\n\n")
        result = service._read_file(f)
        assert len(result) == 1


# ========== Cross-day pagination ==========


class TestCrossDayPagination:
    """Tests for get_messages spanning multiple day files."""

    def test_cross_day_pagination(self, service):
        yesterday = (datetime.now() - timedelta(days=1))
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        # Write messages to yesterday's file manually
        user_dir = service._get_user_dir(1)
        yesterday_file = user_dir / f"{yesterday_str}.jsonl"
        msgs = []
        for i in range(3):
            msg = ConversationMessage(
                id=f"old-{i}",
                timestamp=f"{yesterday_str}T{10+i:02d}:00:00",
                role="user",
                content=f"yesterday-{i}",
            )
            msgs.append(msg)

        with open(yesterday_file, "w", encoding="utf-8") as f:
            for msg in msgs:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")

        # Save today's messages
        service.save_message_pair(
            user_id=1,
            user_content="today-q",
            assistant_content="today-a",
        )

        # Get all messages (limit high enough)
        messages, has_more = service.get_messages(user_id=1, limit=50)
        assert len(messages) == 5  # 3 yesterday + 2 today
        assert not has_more
        # Should be time-sorted oldest first
        assert messages[0].content == "yesterday-0"
        assert messages[-1].content == "today-a"
