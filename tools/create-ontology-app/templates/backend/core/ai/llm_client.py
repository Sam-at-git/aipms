"""
core/ai/llm_client.py

LLM 客户端接口抽象

提供统一的 LLM 调用接口，支持多种 LLM 提供商（OpenAI、DeepSeek、Azure、Ollama 等）。
参考：app/services/llm_service.py
"""
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable
from datetime import date
from dataclasses import dataclass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class LLMResponse:
    """LLM 响应封装"""
    content: str
    raw_response: Optional[Any] = None
    model: str = ""
    usage: Optional[Dict[str, int]] = None

    def to_json(self) -> Optional[Dict]:
        """尝试将内容解析为 JSON"""
        return extract_json_from_text(self.content)


class LLMClient(ABC):
    """
    LLM 客户端抽象基类

    定义了所有 LLM 客户端必须实现的接口，支持：
    - 基本对话
    - 流式输出
    - JSON 模式
    - 错误处理和重试
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> LLMResponse:
        """
        发起对话请求

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            max_tokens: 最大 token 数
            response_format: 响应格式，如 {"type": "json_object"}
            stream: 是否使用流式输出

        Returns:
            LLMResponse 对象
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """检查客户端是否可用"""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        pass


class OpenAICompatibleClient(LLMClient):
    """
    OpenAI 兼容客户端

    支持 OpenAI、DeepSeek、Azure、Ollama 等兼容 OpenAI API 的服务。

    Configuration:
        - api_key: API 密钥
        - base_url: API 基础 URL
        - model: 模型名称
        - timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: float = 30.0,
        max_retries: int = 2
    ):
        """
        初始化 OpenAI 兼容客户端

        Args:
            api_key: API 密钥，为 None 时从环境变量读取
            base_url: API 基础 URL
            model: 模型名称
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.timeout = timeout
        self.max_retries = max_retries

        if self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
                max_retries=max_retries
            )
            self._enabled = True
        else:
            self._client = None
            self._enabled = False

    def is_enabled(self) -> bool:
        """检查客户端是否可用"""
        return self._enabled and self._client is not None

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "enabled": self.is_enabled(),
            "timeout": self.timeout
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> LLMResponse:
        """
        发起对话请求

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            response_format: 响应格式
            stream: 是否使用流式输出

        Returns:
            LLMResponse 对象
        """
        if not self.is_enabled():
            return LLMResponse(
                content="",
                model=self.model,
                usage=None
            )

        try:
            # 尝试使用指定的响应格式
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            if response_format:
                kwargs["response_format"] = response_format

            response = self._client.chat.completions.create(**kwargs)

            if stream:
                # 流式输出处理
                content_parts = []
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)
                content = "".join(content_parts)
            else:
                content = response.choices[0].message.content

            return LLMResponse(
                content=content or "",
                raw_response=response,
                model=self.model,
                usage=getattr(response, "usage", None)
            )

        except Exception as e:
            # 尝试回退到普通模式（某些 API 不支持 json_object）
            if response_format and response_format.get("type") == "json_object":
                return self._chat_without_json_format(
                    messages, temperature, max_tokens
                )
            raise

    def _chat_without_json_format(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """
        在不支持 JSON 模式时回退到普通模式
        """
        # 在最后一条系统消息中强调返回 JSON
        enhanced_messages = messages.copy()
        for i, msg in enumerate(enhanced_messages):
            if msg.get("role") == "system":
                enhanced_messages[i] = {
                    "role": "system",
                    "content": msg["content"] + "\n\n**重要：请务必只返回纯 JSON 格式，不要添加任何其他文字说明。**"
                }
                break

        response = self._client.chat.completions.create(
            model=self.model,
            messages=enhanced_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            raw_response=response,
            model=self.model,
            usage=getattr(response, "usage", None)
        )


# ==================== JSON 提取工具 ====================

def extract_json_from_text(text: str) -> Optional[Dict]:
    """
    从文本中提取 JSON，支持多种容错处理

    处理场景:
    1. JSON 被包裹在 markdown 代码块中 (```json ... ```)
    2. JSON 包含注释 (// 或 /* */)
    3. JSON 包含尾随逗号
    4. JSON 使用单引号而非双引号
    5. 多个 JSON 对象，提取第一个有效的

    Args:
        text: 包含 JSON 的文本

    Returns:
        解析后的字典，失败返回 None
    """
    if not text:
        return None

    text = text.strip()

    # 尝试直接解析
    result = _try_parse_json(text)
    if result:
        return result

    # 尝试从 markdown 代码块中提取
    result = _extract_from_code_block(text)
    if result:
        return result

    # 尝试提取花括号内容
    result = _extract_braces_content(text)
    if result:
        return result

    # 尝试清理并修复常见问题
    result = _try_parse_with_cleaning(text)
    if result:
        return result

    return None


def _try_parse_json(text: str) -> Optional[Dict]:
    """尝试直接解析 JSON"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_from_code_block(text: str) -> Optional[Dict]:
    """从 markdown 代码块中提取 JSON"""
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code_content = match.group(1).strip()
            result = _try_parse_json(code_content)
            if result:
                return result
            result = _try_parse_with_cleaning(code_content)
            if result:
                return result

    return None


def _extract_braces_content(text: str) -> Optional[Dict]:
    """从文本中提取第一个完整的 JSON 对象"""
    start = text.find('{')
    if start == -1:
        return None

    # 使用栈匹配花括号
    stack = []
    end = -1

    for i in range(start, len(text)):
        char = text[i]
        if char == '{':
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
            if not stack:
                end = i + 1
                break

    if end == -1:
        return None

    json_str = text[start:end]
    result = _try_parse_with_cleaning(json_str)
    return result


def _try_parse_with_cleaning(text: str) -> Optional[Dict]:
    """清理文本后尝试解析"""
    text = _remove_comments(text)
    text = _convert_single_quotes(text)
    text = _remove_trailing_commas(text)
    text = _fix_escaped_newlines(text)

    return _try_parse_json(text)


def _remove_comments(text: str) -> str:
    """移除 JavaScript 风格的注释"""
    text = re.sub(r'//.*?(?=\n|$)', '', text)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    text = re.sub(r'#.*?(?=\n|$)', '', text)
    return text


def _convert_single_quotes(text: str) -> str:
    """将单引号转换为双引号"""
    def replace_quotes(match):
        full_match = match.group(0)
        if '"' in full_match:
            return full_match
        return full_match.replace("'", '"')

    text = re.sub(r"'([^']+)'(\s*:)", replace_quotes, text)
    text = re.sub(r'(\s*:\s*)\'([^\']*?)\'(?=\s*[,}])', r'\1"\2"', text)
    text = re.sub(r'\[\'([^\']*?)\'\]', r'["\1"]', text)

    return text


def _remove_trailing_commas(text: str) -> str:
    """移除 JSON 中的尾随逗号"""
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _fix_escaped_newlines(text: str) -> str:
    """修复字符串中未正确转义的换行符"""
    def fix_string_content(match):
        content = match.group(1)
        content = content.replace('\\', '\\\\')
        content = content.replace('\n', '\\n')
        content = content.replace('\r', '\\r')
        content = content.replace('\t', '\\t')
        return '"' + content + '"'

    text = re.sub(r'"([^"\\]*(?:\\.[^"\\\\]*)*)"', fix_string_content, text)
    return text


# ==================== 工厂函数 ====================

def create_llm_client(
    provider: str = "openai",
    **kwargs
) -> LLMClient:
    """
    创建 LLM 客户端实例

    Args:
        provider: 提供商类型 ("openai", "deepseek", "ollama")
        **kwargs: 传递给客户端的额外参数

    Returns:
        LLMClient 实例
    """
    if provider in ("openai", "deepseek", "ollama"):
        return OpenAICompatibleClient(**kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = [
    "LLMClient",
    "OpenAICompatibleClient",
    "LLMResponse",
    "extract_json_from_text",
    "create_llm_client",
]
