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
import logging

from core.ontology.registry import registry, OntologyRegistry
from core.ontology.metadata import EntityMetadata, ActionMetadata, PropertyMetadata, StateMachine

logger = logging.getLogger(__name__)


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
    domain_prompt: str = ""  # 领域特定提示词，由 DomainAdapter 注入
    message_hint: str = ""  # 用户消息（用于关键词匹配按需注入）
    allowed_entities: Optional[List[str]] = None  # None = 全部注入
    allowed_actions: Optional[List[str]] = None   # None = 全部注入

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

    # 基础系统提示词模板（领域无关）
    BASE_SYSTEM_PROMPT = """你是一个 Ontology 驱动的智能助手。你的职责是将用户的自然语言输入转换为结构化的操作指令。

{domain_prompt}

**重要约束：**
1. 你只能返回 JSON 格式的响应
2. 不要编造不存在的数据
3. 尽可能提取用户提供的所有信息，包括部分信息
4. 当信息不足时，明确列出缺失的字段
5. 所有需要确认的操作都要设置 requires_confirmation: true

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

    def __init__(self, ontology_registry=None, action_registry=None,
                 admin_roles=None, adapter=None):
        """
        初始化 PromptBuilder

        Args:
            ontology_registry: 本体注册中心，默认使用全局单例
            action_registry: ActionRegistry 实例（可选），用于构建领域关键词表
            admin_roles: 被视为管理员的角色名集合（可选）
            adapter: IDomainAdapter 实例（可选），用于注入领域相关提示词/上下文
        """
        self.registry = ontology_registry or registry
        self._action_registry = action_registry
        self._admin_roles: set = set(admin_roles) if admin_roles else set()
        self._adapter = adapter
        self._context: Optional[PromptContext] = None

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

        # Store context for sub-methods (e.g. action/entity filtering)
        self._context = context
        try:
            # 构建各部分描述
            role_context = self._build_role_context(context) if context.user_role else ""
            semantic_query_syntax = self._build_semantic_query_syntax() if context.include_entities else ""
            entity_descriptions = self._build_entity_descriptions(context) if context.include_entities else ""
            action_descriptions = self._build_action_descriptions() if context.include_actions else ""
            state_machine_descriptions = self._build_state_machine_descriptions() if context.include_state_machines else ""
            rule_descriptions = self._build_rule_descriptions() if context.include_rules else ""
            permission_context = self._build_permission_context(context) if context.include_permissions else ""
            date_context = self._build_date_context(context.current_date)

            # 使用模板构建
            template = base_template or self.BASE_SYSTEM_PROMPT

            domain_prompt = context.domain_prompt if context.domain_prompt else ""

            prompt = template.format(
                domain_prompt=domain_prompt,
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
        finally:
            self._context = None

    # SPEC-P06: Phase 3 discovery prompt template
    DISCOVERY_TOOL_PROTOCOL = """
## 工具调用协议

你可以使用以下工具来发现和执行操作。使用 <tool_call> 标签调用工具：

### 可用工具

1. **search_actions** - 搜索可用操作
   ```
   <tool_call>{"tool": "search_actions", "args": {"query": "搜索关键词"}}</tool_call>
   ```

2. **describe_action** - 获取操作的详细参数定义
   ```
   <tool_call>{"tool": "describe_action", "args": {"name": "action_name"}}</tool_call>
   ```

### 工作流程

1. 分析用户意图
2. 使用 search_actions 搜索相关操作
3. 使用 describe_action 获取操作参数
4. 返回最终的 JSON 响应（与普通模式格式相同）

### 重要规则
- 每次回复中最多包含一个 <tool_call>
- 收到 <tool_result> 后继续分析，不要重复调用同一工具
- 当你确定了要执行的操作后，直接返回 JSON 响应，不要再调用工具
"""

    def build_discovery_prompt(
        self,
        context: Optional[PromptContext] = None,
        base_template: Optional[str] = None,
    ) -> str:
        """Build system prompt for Phase 3 discovery mode (SPEC-P06).

        Similar to build_system_prompt but:
        - Includes entity descriptions (for context)
        - Does NOT include action descriptions (LLM discovers via tools)
        - Appends the tool calling protocol definition
        """
        if context is None:
            context = PromptContext()

        # SPEC-P01: Store context for sub-methods
        self._context = context

        # Build parts — same as normal but skip actions
        role_context = self._build_role_context(context) if context.user_role else ""
        semantic_query_syntax = self._build_semantic_query_syntax() if context.include_entities else ""
        entity_descriptions = self._build_entity_descriptions(context) if context.include_entities else ""
        # No action_descriptions — that's the whole point of discovery mode
        action_descriptions = ""
        state_machine_descriptions = self._build_state_machine_descriptions() if context.include_state_machines else ""
        rule_descriptions = self._build_rule_descriptions() if context.include_rules else ""
        permission_context = self._build_permission_context(context) if context.include_permissions else ""
        date_context = self._build_date_context(context.current_date)

        template = base_template or self.BASE_SYSTEM_PROMPT
        domain_prompt = context.domain_prompt if context.domain_prompt else ""

        prompt = template.format(
            domain_prompt=domain_prompt,
            role_context=role_context,
            semantic_query_syntax=semantic_query_syntax,
            entity_descriptions=entity_descriptions,
            action_descriptions=action_descriptions,
            state_machine_descriptions=state_machine_descriptions,
            rule_descriptions=rule_descriptions,
            permission_context=permission_context,
            date_context=date_context,
        )

        if context.custom_variables:
            prompt = self._apply_custom_variables(prompt, context.custom_variables)

        # Append tool protocol
        prompt += self.DISCOVERY_TOOL_PROTOCOL

        return prompt

    def _build_role_context(self, context: PromptContext) -> str:
        """构建角色上下文"""
        lines = [f"**当前用户角色:** {context.user_role}"]
        if context.user_id:
            lines.append(f"**用户ID:** {context.user_id}")
        return "\n".join(lines)

    # 系统管理相关关键词（用于按需注入系统实体到 prompt）
    _SYSTEM_KEYWORDS = frozenset({
        "角色", "权限", "部门", "字典", "配置", "菜单",
        "公告", "定时任务", "岗位", "组织架构",
        "system", "role", "permission", "config", "menu", "dict",
    })

    def _build_entity_descriptions(self, context: Optional[PromptContext] = None) -> str:
        """构建实体描述部分 (SPEC-51 + SPEC-23: 按需注入系统实体)"""
        entities = self.registry.get_entities()

        if not entities:
            return "**本体实体:** 暂无注册实体"

        # 按 category 分组
        business_entities = [e for e in entities if getattr(e, 'category', '') != 'system']
        system_entities = [e for e in entities if getattr(e, 'category', '') == 'system']

        # Phase 1/2 filtering: apply allowed_entities whitelist
        if context and context.allowed_entities is not None:
            allowed = set(context.allowed_entities)
            business_entities = [e for e in business_entities if e.name in allowed]
            system_entities = [e for e in system_entities if e.name in allowed]

        lines = ["**本体实体:**"]

        # 业务实体始终注入
        for entity in business_entities:
            self._append_entity_description(entity, lines)

        # 系统实体按需注入
        if system_entities and self._should_include_system_entities(context):
            lines.append("\n## 系统管理实体")
            for entity in system_entities:
                self._append_entity_description(entity, lines)

        return "\n".join(lines)

    def _should_include_system_entities(self, context: Optional[PromptContext] = None) -> bool:
        """判断是否需要注入系统实体到 prompt（SPEC-23）"""
        if context is None:
            return False

        # 条件 1：用户角色是管理员（由 admin_roles 配置）
        if self._admin_roles and context.user_role in self._admin_roles:
            return True

        # 条件 2：用户消息包含系统管理关键词
        if context.message_hint and any(
            kw in context.message_hint for kw in self._SYSTEM_KEYWORDS
        ):
            return True

        return False

    def _append_entity_description(self, entity: EntityMetadata, lines: list) -> None:
        """追加单个实体的描述到 lines"""
        lines.append(f"\n### {entity.name}")
        if entity.description:
            lines.append(f"**描述:** {entity.description}")
        if hasattr(entity, 'table_name') and entity.table_name:
            lines.append(f"**数据表:** {entity.table_name}")

        # 属性列表（SPEC-51: 动态注入属性元数据）
        if getattr(entity, 'properties', None):
            lines.append("\n**属性:**")
            props = entity.properties.values() if isinstance(entity.properties, dict) else entity.properties
            for prop in props:
                if isinstance(prop, PropertyMetadata):
                    required = "必填" if prop.is_required else "可选"
                    type_info = prop.type.value if hasattr(prop.type, 'value') else str(prop.type)
                    security_note = ""
                    if hasattr(prop, 'security_level') and prop.security_level:
                        security_note = f" [{prop.security_level}]"
                    enum_hint = f" 可选值: {', '.join(prop.enum_values)}" if prop.enum_values else ""
                    lines.append(f"- **{prop.name}** ({type_info}) {required}{security_note}: {prop.description or ''}{enum_hint}")
                elif isinstance(prop, dict):
                    required = "必填" if prop.get('required', False) else "可选"
                    lines.append(f"- **{prop.get('name')}** {required}: {prop.get('description', '')}")
                elif isinstance(prop, str):
                    lines.append(f"- **{prop}**")

    def _build_action_descriptions(self) -> str:
        """
        构建操作描述部分 (SPEC-51: 动态注入操作元数据)

        优先从 ActionRegistry 读取（含 Pydantic schema 参数信息），
        回退到 OntologyRegistry.get_actions()。
        """
        if self._action_registry is not None:
            return self._build_action_descriptions_from_action_registry()
        return self._build_action_descriptions_from_ontology()

    def _build_action_descriptions_from_action_registry(self) -> str:
        """从 ActionRegistry 读取操作描述，利用 Pydantic model_json_schema() 提取参数"""
        actions = self._action_registry.list_actions()

        # Phase 1/2 filtering: apply allowed_actions whitelist
        if self._context and self._context.allowed_actions is not None:
            allowed = set(self._context.allowed_actions)
            actions = [a for a in actions if a.name in allowed]

        if not actions:
            return "**支持的操作:** 暂无注册操作"

        # 按 entity 分组
        grouped: Dict[str, list] = {}
        for action in actions:
            entity = action.entity or "general"
            if entity not in grouped:
                grouped[entity] = []
            grouped[entity].append(action)

        lines = ["**支持的操作 (action_type):**"]
        for entity, entity_actions in sorted(grouped.items()):
            if entity != "general":
                lines.append(f"\n### {entity} 操作:")

            for action in entity_actions:
                confirm_tag = "需确认" if action.requires_confirmation else "自动"
                category_tag = action.category
                lines.append(f"\n#### {action.name} [{category_tag}, {confirm_tag}]")
                if action.description:
                    lines.append(f"- **描述**: {action.description}")

                # 从 Pydantic schema 提取参数
                try:
                    schema = action.parameters_schema.model_json_schema()
                    properties = schema.get("properties", {})
                    required_fields = set(schema.get("required", []))

                    if properties:
                        lines.append(f"- **参数**:")
                        for field_name, field_info in properties.items():
                            field_type = field_info.get("type", "string")
                            # Handle anyOf (Optional fields)
                            if "anyOf" in field_info:
                                types = [o.get("type") for o in field_info["anyOf"] if o.get("type") != "null"]
                                field_type = types[0] if types else "string"
                            req_tag = "必填" if field_name in required_fields else "可选"
                            desc = field_info.get("description", "")
                            enum_vals = field_info.get("enum")
                            enum_hint = f" (可选值: {', '.join(str(v) for v in enum_vals)})" if enum_vals else ""
                            lines.append(f"  - {field_name} ({field_type}) {req_tag}: {desc}{enum_hint}")
                except Exception as e:
                    logger.debug(f"Failed to extract schema for {action.name}: {e}")

        return "\n".join(lines)

    def _build_action_descriptions_from_ontology(self) -> str:
        """从 OntologyRegistry 读取操作描述（回退路径）"""
        actions = self.registry.get_actions()

        # Phase 1/2 filtering: apply allowed_actions whitelist
        if self._context and self._context.allowed_actions is not None:
            allowed = set(self._context.allowed_actions)
            actions = [a for a in actions if a.action_type in allowed]

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

        # Phase 1/2 filtering: only inject state machines for allowed entities
        if self._context and self._context.allowed_entities is not None:
            allowed = set(self._context.allowed_entities)
            state_machines = {k: v for k, v in state_machines.items() if k in allowed}

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
        if not self._admin_roles or context.user_role not in self._admin_roles:
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

        # SPEC-R04: RELATIONSHIP_MAP is now a callable returning a dict
        rel_map = RELATIONSHIP_MAP() if callable(RELATIONSHIP_MAP) else RELATIONSHIP_MAP

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
        entity_paths = self._generate_entity_paths(rel_map)

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

        # 查询示例（从 adapter 注入，domain-agnostic）
        examples = self._adapter.get_query_examples() if self._adapter else []
        if examples:
            import json
            lines.extend(["", "## 查询示例", ""])
            for i, example in enumerate(examples, 1):
                desc = example.get("description", f"示例 {i}")
                lines.append(f"### 示例 {i}: {desc}")
                lines.append("```json")
                lines.append(json.dumps(example["query"], ensure_ascii=False, indent=2))
                lines.append("```")
                lines.append("")

        # 重要规则（framework-generic）
        lines.extend([
            "",
            "## 重要规则",
            "",
            "1. **路径必须使用关系属性名**",
            "2. **日期字段使用 ISO 格式**（YYYY-MM-DD）",
            "3. **状态值使用枚举值**",
            "4. **多个过滤器之间是 AND 关系**",
            "5. **limit 默认为 100，最大 1000**",
        ])

        return "\n".join(lines)

    def _generate_entity_paths(self, relationship_map: Dict[str, Dict[str, Tuple[str, str]]]) -> Dict[str, List[str]]:
        """
        Dynamically generate entity path descriptions from the relationship map
        and ontology registry.

        Args:
            relationship_map: Relationship mapping dict from query_engine

        Returns:
            Entity name to path description list mapping
        """
        result = {}

        for entity_name, relationships in relationship_map.items():
            paths = []

            # Get entity metadata from registry for direct fields
            entity_meta = self.registry.get_entity(entity_name)
            if entity_meta and hasattr(entity_meta, 'properties') and entity_meta.properties:
                for prop_name in list(entity_meta.properties.keys())[:8]:
                    paths.append(f"- **{prop_name}** - direct field")

            # Add relationship paths from the relationship map
            for rel_attr, (target_entity, join_col) in relationships.items():
                paths.append(f"- **{rel_attr}** -> {target_entity}")
                # Add one-hop paths for target entity's key fields
                target_meta = self.registry.get_entity(target_entity)
                if target_meta and hasattr(target_meta, 'properties') and target_meta.properties:
                    for prop_name in list(target_meta.properties.keys())[:4]:
                        paths.append(f"- **{rel_attr}.{prop_name}**")

            if paths:
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
            if self._adapter:
                # Delegate formatting to domain adapter
                adapter_lines = self._adapter.get_context_summary(None, additional_context)
                lines.extend(adapter_lines)
            else:
                # Generic fallback: output raw key-value summary
                for key, value in additional_context.items():
                    if isinstance(value, list):
                        lines.append(f"- {key}: {len(value)} 项")
                    elif isinstance(value, dict):
                        summary = ", ".join(f"{k}: {v}" for k, v in list(value.items())[:4])
                        lines.append(f"- {key}: {summary}")
                    else:
                        lines.append(f"- {key}: {value}")

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

        # 如果有数据库会话，获取实时数据（委托给 adapter）
        if db_session and self._adapter:
            try:
                dynamic_ctx = self._adapter.build_llm_context(db_session)
                context.update(dynamic_ctx)
            except Exception as e:
                logger.warning(f"Failed to build dynamic context from adapter: {e}")

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

    def _build_domain_glossary(self) -> str:
        """
        构建领域关键词表（Domain Glossary）

        从注入的 ActionRegistry 收集所有 search_keywords，按 semantic_category 分组，
        生成 LLM 友好的提示词，明确告诉 LLM 哪些词是语义信号而非参数值。

        所有领域知识（类别描述、示例）来自 action 注册时的元数据，框架本身不含领域知识。

        Returns:
            领域关键词表提示词字符串
        """
        if self._action_registry is None:
            return ""

        try:
            glossary_data = self._action_registry.get_domain_glossary()
        except Exception as e:
            logger.debug(f"ActionRegistry.get_domain_glossary() failed: {e}")
            return ""

        if not glossary_data:
            return ""

        lines = [
            "**领域关键词表 (Domain Glossary) - 重要: 以下是语义信号，不是参数值**",
            "",
            "以下关键词表示操作类型或状态，不应被提取为实体参数值:",
            ""
        ]

        # Add each category
        for category_name, category_info in glossary_data.items():
            lines.append(f"### {category_info.get('meaning', category_name)}")

            keywords = category_info.get("keywords", [])
            for kw in keywords:
                lines.append(f"- **{kw}**")

            lines.append("")

        # Add extraction rules
        lines.extend([
            "**参数提取规则:**",
            "1. **关键字不作为参数值**: 上述关键词表示语义信号，不要将它们提取为实体参数的值",
            "2. **正确识别操作意图**: 关键词表示要执行的操作类型，不是数据内容",
            ""
        ])

        # Add examples (all from domain-layer registration)
        has_examples = any(
            category_info.get("examples")
            for category_info in glossary_data.values()
        )
        if has_examples:
            lines.append("**示例:**")
            for category_name, category_info in glossary_data.items():
                examples = category_info.get("examples", [])
                if examples:
                    lines.append(f"\n**{category_info.get('meaning', category_name)}:**")
                    for ex in examples[:3]:
                        if ex.get("correct"):
                            lines.append(f"- correct: {ex['correct']}")
                        if ex.get("incorrect"):
                            lines.append(f"- incorrect: {ex['incorrect']}")

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
