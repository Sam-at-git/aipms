"""
LLM 服务 - 支持 OpenAI 兼容 API
负责将自然语言转换为结构化的业务操作
"""
import json
import os
import re
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from openai import OpenAI
from app.config import settings


def extract_json_from_text(text: str) -> Optional[Dict]:
    """
    从文本中提取 JSON，支持多种容错处理

    处理场景:
    1. JSON 被包裹在 markdown 代码块中 (```json ... ```)
    2. JSON 包含注释 (// 或 /* */)
    3. JSON 包含尾随逗号
    4. JSON 使用单引号而非双引号
    5. JSON 未被正确转义
    6. 多个 JSON 对象，提取第一个有效的
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
    # 匹配 ```json ... ``` 或 ``` ... ```
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
            # 尝试清理后解析
            result = _try_parse_with_cleaning(code_content)
            if result:
                return result

    return None


def _extract_braces_content(text: str) -> Optional[Dict]:
    """从文本中提取第一个完整的 JSON 对象（跳过字符串内的花括号）"""
    start = text.find('{')
    if start == -1:
        return None

    # 使用栈匹配花括号，跳过引号内的内容
    stack = []
    end = -1
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
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
    # 移除注释
    text = _remove_comments(text)

    # 处理单引号
    text = _convert_single_quotes(text)

    # 移除尾随逗号
    text = _remove_trailing_commas(text)

    # 修复未转义的换行符
    text = _fix_escaped_newlines(text)

    # 替换非标准 JSON 值（NaN, Infinity, -Infinity -> null）
    text = re.sub(r'\bNaN\b', 'null', text)
    text = re.sub(r'\bInfinity\b', 'null', text)
    text = re.sub(r'-Infinity\b', 'null', text)

    # 移除控制字符（保留 \n \r \t）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # 尝试解析
    return _try_parse_json(text)


def _remove_comments(text: str) -> str:
    """移除 JavaScript 风格的注释"""
    # 移除单行注释 //
    text = re.sub(r'//.*?(?=\n|$)', '', text)

    # 移除多行注释 /* */
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)

    # 移除 Python 风格的注释 #
    text = re.sub(r'#.*?(?=\n|$)', '', text)

    return text


def _convert_single_quotes(text: str) -> str:
    """将单引号转换为双引号（处理键名和字符串值）"""
    # 这是一个简化的处理，只在安全的情况下转换
    # 使用正则表达式智能替换

    def replace_quotes(match):
        full_match = match.group(0)
        # 如果已经包含双引号，跳过
        if '"' in full_match:
            return full_match
        # 替换单引号为双引号
        return full_match.replace("'", '"')

    # 匹配对象键名: 'key':
    text = re.sub(r"'([^']+)'(\s*:)", replace_quotes, text)

    # 匹配字符串值: : 'value' (但不处理包含转义的)
    text = re.sub(r'(\s*:\s*)\'([^\']*?)\'(?=\s*[,}])', r'\1"\2"', text)

    # 处理数组中的字符串
    text = re.sub(r'\[\'([^\']*?)\'\]', r'["\1"]', text)

    return text


def _remove_trailing_commas(text: str) -> str:
    """移除 JSON 中的尾随逗号"""
    # 移除 } 或 ] 前的逗号
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _fix_escaped_newlines(text: str) -> str:
    """修复字符串中未正确转义的换行符"""
    # 将字符串内的实际换行替换为 \n
    # 这是一个简化版本，处理大多数常见情况

    def fix_string_content(match):
        content = match.group(1)  # 引号内的内容
        # 转义换行符和其他特殊字符
        content = content.replace('\\', '\\\\')
        content = content.replace('\n', '\\n')
        content = content.replace('\r', '\\r')
        content = content.replace('\t', '\\t')
        return '"' + content + '"'

    # 匹配双引号字符串内容
    text = re.sub(r'"([^"\\]*(?:\\.[^"\\\\]*)*)"', fix_string_content, text)

    return text


def extract_and_validate_actions(
    text: str,
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    从文本中提取并验证 JSON 响应

    Args:
        text: LLM 返回的原始文本
        required_fields: 必需的字段列表

    Returns:
        解析后的字典，如果解析失败则返回默认结构
    """
    required_fields = required_fields or ['message', 'suggested_actions', 'context']

    # 提取 JSON
    result = extract_json_from_text(text)

    if result is None:
        # 解析完全失败，返回默认结构
        return {
            "message": text[:200] if len(text) > 200 else text,  # 截取前200字符作为消息
            "suggested_actions": [],
            "context": {"parse_error": True, "raw_response": text}
        }

    # 验证必需字段
    validated = {}
    for field in required_fields:
        if field not in result:
            if field == "suggested_actions":
                validated[field] = []
            elif field == "context":
                validated[field] = {}
            elif field == "message":
                validated[field] = "已处理您的请求"
            else:
                validated[field] = None
        else:
            validated[field] = result[field]

    # 确保 suggested_actions 是列表
    if not isinstance(validated.get("suggested_actions"), list):
        validated["suggested_actions"] = []

    # 验证每个 action 的结构
    validated["suggested_actions"] = [
        _validate_action(action) for action in validated["suggested_actions"]
    ]

    # 确保 context 是字典
    if not isinstance(validated.get("context"), dict):
        validated["context"] = {}

    return validated


def _validate_action(action: Any) -> Dict[str, Any]:
    """验证并标准化单个 action"""
    if not isinstance(action, dict):
        return {
            "action_type": "ontology_query",
            "entity_type": "unknown",
            "description": "无效的操作",
            "requires_confirmation": False,
            "params": {}
        }

    validated = {
        "action_type": action.get("action_type", "ontology_query"),
        "entity_type": action.get("entity_type", "unknown"),
        "description": action.get("description", action.get("action_type", "")),
        "requires_confirmation": action.get("requires_confirmation", True),
        "params": action.get("params") if isinstance(action.get("params"), dict) else {}
    }

    # 添加可选字段
    if "entity_id" in action:
        validated["entity_id"] = action["entity_id"]

    return validated


class TopicRelevance:
    """话题相关性结果"""
    CONTINUATION = "continuation"  # 继续话题
    NEW_TOPIC = "new_topic"  # 新话题
    FOLLOWUP_ANSWER = "followup_answer"  # 回答系统追问


def detect_language(text: str) -> str:
    """
    检测文本语言（中文 vs 英文）

    通过中文字符比例判断：
    - 中文字符占比 > 30% → "zh"
    - 否则 → "en"
    """
    if not text:
        return "zh"
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ratio = chinese_chars / len(text)
    return "zh" if ratio > 0.3 else "en"


# 多语言提示词后缀
LANGUAGE_PROMPTS = {
    "zh": "请用中文回复用户。",
    "en": "Please respond to the user in English.",
}


class LLMService:
    """LLM 服务"""

    # 酒店领域提示词 — 仅包含领域特定约定
    # 操作列表、参数说明、状态机、追问格式等由 PromptBuilder 从 ActionRegistry 动态生成
    # 此属性保留类级别读写，供 settings API 兼容
    SYSTEM_PROMPT = """你是 AIPMS 酒店管理系统的智能助手。

**酒店业务约定：**
1. 房间相关：优先使用 room_number（字符串）而非 room_id，让后端自动转换
2. 当用户指定了房型名称（如"大床房"、"标间"），使用 room_type_id 参数传递（ID 为数字）
3. 查询"空闲房间"时，status 使用 in 操作符，值为 ["vacant_clean", "vacant_dirty"]
4. 对于房型选择，使用 select 类型并提供选项列表（value 为 ID）
5. 追问时设置 requires_confirmation: false，信息完整后设为 true
6. 当信息不完整时，必须在 params 中包含已收集的所有信息，缺失字段在 missing_fields 中定义

**日期处理 - 重要：**
- 将所有相对日期转换为具体的 ISO 格式日期（YYYY-MM-DD）
- "今天" → 当天, "明天"/"明日" → +1天, "后天" → +2天, "大后天" → +3天
- params 中的日期字段必须使用 ISO 格式，不要使用相对词汇

**ontology_query 参数结构：**
ontology_query 用于动态字段级查询，params 结构如下：
{{
  "entity": "实体名 (Guest/Room/Reservation/StayRecord/Task/Bill/Employee)",
  "fields": ["要返回的字段列表"],
  "filters": [{{"field": "字段", "operator": "eq/ne/gt/gte/lt/lte/in/like", "value": "值"}}],
  "joins": [{{"entity": "关联实体", "filters": {{"字段": "值"}}}}],
  "limit": 数字（可选，默认100）
}}
- 查询"空闲房间"时：{{"entity": "Room", "filters": [{{"field": "status", "operator": "in", "value": ["vacant_clean", "vacant_dirty"]}}]}}
- 查询"在住客人"时：{{"entity": "Guest", "joins": [{{"entity": "StayRecord", "filters": {{"status": "ACTIVE"}}}}]}}

**示例对话：**

用户: "为散客汪先生（电话13512345666）办理入住304房间，明天入住，住两天"
回复: {{
  "message": "好的，我来帮您为散客汪先生办理入住。\\n- 客人：汪先生\\n- 电话：13512345666\\n- 房间：304\\n- 入住：明天\\n- 退房：后天\\n\\n确认办理入住吗？",
  "suggested_actions": [{{
    "action_type": "walkin_checkin",
    "entity_type": "guest",
    "description": "为汪先生办理散客入住",
    "requires_confirmation": true,
    "params": {{
      "guest_name": "汪先生",
      "guest_phone": "13512345666",
      "room_number": "304",
      "expected_check_out": "2026-02-13"
    }}
  }}],
  "context": {{}}
}}

用户: "增加新的客户 李瓶儿 13312345670，银卡"
回复: {{
  "message": "好的，我来为您创建新客户李瓶儿。\\n- 姓名：李瓶儿\\n- 电话：13312345670\\n- 客户等级：银卡\\n\\n确认创建客户吗？",
  "suggested_actions": [{{
    "action_type": "create_guest",
    "entity_type": "guest",
    "description": "创建新客户李瓶儿",
    "requires_confirmation": true,
    "params": {{
      "name": "李瓶儿",
      "phone": "13312345670",
      "tier": "silver"
    }}
  }}],
  "context": {{}}
}}

用户: "创建一个预订，李四，电话13800138000，明天入住，住两天"
回复: {{
  "message": "好的，我来帮您创建预订。已收集信息：\\n- 客人：李四\\n- 电话：13800138000\\n- 入住：明天\\n- 退房：后天\\n\\n请问需要预订什么房型？",
  "suggested_actions": [{{
    "action_type": "create_reservation",
    "entity_type": "reservation",
    "description": "创建李四的预订",
    "requires_confirmation": false,
    "params": {{
      "guest_name": "李四",
      "guest_phone": "13800138000",
      "check_in_date": "2026-02-11",
      "check_out_date": "2026-02-12",
      "adult_count": 1
    }},
    "missing_fields": [{{
      "field_name": "room_type_id",
      "display_name": "房型",
      "field_type": "select",
      "options": [{{"value": "1", "label": "标间"}}, {{"value": "2", "label": "大床房"}}, {{"value": "3", "label": "豪华间"}}],
      "placeholder": "请选择房型",
      "required": true
    }}]
  }}],
  "context": {{"guest_name": "李四"}}
}}

用户: "201房退房"
回复: {{
  "message": "找到201房的住宿记录，确认办理退房吗？",
  "suggested_actions": [{{
    "action_type": "checkout",
    "entity_type": "stay_record",
    "entity_id": null,
    "description": "为201房办理退房",
    "requires_confirmation": true,
    "params": {{"room_number": "201"}}
  }}],
  "context": {{"room_number": "201"}}
}}

**重要：对于所有数据查询请求，必须使用 `ontology_query` action_type 并提供结构化的 params。不要使用 `view` action_type。对于跨实体的运营报表/统计，使用 `query_reports`。**

用户: "查看房态"
回复: {{
  "message": "正在为您查询当前房态...",
  "suggested_actions": [{{"action_type": "ontology_query", "entity_type": "Room", "requires_confirmation": false, "params": {{"entity": "Room", "fields": ["room_number", "floor", "status"]}}}}],
  "context": {{}}
}}

用户: "当前有多少在住客人？"
回复: {{
  "message": "正在为您查询在住客人...",
  "suggested_actions": [{{"action_type": "ontology_query", "entity_type": "Guest", "requires_confirmation": false, "params": {{"entity": "Guest", "joins": [{{"entity": "StayRecord", "filters": {{"status": "ACTIVE"}}}}]}}}}],
  "context": {{}}
}}

用户: "系统有哪些员工？"
回复: {{
  "message": "正在为您查询员工信息...",
  "suggested_actions": [{{"action_type": "ontology_query", "entity_type": "Employee", "requires_confirmation": false, "params": {{"entity": "Employee", "fields": ["username", "name", "role"]}}}}],
  "context": {{}}
}}

用户: "今日运营概览"
回复: {{
  "message": "正在为您生成今日运营报告...",
  "suggested_actions": [{{"action_type": "query_reports", "entity_type": "report", "requires_confirmation": false, "params": {{}}}}],
  "context": {{}}
}}
"""

    def __init__(self):
        """初始化 LLM 客户端"""
        self.api_key = settings.OPENAI_API_KEY
        self.enabled = settings.ENABLE_LLM and bool(self.api_key)

        if self.enabled:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=settings.OPENAI_BASE_URL,
                timeout=30.0
            )
        else:
            self.client = None

        # Phase 2.5: 初始化 PromptBuilder 用于本体感知（注入 ActionRegistry）
        try:
            from core.ai.prompt_builder import PromptBuilder
            from app.services.actions import get_action_registry
            self._prompt_builder = PromptBuilder(action_registry=get_action_registry())
        except ImportError:
            self._prompt_builder = None

        # Schema 缓存
        self._query_schema_cache = None

    def _instrumented_completion(self, messages, **kwargs):
        """
        Wrapper around self.client.chat.completions.create() that records
        each LLM call to the debug logger via LLMCallContext.

        Transparent: returns the original response object unchanged.
        """
        from core.ai.llm_call_context import LLMCallContext

        ctx = LLMCallContext.get_current()
        started_at = datetime.now()

        try:
            response = self.client.chat.completions.create(messages=messages, **kwargs)
            ended_at = datetime.now()
            latency_ms = int((ended_at - started_at).total_seconds() * 1000)

            # Record interaction if we have an active debug context
            if ctx and ctx.get('debug_logger') and ctx.get('session_id') and ctx.get('ooda_phase'):
                try:
                    seq = LLMCallContext.next_sequence()
                    debug_logger = ctx['debug_logger']

                    # Extract token usage
                    tokens_input = None
                    tokens_output = None
                    tokens_total = None
                    if hasattr(response, 'usage') and response.usage:
                        tokens_input = getattr(response.usage, 'prompt_tokens', None)
                        tokens_output = getattr(response.usage, 'completion_tokens', None)
                        tokens_total = getattr(response.usage, 'total_tokens', None)

                    # Extract response text
                    resp_text = None
                    if response.choices:
                        resp_text = response.choices[0].message.content

                    # Serialize prompt (messages array)
                    prompt_json = json.dumps(messages, ensure_ascii=False, default=str)

                    debug_logger.log_llm_interaction(
                        session_id=ctx['session_id'],
                        sequence_number=seq,
                        ooda_phase=ctx['ooda_phase'],
                        call_type=ctx.get('call_type', 'unknown'),
                        started_at=started_at.isoformat(),
                        ended_at=ended_at.isoformat(),
                        latency_ms=latency_ms,
                        model=kwargs.get('model', None),
                        prompt=prompt_json,
                        response=resp_text,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        tokens_total=tokens_total,
                        temperature=kwargs.get('temperature', None),
                        success=True,
                    )
                except Exception as log_err:
                    import logging
                    logging.getLogger(__name__).debug(f"Failed to log LLM interaction: {log_err}")

            return response

        except Exception as e:
            ended_at = datetime.now()
            latency_ms = int((ended_at - started_at).total_seconds() * 1000)

            # Record failed interaction
            if ctx and ctx.get('debug_logger') and ctx.get('session_id') and ctx.get('ooda_phase'):
                try:
                    seq = LLMCallContext.next_sequence()
                    debug_logger = ctx['debug_logger']
                    prompt_json = json.dumps(messages, ensure_ascii=False, default=str)
                    debug_logger.log_llm_interaction(
                        session_id=ctx['session_id'],
                        sequence_number=seq,
                        ooda_phase=ctx['ooda_phase'],
                        call_type=ctx.get('call_type', 'unknown'),
                        started_at=started_at.isoformat(),
                        ended_at=ended_at.isoformat(),
                        latency_ms=latency_ms,
                        model=kwargs.get('model', None),
                        prompt=prompt_json,
                        tokens_input=None,
                        tokens_output=None,
                        tokens_total=None,
                        temperature=kwargs.get('temperature', None),
                        success=False,
                        error=str(e),
                    )
                except Exception:
                    pass

            raise

    def on_ontology_changed(self):
        """本体变化时调用 - 清除 PromptBuilder 缓存"""
        if self._prompt_builder:
            self._prompt_builder.invalidate_cache()
        self._query_schema_cache = None

    def get_query_schema(self) -> str:
        """
        获取用于查询解析的 Ontology Schema

        Returns:
            Schema 描述字符串
        """
        if self._query_schema_cache is not None:
            return self._query_schema_cache

        if self._prompt_builder:
            self._query_schema_cache = self._prompt_builder.build_query_schema()
        else:
            # 回退：硬编码的基本 schema
            self._query_schema_cache = """
**可查询实体:**
- `Guest`: 客人信息
  - 字段: name, phone, id_type, id_number, tier
- `Room`: 房间信息
  - 字段: room_number, floor, status, room_type
- `Reservation`: 预订信息
  - 字段: reservation_no, check_in_date, check_out_date, status
- `StayRecord`: 住宿记录
  - 字段: check_in_time, expected_check_out, status
- `Task`: 任务
  - 字段: task_type, status, room_number
- `Bill`: 账单
  - 字段: total_amount, is_settled
- `Employee`: 员工
  - 字段: username, name, role

**实体关系:**
- `Guest` -> `StayRecord` (客人有住宿记录)
- `Guest` -> `Reservation` (客人有预订)
- `Room` -> `StayRecord` (房间有住宿记录)
- `Room` -> `Task` (房间有任务)
- `StayRecord` -> `Room` (住宿记录关联房间)
- `StayRecord` -> `Guest` (住宿记录关联客人)
"""

        return self._query_schema_cache

    def build_system_prompt_with_schema(
        self,
        language: Optional[str] = None,
        include_schema: bool = False,
        include_actions: bool = True,
        include_glossary: bool = True,
        user_role: str = "",
        message_hint: str = "",
    ) -> str:
        """
        构建包含 Schema 的系统提示词

        完全委托给 PromptBuilder.build_system_prompt()，通过 domain_prompt
        注入酒店领域指令（self.SYSTEM_PROMPT）。操作列表、参数说明、状态机、
        追问格式等全部从 ActionRegistry / OntologyRegistry 动态生成。

        Args:
            language: 语言 ("zh"/"en")
            include_schema: 是否包含查询 Schema
            include_actions: 是否包含操作描述（默认 True）
            include_glossary: 是否包含领域关键词表（默认 True）
            user_role: 用户角色（用于按需注入系统实体）
            message_hint: 用户消息（用于关键词匹配按需注入系统实体）

        Returns:
            完整的系统提示词
        """
        if self._prompt_builder:
            from core.ai.prompt_builder import PromptContext
            context = PromptContext(
                user_role=user_role,
                domain_prompt=self.SYSTEM_PROMPT,
                include_entities=True,
                include_actions=include_actions,
                include_rules=True,
                include_state_machines=True,
                message_hint=message_hint,
            )
            system_prompt = self._prompt_builder.build_system_prompt(context)

            # 领域关键词表（Domain Glossary）
            if include_glossary:
                try:
                    glossary = self._prompt_builder._build_domain_glossary()
                    if glossary:
                        system_prompt += f"\n\n{glossary}"
                except Exception:
                    pass
        else:
            # 无 PromptBuilder 时回退到纯领域 prompt
            system_prompt = self.SYSTEM_PROMPT

        # 语言提示
        if language:
            lang_hint = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["zh"])
            system_prompt += f"\n\n{lang_hint}"

        # 查询 Schema（用于 ontology_query）
        if include_schema:
            system_prompt += f"\n\n{self.get_query_schema()}"

        # 注入业务规则（从 core/ontology 读取）
        try:
            from core.ontology.business_rules import get_business_rules
            rules_registry = get_business_rules()
            business_rules_prompt = rules_registry.export_for_llm()
            if business_rules_prompt:
                system_prompt += f"\n\n**业务规则:**\n{business_rules_prompt}"
        except ImportError:
            pass  # 业务规则模块不可用，继续

        return system_prompt

    def is_enabled(self) -> bool:
        """检查 LLM 是否可用"""
        return self.enabled

    def chat(self, message: str, context: Optional[Dict] = None, language: Optional[str] = None) -> Dict[str, Any]:
        """
        与 LLM 对话，获取结构化响应

        Args:
            message: 用户消息
            context: 上下文信息（如当前用户、房间列表等）
            language: 回复语言 ("zh"/"en")，None 则自动检测

        Returns:
            包含 message, suggested_actions, context 的字典
        """
        if not self.enabled:
            return {
                "message": "LLM 服务未启用。请设置 OPENAI_API_KEY 环境变量。",
                "suggested_actions": [],
                "context": {"error": "llm_disabled"}
            }

        # 构建上下文信息
        context_info = self._build_context_info(context)

        # 语言检测
        lang = language or detect_language(message)

        # 使用 build_system_prompt_with_schema 动态注入操作描述（OAG 机制）
        include_schema = context and context.get('include_query_schema', False)
        user_role = context.get('user_role', '') if context else ''
        system_prompt = self.build_system_prompt_with_schema(
            language=lang,
            include_schema=include_schema,
            include_actions=True,  # 动态注入所有注册的操作
            user_role=user_role,
            message_hint=message,
        )

        # 日期上下文已由 PromptBuilder._build_date_context() 注入到 system_prompt
        # 此处仅在用户消息中提供当前日期供 LLM 解析相对日期
        today = date.today()
        user_date_hint = f"\n(当前日期: {today.strftime('%Y-%m-%d')})"

        try:
            # 构建 messages 数组
            messages = [{"role": "system", "content": system_prompt}]

            # 插入对话历史（如果有）
            conv_history = context.get("conversation_history", []) if context else []
            for h in conv_history[-6:]:  # 最近 3 轮
                role = h.get("role", "user")
                content = h.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:500]})

            # 当前用户消息
            messages.append({
                "role": "user",
                "content": f"{context_info}{user_date_hint}\n\n用户输入: {message}"
            })

            # 尝试使用 json_object 模式
            from core.ai.llm_call_context import LLMCallContext
            LLMCallContext.before_call("decide", "chat")
            try:
                response = self._instrumented_completion(
                    messages=messages,
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
            except Exception as json_error:
                # 某些 API 不支持 json_object 模式，回退到普通模式
                # 在系统提示词中强调返回 JSON
                enhanced_prompt = system_prompt + "\n\n**重要：请务必只返回纯 JSON 格式，不要添加任何其他文字说明。**"
                fallback_messages = [{"role": "system", "content": enhanced_prompt}]
                # 复用对话历史
                for h in conv_history[-6:]:
                    role = h.get("role", "user")
                    content = h.get("content", "")
                    if role in ("user", "assistant") and content:
                        fallback_messages.append({"role": role, "content": content[:500]})
                fallback_messages.append({
                    "role": "user",
                    "content": f"{context_info}{user_date_hint}\n\n用户输入: {message}"
                })

                LLMCallContext.before_call("decide", "chat")
                response = self._instrumented_completion(
                    messages=fallback_messages,
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS
                )

            content = response.choices[0].message.content

            # 使用增强的 JSON 提取和解析
            result = extract_and_validate_actions(content)

            # 记录解析状态用于调试
            if result.get("context", {}).get("parse_error"):
                # 解析失败，记录原始响应
                print(f"[LLM] JSON 解析失败，原始响应: {content[:500]}")

            return result

        except Exception as e:
            # API 调用失败
            import traceback
            error_detail = traceback.format_exc()

            return {
                "message": f"LLM 服务错误: {str(e)}",
                "suggested_actions": [],
                "context": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": error_detail
                }
            }

    def _build_context_info(self, context: Optional[Dict]) -> str:
        """构建上下文信息字符串"""
        if not context:
            return "**当前状态:** 无额外上下文信息"

        info_parts = ["**当前状态:**"]

        if context.get("room_summary"):
            rs = context["room_summary"]
            info_parts.append(f"- 总房间: {rs.get('total')}, 空闲: {rs.get('vacant_clean')}, 入住: {rs.get('occupied')}")

        # 添加可用房型信息（关键：让 LLM 知道有哪些房型）
        if context.get("room_types"):
            rt_list = ", ".join([
                f"{rt.get('name')}(ID:{rt.get('id')}, ¥{rt.get('price')})"
                for rt in context["room_types"]
            ])
            info_parts.append(f"- 可用房型: {rt_list}")

        if context.get("active_stays"):
            info_parts.append(f"- 在住客人: {len(context['active_stays'])} 位")
            for stay in context.get("active_stays", []):
                info_parts.append(
                    f"  - stay_record_id={stay.get('id')}, "
                    f"{stay.get('room_number')}号房: {stay.get('guest_name')}, "
                    f"预计退房: {stay.get('expected_check_out')}"
                )

        if context.get("pending_tasks"):
            info_parts.append(f"- 待处理任务: {len(context['pending_tasks'])} 个")
            for task in context.get("pending_tasks", []):
                info_parts.append(
                    f"  - task_id={task.get('id')}, "
                    f"{task.get('room_number')}号房, "
                    f"类型: {task.get('task_type')}"
                )

        if context.get("user_role"):
            info_parts.append(f"- 当前用户角色: {context['user_role']}")

        return "\n".join(info_parts)

    def _validate_and_clean_result(self, result: Dict) -> Dict:
        """验证和清理 LLM 返回结果"""
        # 确保必要字段存在
        if "message" not in result:
            result["message"] = "已处理您的请求"
        if "suggested_actions" not in result:
            result["suggested_actions"] = []
        if "context" not in result:
            result["context"] = {}

        # 验证每个 action 的必要字段
        for action in result.get("suggested_actions", []):
            if "action_type" not in action:
                action["action_type"] = "ontology_query"
            if "entity_type" not in action:
                action["entity_type"] = "unknown"
            if "description" not in action:
                action["description"] = action.get("action_type", "")
            if "requires_confirmation" not in action:
                action["requires_confirmation"] = True
            if "params" not in action:
                action["params"] = {}

        return result

    def extract_entities(self, message: str) -> Dict[str, Any]:
        """
        从消息中提取实体（备用方法）
        使用 LLM 进行实体抽取
        """
        if not self.enabled:
            return {}

        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": """
                    从用户消息中提取酒店管理相关的实体，返回 JSON 格式：
                    {
                        "room_number": "房间号（字符串）",
                        "guest_name": "客人姓名",
                        "phone": "电话号码",
                        "dates": ["日期字符串"],
                        "amount": "金额",
                        "task_type": "cleaning|maintenance",
                        "room_status": "vacant_clean|occupied|vacant_dirty|out_of_order"
                    }
                    只返回明确提到的信息，不要编造。
                    """},
                    {"role": "user", "content": message}
                ],
                temperature=0,
                max_tokens=300,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception:
            return {}

    def check_topic_relevance(
        self,
        new_message: str,
        history: List[Dict[str, str]]
    ) -> str:
        """
        判断新消息与历史对话的关联性

        Args:
            new_message: 新的用户消息
            history: 历史消息列表，每项包含 role 和 content

        Returns:
            TopicRelevance 常量之一：
            - continuation: 继续当前话题
            - new_topic: 开始新话题
            - followup_answer: 回答系统追问
        """
        # 如果没有历史，一定是新话题
        if not history:
            return TopicRelevance.NEW_TOPIC

        # 规则优先：检测是否是回答系统追问
        last_msg = history[-1] if history else None
        if last_msg and last_msg.get('role') == 'assistant':
            last_content = last_msg.get('content', '')
            # 检测追问模式（问号结尾或包含"请"字的询问）
            if '?' in last_content or '？' in last_content:
                # 检测用户的简短回答（可能是对追问的回答）
                if self._is_short_answer(new_message):
                    return TopicRelevance.FOLLOWUP_ANSWER

        # 规则：检测代词和确认词（表示继续话题）
        continuation_keywords = [
            '好的', '好', '是的', '对', '确认', '确定', '可以', '行',
            '这个', '那个', '他', '她', '它', '这', '那',
            '然后', '接着', '继续', '还有', '另外',
            '刚才', '之前', '上面'
        ]
        msg_lower = new_message.lower().strip()
        if any(msg_lower.startswith(kw) or msg_lower == kw for kw in continuation_keywords):
            return TopicRelevance.CONTINUATION

        # 规则：检测新话题关键词
        new_topic_keywords = [
            '帮我', '请帮', '我想', '我要', '查看', '查询',
            '你好', '在吗', '重新', '换个'
        ]
        if any(kw in new_message for kw in new_topic_keywords):
            # 使用 LLM 进一步判断
            pass

        # 使用 LLM 进行更精确的判断
        if self.enabled:
            try:
                return self._check_topic_with_llm(new_message, history)
            except Exception as e:
                print(f"LLM topic check failed: {e}")

        # 默认返回继续话题
        return TopicRelevance.CONTINUATION

    def _is_short_answer(self, message: str) -> bool:
        """判断是否为简短回答"""
        # 去除标点和空格后长度较短
        import re
        clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', message)
        return len(clean) <= 10

    def _check_topic_with_llm(
        self,
        new_message: str,
        history: List[Dict[str, str]]
    ) -> str:
        """使用 LLM 判断话题相关性"""
        # 构建历史对话摘要
        history_text = ""
        for msg in history[-4:]:  # 只看最近 2 轮
            role = "用户" if msg.get('role') == 'user' else "助手"
            history_text += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""判断新消息是否与之前的对话相关。

之前的对话:
{history_text}

新消息: {new_message}

请判断新消息属于以下哪种情况，只返回一个单词：
- continuation: 新消息是在继续之前的话题或任务
- new_topic: 新消息开始了一个全新的、与之前无关的话题
- followup_answer: 新消息是在回答助手的追问

只返回一个单词，不要解释。"""

        try:
            from core.ai.llm_call_context import LLMCallContext
            LLMCallContext.before_call("orient", "topic_relevance")
            response = self._instrumented_completion(
                messages=[
                    {"role": "user", "content": prompt}
                ],
                model=settings.LLM_MODEL,
                temperature=0,
                max_tokens=20
            )

            result = response.choices[0].message.content.strip().lower()

            if 'continuation' in result:
                return TopicRelevance.CONTINUATION
            elif 'new_topic' in result or 'new' in result:
                return TopicRelevance.NEW_TOPIC
            elif 'followup' in result or 'answer' in result:
                return TopicRelevance.FOLLOWUP_ANSWER
            else:
                return TopicRelevance.CONTINUATION

        except Exception:
            return TopicRelevance.CONTINUATION

    def _build_action_params_hints(self) -> str:
        """从 ActionRegistry 动态生成 mutation actions 的必需参数列表"""
        try:
            from app.services.actions import get_action_registry
            registry = get_action_registry()
            lines = []
            for action_def in registry.list_actions():
                if action_def.category != "mutation":
                    continue
                schema = action_def.parameters_schema.model_json_schema()
                required = schema.get("required", [])
                if required:
                    lines.append(f"- {action_def.name} 需要: {', '.join(required)}")
            return "\n".join(lines) if lines else ""
        except Exception:
            return ""

    def parse_followup_input(
        self,
        user_input: str,
        action_type: str,
        collected_params: dict,
        context: Optional[Dict] = None,
        missing_fields: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        解析追问时的用户输入

        Args:
            user_input: 用户新输入
            action_type: 已确定的操作类型
            collected_params: 已收集的参数
            context: 额外上下文（如可用房型列表）
            missing_fields: 上一轮校验产生的缺失字段详情

        Returns:
            {
                "params": {...},  # 合并后的所有参数
                "is_complete": true/false,
                "missing_fields": [...],
                "message": "自然语言回复"
            }
        """
        if not self.enabled:
            return {
                "params": collected_params,
                "is_complete": False,
                "missing_fields": [],
                "message": "LLM 服务未启用"
            }

        # 构建已收集参数的描述
        collected_info = []
        for key, value in collected_params.items():
            if value:
                collected_info.append(f"- {key}: {value}")

        # 构建上下文信息
        context_info = ""
        if context:
            if context.get("room_types"):
                rt_list = ", ".join([
                    f"{rt.get('name')}"
                    for rt in context["room_types"]
                ])
                context_info += f"\n可用房型: {rt_list}"

        today = date.today()
        from datetime import timedelta
        date_context = f"\n**当前日期: {today.year}年{today.month}月{today.day}日**"
        date_context += f"\n**明天: {(today + timedelta(days=1)).strftime('%Y-%m-%d')}**"
        date_context += f"\n**后天: {(today + timedelta(days=2)).strftime('%Y-%m-%d')}**"

        # 从 ActionRegistry 动态获取参数说明
        params_hints = self._build_action_params_hints()

        # 构建缺失字段提示（来自上一轮校验）
        missing_fields_hint = ""
        if missing_fields:
            lines = []
            select_options = []
            for f in missing_fields:
                field_name = f.get('field_name', '')
                display_name = f.get('display_name', field_name)
                field_type = f.get('field_type', 'text')
                placeholder = f.get('placeholder', '')
                type_label = {'text': '文本', 'date': '日期', 'number': '数字', 'select': '选择'}.get(field_type, field_type)
                hint = f"- {field_name}（{display_name}，{type_label}"
                if placeholder:
                    hint += f"，格式：{placeholder}"
                hint += "）"
                lines.append(hint)
                # 收集 select 类型的 options
                options = f.get('options')
                if field_type == 'select' and options:
                    opt_str = ", ".join([f"{o.get('label', '')}({o.get('value', '')})" for o in options])
                    select_options.append(f"- {field_name}: {opt_str}")
            missing_fields_hint = "\n**当前缺失的字段（请重点从用户输入中提取这些）：**\n" + "\n".join(lines)
            if select_options:
                missing_fields_hint += "\n\n**选择类型字段的有效选项：**\n" + "\n".join(select_options)

        prompt = f"""你正在帮用户收集信息以完成酒店管理操作。

**已确定的操作类型:** {action_type}

**已收集的参数:**
{chr(10).join(collected_info) if collected_info else "（无）"}

**用户新输入:** {user_input}
{date_context}
{context_info}
{missing_fields_hint}

**任务:**
1. 从用户新输入中提取参数（重点提取上述缺失字段）
2. 将新参数与已收集参数合并
3. 判断信息是否完整
4. 如果不完整，列出缺失的字段

**返回 JSON 格式:**
```json
{{
  "params": {{
    "合并后的所有参数": "值"
  }},
  "is_complete": true/false,
  "missing_fields": [
    {{
      "field_name": "参数名",
      "display_name": "显示名称",
      "field_type": "text|select|date|number",
      "placeholder": "提示文本",
      "required": true
    }}
  ],
  "message": "给用户的自然语言回复"
}}
```

**参数说明:**
{params_hints}

**日期处理 - 重要：**
- 所有日期字段在 params 中必须使用 ISO 格式（YYYY-MM-DD）
- 支持相对日期词汇："今天"、"明天"、"后天"、"大后天"
- 你必须根据提供的当前日期信息，将相对日期转换为 ISO 格式
"""

        try:
            from core.ai.llm_call_context import LLMCallContext
            LLMCallContext.before_call("decide", "parse_followup")
            response = self._instrumented_completion(
                messages=[
                    {"role": "system", "content": "你是酒店管理系统的参数提取助手，必须返回纯 JSON 格式。"},
                    {"role": "user", "content": prompt}
                ],
                model=settings.LLM_MODEL,
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = extract_json_from_text(content)

            if result:
                # 确保返回值包含所有必需字段
                if "params" not in result:
                    result["params"] = collected_params
                if "is_complete" not in result:
                    result["is_complete"] = False
                if "missing_fields" not in result:
                    result["missing_fields"] = []
                if "message" not in result:
                    result["message"] = "信息已收到"

                return result
            else:
                # 解析失败，返回默认值
                return {
                    "params": collected_params,
                    "is_complete": False,
                    "missing_fields": [],
                    "message": "抱歉，没有理解您的输入，请重新提供信息。"
                }

        except Exception as e:
            # 调用失败
            return {
                "params": collected_params,
                "is_complete": False,
                "missing_fields": [],
                "message": f"处理出错: {str(e)}"
            }

    # 系统实体修改意图 — 检测到时返回拒绝提示（SPEC-24）
    _SYSTEM_DENIED_INTENTS: Dict[str, List[str]] = {
        "modify_role": ["修改角色", "添加角色", "删除角色", "创建角色", "编辑角色"],
        "modify_permission": ["修改权限", "分配权限", "回收权限", "删除权限", "添加权限"],
        "modify_menu": ["修改菜单", "添加菜单", "删除菜单", "编辑菜单"],
        "modify_security": ["修改安全配置", "修改密码策略", "修改锁定策略"],
    }

    # 拒绝意图到管理页面的映射
    _DENIED_INTENT_REDIRECTS: Dict[str, str] = {
        "modify_role": "系统管理 > 权限管理",
        "modify_permission": "系统管理 > 权限管理",
        "modify_menu": "系统管理 > 菜单管理",
        "modify_security": "系统管理 > 系统配置",
    }

    def extract_intent(self, message: str) -> Dict[str, Any]:
        """
        Rule-based intent extraction from user message

        Returns a dict with:
        - entity_mentions: List of entity types mentioned (Guest, Room, etc.)
        - action_hints: List of potential actions (checkin, checkout, query, etc.)
        - extracted_values: Dict of extracted values (room_number, etc.)
        - time_references: List of time-related terms
        - denied_intents: List of denied system mutation intents (SPEC-24)
        """
        result = {
            "entity_mentions": [],
            "action_hints": [],
            "extracted_values": {},
            "time_references": [],
            "denied_intents": [],
        }

        if not message:
            return result

        message_lower = message.lower()

        # Entity detection - Chinese and English (business + system)
        entity_keywords = {
            "Guest": ["客人", "旅客", "住客", "访客", "guest", "customer"],
            "Room": ["房间", "客房", "房", "号房", "room", "客房"],
            "Reservation": ["预订", "预约", "reservation", "booking"],
            "StayRecord": ["住宿", "入住", "在住", "stay", "checkin"],
            "Task": ["任务", "清洁", "打扫", "维修", "task", "cleaning", "maintenance"],
            "Bill": ["账单", "费用", "账", "付款", "bill", "payment", "charge"],
            "Employee": ["员工", "服务员", "清洁工", "employee", "staff"],
            # System entities (SPEC-24)
            "SysRole": ["角色", "role"],
            "SysPermission": ["权限", "permission"],
            "SysMenu": ["菜单", "menu"],
            "SysDictType": ["字典类型", "数据字典", "dict type"],
            "SysDictItem": ["字典项", "dict item"],
            "SysConfig": ["系统配置", "配置项", "system config"],
        }

        for entity, keywords in entity_keywords.items():
            if any(kw in message for kw in keywords):
                result["entity_mentions"].append(entity)

        # Action detection
        action_keywords = {
            "checkin": ["办理入住", "入住", "登记", "checkin", "check in", "check-in"],
            "checkout": ["退房", "结账", "checkout", "check out", "check-out"],
            "query": ["查询", "查看", "显示", "搜索", "query", "show", "search", "list", "get"],
            "create": ["创建", "新建", "增加", "create", "new", "add"],
            "cancel": ["取消", "撤销", "cancel", "delete"],
            "assign": ["分配", "指派", "assign", "allocate"],
            "complete": ["完成", "结束", "complete", "finish", "done"],
            "start": ["开始", "启动", "start", "begin"],
            "update": ["更新", "修改", "改变", "update", "modify", "change"],
            "extend": ["续住", "延长", "extend"],
            # System query action (SPEC-24)
            "query_system": ["查角色", "查权限", "查字典", "查配置", "查菜单",
                            "有哪些角色", "有哪些权限", "有哪些字典", "有哪些配置"],
        }

        for action, keywords in action_keywords.items():
            if any(kw in message for kw in keywords):
                result["action_hints"].append(action)

        # Denied intent detection — system mutation via chat (SPEC-24)
        for intent_name, keywords in self._SYSTEM_DENIED_INTENTS.items():
            if any(kw in message for kw in keywords):
                result["denied_intents"].append(intent_name)

        # Extract room number
        import re
        room_match = re.search(r'(\d{3,4})\s*号?房?', message)
        if room_match:
            result["extracted_values"]["room_number"] = room_match.group(1)

        # Time references
        time_keywords = ["今天", "明日", "明天", "明", "后天", "大后天", "昨天", "前天",
                        "today", "tomorrow", "tmr", "yesterday"]
        for kw in time_keywords:
            if kw in message_lower:
                result["time_references"].append(kw)

        return result

    def _extract_intent_rule_based(self, message: str) -> Dict[str, Any]:
        """
        Internal method for rule-based intent extraction
        Used by tests for direct testing
        """
        return self.extract_intent(message)

    def extract_params(
        self,
        message: str,
        schema: Dict,
        known_values: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract parameters from message based on JSON schema

        Args:
            message: User input message
            schema: JSON schema describing expected parameters
            known_values: Previously collected values

        Returns:
            {
                "params": Dict of extracted parameters,
                "missing": List of missing required field names,
                "confidence": Float confidence score (0.0-1.0)
            }
        """
        if known_values is None:
            known_values = {}

        result = {
            "params": known_values.copy(),
            "missing": [],
            "confidence": 0.0
        }

        if not schema:
            return result

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Check which required fields are still missing
        for field_name in required:
            if field_name not in known_values:
                result["missing"].append(field_name)

        # If all required fields are provided via known_values
        if not result["missing"]:
            result["confidence"] = 1.0
            return result

        # When LLM is disabled, we can't do more extraction
        # Return what we have with the missing fields listed
        if not self.enabled:
            return result

        # If LLM is enabled, try to extract from message
        try:
            # Build extraction prompt
            props_desc = []
            for field_name, field_def in properties.items():
                desc = field_def.get("description", field_name)
                field_type = field_def.get("type", "string")
                props_desc.append(f"- {field_name} ({field_type}): {desc}")

            prompt = f"""从用户消息中提取参数。

用户消息: {message}

已知的值:
{json.dumps(known_values, ensure_ascii=False) if known_values else "(无)"}

需要提取的参数:
{chr(10).join(props_desc)}

只返回JSON格式:
{{
    "params": {{"参数名": "值"}},
    "missing": ["缺失的必需字段名"]
}}

如果参数值不在消息中，不要编造。
"""

            from core.ai.llm_call_context import LLMCallContext
            LLMCallContext.before_call("decide", "extract_params")
            response = self._instrumented_completion(
                messages=[
                    {"role": "system", "content": "你是参数提取助手，必须返回纯JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                model=settings.LLM_MODEL,
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            extracted = json.loads(response.choices[0].message.content)

            # Merge extracted params
            if "params" in extracted:
                result["params"].update(extracted["params"])

            # Update missing list
            if "missing" in extracted:
                result["missing"] = extracted["missing"]
            else:
                # Recalculate missing based on merged params
                result["missing"] = [
                    f for f in required
                    if f not in result["params"]
                ]

            # Calculate confidence
            if not result["missing"]:
                result["confidence"] = 1.0
            elif len(result["missing"]) < len(required):
                result["confidence"] = 0.5
            else:
                result["confidence"] = 0.0

        except Exception as e:
            # On error, return the original state
            pass

        return result
