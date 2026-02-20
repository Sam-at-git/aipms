"""
core/ontology/metadata.py

本体元数据定义 - Palantir 式架构的语义层
定义实体、动作、属性、状态机等核心元数据结构

Enhanced for domain-agnostic LLM reasoning framework (Phase 0)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Optional, Any, Callable, Tuple
from abc import ABC, abstractmethod


class ParamType(str, Enum):
    """参数类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"


class PIIType(Enum):
    """个人数据类型 - Personal Identifiable Information types"""
    NONE = "none"
    NAME = "name"
    PHONE = "phone"
    EMAIL = "email"
    ID_NUMBER = "id_number"
    ADDRESS = "address"
    FINANCIAL = "financial"
    HEALTH = "health"


class ActionScope(Enum):
    """操作范围"""
    SINGLE = "single"           # 单个实体操作
    BULK = "bulk"               # 批量操作
    QUERY = "query"             # 查询操作
    SYSTEM = "system"           # 系统操作


class ConfirmationLevel(Enum):
    """确认级别"""
    NONE = "none"               # 无需确认
    LOW = "low"                 # 简单确认
    MEDIUM = "medium"           # 需要详细信息展示
    HIGH = "high"               # 需要显式审批


class ConstraintType(Enum):
    """约束类型"""
    STATE = "state"                   # 状态约束
    CARDINALITY = "cardinality"       # 基数约束
    BUSINESS_RULE = "business_rule"   # 业务规则
    REFERENCE = "reference"           # 引用完整性
    CUSTOM = "custom"                 # 自定义约束


class ConstraintSeverity(Enum):
    """约束严重程度"""
    INFO = "info"             # 信息提示
    WARNING = "warning"       # 警告但可继续
    ERROR = "error"           # 错误，阻止操作
    CRITICAL = "critical"     # 严重错误，需要立即处理


@dataclass
class ConstraintEvaluationContext:
    """约束评估上下文"""
    entity_type: str
    action_type: str
    parameters: Dict[str, Any]
    current_state: Dict[str, Any]
    user_context: Dict[str, Any]

    def get_parameter(self, name: str, default: Any = None) -> Any:
        return self.parameters.get(name, default)


class IConstraintValidator(ABC):
    """约束验证器接口"""

    @abstractmethod
    def validate(self, context: ConstraintEvaluationContext) -> Tuple[bool, Optional[str]]:
        """
        验证约束

        Returns:
            (is_valid, error_message)
        """
        pass


@dataclass
class RelationshipMetadata:
    """关系元数据 - 实体间关系的一等公民定义"""
    name: str                    # 源实体上的属性名 (如 "stays")
    target_entity: str           # 目标实体名 (如 "StayRecord")
    cardinality: str             # "one_to_many" | "many_to_one" | "one_to_one"
    foreign_key: str             # FK 列名 (如 "guest_id")
    foreign_key_entity: str      # 拥有 FK 的实体名
    inverse_name: Optional[str] = None  # 反向导航属性名
    description: str = ""

    def to_llm_description(self) -> str:
        """生成 LLM 可理解的描述"""
        parts = [f"- {self.name} → {self.target_entity} ({self.cardinality})"]
        if self.description:
            parts.append(f": {self.description}")
        if self.inverse_name:
            parts.append(f" [反向: {self.inverse_name}]")
        return "".join(parts)


@dataclass
class ActionParam:
    """动作参数定义"""
    name: str
    type: ParamType
    required: bool = True
    description: str = ""
    default_value: Any = None
    enum_values: Optional[List[str]] = None
    format: Optional[str] = None  # 如 "date-time", "email" 等
    validation_regex: Optional[str] = None

    def to_llm_description(self) -> str:
        """生成 LLM 可理解的描述"""
        parts = [f"- `{self.name}`"]

        if self.description:
            parts.append(f" ({self.description})")

        parts.append(f" : {self.type.value if isinstance(self.type, Enum) else self.type}")

        if self.required:
            parts.append(" [必填]")
        else:
            parts.append(f" [可选，默认: {self.default_value}]")

        if self.enum_values:
            parts.append(f" 可选值: {', '.join(self.enum_values)}")

        return "".join(str(p) for p in parts)


@dataclass
class BusinessRule:
    """业务规则定义"""
    rule_id: str
    entity: str
    rule_name: str
    description: str
    condition: str  # 条件表达式
    action: str  # 触发的动作
    severity: str = "error"  # error, warning, info

    # 框架增强字段
    constraint_type: ConstraintType = ConstraintType.BUSINESS_RULE

    def to_llm_summary(self) -> str:
        """生成 LLM 可理解的约束摘要"""
        severity_symbols = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚫",
            "critical": "⛔"
        }
        symbol = severity_symbols.get(self.severity, "")

        lines = [
            f"{symbol} **{self.rule_name}**",
            f"{self.description}",
            ""
        ]

        if self.condition:
            lines.append(f"**条件**: {self.condition}")

        if self.action:
            lines.append(f"**动作**: {self.action}")

        return "\n".join(lines)


@dataclass
class ConstraintMetadata:
    """约束元数据 - 领域无关的核心抽象"""

    # 基本标识
    id: str
    name: str
    description: str

    # 约束分类
    constraint_type: ConstraintType
    severity: ConstraintSeverity

    # 作用域
    entity: str  # 约束的实体
    action: str  # 约束的操作 (空表示所有操作)

    # 约束表达式
    condition_text: str  # 自然语言描述 (给 LLM)
    condition_code: Optional[str] = None  # 代码表达式 (运行时验证)
    validator: Optional[IConstraintValidator] = None  # 自定义验证器

    # 错误消息
    error_message: str = ""
    suggestion_message: str = ""

    # 触发条件
    trigger_conditions: List[str] = field(default_factory=list)

    # 扩展字段
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_llm_summary(self) -> str:
        """生成 LLM 可理解的约束摘要"""
        severity_symbol = {
            ConstraintSeverity.INFO: "ℹ️",
            ConstraintSeverity.WARNING: "⚠️",
            ConstraintSeverity.ERROR: "🚫",
            ConstraintSeverity.CRITICAL: "⛔"
        }

        lines = [
            f"{severity_symbol.get(self.severity, '')} **{self.name}**",
            f"{self.description}",
            ""
        ]

        if self.condition_text:
            lines.append(f"**条件**: {self.condition_text}")

        if self.error_message:
            lines.append(f"**错误**: {self.error_message}")

        if self.suggestion_message:
            lines.append(f"**建议**: {self.suggestion_message}")

        return "\n".join(lines)


@dataclass
class StateTransition:
    """状态转换定义"""
    from_state: str
    to_state: str
    trigger: str  # 触发动作
    condition: Optional[str] = None  # 条件
    side_effects: List[str] = field(default_factory=list)  # 副作用

    def to_llm_description(self) -> str:
        """生成 LLM 可理解的描述"""
        parts = [f"{self.from_state} → {self.to_state}"]
        parts.append(f" (触发: {self.trigger})")

        if self.condition:
            parts.append(f" [条件: {self.condition}]")

        if self.side_effects:
            parts.append(f"\n    副作用: {', '.join(self.side_effects)}")

        return "".join(parts)


@dataclass
class StateMachine:
    """状态机定义"""
    entity: str
    states: List[str]
    transitions: List[StateTransition]
    initial_state: str

    # 框架增强字段
    final_states: Set[str] = field(default_factory=set)
    name: str = ""  # 状态机名称
    description: str = ""  # 状态机描述

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.entity}_lifecycle"

    def get_valid_transitions(self, current_state: str) -> List[StateTransition]:
        """获取当前状态的有效转移"""
        return [
            t for t in self.transitions
            if t.from_state == current_state
        ]

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """检查转移是否有效"""
        return any(
            t.from_state == from_state and t.to_state == to_state
            for t in self.transitions
        )

    def to_llm_summary(self) -> str:
        """生成 LLM 可理解的状态机摘要"""
        lines = [
            f"### {self.name} - {self.entity}",
            f"{self.description}",
            ""
        ]

        if self.states:
            lines.append("**状态:**")
            for state in self.states:
                prefix = "→ " if state == self.initial_state else ""
                if state in self.final_states:
                    prefix += "[终态] "
                lines.append(f"{prefix}{state}")
            lines.append("")

        if self.transitions:
            lines.append("**状态转移:**")
            for trans in self.transitions:
                lines.append(f"- {trans.to_llm_description()}")

        return "\n".join(lines)


@dataclass
class ActionMetadata:
    """动作元数据"""
    action_type: str
    entity: str
    method_name: str
    description: str
    params: List[ActionParam] = field(default_factory=list)
    requires_confirmation: bool = False
    allowed_roles: Set[str] = field(default_factory=set)
    writeback: bool = True  # 是否回写业务系统
    undoable: bool = False  # 是否可撤销

    # ========== 新增字段 (Phase 0 - Framework Enhancement) ==========

    # 框架增强字段
    name: str = ""  # 操作名称（可能与action_type不同）
    scope: ActionScope = ActionScope.SINGLE
    parameters: Dict[str, ActionParam] = field(default_factory=dict)  # Dict 版本的 params
    confirmation_level: ConfirmationLevel = ConfirmationLevel.MEDIUM
    requires_approval: bool = False
    denied_roles: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    pre_conditions: List[str] = field(default_factory=list)
    post_conditions: List[str] = field(default_factory=list)
    extensions: Dict[str, Any] = field(default_factory=dict)

    # ========== Classification fields (SPEC-04) ==========
    category: str = ""  # "query" | "mutation" | "system" | "tool"
    risk_level: str = ""  # "none" | "low" | "medium" | "high" | "critical"
    is_financial: bool = False
    ui_required_fields: List[str] = field(default_factory=list)

    # 如果 name 未设置，使用 action_type
    def __post_init__(self):
        if not self.name:
            self.name = self.action_type

    def add_parameter(self, param: ActionParam) -> 'ActionMetadata':
        """添加参数 (流式 API)"""
        self.parameters[param.name] = param
        # 同时保持 params 列表同步
        self.params.append(param)
        return self

    def to_llm_summary(self) -> str:
        """生成 LLM 可理解的操作摘要"""
        lines = [
            f"### {self.name}",
            f"{self.description}",
            ""
        ]

        # 使用 parameters 字典或 params 列表
        params_to_show = self.parameters if self.parameters else {
            p.name: p for p in self.params
        }

        if params_to_show:
            lines.append("**参数:**")
            for param in params_to_show.values():
                if hasattr(param, 'to_llm_description'):
                    lines.append(param.to_llm_description())
                else:
                    lines.append(f"- {param.name} ({param.type})")
            lines.append("")

        if self.pre_conditions:
            lines.append("**前置条件:**")
            for cond in self.pre_conditions:
                lines.append(f"- {cond}")
            lines.append("")

        if self.side_effects:
            lines.append("**副作用:**")
            for effect in self.side_effects:
                lines.append(f"- {effect}")
            lines.append("")

        if self.undoable:
            lines.append("**可撤销**: 是")

        return "\n".join(lines)


@dataclass
class PropertyMetadata:
    """属性元数据 - 增强版

    OAG (Ontology-Augmented Generation) 增强字段：
    - 支持属性可变性控制
    - 支持基于角色的更新权限
    - 支持格式验证和约束检查
    """
    name: str
    type: str
    python_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_required: bool = False
    is_unique: bool = False
    is_nullable: bool = True
    default_value: Any = None
    max_length: Optional[int] = None
    enum_values: Optional[List[str]] = None
    description: str = ""
    security_level: str = "INTERNAL"  # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    foreign_key_target: Optional[str] = None  # 引用的表

    # ========== 新增字段 (Phase 2.5) ==========

    # 显示名称（用于UI展示）
    display_name: str = ""

    # 是否支持全文搜索
    searchable: bool = False

    # 是否建立索引
    indexed: bool = False

    # 验证器列表
    validators: List[Callable] = field(default_factory=list)

    # 是否为富文本内容
    is_rich_text: bool = False

    # 敏感信息标记
    pii: bool = False  # Personal Identifiable Information
    phi: bool = False  # Protected Health Information

    # 脱敏策略 (如 "mask_middle": "138****1234")
    mask_strategy: Optional[str] = None

    # ========== 新增字段 (Phase 0 - Framework Enhancement) ==========

    # 框架增强字段
    pii_type: PIIType = PIIType.NONE
    relationship_target: Optional[str] = None  # 关联目标实体
    relationship_cardinality: Optional[str] = None  # one-to-one, one-to-many, many-to-one

    # ========== OAG (Ontology-Augmented Generation) 增强字段 ==========

    # 属性可变性 - 此属性是否可以被修改
    mutable: bool = True

    # 更新权限列表 - 允许修改此属性的角色列表
    # 空列表表示所有已授权角色都可以修改
    updatable_by: List[str] = field(default_factory=list)

    # 格式验证正则表达式
    format_regex: Optional[str] = None

    # 更新频率限制 - 每个时间周期内最多修改次数（None表示无限制）
    update_frequency_limit: Optional[int] = None

    # 更新频率限制的时间周期（小时）
    update_frequency_period_hours: Optional[int] = None

    # 更新验证规则列表 - 运行时验证函数
    update_validation_rules: List[Callable] = field(default_factory=list)

    # 是否为敏感字段（修改需要额外确认）
    sensitive: bool = False

    # 修改原因要求 - 修改此字段是否需要填写原因
    requires_reason: bool = False

    def to_llm_description(self) -> str:
        """生成 LLM 可理解的描述"""
        parts = [f"- {self.name} ({self.type})"]

        if self.description:
            parts.append(f": {self.description}")

        if self.is_required:
            parts.append(" [必填]")

        if self.enum_values:
            parts.append(f" 可选值: {', '.join(self.enum_values)}")

        if self.security_level != "INTERNAL":
            parts.append(f" [安全级别: {self.security_level}]")

        if self.pii or self.pii_type != PIIType.NONE:
            pii_display = self.pii_type.value if self.pii_type != PIIType.NONE else "yes"
            parts.append(f" [敏感数据: {pii_display}]")

        return "".join(parts)


@dataclass
class EventMetadata:
    """领域事件元数据"""
    name: str                          # Event name (e.g. "ROOM_STATUS_CHANGED")
    description: str = ""              # Human-readable description
    entity: str = ""                   # Related entity (e.g. "Room")
    triggered_by: List[str] = field(default_factory=list)  # Actions that trigger this event
    payload_fields: List[str] = field(default_factory=list)  # Expected payload field names
    subscribers: List[str] = field(default_factory=list)  # Known subscriber descriptions


@dataclass
class EntityMetadata:
    """实体元数据"""
    name: str
    description: str
    table_name: str
    is_aggregate_root: bool = False
    related_entities: List[str] = field(default_factory=list)
    business_rules: List[BusinessRule] = field(default_factory=list)
    state_machine: Optional[StateMachine] = None

    # ========== 数据作用域 ==========
    data_scope_type: str = "global"       # "global" | "scoped"
    scope_column: Optional[str] = None    # SCOPED 实体的过滤列名

    # ========== 新增字段 (Phase 0 - Framework Enhancement) ==========

    # 框架增强字段
    properties: Dict[str, PropertyMetadata] = field(default_factory=dict)
    category: str = ""  # 如 "transactional", "master_data", "dimension"
    tags: List[str] = field(default_factory=list)
    extends: Optional[str] = None  # 父实体
    implements: List[str] = field(default_factory=list)  # 实现的接口
    lifecycle_states: Optional[List[str]] = None  # 可能的状态列表
    default_permissions: Dict[str, List[str]] = field(default_factory=dict)
    extensions: Dict[str, Any] = field(default_factory=dict)

    # 关系元数据列表
    relationships: List['RelationshipMetadata'] = field(default_factory=list)

    def add_property(self, prop: PropertyMetadata) -> 'EntityMetadata':
        """添加属性 (流式 API)"""
        self.properties[prop.name] = prop
        return self

    def add_relationship(self, rel: 'RelationshipMetadata') -> 'EntityMetadata':
        """添加关系元数据 (流式 API)"""
        self.relationships.append(rel)
        return self

    def get_property(self, name: str) -> Optional[PropertyMetadata]:
        """获取属性"""
        return self.properties.get(name)

    def get_relationships(self) -> List[Tuple[str, str, str]]:
        """获取所有关系 (返回 [(property_name, target_entity, cardinality)])"""
        relationships = []
        for name, prop in self.properties.items():
            if prop.relationship_target:
                relationships.append((
                    name,
                    prop.relationship_target,
                    prop.relationship_cardinality or "unknown"
                ))
        return relationships

    def to_llm_summary(self) -> str:
        """生成 LLM 可理解的实体摘要"""
        lines = [
            f"## {self.name}",
            f"{self.description}",
            ""
        ]

        if self.is_aggregate_root:
            lines.append("**聚合根** - 此实体是业务操作的入口点")
            lines.append("")

        if self.properties:
            lines.append("**属性:**")
            for prop in self.properties.values():
                if hasattr(prop, 'to_llm_description'):
                    lines.append(prop.to_llm_description())
                else:
                    required = " [必填]" if prop.is_required else ""
                    lines.append(f"- {prop.name} ({prop.type}){required}")
            lines.append("")

        if self.lifecycle_states:
            lines.append(f"**生命周期状态:** {', '.join(self.lifecycle_states)}")

        return "\n".join(lines)


# ============== Searchable 装饰器 - 意图识别关键字支持 ==============

# 存储实体和属性的关键字映射
# 格式: {keyword: [(type, name), ...]}
# type: 'entity' 或 'property'
# name: 实体名或属性路径 (如 'Room.status')
_SEARCHABLE_KEYWORDS: Dict[str, List[Tuple[str, str]]] = {}


def register_searchable_keyword(keyword: str, item_type: str, name: str):
    """
    注册可搜索关键字

    Args:
        keyword: 关键字（如 '房间', '空闲'）
        item_type: 类型 ('entity' 或 'property')
        name: 实体名或属性路径 (如 'Room', 'Room.status')
    """
    if keyword not in _SEARCHABLE_KEYWORDS:
        _SEARCHABLE_KEYWORDS[keyword] = []
    _SEARCHABLE_KEYWORDS[keyword].append((item_type, name))


def get_searchable_mapping() -> Dict[str, List[Tuple[str, str]]]:
    """获取所有可搜索关键字映射"""
    return _SEARCHABLE_KEYWORDS.copy()


def ontology_entity(
    name: str = "",
    description: str = "",
    table_name: str = "",
    keywords: List[str] = None
):
    """
    实体装饰器 - 声明实体的可搜索关键字

    Args:
        name: 实体名称（如果为空，使用类名）
        description: 实体描述
        table_name: 数据库表名
        keywords: 可搜索关键字列表（用于意图识别）

    Example:
        @ontology_entity(keywords=['房间', '房态', '空房'])
        class Room(Base):
            ...
    """
    def decorator(cls):
        # 设置实体名称
        entity_name = name or cls.__name__
        cls._ontology_entity_name = entity_name
        cls._ontology_description = description
        cls._ontology_table_name = table_name or cls.__tablename__

        # 注册关键字
        if keywords:
            for kw in keywords:
                register_searchable_keyword(kw, 'entity', entity_name)

        # 存储 keywords 以便后续访问
        cls._ontology_keywords = keywords or []

        return cls
    return decorator


def ontology_property(
    keywords: List[str] = None,
    entity_name: str = None
):
    """
    属性装饰器 - 声明属性的可搜索关键字

    Args:
        keywords: 可搜索关键字列表
        entity_name: 所属实体名（如果为空，尝试从类上下文推断）

    Example:
        class Room(Base):
            status = Column(String)

            @ontology_property(keywords=['空闲', '入住', '待清洁'])
            def get_status_display(self):
                return self.status

    或者在 SQLAlchemy 模型中作为类方法使用：

        class Room:
            @staticmethod
            @ontology_property(keywords=['空闲', '入住', '待清洁'])
            def status_keywords():
                pass
    """
    def decorator(method_or_property):
        # 获取所属类名（如果可能）
        if entity_name:
            prop_path = f"{entity_name}.{method_or_property.__name__}"
        else:
            # 标记需要延迟解析
            prop_path = f"<deferred>.{method_or_property.__name__}"
            method_or_property._ontology_property_deferred = True

        # 注册关键字
        if keywords:
            for kw in keywords:
                register_searchable_keyword(kw, 'property', prop_path)

        # 存储 keywords
        method_or_property._ontology_keywords = keywords or []
        method_or_property._ontology_property_path = prop_path

        return method_or_property
    return decorator


# 导出
__all__ = [
    "ParamType",
    "RelationshipMetadata",
    "ActionParam",
    "BusinessRule",
    "StateTransition",
    "StateMachine",
    "ActionMetadata",
    "PropertyMetadata",
    "EntityMetadata",
    # New types for framework
    "PIIType",
    "ActionScope",
    "ConfirmationLevel",
    "ConstraintType",
    "ConstraintSeverity",
    "ConstraintEvaluationContext",
    "IConstraintValidator",
    "ConstraintMetadata",
    "EventMetadata",
    # Searchable decorators
    "ontology_entity",
    "ontology_property",
    "register_searchable_keyword",
    "get_searchable_mapping",
]
