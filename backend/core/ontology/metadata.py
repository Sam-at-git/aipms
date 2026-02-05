"""
core/ontology/metadata.py

本体元数据定义 - Palantir 式架构的语义层
定义实体、动作、属性、状态机等核心元数据结构
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Optional, Any


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


@dataclass
class StateTransition:
    """状态转换定义"""
    from_state: str
    to_state: str
    trigger: str  # 触发动作
    condition: Optional[str] = None  # 条件
    side_effects: List[str] = field(default_factory=list)  # 副作用


@dataclass
class StateMachine:
    """状态机定义"""
    entity: str
    states: List[str]
    transitions: List[StateTransition]
    initial_state: str


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


@dataclass
class PropertyMetadata:
    """属性元数据"""
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


# 导出
__all__ = [
    "ParamType",
    "ActionParam",
    "BusinessRule",
    "StateTransition",
    "StateMachine",
    "ActionMetadata",
    "PropertyMetadata",
    "EntityMetadata",
]
