"""
core/ai/prompt_builder.py

PromptBuilder - 动态提示词构建器

从 OntologyRegistry 获取元数据，动态构建系统提示词。
支持模板变量替换、实体描述注入、操作描述注入、规则描述注入。

SPEC-51: 动态注入本体元数据
SPEC-52: 完整的 build_system_prompt() 实现
SPEC-13: 语义查询语法提示词 (Semantic Query Syntax)
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import date, timedelta
from dataclasses import dataclass, field

from core.ontology.registry import registry, OntologyRegistry
from core.ontology.metadata import EntityMetadata, ActionMetadata, PropertyMetadata, StateMachine


@dataclass
class PromptContext:
    """提示词上下文"""
    user_role: str = ""
    user_id: Optional[int] = None
    current_date: Optional[date] = None
    include_entities: bool = True
    include_actions: bool = True
    include_rules: bool = True
    include_state_machines: bool = True
    include_permissions: bool = False  # 默认不包含权限矩阵（除非是管理员）
    custom_variables: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.current_date is None:
            self.current_date = date.today()


class PromptBuilder:
    """
    动态提示词构建器

    从 OntologyRegistry 获取元数据，动态构建系统提示词。

    功能：
    - 基础系统提示词模板
    - 实体描述注入（含属性元数据）
    - 操作描述注入（含参数定义）
    - 状态机注入（状态转换规则）
    - 业务规则注入
    - 权限矩阵注入
    - 日期上下文注入
    - 模板变量替换
    - 语义查询语法注入（SPEC-13）

    SPEC-51: 动态注入本体元数据
    SPEC-52: 完整的 build_system_prompt() 实现
    SPEC-13: 语义查询语法提示词
    """

    # 基础系统提示词模板
    BASE_SYSTEM_PROMPT = """你是 AIPMS 酒店管理系统的智能助手。你的职责是将用户的自然语言输入转换为结构化的操作指令。

**重要约束：**
1. 你只能返回 JSON 格式的响应
2. 不要编造不存在的数据（如房间号、预订号）
3. 尽可能提取用户提供的所有信息，包括部分信息
4. 当信息不足时，明确列出缺失的字段
5. 所有需要确认的操作都要设置 requires_confirmation: true
6. **房间相关：优先使用 room_number（字符串）而非 room_id，让后端自动转换**

{role_context}

{semantic_query_syntax}

{entity_descriptions}

{action_descriptions}

{state_machine_descriptions}

{rule_descriptions}

{permission_context}

{date_context}

**追问模式 - 当信息不完整时:**
当用户的操作请求信息不完整时，你需要：
1. 提取所有已提供的参数放入 params
2. 在 message 中用自然语言询问缺失的信息
3. 在 missing_fields 中列出所有缺失的字段定义
4. 设置 requires_confirmation: false（表示需要先收集信息）

**响应格式:**
```json
{{
  "message": "给用户的回复或追问",
  "suggested_actions": [
    {{
      "action_type": "操作类型",
      "entity_type": "实体类型",
      "entity_id": 实体ID（数字或null）,
      "description": "操作描述",
      "requires_confirmation": true,
      "params": {{
        "已收集的参数": "值"
      }},
      "missing_fields": [
        {{
          "field_name": "参数名",
          "display_name": "显示名称",
          "field_type": "text|select|date|number",
          "options": [{{"value": "值", "label": "显示"}}],
          "placeholder": "提示文本",
          "required": true
        }}
      ]
    }}
  ],
  "context": {{}}
}}
```
"""

    def __init__(self, ontology_registry=None):
        """
        初始化 PromptBuilder

        Args:
            ontology_registry: 本体注册中心，默认使用全局单例
        """
        self.registry = ontology_registry or registry

    def build_system_prompt(
        self,
        context: Optional[PromptContext] = None,
        base_template: Optional[str] = None
    ) -> str:
        """
        构建完整的系统提示词 (SPEC-52)

        动态从 OntologyRegistry 注入：
        - 实体元数据（名称、描述、属性）
        - 操作元数据（类型、描述、参数）
        - 状态机定义（状态、转换）
        - 业务规则（名称、描述）
        - 权限矩阵（角色允许的操作）
        - 语义查询语法（SPEC-13）

        Args:
            context: 提示词上下文
            base_template: 基础模板，默认使用 BASE_SYSTEM_PROMPT

        Returns:
            完整的系统提示词字符串
        """
        if context is None:
            context = PromptContext()

        # 构建各部分描述
        role_context = self._build_role_context(context) if context.user_role else ""
        semantic_query_syntax = self._build_semantic_query_syntax() if context.include_entities else ""
        entity_descriptions = self._build_entity_descriptions() if context.include_entities else ""
        action_descriptions = self._build_action_descriptions() if context.include_actions else ""
        state_machine_descriptions = self._build_state_machine_descriptions() if context.include_state_machines else ""
        rule_descriptions = self._build_rule_descriptions() if context.include_rules else ""
        permission_context = self._build_permission_context(context) if context.include_permissions else ""
        date_context = self._build_date_context(context.current_date)

        # 使用模板构建
        template = base_template or self.BASE_SYSTEM_PROMPT

        prompt = template.format(
            role_context=role_context,
            semantic_query_syntax=semantic_query_syntax,
            entity_descriptions=entity_descriptions,
            action_descriptions=action_descriptions,
            state_machine_descriptions=state_machine_descriptions,
            rule_descriptions=rule_descriptions,
            permission_context=permission_context,
            date_context=date_context
        )

        # 应用自定义变量替换
        if context.custom_variables:
            prompt = self._apply_custom_variables(prompt, context.custom_variables)

        return prompt

    def _build_role_context(self, context: PromptContext) -> str:
        """构建角色上下文"""
        lines = [f"**当前用户角色:** {context.user_role}"]
        if context.user_id:
            lines.append(f"**用户ID:** {context.user_id}")
        return "\n".join(lines)

    def _build_entity_descriptions(self) -> str:
        """构建实体描述部分 (SPEC-51)"""
        entities = self.registry.get_entities()

        if not entities:
            return "**本体实体:** 暂无注册实体"

        lines = ["**本体实体:**"]
        for entity in entities:
            # 实体基本信息
            lines.append(f"\n### {entity.name}")
            if entity.description:
                lines.append(f"**描述:** {entity.description}")
            if hasattr(entity, 'table_name') and entity.table_name:
                lines.append(f"**数据表:** {entity.table_name}")

            # 属性列表（SPEC-51: 动态注入属性元数据）
            if getattr(entity, 'properties', None):
                lines.append("\n**属性:**")
                for prop in entity.properties:
                    if isinstance(prop, PropertyMetadata):
                        # 使用 PropertyMetadata 的信息
                        required = "必填" if prop.required else "可选"
                        type_info = prop.type.value if hasattr(prop.type, 'value') else str(prop.type)
                        security_note = ""
                        if hasattr(prop, 'security_level') and prop.security_level:
                            security_note = f" [{prop.security_level}]"

                        lines.append(f"- **{prop.name}** ({type_info}) {required}{security_note}: {prop.description or ''}")
                    else:
                        # 回退到字典处理
                        required = "必填" if prop.get('required', False) else "可选"
                        lines.append(f"- **{prop.get('name')}** {required}: {prop.get('description', '')}")

        return "\n".join(lines)

    def _build_action_descriptions(self) -> str:
        """构建操作描述部分 (SPEC-51: 动态注入操作元数据)"""
        actions = self.registry.get_actions()

        if not actions:
            return "**支持的操作:** 暂无注册操作"

        # 按实体分组
        grouped: Dict[str, List[ActionMetadata]] = {}
        for action in actions:
            entity = action.entity if hasattr(action, 'entity') and action.entity else "general"
            if entity not in grouped:
                grouped[entity] = []
            grouped[entity].append(action)

        lines = ["**支持的操作 (action_type):**"]
        for entity, entity_actions in sorted(grouped.items()):
            if entity != "general":
                lines.append(f"\n### {entity} 操作:")

            for action in entity_actions:
                lines.append(f"\n#### {action.action_type}")
                if action.description:
                    lines.append(f"- **描述**: {action.description}")

                # 权限信息
                if hasattr(action, 'allowed_roles') and action.allowed_roles:
                    lines.append(f"- **允许角色**: {', '.join(action.allowed_roles)}")

                # 确认要求
                if hasattr(action, 'requires_confirmation') and action.requires_confirmation:
                    lines.append(f"- **需要确认**: 是")
                elif hasattr(action, 'requires_confirmation'):
                    lines.append(f"- **需要确认**: 否")

                # 写回信息
                if hasattr(action, 'writeback') and action.writeback:
                    lines.append(f"- **数据修改**: 是")
                elif hasattr(action, 'writeback'):
                    lines.append(f"- **数据修改**: 否")

                # 参数列表 (SPEC-51: 动态注入参数定义)
                if hasattr(action, 'params') and action.params:
                    lines.append(f"- **参数**:")
                    for param in action.params:
                        if isinstance(param, dict):
                            param_name = param.get('name', 'unknown')
                            param_type = param.get('type', 'string')
                            param_required = "必填" if param.get('required', False) else "可选"
                            param_desc = param.get('description', '')
                        else:
                            # ActionParam dataclass
                            param_name = getattr(param, 'name', 'unknown')
                            param_type = getattr(param, 'type', 'string')
                            if hasattr(param_type, 'value'):
                                param_type = param_type.value
                            param_required = "必填" if getattr(param, 'required', False) else "可选"
                            param_desc = getattr(param, 'description', '')
                        lines.append(f"  - {param_name} ({param_type}) {param_required}: {param_desc}")

        return "\n".join(lines)

    def _build_state_machine_descriptions(self) -> str:
        """构建状态机描述部分 (SPEC-51: 动态注入状态机元数据)"""
        state_machines = self.registry._state_machines

        if not state_machines:
            return ""

        lines = ["**状态机定义:**"]
        for entity_name, sm in state_machines.items():
            lines.append(f"\n### {entity_name} 状态机")
            if hasattr(sm, 'initial_state') and sm.initial_state:
                lines.append(f"- **初始状态**: {sm.initial_state}")
            if hasattr(sm, 'states') and sm.states:
                lines.append(f"- **状态列表**: {', '.join(sm.states)}")
            if hasattr(sm, 'transitions') and sm.transitions:
                lines.append(f"- **状态转换:**")
                for transition in sm.transitions:
                    if isinstance(transition, dict):
                        from_state = transition.get('from', transition.get('from_state', '?'))
                        to_state = transition.get('to', transition.get('to_state', '?'))
                        event = transition.get('event', transition.get('trigger', '直接转换'))
                    else:
                        # StateTransition dataclass
                        from_state = getattr(transition, 'from_state', '?')
                        to_state = getattr(transition, 'to_state', '?')
                        event = getattr(transition, 'trigger', '直接转换')
                    lines.append(f"  - {from_state} → {to_state} (事件: {event})")

        return "\n".join(lines)

    def _build_rule_descriptions(self) -> str:
        """构建业务规则描述部分 (SPEC-51: 动态注入业务规则元数据)"""
        rules = self.registry.get_business_rules()

        if not rules:
            return ""

        lines = ["**业务规则:**"]
        for rule in rules:
            rule_name = getattr(rule, 'name', '未命名规则')
            rule_desc = getattr(rule, 'description', '')
            lines.append(f"- **{rule_name}**: {rule_desc}")

        return "\n".join(lines)

    def _build_permission_context(self, context: PromptContext) -> str:
        """构建权限上下文 (SPEC-51: 动态注入权限矩阵)"""
        # 只对管理员显示完整权限矩阵
        if context.user_role not in ('manager', 'sysadmin'):
            return ""

        permissions = self.registry.get_permissions()

        if not permissions:
            return "**权限矩阵:** 暂无"

        lines = ["**权限矩阵 (当前角色可执行的操作):**"]
        user_perms = {
            action: roles
            for action, roles in permissions.items()
            if context.user_role in roles
        }

        if user_perms:
            for action, roles in sorted(user_perms.items()):
                lines.append(f"- {action}: {', '.join(sorted(roles))}")
        else:
            lines.append("- (当前角色无特殊权限)")

        return "\n".join(lines)

    def _build_date_context(self, current_date: date) -> str:
        """构建日期上下文"""
        tomorrow = current_date + timedelta(days=1)
        day_after = current_date + timedelta(days=2)

        lines = [
            f"**当前日期: {current_date.year}年{current_date.month}月{current_date.day}日 ({current_date.strftime('%A')})**",
            f"**明天: {tomorrow.strftime('%Y-%m-%d')}**",
            f"**后天: {day_after.strftime('%Y-%m-%d')}**"
        ]

        return "\n".join(lines)

    def _build_semantic_query_syntax(self) -> str:
        """
        构建语义查询语法说明 (SPEC-13)

        生成用于 SemanticQuery 的完整语法说明，包括：
        - 路径语法规则
        - 可用实体及路径示例
        - 过滤操作符
        - 查询示例

        Returns:
            语义查询语法提示词部分
        """
        from core.ontology.query_engine import RELATIONSHIP_MAP

        lines = [
            "**Semantic Query Syntax (语义查询语法)**",
            "",
            "你不需要编写 SQL JOIN。使用点分路径（dot-notation）导航实体关系。",
            "",
            "## 路径语法规则",
            "",
            "- **简单字段**: `name`, `status`, `room_number`",
            "- **单跳关联**: `stays.room_number`, `room.room_type`",
            "- **多跳导航**: `stays.room.room_type.name`",
            "- **深度导航**: 支持最多 10 跳（但通常 2-3 跳已足够）",
            "",
            "## 可用实体及路径",
        ]

        # 动态生成实体路径说明（基于 RELATIONSHIP_MAP）
        entity_paths = self._generate_entity_paths(RELATIONSHIP_MAP)

        for entity_name, paths in entity_paths.items():
            lines.append(f"\n### {entity_name}")
            for path_desc in paths:
                lines.append(f"- {path_desc}")

        # 过滤操作符
        lines.extend([
            "",
            "## 过滤操作符",
            "",
            "- `eq` - 等于",
            "- `ne` - 不等于",
            "- `gt` - 大于",
            "- `gte` - 大于等于",
            "- `lt` - 小于",
            "- `lte` - 小于等于",
            "- `in` - 在列表中",
            "- `not_in` - 不在列表中",
            "- `like` - 模糊匹配（支持 % 通配符）",
            "- `between` - 在范围内",
        ])

        # 查询示例
        lines.extend([
            "",
            "## 查询示例",
            "",
            "### 示例 1: 查询所有在住客人",
            "```json",
            "{",
            '  "root_object": "Guest",',
            '  "fields": ["name", "phone"],',
            '  "filters": [',
            '    {"path": "stays.status", "operator": "eq", "value": "ACTIVE"}',
            "  ]",
            "}",
            "```",
            "",
            "### 示例 2: 查询特定房间的在住客人",
            "```json",
            "{",
            '  "root_object": "Guest",',
            '  "fields": ["name", "phone"],',
            '  "filters": [',
            '    {"path": "stays.status", "operator": "eq", "value": "ACTIVE"},',
            '    {"path": "stays.room.room_number", "operator": "eq", "value": "201"}',
            "  ]",
            "}",
            "```",
            "",
            "### 示例 3: 查询本月的入住记录",
            "```json",
            "{",
            '  "root_object": "StayRecord",',
            '  "fields": ["guest.name", "check_in_time", "room.room_number"],',
            '  "filters": [',
            '    {"path": "check_in_time", "operator": "gte", "value": "2026-02-01"},',
            '    {"path": "check_in_time", "operator": "lt", "value": "2026-03-01"}',
            "  ],",
            '  "order_by": ["check_in_time DESC"],',
            '  "limit": 50',
            "}",
            "```",
            "",
            "### 示例 4: 查询 VIP 客人的入住历史",
            "```json",
            "{",
            '  "root_object": "StayRecord",',
            '  "fields": ["guest.name", "check_in_time", "room.room_number", "room.room_type.name"],',
            '  "filters": [',
            '    {"path": "guest.tier", "operator": "eq", "value": "VIP"}',
            "  ],",
            '  "order_by": ["check_in_time DESC"],',
            '  "limit": 20',
            "}",
            "```",
            "",
            "## 重要规则",
            "",
            "1. **路径必须使用关系属性名**（如 `stays` 而非 `stay_records`）",
            "2. **日期字段使用 ISO 格式**（YYYY-MM-DD）",
            "3. **状态值使用枚举值**（如 ACTIVE, VACANT_CLEAN, CHECKED_IN）",
            "4. **多个过滤器之间是 AND 关系**",
            "5. **limit 默认为 100，最大 1000**",
        ])

        return "\n".join(lines)

    def _generate_entity_paths(self, relationship_map: Dict[str, Dict[str, Tuple[str, str]]]) -> Dict[str, List[str]]:
        """
        生成实体路径说明

        Args:
            relationship_map: 关系映射字典

        Returns:
            实体名到路径说明列表的映射
        """
        # 常用字段的路径模板
        common_fields = {
            "Guest": ["id", "name", "phone", "email", "tier", "id_number"],
            "Room": ["id", "room_number", "status", "floor"],
            "StayRecord": ["id", "status", "check_in_time", "check_out_time"],
            "Reservation": ["id", "status", "check_in_date", "check_out_date"],
            "Task": ["id", "type", "status", "priority"],
            "Bill": ["id", "total_amount", "status"],
            "RoomType": ["id", "name", "price", "base_occupancy"],
        }

        # 关系路径模板
        relationship_paths = {
            "Guest": [
                ("stay_records", "stays", [
                    "stays.status - 住宿记录状态",
                    "stays.check_in_time - 入住时间",
                    "stays.check_out_time - 退房时间",
                ]),
                ("stay_records", "stays.room", [
                    "stays.room.room_number - 住宿房间号",
                    "stays.room.status - 房间状态",
                ]),
                ("stay_records", "stays.room.room_type", [
                    "stays.room.room_type.name - 房型名称",
                    "stays.room.room_type.price - 房型价格",
                ]),
            ],
            "Room": [
                ("room_type", "room_type", [
                    "room_type.name - 房型名称",
                    "room_type.price - 房型价格",
                ]),
                ("tasks", "tasks", [
                    "tasks.type - 任务类型",
                    "tasks.status - 任务状态",
                ]),
            ],
            "StayRecord": [
                ("guest", "guest", [
                    "guest.name - 客人姓名",
                    "guest.phone - 客人电话",
                    "guest.tier - 客人等级",
                ]),
                ("room", "room", [
                    "room.room_number - 房间号",
                    "room.status - 房间状态",
                ]),
                ("room", "room.room_type", [
                    "room.room_type.name - 房型名称",
                    "room.room_type.price - 房型价格",
                ]),
            ],
            "Reservation": [
                ("guest", "guest", [
                    "guest.name - 预订客人姓名",
                    "guest.phone - 预订客人电话",
                ]),
                ("room_type", "room_type", [
                    "room_type.name - 预订房型名称",
                    "room_type.price - 房型价格",
                ]),
            ],
            "Task": [
                ("room", "room", [
                    "room.room_number - 关联房间号",
                    "room.status - 房间状态",
                ]),
            ],
        }

        result = {}

        for entity_name, fields in common_fields.items():
            paths = [f"- **{f}** - 直接字段" for f in fields]

            # 添加关系路径
            if entity_name in relationship_paths:
                for _, rel_name, rel_fields in relationship_paths[entity_name]:
                    paths.extend([f"- **{f}**" for f in rel_fields])

            result[entity_name] = paths

        return result

    def _apply_custom_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """应用自定义变量替换"""
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            text = text.replace(placeholder, str(value))
        return text

    def build_user_message(
        self,
        user_input: str,
        context: Optional[PromptContext] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建用户消息

        Args:
            user_input: 用户原始输入
            context: 提示词上下文
            additional_context: 额外上下文信息

        Returns:
            完整的用户消息字符串
        """
        parts = []

        # 添加额外上下文
        if additional_context:
            lines = ["**当前状态:**"]
            if additional_context.get("room_summary"):
                rs = additional_context["room_summary"]
                lines.append(f"- 总房间: {rs.get('total')}, 空闲: {rs.get('vacant_clean')}, 入住: {rs.get('occupied')}")
            if additional_context.get("room_types"):
                rt_list = ", ".join([
                    f"{rt.get('name')}(ID:{rt.get('id')}, ¥{rt.get('price')})"
                    for rt in additional_context["room_types"]
                ])
                lines.append(f"- 可用房型: {rt_list}")
            if additional_context.get("active_stays"):
                lines.append(f"- 在住客人: {len(additional_context['active_stays'])} 位")
            if additional_context.get("pending_tasks"):
                lines.append(f"- 待处理任务: {len(additional_context['pending_tasks'])} 个")

            parts.append("\n".join(lines))

        # 添加用户输入
        parts.append(f"\n\n用户输入: {user_input}")

        return "\n".join(parts)

    def format_conversation_history(
        self,
        history: List[Dict[str, str]],
        max_rounds: int = 3
    ) -> str:
        """
        格式化对话历史为字符串

        Args:
            history: 历史消息列表，每项包含 role 和 content
            max_rounds: 最大包含的轮数

        Returns:
            格式化后的对话历史字符串
        """
        if not history:
            return ""

        lines = ["\n**最近对话历史：**"]
        for msg in history[-max_rounds * 2:]:  # 每轮2条消息
            role = "用户" if msg.get('role') == 'user' else "助手"
            content = msg.get('content', '')[:200]  # 截断过长内容
            lines.append(f"- {role}: {content}")

        return "\n".join(lines)

    def get_dynamic_context(
        self,
        user_role: str,
        db_session=None
    ) -> Dict[str, Any]:
        """
        获取动态上下文 (SPEC-51)

        从数据库和注册中心获取动态上下文信息，
        用于增强提示词的相关性。

        Args:
            user_role: 用户角色
            db_session: 数据库会话（可选）

        Returns:
            动态上下文字典
        """
        context = {
            "user_role": user_role,
            "timestamp": date.today().isoformat()
        }

        # 从注册中心获取实体统计
        entities = self.registry.get_entities()
        context["registered_entities"] = [e.name for e in entities]

        # 从注册中心获取操作列表
        actions = self.registry.get_actions()
        context["registered_actions"] = [a.action_type for a in actions]

        # 从注册中心获取业务规则
        rules = self.registry.get_business_rules()
        context["registered_rules"] = [getattr(r, 'name', 'unnamed') for r in rules]

        # 如果有数据库会话，获取实时数据
        if db_session:
            try:
                from app.models.ontology import Room, Guest, Reservation, Task

                # 房间统计
                total_rooms = db_session.query(Room).count()
                occupied_rooms = db_session.query(Room).filter(
                    Room.status == 'occupied'
                ).count()
                context["room_stats"] = {
                    "total": total_rooms,
                    "occupied": occupied_rooms,
                    "available": total_rooms - occupied_rooms
                }

                # 任务统计
                pending_tasks = db_session.query(Task).filter(
                    Task.status == 'pending'
                ).count()
                context["pending_tasks"] = pending_tasks

            except Exception:
                pass  # 数据库查询失败时忽略

        return context

    # ==================== Schema 导出方法 (Phase 2.5) ====================

    def build_entity_description(self, entity_name: str) -> str:
        """
        构建单个实体的描述

        Args:
            entity_name: 实体名称

        Returns:
            实体描述文本
        """
        schema = self._get_schema()
        entity = schema.get("entity_types", {}).get(entity_name)

        if not entity:
            return f"# {entity_name}\n\n实体不存在。"

        lines = [
            f"# {entity.get('display_name', entity_name)}",
            f"{entity.get('description', '')}",
            "",
            "## 属性"
        ]

        for prop_name, prop_meta in entity.get("properties", {}).items():
            required = " (必填)" if prop_meta.get("is_required") else ""
            lines.append(f"- **{prop_name}**{required}: {prop_meta.get('type', 'unknown')}")

        if entity.get("interfaces"):
            lines.append("\n## 实现接口")
            lines.extend(f"- {iface}" for iface in entity["interfaces"])

        if entity.get("actions"):
            lines.append("\n## 可用操作")
            for action in entity["actions"]:
                lines.append(f"- {action}")

        return "\n".join(lines)

    def build_interface_description(self, interface_name: str) -> str:
        """
        构建接口描述

        Args:
            interface_name: 接口名称

        Returns:
            接口描述文本
        """
        schema = self._get_schema()
        interface = schema.get("interfaces", {}).get(interface_name)

        if not interface:
            return f"# 接口 {interface_name}\n\n接口不存在。"

        lines = [
            f"# {interface_name} (接口)",
        ]

        if interface.get("description"):
            lines.append(f"{interface['description']}")

        lines.append("")
        lines.append("## 实现该接口的实体")

        for impl in interface.get("implementations", []):
            lines.append(f"- {impl}")

        if interface.get("required_properties"):
            lines.append("\n## 必需属性")
            for name, ptype in interface["required_properties"].items():
                lines.append(f"- {name}: {ptype}")

        if interface.get("required_actions"):
            lines.append("\n## 必需动作")
            for action in interface["required_actions"]:
                lines.append(f"- {action}")

        return "\n".join(lines)

    def _get_schema(self) -> Dict[str, Any]:
        """获取 schema（带缓存）"""
        if not hasattr(self, '_schema_cache') or self._schema_cache is None:
            self._schema_cache = self.registry.export_schema()
        return self._schema_cache

    def invalidate_cache(self):
        """清除缓存 - 当本体发生变化时调用"""
        self._schema_cache = None

    # ==================== NL2OntologyQuery 支持 ====================

    def build_query_schema(self) -> str:
        """
        构建用于 NL2OntologyQuery 的 Schema

        生成精确的、结构化的 Schema JSON，确保 LLM 使用正确的字段名。

        Returns:
            Schema 描述字符串（包含精确的 JSON Schema）
        """
        # 使用新的 export_query_schema 方法获取精确的 Schema
        query_schema = self.registry.export_query_schema()

        lines = ["**Ontology Query Schema (精确字段定义)**", ""]
        lines.append("**重要: 必须使用下面定义的精确字段名，不要猜测或创造新字段名**")
        lines.append("")

        # 输出实体及其字段的精确定义
        lines.append("## 可查询实体及字段")
        lines.append("")

        for entity_name, entity_info in query_schema.get("entities", {}).items():
            lines.append(f"### {entity_name}")
            if entity_info.get("description"):
                lines.append(f"- 描述: {entity_info['description']}")
            if entity_info.get("table"):
                lines.append(f"- 表名: {entity_info['table']}")

            # 字段列表
            lines.append("- 字段:")
            fields = entity_info.get("fields", {})
            for field_name, field_info in fields.items():
                field_type = field_info.get("type", "unknown")
                line = f"  - `{field_name}` ({field_type})"

                # 标记特殊字段
                if field_info.get("primary_key"):
                    line += " [主键]"
                if field_info.get("filterable"):
                    line += " [可过滤]"
                if field_info.get("aggregatable"):
                    line += " [可聚合]"

                # 关系字段特殊标记
                if field_info.get("type") == "relationship":
                    target_entity = field_info.get("target_entity", "")
                    line += f" → 关联到 {target_entity}"

                lines.append(line)

            # 关系定义
            relationships = entity_info.get("relationships", {})
            if relationships:
                lines.append("- 关系:")
                for rel_name, rel_info in relationships.items():
                    rel_type = rel_info.get("type", "")
                    target = rel_info.get("entity", "")
                    lines.append(f"  - `{rel_name}` → {target} ({rel_type})")

            lines.append("")

        # 聚合查询说明
        lines.append("## 聚合查询")
        lines.append("")
        lines.append(f"- 支持的聚合函数: {', '.join(query_schema.get('aggregate_functions', []))}")
        lines.append(f"- 支持的过滤操作符: {', '.join(query_schema.get('filter_operators', []))}")
        lines.append("")
        lines.append("**重要规则:**")
        lines.append('1. 使用 field="id" + function="COUNT" 进行计数统计')
        lines.append('2. 日期过滤使用 check_in_time 字段（不是 check_in_date）')
        lines.append('3. 关联字段使用点号路径: guest.name, room.room_number')
        lines.append("")
        lines.append("**查询示例:**")
        lines.append("```json")
        lines.append('{')
        lines.append('  "entity": "StayRecord",')
        lines.append('  "fields": ["guest.name", "stay_count"],')
        lines.append('  "aggregate": {"field": "id", "function": "COUNT", "alias": "stay_count"},')
        lines.append('  "filters": [')
        lines.append('    {"field": "check_in_time", "operator": "gte", "value": "2026-01-01"},')
        lines.append('    {"field": "check_in_time", "operator": "lt", "value": "2026-02-01"}')
        lines.append('  ],')
        lines.append('  "order_by": ["stay_count DESC"],')
        lines.append('  "limit": 3')
        lines.append('}')
        lines.append('```')

        return "\n".join(lines)


# ==================== 便捷函数 ====================

def build_system_prompt(
    user_role: str = "",
    current_date: Optional[date] = None,
    include_entities: bool = True,
    include_actions: bool = True,
    include_rules: bool = True,
    include_state_machines: bool = True,
    include_permissions: bool = False
) -> str:
    """
    构建系统提示词的便捷函数

    Args:
        user_role: 用户角色
        current_date: 当前日期
        include_entities: 是否包含实体描述
        include_actions: 是否包含操作描述
        include_rules: 是否包含规则描述
        include_state_machines: 是否包含状态机
        include_permissions: 是否包含权限矩阵

    Returns:
        系统提示词字符串
    """
    context = PromptContext(
        user_role=user_role,
        current_date=current_date,
        include_entities=include_entities,
        include_actions=include_actions,
        include_rules=include_rules,
        include_state_machines=include_state_machines,
        include_permissions=include_permissions
    )

    builder = PromptBuilder()
    return builder.build_system_prompt(context)


__all__ = [
    "PromptBuilder",
    "PromptContext",
    "build_system_prompt",
]
