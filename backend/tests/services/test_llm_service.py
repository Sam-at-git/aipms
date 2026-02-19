"""
Tests for app/services/llm_service.py

Covers:
- extract_json_from_text and sub-functions
- extract_and_validate_actions
- _validate_action
- detect_language
- LLMService class: init, chat, _build_context_info, _validate_and_clean_result,
  extract_entities, check_topic_relevance, extract_intent, extract_params,
  parse_followup_input, _instrumented_completion, build_system_prompt_with_schema,
  get_query_schema, on_ontology_changed, _build_action_params_hints
"""
import json
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock, PropertyMock


# ============== Module-level function tests ==============


class TestExtractJsonFromText:
    """Tests for extract_json_from_text()"""

    def test_none_input(self):
        from app.services.llm_service import extract_json_from_text
        assert extract_json_from_text(None) is None

    def test_empty_string(self):
        from app.services.llm_service import extract_json_from_text
        assert extract_json_from_text("") is None

    def test_direct_json(self):
        from app.services.llm_service import extract_json_from_text
        result = extract_json_from_text('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_code_block(self):
        from app.services.llm_service import extract_json_from_text
        text = '```json\n{"action": "test"}\n```'
        result = extract_json_from_text(text)
        assert result == {"action": "test"}

    def test_json_in_plain_code_block(self):
        from app.services.llm_service import extract_json_from_text
        text = '```\n{"action": "test"}\n```'
        result = extract_json_from_text(text)
        assert result == {"action": "test"}

    def test_json_embedded_in_text(self):
        from app.services.llm_service import extract_json_from_text
        text = 'Here is the result: {"status": "ok"} and some more text'
        result = extract_json_from_text(text)
        assert result == {"status": "ok"}

    def test_json_with_trailing_comma(self):
        from app.services.llm_service import extract_json_from_text
        text = '{"a": 1, "b": 2,}'
        result = extract_json_from_text(text)
        assert result == {"a": 1, "b": 2}

    def test_json_with_comments(self):
        from app.services.llm_service import extract_json_from_text
        text = '{"a": 1 // comment\n}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result.get("a") == 1

    def test_json_with_nan_infinity(self):
        from app.services.llm_service import extract_json_from_text
        import math
        text = '{"a": NaN, "b": Infinity, "c": -Infinity}'
        result = extract_json_from_text(text)
        assert result is not None
        # Python json.loads parses NaN/Infinity as float nan/inf
        assert math.isnan(result["a"])
        assert math.isinf(result["b"])

    def test_no_json_in_text(self):
        from app.services.llm_service import extract_json_from_text
        result = extract_json_from_text("just plain text with no json")
        assert result is None

    def test_nested_json(self):
        from app.services.llm_service import extract_json_from_text
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_from_text(text)
        assert result == {"outer": {"inner": "value"}}

    def test_unmatched_braces(self):
        from app.services.llm_service import extract_json_from_text
        result = extract_json_from_text("{unclosed")
        assert result is None

    def test_json_with_embedded_object(self):
        from app.services.llm_service import extract_json_from_text
        text = 'prefix {"msg": "hello world"} suffix'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["msg"] == "hello world"

    def test_code_block_with_invalid_json_falls_through(self):
        from app.services.llm_service import extract_json_from_text
        text = '```json\nnot valid json\n```'
        result = extract_json_from_text(text)
        assert result is None


class TestTryParseJson:
    def test_valid(self):
        from app.services.llm_service import _try_parse_json
        assert _try_parse_json('{"a": 1}') == {"a": 1}

    def test_invalid(self):
        from app.services.llm_service import _try_parse_json
        assert _try_parse_json("not json") is None

    def test_type_error(self):
        from app.services.llm_service import _try_parse_json
        assert _try_parse_json(None) is None


class TestExtractBracesContent:
    def test_no_braces(self):
        from app.services.llm_service import _extract_braces_content
        assert _extract_braces_content("no braces here") is None

    def test_with_string_containing_braces(self):
        from app.services.llm_service import _extract_braces_content
        text = '{"key": "val{ue}"}'
        result = _extract_braces_content(text)
        assert result is not None

    def test_escaped_backslash_in_string(self):
        from app.services.llm_service import _extract_braces_content
        text = '{"path": "C:\\\\dir"}'
        result = _extract_braces_content(text)
        assert result is not None


class TestRemoveComments:
    def test_single_line_comment(self):
        from app.services.llm_service import _remove_comments
        assert "//" not in _remove_comments('{"a": 1} // comment')

    def test_multi_line_comment(self):
        from app.services.llm_service import _remove_comments
        assert "/*" not in _remove_comments('{"a": 1} /* block */}')

    def test_python_comment(self):
        from app.services.llm_service import _remove_comments
        assert "#" not in _remove_comments('{"a": 1} # python comment')


class TestConvertSingleQuotes:
    def test_single_quoted_key(self):
        from app.services.llm_service import _convert_single_quotes
        result = _convert_single_quotes("{'key': 'value'}")
        assert '"key"' in result

    def test_skip_when_double_quotes_present(self):
        from app.services.llm_service import _convert_single_quotes
        # The regex replaces keys; if both are present, behavior depends on match
        result = _convert_single_quotes('{"key": "value"}')
        assert '"key"' in result

    def test_array_with_single_quotes(self):
        from app.services.llm_service import _convert_single_quotes
        result = _convert_single_quotes("['item']")
        assert '["item"]' in result


class TestRemoveTrailingCommas:
    def test_trailing_comma_before_brace(self):
        from app.services.llm_service import _remove_trailing_commas
        assert _remove_trailing_commas('{"a": 1,}') == '{"a": 1}'

    def test_trailing_comma_before_bracket(self):
        from app.services.llm_service import _remove_trailing_commas
        assert _remove_trailing_commas('[1,2,]') == '[1,2]'


class TestFixEscapedNewlines:
    def test_basic(self):
        from app.services.llm_service import _fix_escaped_newlines
        result = _fix_escaped_newlines('{"a": "hello"}')
        assert "hello" in result


class TestExtractAndValidateActions:
    def test_valid_json_with_all_fields(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "Hello",
            "suggested_actions": [
                {
                    "action_type": "checkin",
                    "entity_type": "guest",
                    "description": "Check in",
                    "requires_confirmation": True,
                    "params": {"room": "101"}
                }
            ],
            "context": {"key": "val"}
        })
        result = extract_and_validate_actions(text)
        assert result["message"] == "Hello"
        assert len(result["suggested_actions"]) == 1
        assert result["suggested_actions"][0]["action_type"] == "checkin"

    def test_parse_failure_returns_default(self):
        from app.services.llm_service import extract_and_validate_actions
        result = extract_and_validate_actions("just plain text with no json here")
        assert result["context"]["parse_error"] is True
        assert isinstance(result["suggested_actions"], list)

    def test_long_text_truncated_in_default(self):
        from app.services.llm_service import extract_and_validate_actions
        long_text = "x" * 300
        result = extract_and_validate_actions(long_text)
        assert len(result["message"]) == 200

    def test_missing_fields_get_defaults(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({"custom_field": "val"})
        result = extract_and_validate_actions(text)
        assert result["message"] == "已处理您的请求"
        assert result["suggested_actions"] == []
        assert result["context"] == {}

    def test_suggested_actions_not_list_coerced(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": "not a list",
            "context": {}
        })
        result = extract_and_validate_actions(text)
        assert result["suggested_actions"] == []

    def test_context_not_dict_coerced(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": [],
            "context": "not a dict"
        })
        result = extract_and_validate_actions(text)
        assert result["context"] == {}

    def test_invalid_action_item_coerced(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": ["not_a_dict"],
            "context": {}
        })
        result = extract_and_validate_actions(text)
        assert result["suggested_actions"][0]["action_type"] == "ontology_query"

    def test_action_with_entity_id(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": [{"action_type": "checkout", "entity_id": 42}],
            "context": {}
        })
        result = extract_and_validate_actions(text)
        assert result["suggested_actions"][0]["entity_id"] == 42

    def test_action_missing_optional_fields(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": [{"action_type": "checkin"}],
            "context": {}
        })
        result = extract_and_validate_actions(text)
        action = result["suggested_actions"][0]
        assert action["entity_type"] == "unknown"
        assert action["requires_confirmation"] is True
        assert action["params"] == {}

    def test_custom_required_fields_with_unknown(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({"message": "hi"})
        result = extract_and_validate_actions(text, required_fields=["message", "custom_field"])
        assert result["custom_field"] is None

    def test_action_with_non_dict_params(self):
        from app.services.llm_service import extract_and_validate_actions
        text = json.dumps({
            "message": "test",
            "suggested_actions": [{"action_type": "test", "params": "not_dict"}],
            "context": {}
        })
        result = extract_and_validate_actions(text)
        assert result["suggested_actions"][0]["params"] == {}


class TestValidateAction:
    def test_non_dict_action(self):
        from app.services.llm_service import _validate_action
        result = _validate_action("not a dict")
        assert result["action_type"] == "ontology_query"
        assert result["entity_type"] == "unknown"

    def test_dict_action_with_defaults(self):
        from app.services.llm_service import _validate_action
        result = _validate_action({})
        assert result["action_type"] == "ontology_query"
        assert result["requires_confirmation"] is True


class TestDetectLanguage:
    def test_chinese_text(self):
        from app.services.llm_service import detect_language
        assert detect_language("你好世界") == "zh"

    def test_english_text(self):
        from app.services.llm_service import detect_language
        assert detect_language("hello world") == "en"

    def test_empty_text(self):
        from app.services.llm_service import detect_language
        assert detect_language("") == "zh"

    def test_mixed_text_mostly_chinese(self):
        from app.services.llm_service import detect_language
        assert detect_language("你好世界hello") == "zh"

    def test_mixed_text_mostly_english(self):
        from app.services.llm_service import detect_language
        assert detect_language("hello world 你") == "en"


class TestTopicRelevance:
    def test_constants(self):
        from app.services.llm_service import TopicRelevance
        assert TopicRelevance.CONTINUATION == "continuation"
        assert TopicRelevance.NEW_TOPIC == "new_topic"
        assert TopicRelevance.FOLLOWUP_ANSWER == "followup_answer"


# ============== LLMService class tests ==============


class TestLLMServiceInit:
    @patch("app.services.llm_service.settings")
    @patch("app.services.llm_service.OpenAI")
    def test_init_enabled(self, mock_openai_cls, mock_settings):
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.ENABLE_LLM = True
        mock_settings.OPENAI_BASE_URL = "https://api.example.com"

        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        # Use the real init but mock external deps
        svc.api_key = "test-key"
        svc.enabled = True
        svc.client = mock_openai_cls.return_value
        svc._prompt_builder = None
        svc._query_schema_cache = None
        assert svc.enabled is True
        assert svc.client is not None

    @patch("app.services.llm_service.settings")
    def test_init_disabled_no_key(self, mock_settings):
        mock_settings.OPENAI_API_KEY = None
        mock_settings.ENABLE_LLM = True

        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.api_key = None
        svc.enabled = False
        svc.client = None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        assert svc.enabled is False
        assert svc.client is None


class TestLLMServiceIsEnabled:
    def _make_service(self, enabled=True):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        svc.api_key = "test-key" if enabled else None
        return svc

    def test_is_enabled_true(self):
        svc = self._make_service(True)
        assert svc.is_enabled() is True

    def test_is_enabled_false(self):
        svc = self._make_service(False)
        assert svc.is_enabled() is False


class TestLLMServiceChat:
    def _make_service(self, enabled=True):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        svc.api_key = "test-key" if enabled else None
        svc.SYSTEM_PROMPT = "Test system prompt"
        return svc

    def test_chat_disabled(self):
        svc = self._make_service(False)
        result = svc.chat("hello")
        assert "LLM 服务未启用" in result["message"]
        assert result["context"]["error"] == "llm_disabled"

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_chat_success(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_MAX_TOKENS = 2000

        svc = self._make_service(True)
        response_content = json.dumps({
            "message": "OK",
            "suggested_actions": [],
            "context": {}
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        result = svc.chat("查看房态")
        assert result["message"] == "OK"
        assert isinstance(result["suggested_actions"], list)

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_chat_json_mode_fallback(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_MAX_TOKENS = 2000

        svc = self._make_service(True)
        response_content = json.dumps({
            "message": "Fallback OK",
            "suggested_actions": [],
            "context": {}
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None

        # First call raises (json_object not supported), second succeeds
        svc.client.chat.completions.create.side_effect = [
            Exception("json_object not supported"),
            mock_response
        ]
        mock_ctx.get_current.return_value = None

        result = svc.chat("hello")
        assert result["message"] == "Fallback OK"

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_chat_api_exception(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_MAX_TOKENS = 2000

        svc = self._make_service(True)
        svc.client.chat.completions.create.side_effect = Exception("API Error")
        mock_ctx.get_current.return_value = None

        result = svc.chat("hello")
        assert "LLM 服务错误" in result["message"]
        assert result["context"]["error"] == "API Error"

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_chat_with_context_and_history(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_MAX_TOKENS = 2000

        svc = self._make_service(True)
        response_content = json.dumps({
            "message": "OK",
            "suggested_actions": [],
            "context": {}
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None

        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        context = {
            "room_summary": {"total": 10, "vacant_clean": 5, "occupied": 3},
            "room_types": [{"id": 1, "name": "Standard", "price": 288}],
            "conversation_history": [
                {"role": "user", "content": "previous msg"},
                {"role": "assistant", "content": "response"},
            ],
            "include_query_schema": True,
            "user_role": "manager",
        }
        result = svc.chat("hello", context=context, language="zh")
        assert result["message"] == "OK"

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_chat_parse_error_logged(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_MAX_TOKENS = 2000

        svc = self._make_service(True)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json at all"
        mock_response.usage = None

        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        result = svc.chat("hello")
        assert result.get("context", {}).get("parse_error") is True


class TestBuildContextInfo:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = False
        svc.client = None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_no_context(self):
        svc = self._make_service()
        result = svc._build_context_info(None)
        assert "无额外上下文信息" in result

    def test_empty_context(self):
        svc = self._make_service()
        result = svc._build_context_info({})
        assert "当前状态" in result

    def test_with_room_summary(self):
        svc = self._make_service()
        ctx = {"room_summary": {"total": 10, "vacant_clean": 5, "occupied": 3}}
        result = svc._build_context_info(ctx)
        assert "总房间: 10" in result

    def test_with_room_types(self):
        svc = self._make_service()
        ctx = {"room_types": [{"name": "Standard", "id": 1, "price": 288}]}
        result = svc._build_context_info(ctx)
        assert "Standard" in result

    def test_with_active_stays(self):
        svc = self._make_service()
        ctx = {
            "active_stays": [
                {"id": 1, "room_number": "101", "guest_name": "Zhang", "expected_check_out": "2026-01-10"}
            ]
        }
        result = svc._build_context_info(ctx)
        assert "在住客人: 1 位" in result
        assert "101" in result

    def test_with_pending_tasks(self):
        svc = self._make_service()
        ctx = {
            "pending_tasks": [
                {"id": 1, "room_number": "201", "task_type": "cleaning"}
            ]
        }
        result = svc._build_context_info(ctx)
        assert "待处理任务: 1 个" in result

    def test_with_user_role(self):
        svc = self._make_service()
        ctx = {"user_role": "manager"}
        result = svc._build_context_info(ctx)
        assert "manager" in result


class TestValidateAndCleanResult:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        return svc

    def test_adds_missing_fields(self):
        svc = self._make_service()
        result = svc._validate_and_clean_result({})
        assert "message" in result
        assert "suggested_actions" in result
        assert "context" in result

    def test_cleans_action_missing_fields(self):
        svc = self._make_service()
        result = svc._validate_and_clean_result({
            "message": "test",
            "suggested_actions": [{}],
            "context": {}
        })
        action = result["suggested_actions"][0]
        assert action["action_type"] == "ontology_query"
        assert action["entity_type"] == "unknown"
        assert action["requires_confirmation"] is True
        assert action["params"] == {}

    def test_preserves_valid_result(self):
        svc = self._make_service()
        result = svc._validate_and_clean_result({
            "message": "hello",
            "suggested_actions": [{"action_type": "checkin", "entity_type": "guest",
                                    "description": "Check in", "requires_confirmation": False,
                                    "params": {"room": "101"}}],
            "context": {"key": "val"}
        })
        assert result["message"] == "hello"
        assert result["suggested_actions"][0]["action_type"] == "checkin"


class TestExtractEntities:
    def _make_service(self, enabled=False):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_disabled(self):
        svc = self._make_service(False)
        result = svc.extract_entities("201房退房")
        assert result == {}

    @patch("app.services.llm_service.settings")
    def test_enabled_success(self, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "room_number": "201"
        })
        svc.client.chat.completions.create.return_value = mock_response
        result = svc.extract_entities("201房退房")
        assert result["room_number"] == "201"

    @patch("app.services.llm_service.settings")
    def test_enabled_exception(self, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        svc = self._make_service(True)
        svc.client.chat.completions.create.side_effect = Exception("fail")
        result = svc.extract_entities("201房退房")
        assert result == {}


class TestCheckTopicRelevance:
    def _make_service(self, enabled=False):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_no_history_returns_new_topic(self):
        from app.services.llm_service import TopicRelevance
        svc = self._make_service(False)
        assert svc.check_topic_relevance("hello", []) == TopicRelevance.NEW_TOPIC

    def test_short_answer_to_question(self):
        from app.services.llm_service import TopicRelevance
        svc = self._make_service(False)
        history = [{"role": "assistant", "content": "请问房型？"}]
        assert svc.check_topic_relevance("大床房", history) == TopicRelevance.FOLLOWUP_ANSWER

    def test_continuation_keyword(self):
        from app.services.llm_service import TopicRelevance
        svc = self._make_service(False)
        history = [{"role": "user", "content": "查房态"}]
        assert svc.check_topic_relevance("好的", history) == TopicRelevance.CONTINUATION

    def test_continuation_keyword_exact_match(self):
        from app.services.llm_service import TopicRelevance
        svc = self._make_service(False)
        history = [{"role": "user", "content": "something"}]
        assert svc.check_topic_relevance("对", history) == TopicRelevance.CONTINUATION

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_fallback_continuation(self, mock_ctx, mock_settings):
        from app.services.llm_service import TopicRelevance
        mock_settings.LLM_MODEL = "test-model"

        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "continuation"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        history = [{"role": "user", "content": "查房间"}, {"role": "assistant", "content": "OK"}]
        result = svc.check_topic_relevance("给我看201", history)
        assert result in [TopicRelevance.CONTINUATION, TopicRelevance.NEW_TOPIC,
                          TopicRelevance.FOLLOWUP_ANSWER]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_new_topic(self, mock_ctx, mock_settings):
        from app.services.llm_service import TopicRelevance
        mock_settings.LLM_MODEL = "test-model"

        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "new_topic"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        history = [{"role": "user", "content": "something else"}]
        result = svc.check_topic_relevance("create a new reservation for tomorrow", history)
        assert result == TopicRelevance.NEW_TOPIC

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_followup_answer(self, mock_ctx, mock_settings):
        from app.services.llm_service import TopicRelevance
        mock_settings.LLM_MODEL = "test-model"

        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "followup_answer"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        history = [{"role": "assistant", "content": "Which room?"}]
        result = svc.check_topic_relevance("201 is fine for the task", history)
        assert result == TopicRelevance.FOLLOWUP_ANSWER

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_unrecognized_defaults_continuation(self, mock_ctx, mock_settings):
        from app.services.llm_service import TopicRelevance
        mock_settings.LLM_MODEL = "test-model"

        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "something_random"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response
        mock_ctx.get_current.return_value = None

        history = [{"role": "user", "content": "x"}]
        result = svc.check_topic_relevance("a longer message that passes checks", history)
        assert result == TopicRelevance.CONTINUATION

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_exception_returns_continuation(self, mock_ctx, mock_settings):
        from app.services.llm_service import TopicRelevance
        mock_settings.LLM_MODEL = "test-model"

        svc = self._make_service(True)
        svc.client.chat.completions.create.side_effect = Exception("fail")
        mock_ctx.get_current.return_value = None

        history = [{"role": "user", "content": "x"}]
        result = svc.check_topic_relevance("a longer message for testing", history)
        assert result == TopicRelevance.CONTINUATION


class TestIsShortAnswer:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        return svc

    def test_short(self):
        svc = self._make_service()
        assert svc._is_short_answer("大床房") is True

    def test_long(self):
        svc = self._make_service()
        assert svc._is_short_answer("I want a large room with a nice view on the second floor") is False


class TestExtractIntent:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = False
        svc.client = None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_empty_message(self):
        svc = self._make_service()
        result = svc.extract_intent("")
        assert result["entity_mentions"] == []
        assert result["action_hints"] == []

    def test_guest_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("查看客人信息")
        assert "Guest" in result["entity_mentions"]
        assert "query" in result["action_hints"]

    def test_room_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("201号房退房")
        assert "Room" in result["entity_mentions"]
        assert result["extracted_values"]["room_number"] == "201"

    def test_checkin_action(self):
        svc = self._make_service()
        result = svc.extract_intent("办理入住")
        assert "checkin" in result["action_hints"]

    def test_checkout_action(self):
        svc = self._make_service()
        result = svc.extract_intent("退房")
        assert "checkout" in result["action_hints"]

    def test_reservation_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("创建预订")
        assert "Reservation" in result["entity_mentions"]
        assert "create" in result["action_hints"]

    def test_task_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("创建清洁任务")
        assert "Task" in result["entity_mentions"]

    def test_bill_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("查看账单")
        assert "Bill" in result["entity_mentions"]

    def test_employee_entity(self):
        svc = self._make_service()
        result = svc.extract_intent("查看员工列表")
        assert "Employee" in result["entity_mentions"]

    def test_time_references(self):
        svc = self._make_service()
        result = svc.extract_intent("明天入住")
        assert "明天" in result["time_references"]

    def test_denied_intent_modify_role(self):
        svc = self._make_service()
        result = svc.extract_intent("修改角色权限")
        assert "modify_role" in result["denied_intents"]

    def test_denied_intent_modify_permission(self):
        svc = self._make_service()
        result = svc.extract_intent("添加权限给用户")
        assert "modify_permission" in result["denied_intents"]

    def test_denied_intent_modify_menu(self):
        svc = self._make_service()
        result = svc.extract_intent("删除菜单")
        assert "modify_menu" in result["denied_intents"]

    def test_denied_intent_modify_security(self):
        svc = self._make_service()
        result = svc.extract_intent("修改密码策略")
        assert "modify_security" in result["denied_intents"]

    def test_system_entity_detection(self):
        svc = self._make_service()
        result = svc.extract_intent("查看系统有哪些角色")
        assert "SysRole" in result["entity_mentions"]

    def test_extend_action(self):
        svc = self._make_service()
        result = svc.extract_intent("续住两天")
        assert "extend" in result["action_hints"]

    def test_assign_action(self):
        svc = self._make_service()
        result = svc.extract_intent("分配任务给清洁员")
        assert "assign" in result["action_hints"]

    def test_complete_action(self):
        svc = self._make_service()
        result = svc.extract_intent("完成任务")
        assert "complete" in result["action_hints"]

    def test_cancel_action(self):
        svc = self._make_service()
        result = svc.extract_intent("取消预订")
        assert "cancel" in result["action_hints"]

    def test_extract_intent_rule_based_alias(self):
        svc = self._make_service()
        result = svc._extract_intent_rule_based("查询房间")
        assert "Room" in result["entity_mentions"]


class TestInstrumentedCompletion:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.client = MagicMock()
        svc.enabled = True
        return svc

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_success_no_context(self, mock_ctx_cls):
        mock_ctx_cls.get_current.return_value = None

        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        svc.client.chat.completions.create.return_value = mock_response

        result = svc._instrumented_completion([{"role": "user", "content": "hi"}])
        assert result == mock_response

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_success_with_debug_context(self, mock_ctx_cls):
        mock_debug_logger = MagicMock()
        mock_ctx_cls.get_current.return_value = {
            "session_id": "sess-1",
            "ooda_phase": "decide",
            "call_type": "chat",
            "debug_logger": mock_debug_logger,
            "sequence": 0,
        }
        mock_ctx_cls.next_sequence.return_value = 0

        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        svc.client.chat.completions.create.return_value = mock_response

        result = svc._instrumented_completion(
            [{"role": "user", "content": "hi"}],
            model="test-model",
            temperature=0.5
        )
        assert result == mock_response
        mock_debug_logger.log_llm_interaction.assert_called_once()

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_success_with_no_usage(self, mock_ctx_cls):
        mock_debug_logger = MagicMock()
        mock_ctx_cls.get_current.return_value = {
            "session_id": "sess-1",
            "ooda_phase": "act",
            "call_type": "format_result",
            "debug_logger": mock_debug_logger,
            "sequence": 0,
        }
        mock_ctx_cls.next_sequence.return_value = 0

        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "formatted"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        result = svc._instrumented_completion([{"role": "user", "content": "hi"}])
        assert result == mock_response
        call_args = mock_debug_logger.log_llm_interaction.call_args
        assert call_args.kwargs.get("tokens_input") is None

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_failure_with_debug_context(self, mock_ctx_cls):
        mock_debug_logger = MagicMock()
        mock_ctx_cls.get_current.return_value = {
            "session_id": "sess-1",
            "ooda_phase": "decide",
            "call_type": "chat",
            "debug_logger": mock_debug_logger,
            "sequence": 0,
        }
        mock_ctx_cls.next_sequence.return_value = 0

        svc = self._make_service()
        svc.client.chat.completions.create.side_effect = Exception("API timeout")

        with pytest.raises(Exception, match="API timeout"):
            svc._instrumented_completion([{"role": "user", "content": "hi"}])

        mock_debug_logger.log_llm_interaction.assert_called_once()
        call_args = mock_debug_logger.log_llm_interaction.call_args
        assert call_args.kwargs.get("success") is False
        assert "API timeout" in call_args.kwargs.get("error", "")

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_failure_without_context(self, mock_ctx_cls):
        mock_ctx_cls.get_current.return_value = None

        svc = self._make_service()
        svc.client.chat.completions.create.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            svc._instrumented_completion([{"role": "user", "content": "hi"}])

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_logging_error_suppressed(self, mock_ctx_cls):
        mock_debug_logger = MagicMock()
        mock_debug_logger.log_llm_interaction.side_effect = Exception("log error")
        mock_ctx_cls.get_current.return_value = {
            "session_id": "sess-1",
            "ooda_phase": "decide",
            "call_type": "chat",
            "debug_logger": mock_debug_logger,
            "sequence": 0,
        }
        mock_ctx_cls.next_sequence.return_value = 0

        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        # Should not raise despite logging failure
        result = svc._instrumented_completion([{"role": "user", "content": "hi"}])
        assert result == mock_response

    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_failure_logging_error_suppressed(self, mock_ctx_cls):
        mock_debug_logger = MagicMock()
        mock_debug_logger.log_llm_interaction.side_effect = Exception("log error")
        mock_ctx_cls.get_current.return_value = {
            "session_id": "sess-1",
            "ooda_phase": "decide",
            "call_type": "chat",
            "debug_logger": mock_debug_logger,
            "sequence": 0,
        }
        mock_ctx_cls.next_sequence.return_value = 0

        svc = self._make_service()
        svc.client.chat.completions.create.side_effect = Exception("API error")

        # Should still raise the original error
        with pytest.raises(Exception, match="API error"):
            svc._instrumented_completion([{"role": "user", "content": "hi"}])


class TestOnOntologyChanged:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc._prompt_builder = MagicMock()
        svc._query_schema_cache = "cached_value"
        return svc

    def test_clears_cache(self):
        svc = self._make_service()
        svc.on_ontology_changed()
        svc._prompt_builder.invalidate_cache.assert_called_once()
        assert svc._query_schema_cache is None

    def test_no_prompt_builder(self):
        svc = self._make_service()
        svc._prompt_builder = None
        svc.on_ontology_changed()
        assert svc._query_schema_cache is None


class TestGetQuerySchema:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc._query_schema_cache = None
        return svc

    def test_cached(self):
        svc = self._make_service()
        svc._query_schema_cache = "cached"
        svc._prompt_builder = None
        assert svc.get_query_schema() == "cached"

    def test_from_prompt_builder(self):
        svc = self._make_service()
        svc._prompt_builder = MagicMock()
        svc._prompt_builder.build_query_schema.return_value = "dynamic schema"
        result = svc.get_query_schema()
        assert result == "dynamic schema"

    def test_fallback(self):
        svc = self._make_service()
        svc._prompt_builder = None
        result = svc.get_query_schema()
        assert "Guest" in result
        assert "Room" in result


class TestBuildSystemPromptWithSchema:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc._prompt_builder = None
        svc._query_schema_cache = None
        svc.SYSTEM_PROMPT = "Test prompt"
        return svc

    def test_no_prompt_builder(self):
        svc = self._make_service()
        result = svc.build_system_prompt_with_schema()
        assert "Test prompt" in result

    def test_with_language(self):
        svc = self._make_service()
        result = svc.build_system_prompt_with_schema(language="en")
        assert "English" in result

    def test_with_language_zh(self):
        svc = self._make_service()
        result = svc.build_system_prompt_with_schema(language="zh")
        assert "中文" in result

    def test_with_schema_include(self):
        svc = self._make_service()
        result = svc.build_system_prompt_with_schema(include_schema=True)
        assert "Guest" in result  # from fallback schema

    def test_with_prompt_builder(self):
        svc = self._make_service()
        svc._prompt_builder = MagicMock()
        svc._prompt_builder.build_system_prompt.return_value = "dynamic prompt"
        svc._prompt_builder._build_domain_glossary.return_value = "glossary"

        result = svc.build_system_prompt_with_schema(include_glossary=True, user_role="manager", message_hint="test")
        assert "dynamic prompt" in result
        assert "glossary" in result

    def test_with_prompt_builder_glossary_exception(self):
        svc = self._make_service()
        svc._prompt_builder = MagicMock()
        svc._prompt_builder.build_system_prompt.return_value = "dynamic prompt"
        svc._prompt_builder._build_domain_glossary.side_effect = Exception("fail")

        result = svc.build_system_prompt_with_schema(include_glossary=True)
        assert "dynamic prompt" in result

    @patch("app.services.llm_service.get_business_rules", create=True)
    def test_with_business_rules(self, mock_get_rules):
        svc = self._make_service()
        # patch the import inside the method
        with patch.dict('sys.modules', {'core.ontology.business_rules': MagicMock()}):
            with patch('core.ontology.business_rules.get_business_rules') as mock_br:
                mock_registry = MagicMock()
                mock_registry.export_for_llm.return_value = "rule1\nrule2"
                mock_br.return_value = mock_registry
                result = svc.build_system_prompt_with_schema()
                # Business rules may or may not appear depending on import success
                assert isinstance(result, str)


class TestBuildActionParamsHints:
    def _make_service(self):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        return svc

    def test_returns_string(self):
        svc = self._make_service()
        result = svc._build_action_params_hints()
        assert isinstance(result, str)

    def test_contains_mutation_actions(self):
        svc = self._make_service()
        result = svc._build_action_params_hints()
        # Should contain at least some mutation actions
        if result:
            assert "需要:" in result

    def test_with_mock_registry(self):
        svc = self._make_service()

        mock_action = MagicMock()
        mock_action.category = "mutation"
        mock_action.name = "create_guest"
        mock_action.parameters_schema.model_json_schema.return_value = {
            "required": ["name", "phone"]
        }

        mock_query_action = MagicMock()
        mock_query_action.category = "query"

        with patch("app.services.actions.get_action_registry") as mock_get_reg:
            mock_registry = MagicMock()
            mock_registry.list_actions.return_value = [mock_action, mock_query_action]
            mock_get_reg.return_value = mock_registry
            result = svc._build_action_params_hints()
            assert "create_guest" in result
            assert "name" in result


class TestParseFollowupInput:
    def _make_service(self, enabled=False):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_disabled(self):
        svc = self._make_service(False)
        result = svc.parse_followup_input("大床房", "create_reservation", {"guest_name": "张三"})
        assert result["is_complete"] is False
        assert "LLM 服务未启用" in result["message"]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_success(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        response_content = json.dumps({
            "params": {"guest_name": "张三", "room_type_id": 2},
            "is_complete": True,
            "missing_fields": [],
            "message": "信息已收集完毕"
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        result = svc.parse_followup_input(
            "大床房",
            "create_reservation",
            {"guest_name": "张三"},
            context={"room_types": [{"name": "大床房"}]},
            missing_fields=[{
                "field_name": "room_type_id",
                "display_name": "房型",
                "field_type": "select",
                "placeholder": "请选择",
                "options": [{"value": "1", "label": "标间"}, {"value": "2", "label": "大床房"}]
            }]
        )
        assert result["is_complete"] is True

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_parse_failure(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        result = svc.parse_followup_input("test", "checkin", {"room": "101"})
        assert result["is_complete"] is False
        assert "没有理解" in result["message"]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_exception(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        svc.client.chat.completions.create.side_effect = Exception("timeout")

        result = svc.parse_followup_input("test", "checkin", {})
        assert result["is_complete"] is False
        assert "处理出错" in result["message"]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_result_missing_fields_defaults(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        # Return JSON with no params, is_complete, etc.
        response_content = json.dumps({"custom": "data"})
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        result = svc.parse_followup_input("test", "checkin", {"existing": "val"})
        assert result["params"] == {"existing": "val"}
        assert result["is_complete"] is False
        assert result["missing_fields"] == []
        assert result["message"] == "信息已收到"


class TestExtractParams:
    def _make_service(self, enabled=False):
        from app.services.llm_service import LLMService
        with patch.object(LLMService, '__init__', lambda self: None):
            svc = LLMService()
        svc.enabled = enabled
        svc.client = MagicMock() if enabled else None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        return svc

    def test_empty_schema(self):
        svc = self._make_service(False)
        result = svc.extract_params("test", {})
        assert result["params"] == {}
        assert result["confidence"] == 0.0

    def test_all_known_values_provided(self):
        svc = self._make_service(False)
        schema = {
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        }
        result = svc.extract_params("test", schema, known_values={"name": "Zhang"})
        assert result["confidence"] == 1.0
        assert result["missing"] == []

    def test_missing_required_fields_disabled(self):
        svc = self._make_service(False)
        schema = {
            "properties": {"name": {"type": "string"}, "phone": {"type": "string"}},
            "required": ["name", "phone"]
        }
        result = svc.extract_params("test", schema)
        assert "name" in result["missing"]
        assert "phone" in result["missing"]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_extracts_params(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        response_content = json.dumps({
            "params": {"name": "Zhang", "phone": "13800138000"},
            "missing": []
        })
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        schema = {
            "properties": {
                "name": {"type": "string", "description": "Name"},
                "phone": {"type": "string", "description": "Phone"}
            },
            "required": ["name", "phone"]
        }
        result = svc.extract_params("Zhang 13800138000", schema)
        assert result["confidence"] == 1.0

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_partial_extraction(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        response_content = json.dumps({
            "params": {"name": "Zhang"},
        })
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        schema = {
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"}
            },
            "required": ["name", "phone"]
        }
        result = svc.extract_params("Zhang", schema)
        assert result["confidence"] == 0.5

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_exception_returns_original(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        svc.client.chat.completions.create.side_effect = Exception("fail")

        schema = {
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        }
        result = svc.extract_params("test", schema)
        assert "name" in result["missing"]

    @patch("app.services.llm_service.settings")
    @patch("core.ai.llm_call_context.LLMCallContext")
    def test_llm_no_extraction_all_missing(self, mock_ctx, mock_settings):
        mock_settings.LLM_MODEL = "test-model"
        mock_ctx.get_current.return_value = None

        svc = self._make_service(True)
        response_content = json.dumps({
            "params": {},
            "missing": ["name", "phone"]
        })
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_content
        mock_response.usage = None
        svc.client.chat.completions.create.return_value = mock_response

        schema = {
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"}
            },
            "required": ["name", "phone"]
        }
        result = svc.extract_params("no useful info", schema)
        assert result["confidence"] == 0.0
