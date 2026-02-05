"""
tests/ai/test_llm_client.py

LLM 客户端单元测试
"""
import pytest

from core.ai.llm_client import (
    LLMClient,
    OpenAICompatibleClient,
    LLMResponse,
    extract_json_from_text,
    _try_parse_json,
    _extract_from_code_block,
    _extract_braces_content,
)


class TestJSONExtraction:
    """JSON 提取测试"""

    def test_simple_json(self):
        """测试简单 JSON 解析"""
        text = '{"key": "value", "number": 123}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 123

    def test_json_in_markdown_code_block(self):
        """测试 Markdown 代码块中的 JSON"""
        text = '''```json
{"message": "hello", "actions": []}
```'''
        result = extract_json_from_text(text)
        assert result is not None
        assert result["message"] == "hello"

    def test_json_with_comments(self):
        """测试带注释的 JSON"""
        text = '''{"key": "value", // comment
        "number": 123}'''
        result = extract_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"

    def test_json_with_trailing_comma(self):
        """测试带尾随逗号的 JSON"""
        text = '{"key": "value", "number": 123,}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"

    def test_json_with_single_quotes(self):
        """测试单引号 JSON"""
        text = "{'key': 'value', 'number': 123}"
        result = extract_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"

    def test_extract_from_mixed_text(self):
        """测试从混合文本中提取 JSON"""
        text = '''这是一些文字

```json
{"message": "hello"}
```

更多文字'''
        result = extract_json_from_text(text)
        assert result is not None
        assert result["message"] == "hello"

    def test_invalid_json_returns_none(self):
        """测试无效 JSON 返回 None"""
        text = "not a json"
        result = extract_json_from_text(text)
        assert result is None


class TestLLMResponse:
    """LLMResponse 测试"""

    def test_to_json_valid(self):
        """测试解析有效 JSON"""
        response = LLMResponse(content='{"key": "value"}')
        result = response.to_json()
        assert result is not None
        assert result["key"] == "value"

    def test_to_json_invalid(self):
        """测试解析无效 JSON"""
        response = LLMResponse(content="not json")
        result = response.to_json()
        assert result is None


class TestOpenAICompatibleClient:
    """OpenAI 兼容客户端测试"""

    def test_client_without_api_key(self):
        """测试没有 API key 的客户端"""
        client = OpenAICompatibleClient(api_key=None)
        assert not client.is_enabled()

    def test_client_with_empty_api_key(self):
        """测试空 API key 的客户端"""
        client = OpenAICompatibleClient(api_key="")
        assert not client.is_enabled()

    def test_get_model_info(self):
        """测试获取模型信息"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            model="test-model",
            base_url="https://test.example.com"
        )
        info = client.get_model_info()
        assert info["model"] == "test-model"
        assert info["base_url"] == "https://test.example.com"
        assert info["timeout"] == 30.0


class TestLLMResponseDataclass:
    """LLMResponse 数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        response = LLMResponse(content="test")
        assert response.content == "test"
        assert response.raw_response is None
        assert response.model == ""
        assert response.usage is None

    def test_with_all_fields(self):
        """测试所有字段"""
        response = LLMResponse(
            content="test",
            raw_response={"data": "value"},
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        )
        assert response.content == "test"
        assert response.raw_response == {"data": "value"}
        assert response.model == "gpt-4"
        assert response.usage == {"prompt_tokens": 10, "completion_tokens": 20}


class TestJSONHelpers:
    """JSON 工具函数测试"""

    def test_try_parse_json_valid(self):
        """测试解析有效 JSON"""
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_try_parse_json_invalid(self):
        """测试解析无效 JSON"""
        result = _try_parse_json("not json")
        assert result is None

    def test_extract_from_code_block_json(self):
        """测试从 JSON 代码块提取"""
        text = '```json\n{"key": "value"}\n```'
        result = _extract_from_code_block(text)
        assert result == {"key": "value"}

    def test_extract_from_code_block_plain(self):
        """测试从普通代码块提取"""
        text = '```\n{"key": "value"}\n```'
        result = _extract_from_code_block(text)
        assert result == {"key": "value"}

    def test_extract_braces_content(self):
        """测试提取花括号内容"""
        text = 'some text {"key": "value"} more text'
        result = _extract_braces_content(text)
        assert result == {"key": "value"}

    def test_extract_braces_nested(self):
        """测试嵌套花括号"""
        text = '{"outer": {"inner": "value"}}'
        result = _extract_braces_content(text)
        assert result == {"outer": {"inner": "value"}}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
