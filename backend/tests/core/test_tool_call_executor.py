"""
tests/core/test_tool_call_executor.py

Unit tests for core/ai/tool_call_executor.py — Phase 3 tool calling protocol.
"""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from core.ai.tool_call_executor import (
    extract_tool_call,
    execute_tool,
    format_result,
    ToolCall,
    MAX_ROUNDS,
)


class TestExtractToolCall:

    def test_valid_tool_call(self):
        text = 'Some text <tool_call>{"tool": "search_actions", "args": {"query": "入住"}}</tool_call> more text'
        tc = extract_tool_call(text)
        assert tc is not None
        assert tc.tool == "search_actions"
        assert tc.args == {"query": "入住"}

    def test_no_tool_call(self):
        text = "Just some regular text without any tool calls"
        assert extract_tool_call(text) is None

    def test_invalid_json(self):
        text = "<tool_call>not valid json</tool_call>"
        assert extract_tool_call(text) is None

    def test_empty_tool_name(self):
        text = '<tool_call>{"tool": "", "args": {}}</tool_call>'
        assert extract_tool_call(text) is None

    def test_missing_tool_field(self):
        text = '<tool_call>{"args": {"query": "test"}}</tool_call>'
        assert extract_tool_call(text) is None

    def test_multiline_tool_call(self):
        text = """Some preamble
<tool_call>
{
  "tool": "describe_action",
  "args": {"name": "checkin"}
}
</tool_call>
Some postamble"""
        tc = extract_tool_call(text)
        assert tc is not None
        assert tc.tool == "describe_action"
        assert tc.args == {"name": "checkin"}

    def test_no_args_defaults_to_empty(self):
        text = '<tool_call>{"tool": "search_actions"}</tool_call>'
        tc = extract_tool_call(text)
        assert tc is not None
        assert tc.args == {}


class TestExecuteTool:

    def test_search_actions(self):
        @dataclass
        class FakeResult:
            name: str
            entity: str
            description: str
            score: float
            source: str

        engine = MagicMock()
        engine.search.return_value = [
            FakeResult("checkin", "StayRecord", "办理入住", 1.0, "keyword"),
        ]

        tc = ToolCall(tool="search_actions", args={"query": "入住"})
        result = execute_tool(tc, search_engine=engine)

        assert "actions" in result
        assert len(result["actions"]) == 1
        assert result["actions"][0]["name"] == "checkin"
        engine.search.assert_called_once_with("入住", user_role="", top_k=5)

    def test_search_actions_no_engine(self):
        tc = ToolCall(tool="search_actions", args={"query": "test"})
        result = execute_tool(tc, search_engine=None)
        assert "error" in result

    def test_search_actions_no_query(self):
        engine = MagicMock()
        tc = ToolCall(tool="search_actions", args={})
        result = execute_tool(tc, search_engine=engine)
        assert "error" in result

    def test_describe_action(self):
        from pydantic import BaseModel

        class FakeParams(BaseModel):
            guest_name: str = ""

        defn = MagicMock()
        defn.name = "checkin"
        defn.entity = "StayRecord"
        defn.description = "办理入住"
        defn.category = "mutation"
        defn.parameters_schema = FakeParams
        defn.requires_confirmation = True

        registry = MagicMock()
        registry.get_action.return_value = defn

        tc = ToolCall(tool="describe_action", args={"name": "checkin"})
        result = execute_tool(tc, action_registry=registry)

        assert result["name"] == "checkin"
        assert result["entity"] == "StayRecord"
        assert "parameters" in result
        registry.get_action.assert_called_once_with("checkin")

    def test_describe_action_not_found(self):
        registry = MagicMock()
        registry.get_action.return_value = None

        tc = ToolCall(tool="describe_action", args={"name": "nonexistent"})
        result = execute_tool(tc, action_registry=registry)
        assert "error" in result

    def test_describe_action_no_registry(self):
        tc = ToolCall(tool="describe_action", args={"name": "checkin"})
        result = execute_tool(tc, action_registry=None)
        assert "error" in result

    def test_describe_action_no_name(self):
        registry = MagicMock()
        tc = ToolCall(tool="describe_action", args={})
        result = execute_tool(tc, action_registry=registry)
        assert "error" in result

    def test_unknown_tool(self):
        tc = ToolCall(tool="unknown_tool", args={})
        result = execute_tool(tc)
        assert "error" in result
        assert "Unknown tool" in result["error"]


class TestFormatResult:

    def test_format_result(self):
        result = format_result("search_actions", {"actions": [], "total": 0})
        assert "<tool_result>" in result
        assert "</tool_result>" in result
        assert '"tool": "search_actions"' in result

    def test_format_result_chinese_content(self):
        result = format_result("describe_action", {"name": "checkin", "description": "办理入住"})
        assert "办理入住" in result


class TestMaxRounds:

    def test_max_rounds_value(self):
        assert MAX_ROUNDS == 3


class TestPromptShaperDiscovery:
    """Test Phase 3 in PromptShaper."""

    def test_discovery_with_search_engine(self):
        from core.ai.prompt_shaper import PromptShaper, _role_filter_registry
        _role_filter_registry.clear()

        reg = MagicMock()
        ar = MagicMock()
        # Simulate search engine with indexed actions
        ar._search_engine = MagicMock()
        ar._search_engine._action_meta = {"checkin": {}, "checkout": {}}

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("test", "manager")

        assert result.strategy == "discovery"
        assert result.actions == []  # No actions injected
        assert result.metadata["indexed_actions"] == 2

    def test_discovery_fallback_no_engine(self):
        from core.ai.prompt_shaper import PromptShaper, _role_filter_registry
        _role_filter_registry.clear()

        reg = MagicMock()
        reg.get_related_entities.side_effect = AttributeError
        ar = MagicMock()
        ar._search_engine = None
        ar.list_actions.return_value = []

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("test", "manager")

        # Should fall through to "full" (no search engine, no role filter)
        assert result.strategy == "full"
        assert "discovery_unavailable" in result.metadata.get("fallback_chain", [])

    def test_discovery_fallback_empty_engine(self):
        from core.ai.prompt_shaper import PromptShaper, _role_filter_registry
        _role_filter_registry.clear()

        reg = MagicMock()
        reg.get_related_entities.side_effect = AttributeError
        ar = MagicMock()
        ar._search_engine = MagicMock()
        ar._search_engine._action_meta = {}  # Empty engine
        ar.list_actions.return_value = []

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("test", "manager")

        assert result.strategy == "full"
        assert "discovery_unavailable" in result.metadata.get("fallback_chain", [])

    def test_full_fallback_chain(self):
        """Phase 3 → Phase 2 → Phase 1 → Full degradation chain."""
        from core.ai.prompt_shaper import PromptShaper, _role_filter_registry
        _role_filter_registry.clear()

        reg = MagicMock()
        reg.get_related_entities.side_effect = AttributeError
        ar = MagicMock()
        ar._search_engine = None  # No search engine → Phase 3 fails
        ar.list_actions.return_value = []

        # No intent → Phase 2 skipped
        # No role filter → Phase 1 passes through

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("test", "unknown_role", intent=None)

        assert result.strategy == "full"
        assert "discovery_unavailable" in result.metadata.get("fallback_chain", [])
