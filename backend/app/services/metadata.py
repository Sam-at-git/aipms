"""
本体元数据装饰器系统 (DEPRECATED)

This module is deprecated. Use core.ontology.registry.OntologyRegistry instead.
The only active components are the SQLAlchemy reflection utilities:
- get_model_attributes() - Extract column metadata from ORM models
- get_entity_relationships() - Extract relationship metadata from ORM models
- AttributeMetadata - Dataclass for column metadata

The MetadataRegistry, decorators (ontology_entity, ontology_action, etc.)
are deprecated and will be removed in a future version.
"""
import warnings
from typing import Dict, List, Optional, Callable, Any, Set
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum

# ============== 数据结构 ==============

class ParamType(str, Enum):
    """参数类型"""
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
    """业务规则"""
    rule_id: str
    entity: str
    rule_name: str
    description: str
    condition: str  # 条件表达式
    action: str  # 触发的动作
    severity: str = "error"  # error, warning, info


@dataclass
class StateTransition:
    """状态转换"""
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
class EntityMetadata:
    """实体元数据"""
    name: str
    description: str
    table_name: str
    is_aggregate_root: bool = False
    related_entities: List[str] = field(default_factory=list)
    business_rules: List[BusinessRule] = field(default_factory=list)
    state_machine: Optional[StateMachine] = None


@dataclass
class AttributeMetadata:
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


# ============== 元数据注册表 ==============

class MetadataRegistry:
    """元数据注册表 - 单例模式 (DEPRECATED: Use core.ontology.registry.OntologyRegistry)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entities: Dict[str, EntityMetadata] = {}
            cls._instance._actions: Dict[str, List[ActionMetadata]] = {}
            cls._instance._state_machines: Dict[str, StateMachine] = {}
            cls._instance._business_rules: Dict[str, List[BusinessRule]] = {}
            cls._instance._permission_matrix: Dict[str, Dict[str, Set[str]]] = {}
        return cls._instance

    def register_entity(self, metadata: EntityMetadata):
        """注册实体元数据"""
        self._entities[metadata.name] = metadata

    def register_action(self, entity: str, metadata: ActionMetadata):
        """注册动作元数据"""
        if entity not in self._actions:
            self._actions[entity] = []
        self._actions[entity].append(metadata)

    def register_state_machine(self, metadata: StateMachine):
        """注册状态机"""
        self._state_machines[metadata.entity] = metadata

    def register_business_rule(self, entity: str, rule: BusinessRule):
        """注册业务规则"""
        if entity not in self._business_rules:
            self._business_rules[entity] = []
        self._business_rules[entity].append(rule)

    def register_permission(self, action_type: str, roles: Set[str]):
        """注册权限"""
        if action_type not in self._permission_matrix:
            self._permission_matrix[action_type] = set()
        self._permission_matrix[action_type].update(roles)

    # Getters
    def get_entity(self, name: str) -> Optional[EntityMetadata]:
        return self._entities.get(name)

    def get_entities(self) -> List[EntityMetadata]:
        return list(self._entities.values())

    def get_actions(self, entity: str = None) -> List[ActionMetadata]:
        if entity:
            return self._actions.get(entity, [])
        result = []
        for actions in self._actions.values():
            result.extend(actions)
        return result

    def get_state_machine(self, entity: str) -> Optional[StateMachine]:
        return self._state_machines.get(entity)

    def get_business_rules(self, entity: str = None) -> List[BusinessRule]:
        if entity:
            return self._business_rules.get(entity, [])
        result = []
        for rules in self._business_rules.values():
            result.extend(rules)
        return result

    def get_permissions(self) -> Dict[str, Set[str]]:
        return self._permission_matrix.copy()


# 全局注册表实例
registry = MetadataRegistry()


# ============== 装饰器定义 (DEPRECATED) ==============
# Use HotelDomainAdapter.register_ontology() instead

def ontology_entity(
    name: str,
    description: str,
    table_name: str = None,
    is_aggregate_root: bool = False,
    related_entities: List[str] = None
):
    """
    实体类装饰器 - 标记本体实体

    用法:
        @ontology_entity(
            name="Room",
            description="房间",
            table_name="rooms",
            is_aggregate_root=False,
            related_entities=["RoomType", "StayRecord", "Task"]
        )
        class Room(Base):
            ...
    """
    def decorator(cls):
        metadata = EntityMetadata(
            name=name,
            description=description,
            table_name=table_name or cls.__tablename__,
            is_aggregate_root=is_aggregate_root,
            related_entities=related_entities or []
        )
        registry.register_entity(metadata)
        cls._ontology_metadata = metadata
        return cls
    return decorator


def ontology_action(
    entity: str,
    action_type: str,
    description: str,
    params: List[Dict] = None,
    requires_confirmation: bool = False,
    allowed_roles: List[str] = None,
    writeback: bool = True,
    undoable: bool = False
):
    """
    方法装饰器 - 标记本体动作（动力维度）

    用法:
        @ontology_action(
            entity="Room",
            action_type="update_status",
            description="更新房间状态",
            params=[
                {"name": "room_id", "type": "integer", "required": True},
                {"name": "status", "type": "enum", "enum_values": ["vacant_clean", "occupied", ...], "required": True}
            ],
            requires_confirmation=True,
            allowed_roles=["manager", "receptionist"],
            writeback=True,
            undoable=True
        )
        def update_room_status(self, room_id: int, status: RoomStatus):
            ...
    """
    def decorator(method):
        # 构建 ActionParam 对象
        action_params = []
        if params:
            for p in params:
                param_type = ParamType.STRING
                if p.get("type") in ["integer", "int"]:
                    param_type = ParamType.INTEGER
                elif p.get("type") in ["number", "float", "decimal"]:
                    param_type = ParamType.NUMBER
                elif p.get("type") == "boolean":
                    param_type = ParamType.BOOLEAN
                elif p.get("type") == "date":
                    param_type = ParamType.DATE
                elif p.get("type") == "datetime":
                    param_type = ParamType.DATETIME
                elif p.get("type") == "enum":
                    param_type = ParamType.ENUM
                elif p.get("type") in ["list", "array"]:
                    param_type = ParamType.ARRAY
                elif p.get("type") in ["dict", "object"]:
                    param_type = ParamType.OBJECT

                action_params.append(ActionParam(
                    name=p["name"],
                    type=param_type,
                    required=p.get("required", True),
                    description=p.get("description", ""),
                    enum_values=p.get("enum_values"),
                    format=p.get("format")
                ))

        metadata = ActionMetadata(
            action_type=action_type,
            entity=entity,
            method_name=method.__name__,
            description=description,
            params=action_params,
            requires_confirmation=requires_confirmation,
            allowed_roles=set(allowed_roles or []),
            writeback=writeback,
            undoable=undoable
        )
        registry.register_action(entity, metadata)

        # 注册权限
        if allowed_roles:
            registry.register_permission(action_type, set(allowed_roles))

        @wraps(method)
        def wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        wrapper._ontology_action = metadata
        return wrapper

    return decorator


def business_rule(
    entity: str,
    rule_id: str,
    rule_name: str,
    description: str,
    condition: str,
    action: str,
    severity: str = "error"
):
    """
    业务规则装饰器 - 定义业务规则（动态维度）

    用法:
        @business_rule(
            entity="Room",
            rule_id="room_occupied_no_manual_change",
            rule_name="入住中房间禁止手动改状态",
            description="当房间状态为入住中时，不能手动更改状态",
            condition="status == 'occupied'",
            action="raise ValueError",
            severity="error"
        )
    """
    def decorator(method):
        rule = BusinessRule(
            rule_id=rule_id,
            entity=entity,
            rule_name=rule_name,
            description=description,
            condition=condition,
            action=action,
            severity=severity
        )
        registry.register_business_rule(entity, rule)

        @wraps(method)
        def wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        wrapper._business_rule = rule
        return wrapper

    return decorator


def state_machine(
    entity: str,
    states: List[str],
    transitions: List[Dict],
    initial_state: str
):
    """
    状态机装饰器 - 定义状态转换（动态维度）

    用法:
        @state_machine(
            entity="Room",
            states=["vacant_clean", "occupied", "vacant_dirty", "out_of_order"],
            transitions=[
                {"from": "vacant_clean", "to": "occupied", "trigger": "check_in"},
                {"from": "occupied", "to": "vacant_dirty", "trigger": "check_out", "side_effects": ["create_cleaning_task"]},
                {"from": "vacant_dirty", "to": "vacant_clean", "trigger": "task_complete"},
                # ...
            ],
            initial_state="vacant_clean"
        )
    """
    state_transitions = []
    for t in transitions:
        state_transitions.append(StateTransition(
            from_state=t["from"],
            to_state=t["to"],
            trigger=t["trigger"],
            condition=t.get("condition"),
            side_effects=t.get("side_effects", [])
        ))

    machine = StateMachine(
        entity=entity,
        states=states,
        transitions=state_transitions,
        initial_state=initial_state
    )
    registry.register_state_machine(machine)

    def decorator(cls):
        cls._state_machine = machine
        return cls

    return decorator


def require_role_metadata(roles: List[str]):
    """
    权限装饰器 - 记录动作权限需求（动态维度）

    用法:
        @require_role_metadata(["manager"])
        def adjust_bill(self, bill_id: int, amount: Decimal):
            ...
    """
    def decorator(method):
        method._required_roles = set(roles)
        return method
    return decorator


# ============== 辅助函数 ==============

def get_model_attributes(model_class) -> List[AttributeMetadata]:
    """
    从 SQLAlchemy 模型提取属性元数据

    Args:
        model_class: SQLAlchemy 模型类

    Returns:
        属性元数据列表
    """
    attributes = []

    if not hasattr(model_class, '__table__'):
        return attributes

    from sqlalchemy import inspect

    mapper = inspect(model_class)
    columns = mapper.columns

    for column in columns:
        attr = AttributeMetadata(
            name=column.name,
            type=str(column.type),
            python_type=str(column.type.python_type) if hasattr(column.type, 'python_type') else str(column.type),
            is_primary_key=column.primary_key,
            is_foreign_key=column.foreign_keys is not None and len(column.foreign_keys) > 0,
            is_required=not column.nullable and not column.default,
            is_nullable=column.nullable,
            is_unique=column.unique or column.primary_key,
            default_value=column.default.arg if column.default else None,
            max_length=getattr(column.type, 'length', None),
            description=column.comment or ""
        )

        # 处理外键
        if attr.is_foreign_key:
            for fk in column.foreign_keys:
                attr.foreign_key_target = fk.column.table.name

        # 处理枚举
        if hasattr(column.type, 'enum_class'):
            attr.enum_values = [e.value for e in column.type.enum_class]

        attributes.append(attr)

    return attributes


def get_entity_relationships(model_class) -> List[Dict]:
    """
    从 SQLAlchemy 模型提取关系

    Args:
        model_class: SQLAlchemy 模型类

    Returns:
        关系列表
    """
    relationships = []

    if not hasattr(model_class, '__table__'):
        return relationships

    from sqlalchemy import inspect

    mapper = inspect(model_class)

    for rel_name, relationship in mapper.relationships.items():
        target_class = relationship.mapper.class_
        # Get foreign key column name from local columns
        fk_column = None
        if relationship.local_remote_pairs:
            # The first element of the pair is the local column
            local_col = relationship.local_remote_pairs[0][0]
            fk_column = str(local_col.key) if hasattr(local_col, 'key') else None

        relationships.append({
            "name": rel_name,
            "target": target_class.__name__,
            "type": "one_to_many" if relationship.uselist else "many_to_one",
            "foreign_key": fk_column
        })

    return relationships
