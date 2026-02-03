"""
LLM 服务 - 支持 OpenAI 兼容 API
负责将自然语言转换为结构化的业务操作
"""
import json
import os
import re
from typing import Optional, Dict, Any, List
from datetime import date
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
    """从文本中提取第一个完整的 JSON 对象"""
    # 找到第一个 { 和最后一个 }
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
    # 移除注释
    text = _remove_comments(text)

    # 处理单引号
    text = _convert_single_quotes(text)

    # 移除尾随逗号
    text = _remove_trailing_commas(text)

    # 修复未转义的换行符
    text = _fix_escaped_newlines(text)

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
            "action_type": "view",
            "entity_type": "unknown",
            "description": "无效的操作",
            "requires_confirmation": False,
            "params": {}
        }

    validated = {
        "action_type": action.get("action_type", "view"),
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


class LLMService:
    """LLM 服务"""

    # 支持的操作类型
    ACTION_TYPES = [
        "checkout", "create_task", "walkin_checkin", "checkin",
        "create_reservation", "extend_stay", "change_room",
        "cancel_reservation", "assign_task", "start_task",
        "complete_task", "add_payment", "adjust_bill",
        "update_room_status", "view"
    ]

    # 任务状态
    TASK_STATUS = ["pending", "assigned", "in_progress", "completed"]
    TASK_TYPES = ["cleaning", "maintenance"]

    # 房间状态
    ROOM_STATUS = ["vacant_clean", "occupied", "vacant_dirty", "out_of_order"]

    # 支付方式
    PAYMENT_METHODS = ["cash", "card"]

    # 系统提示词
    SYSTEM_PROMPT = """你是 AIPMS 酒店管理系统的智能助手。你的职责是将用户的自然语言输入转换为结构化的操作指令。

**重要约束：**
1. 你只能返回 JSON 格式的响应
2. 不要编造不存在的数据（如房间号、预订号）
3. 尽可能提取用户提供的所有信息，包括部分信息
4. 当信息不足时，明确列出缺失的字段
5. 所有需要确认的操作都要设置 requires_confirmation: true
6. **房间相关：优先使用 room_number（字符串）而非 room_id，让后端自动转换**

**支持的操作类型 (action_type):**
- query_rooms: 查看房态
- query_reservations: 查询预订
- query_guests: 查询在住客人
- query_tasks: 查询任务
- query_reports: 查询统计报表
- checkin: 预订入住（需要 reservation_id 和 room_number）
- walkin_checkin: 散客入住（需要 room_number, guest_name, guest_phone, expected_check_out）
- checkout: 退房（需要 stay_record_id）
- create_reservation: 创建预订（需要 guest_name, guest_phone, room_type, 日期）
- extend_stay: 续住（需要 stay_record_id, new_check_out_date）
- change_room: 换房（需要 stay_record_id, new_room_number）
- cancel_reservation: 取消预订（需要 reservation_id, cancel_reason）
- create_task: 创建任务（需要 room_number, task_type: cleaning/maintenance）
- assign_task: 分配任务（需要 task_id, assignee_name）
- start_task: 开始任务（需要 task_id）
- complete_task: 完成任务（需要 task_id）
- add_payment: 收款（需要 bill_id, amount, method: cash/card）
- adjust_bill: 账单调整（需要 bill_id, adjustment_amount, reason）
- update_room_status: 修改房态（需要 room_number, status: vacant_clean/occupied/vacant_dirty/out_of_order）

**各操作必需参数:**
walkin_checkin: room_number, guest_name, guest_phone, expected_check_out
create_reservation: guest_name, guest_phone, room_type, check_in_date, check_out_date
checkin: reservation_id, room_number
checkout: stay_record_id
extend_stay: stay_record_id, new_check_out_date
change_room: stay_record_id, new_room_number
create_task: room_number, task_type

**日期处理 - 重要：**
- 用户的输入会包含"当前日期"、"明天"、"后天"等具体日期信息
- 你必须根据注入的当前日期信息，将所有相对日期转换为具体的 ISO 格式日期（YYYY-MM-DD）
- 在 params 中，所有日期字段必须使用 ISO 格式（如 "2025-02-03"），不要使用"明天"、"后天"等相对词汇
- 支持的日期词汇转换：
  * "今天" → 当天的 ISO 日期
  * "明天"/"明日"/"明" → 今天+1天的 ISO 日期
  * "后天"/"后日" → 今天+2天的 ISO 日期
  * "大后天" → 今天+3天的 ISO 日期
  * 已有的 ISO 格式日期保持不变

**追问模式 - 当信息不完整时:**
当用户的操作请求信息不完整时，你需要：
1. 提取所有已提供的参数放入 params
2. 在 message 中用自然语言询问缺失的信息
3. 在 missing_fields 中列出所有缺失的字段定义
4. 设置 requires_confirmation: false（表示需要先收集信息）

**响应格式:**
```json
{
  "message": "给用户的回复或追问",
  "suggested_actions": [
    {
      "action_type": "操作类型",
      "entity_type": "实体类型",
      "entity_id": 实体ID（数字或null）,
      "description": "操作描述",
      "requires_confirmation": true,
      "params": {
        "已收集的参数": "值"
      },
      "missing_fields": [
        {
          "field_name": "参数名",
          "display_name": "显示名称",
          "field_type": "text|select|date|number",
          "options": [{"value": "值", "label": "显示"}],
          "placeholder": "提示文本",
          "required": true
        }
      ]
    }
  ],
  "context": {"已收集的信息": "值"}
}
```

**示例对话:**

用户: "创建一个预订，李四，电话13800138000，明天入住，住两天"
回复: {
  "message": "好的，我来帮您创建预订。已收集信息：\\n- 客人：李四\\n- 电话：13800138000\\n- 入住：明天\\n- 退房：后天\\n\\n请问需要预订什么房型？",
  "suggested_actions": [{
    "action_type": "create_reservation",
    "entity_type": "reservation",
    "description": "创建李四的预订",
    "requires_confirmation": false,
    "params": {
      "guest_name": "李四",
      "guest_phone": "13800138000",
      "check_in_date": "2025-02-04",
      "check_out_date": "2025-02-05",
      "adult_count": 1
    },
    "missing_fields": [{
      "field_name": "room_type",
      "display_name": "房型",
      "field_type": "select",
      "options": [{"value": "标间", "label": "标间 ¥288/晚"}, {"value": "大床房", "label": "大床房 ¥328/晚"}, {"value": "豪华间", "label": "豪华间 ¥458/晚"}],
      "placeholder": "请选择房型",
      "required": true
    }]
  }],
  "context": {"guest_name": "李四", "guest_phone": "13800138000", "check_in_date": "明天", "check_out_date": "后天"}
}

用户: "大床房"
回复: {
  "message": "好的，为您预订大床房。\\n- 客人：李四\\n- 电话：13800138000\\n- 房型：大床房 ¥328/晚\\n- 入住：明天\\n- 退房：后天\\n\\n确认创建预订吗？",
  "suggested_actions": [{
    "action_type": "create_reservation",
    "entity_type": "reservation",
    "description": "创建李四的大床房预订",
    "requires_confirmation": true,
    "params": {
      "guest_name": "李四",
      "guest_phone": "13800138000",
      "room_type": "大床房",
      "check_in_date": "2025-02-04",
      "check_out_date": "2025-02-05",
      "adult_count": 1
    }
  }],
  "context": {}
}

用户: "帮王五办理入住"
回复: {
  "message": "请问王五是预订入住还是散客入住？如果是预订入住，请提供预订号；如果是散客入住，请告诉我需要什么房型。",
  "suggested_actions": [{
    "action_type": "checkin",
    "entity_type": "reservation",
    "description": "为王五办理入住",
    "requires_confirmation": false,
    "params": {"guest_name": "王五"},
    "missing_fields": [
      {"field_name": "checkin_type", "display_name": "入住类型", "field_type": "select", "options": [{"value": "reservation", "label": "预订入住"}, {"value": "walkin", "label": "散客入住"}], "required": true},
      {"field_name": "room_number", "display_name": "房间号", "field_type": "text", "placeholder": "如：201", "required": true}
    ]
  }],
  "context": {"guest_name": "王五"}
}

用户: "201房退房"
回复: {
  "message": "找到201房的住宿记录，确认办理退房吗？",
  "suggested_actions": [{
    "action_type": "checkout",
    "entity_type": "stay_record",
    "entity_id": 1,
    "description": "为张三办理退房",
    "requires_confirmation": true,
    "params": {"room_number": "201", "stay_record_id": 1}
  }],
  "context": {"room_number": "201", "guest_name": "张三"}
}

用户: "查看房态"
回复: {
  "message": "正在为您查询当前房态...",
  "suggested_actions": [{"action_type": "view", "entity_type": "room_status", "requires_confirmation": false, "params": {} }],
  "context": {}
}

用户: "大床房有多少间？"
回复: {
  "message": "正在为您查询大床房数量...",
  "suggested_actions": [{"action_type": "query_rooms", "entity_type": "room", "requires_confirmation": false, "params": {"room_type": "大床房"}}],
  "context": {"room_type": "大床房"}
}

**关键规则：**
1. 当用户明确指定了房型（如"大床房"、"标间"、"豪华间"），使用 room_type 参数传递房型名称
2. 当信息不完整时，必须在 params 中包含已收集的所有信息
3. 缺失字段必须在 missing_fields 中明确定义
4. field_type 可以是：text（文本）、select（下拉选择）、date（日期）、number（数字）
5. 对于房型选择，使用 select 类型并提供选项列表
6. 追问时设置 requires_confirmation: false，信息完整后设置为 true
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

    def is_enabled(self) -> bool:
        """检查 LLM 是否可用"""
        return self.enabled

    def chat(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        与 LLM 对话，获取结构化响应

        Args:
            message: 用户消息
            context: 上下文信息（如当前用户、房间列表等）

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

        # 显式注入当前日期
        today = date.today()
        date_context = f"\n**当前日期: {today.year}年{today.month}月{today.day}日 ({today.strftime('%A')})**"
        date_context += f"\n**明天: {(today + __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}**"
        date_context += f"\n**后天: {(today + __import__('datetime').timedelta(days=2)).strftime('%Y-%m-%d')}**"

        try:
            # 尝试使用 json_object 模式
            try:
                response = self.client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": f"{context_info}{date_context}\n\n用户输入: {message}"}
                    ],
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
            except Exception as json_error:
                # 某些 API 不支持 json_object 模式，回退到普通模式
                # 在系统提示词中强调返回 JSON
                enhanced_prompt = self.SYSTEM_PROMPT + "\n\n**重要：请务必只返回纯 JSON 格式，不要添加任何其他文字说明。**"

                response = self.client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": enhanced_prompt},
                        {"role": "user", "content": f"{context_info}{date_context}\n\n用户输入: {message}"}
                    ],
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
            for stay in context.get("active_stays", [])[:3]:
                info_parts.append(f"  - {stay.get('room_number')}号房: {stay.get('guest_name')}")

        if context.get("pending_tasks"):
            info_parts.append(f"- 待处理任务: {len(context['pending_tasks'])} 个")

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
                action["action_type"] = "view"
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
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
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

    def parse_followup_input(
        self,
        user_input: str,
        action_type: str,
        collected_params: dict,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        解析追问时的用户输入

        Args:
            user_input: 用户新输入
            action_type: 已确定的操作类型
            collected_params: 已收集的参数
            context: 额外上下文（如可用房型列表）

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
        date_context = f"\n**当前日期: {today.year}年{today.month}月{today.day}日**"
        date_context += f"\n**明天: {(today + __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}**"
        date_context += f"\n**后天: {(today + __import__('datetime').timedelta(days=2)).strftime('%Y-%m-%d')}**"

        prompt = f"""你正在帮用户收集信息以完成酒店管理操作。

**已确定的操作类型:** {action_type}

**已收集的参数:**
{chr(10).join(collected_info) if collected_info else "（无）"}

**用户新输入:** {user_input}
{date_context}
{context_info}

**任务:**
1. 从用户新输入中提取参数
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
- walkin_checkin 需要: room_number, guest_name, guest_phone, expected_check_out
- create_reservation 需要: guest_name, guest_phone, room_type, check_in_date, check_out_date
- checkin 需要: reservation_id, room_number
- checkout 需要: stay_record_id
- extend_stay 需要: stay_record_id, new_check_out_date
- change_room 需要: stay_record_id, new_room_number
- create_task 需要: room_number, task_type

**日期处理 - 重要：**
- 所有日期字段在 params 中必须使用 ISO 格式（YYYY-MM-DD）
- 支持相对日期词汇："今天"、"明天"、"后天"、"大后天"
- 你必须根据提供的当前日期信息，将相对日期转换为 ISO 格式
- 例如："明天" → "2025-02-04"（根据当前日期计算）

**示例:**

用户输入: "大床房"
已收集: {{guest_name: "李四", check_in_date: "2025-02-04", check_out_date: "2025-02-05"}}
返回:
{{
  "params": {{"guest_name": "李四", "room_type": "大床房", "check_in_date": "2025-02-04", "check_out_date": "2025-02-05"}},
  "is_complete": false,
  "missing_fields": [{{"field_name": "guest_phone", "display_name": "联系电话", "field_type": "text", "placeholder": "请输入手机号", "required": true}}],
  "message": "好的，选择大床房。还需要提供联系电话。"
}}

用户输入: "13800138000"
已收集: {{guest_name: "李四", room_type: "大床房", check_in_date: "2025-02-04", check_out_date: "2025-02-05"}}
返回:
{{
  "params": {{"guest_name": "李四", "guest_phone": "13800138000", "room_type": "大床房", "check_in_date": "2025-02-04", "check_out_date": "2025-02-05"}},
  "is_complete": true,
  "missing_fields": [],
  "message": "信息已完整：\\n- 客人：李四\\n- 电话：13800138000\\n- 房型：大床房\\n- 入住：2025-02-04\\n- 退房：2025-02-05\\n\\n确认创建预订吗？"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是酒店管理系统的参数提取助手，必须返回纯 JSON 格式。"},
                    {"role": "user", "content": prompt}
                ],
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
