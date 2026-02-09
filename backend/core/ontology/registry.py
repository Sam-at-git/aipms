"""
core/ontology/registry.py

本体注册中心 - 运行时元数据管理
提供实体、动作、状态机、业务规则的注册和检索功能

Enhanced for domain-agnostic LLM reasoning framework (Phase 0)
"""
from typing import Dict, List, Set, Optional, Any, TYPE_CHECKING

from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    StateMachine,
    BusinessRule,
    PropertyMetadata,
    StateTransition,
    ConstraintMetadata,
    ConstraintSeverity,
    RelationshipMetadata,
    EventMetadata,
)

if TYPE_CHECKING:
    from typing import Self


class OntologyRegistry:
    """
    本体注册中心 - 单例模式

    提供元数据的注册和检索功能：
    - 实体元数据
    - 动作元数据
    - 状态机定义
    - 业务规则
    - 权限矩阵
    - 接口实现关系

    Example:
        >>> registry = OntologyRegistry()
        >>> registry.register_entity(EntityMetadata(...))
        >>> entity = registry.get_entity("Room")
    """

    _instance: Optional["OntologyRegistry"] = None

    def __new__(cls) -> "OntologyRegistry":
        """单例模式 - 确保全局唯一实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entities: Dict[str, EntityMetadata] = {}
            cls._instance._actions: Dict[str, List[ActionMetadata]] = {}
            cls._instance._state_machines: Dict[str, StateMachine] = {}
            cls._instance._business_rules: Dict[str, List[BusinessRule]] = {}
            cls._instance._constraints: Dict[str, ConstraintMetadata] = {}  # Framework enhancement
            cls._instance._permission_matrix: Dict[str, Set[str]] = {}
            cls._instance._interface_implementations: Dict[str, List[str]] = {}
            cls._instance._interfaces: Dict[str, Any] = {}
            cls._instance._models: Dict[str, Any] = {}
            cls._instance._relationships: Dict[str, List[RelationshipMetadata]] = {}
            cls._instance._events: Dict[str, EventMetadata] = {}
        return cls._instance

    def register_entity(self, metadata: EntityMetadata) -> "OntologyRegistry":
        """
        注册实体元数据

        Args:
            metadata: 实体元数据对象

        Returns:
            self (for fluent API)
        """
        self._entities[metadata.name] = metadata
        return self

    def register_action(self, entity: str, metadata: ActionMetadata) -> "OntologyRegistry":
        """
        注册动作元数据

        Args:
            entity: 实体名称
            metadata: 动作元数据对象

        Returns:
            self (for fluent API)
        """
        if entity not in self._actions:
            self._actions[entity] = []
        self._actions[entity].append(metadata)
        return self

    def register_state_machine(self, metadata: StateMachine) -> "OntologyRegistry":
        """
        注册状态机

        Args:
            metadata: 状态机对象

        Returns:
            self (for fluent API)
        """
        self._state_machines[metadata.entity] = metadata
        return self

    def register_business_rule(self, entity: str, rule: BusinessRule) -> "OntologyRegistry":
        """
        注册业务规则

        Args:
            entity: 实体名称
            rule: 业务规则对象

        Returns:
            self (for fluent API)
        """
        if entity not in self._business_rules:
            self._business_rules[entity] = []
        self._business_rules[entity].append(rule)
        return self

    def register_constraint(self, constraint: ConstraintMetadata) -> "OntologyRegistry":
        """
        注册约束元数据

        Args:
            constraint: 约束元数据对象

        Returns:
            self (for fluent API)
        """
        self._constraints[constraint.id] = constraint
        return self

    def register_permission(self, action_type: str, roles: Set[str]) -> "OntologyRegistry":
        """
        注册权限

        Args:
            action_type: 动作类型
            roles: 允许执行该动作的角色集合

        Returns:
            self (for fluent API)
        """
        if action_type not in self._permission_matrix:
            self._permission_matrix[action_type] = set()
        self._permission_matrix[action_type].update(roles)
        return self

    def register_interface(self, interface_cls: Any) -> "OntologyRegistry":
        """
        注册接口定义

        Args:
            interface_cls: 接口类

        Returns:
            self (for fluent API)
        """
        self._interfaces[interface_cls.__name__] = interface_cls
        return self

    def register_interface_implementation(self, interface_name: str, entity_name: str) -> "OntologyRegistry":
        """
        注册接口实现关系

        Args:
            interface_name: 接口名称
            entity_name: 实体名称

        Returns:
            self (for fluent API)
        """
        if interface_name not in self._interface_implementations:
            self._interface_implementations[interface_name] = []
        if entity_name not in self._interface_implementations[interface_name]:
            self._interface_implementations[interface_name].append(entity_name)
        return self

    def register_model(self, entity_name: str, model_class: Any) -> "OntologyRegistry":
        """
        注册 ORM 模型类

        Args:
            entity_name: 实体名称
            model_class: SQLAlchemy ORM 模型类

        Returns:
            self (for fluent API)
        """
        self._models[entity_name] = model_class
        return self

    def register_relationship(self, entity_name: str, rel: RelationshipMetadata) -> "OntologyRegistry":
        """
        注册关系元数据

        Args:
            entity_name: 源实体名称
            rel: 关系元数据对象

        Returns:
            self (for fluent API)
        """
        if entity_name not in self._relationships:
            self._relationships[entity_name] = []
        self._relationships[entity_name].append(rel)
        # 同步到 EntityMetadata (如果已注册)
        entity = self._entities.get(entity_name)
        if entity:
            entity.add_relationship(rel)
        return self

    def register_event(self, metadata: EventMetadata) -> "OntologyRegistry":
        """
        注册事件元数据

        Args:
            metadata: 事件元数据对象

        Returns:
            self (for fluent API)
        """
        self._events[metadata.name] = metadata
        return self

    # Getters

    def get_entity(self, name: str) -> Optional[EntityMetadata]:
        """
        获取实体元数据

        Args:
            name: 实体名称

        Returns:
            EntityMetadata 对象，如果不存在则返回 None
        """
        return self._entities.get(name)

    def get_entities(self) -> List[EntityMetadata]:
        """
        获取所有实体元数据

        Returns:
            实体元数据列表
        """
        return list(self._entities.values())

    def get_actions(self, entity: str = None) -> List[ActionMetadata]:
        """
        获取动作元数据

        Args:
            entity: 实体名称，如果为 None 则返回所有动作

        Returns:
            动作元数据列表
        """
        if entity:
            return self._actions.get(entity, [])
        result = []
        for actions in self._actions.values():
            result.extend(actions)
        return result

    def get_state_machine(self, entity: str) -> Optional[StateMachine]:
        """
        获取状态机

        Args:
            entity: 实体名称

        Returns:
            StateMachine 对象，如果不存在则返回 None
        """
        return self._state_machines.get(entity)

    def get_business_rules(self, entity: str = None) -> List[BusinessRule]:
        """
        获取业务规则

        Args:
            entity: 实体名称，如果为 None 则返回所有规则

        Returns:
            业务规则列表
        """
        if entity:
            return self._business_rules.get(entity, [])
        result = []
        for rules in self._business_rules.values():
            result.extend(rules)
        return result

    def get_constraint(self, constraint_id: str) -> Optional[ConstraintMetadata]:
        """
        获取约束元数据

        Args:
            constraint_id: 约束ID

        Returns:
            ConstraintMetadata 对象，如果不存在则返回 None
        """
        return self._constraints.get(constraint_id)

    def get_constraints(self, entity: str = None) -> List[ConstraintMetadata]:
        """
        获取约束元数据

        Args:
            entity: 实体名称，如果为 None 则返回所有约束

        Returns:
            约束元数据列表
        """
        if entity:
            return [
                c for c in self._constraints.values()
                if c.entity == entity or c.entity == "*"
            ]
        return list(self._constraints.values())

    def get_constraints_for_entity_action(
        self,
        entity: str,
        action: str
    ) -> List[ConstraintMetadata]:
        """
        获取实体+操作的约束

        Args:
            entity: 实体名称
            action: 操作名称

        Returns:
            约束元数据列表
        """
        return [
            c for c in self._constraints.values()
            if (c.entity == entity or c.entity == "*") and
               (c.action == action or c.action == "" or c.action == "*")
        ]

    def get_constraints_by_severity(
        self,
        severity: ConstraintSeverity
    ) -> List[ConstraintMetadata]:
        """
        按严重程度获取约束

        Args:
            severity: 约束严重程度

        Returns:
            约束元数据列表
        """
        return [
            c for c in self._constraints.values()
            if c.severity == severity
        ]

    def get_permissions(self) -> Dict[str, Set[str]]:
        """
        获取权限矩阵

        Returns:
            动作类型到角色集合的映射
        """
        return self._permission_matrix.copy()

    def get_implementations(self, interface_name: str) -> List[str]:
        """
        获取实现指定接口的所有实体类型名称

        Args:
            interface_name: 接口名称

        Returns:
            实体类型名称列表
        """
        return list(self._interface_implementations.get(interface_name, []))

    def get_interface(self, name: str) -> Optional[Any]:
        """
        获取接口定义

        Args:
            name: 接口名称

        Returns:
            接口类，如果不存在则返回 None
        """
        return self._interfaces.get(name)

    def get_interfaces(self) -> Dict[str, Any]:
        """
        获取所有注册的接口

        Returns:
            接口名称到接口类的映射
        """
        return dict(self._interfaces)

    def get_model(self, entity_name: str) -> Optional[Any]:
        """
        获取 ORM 模型类

        Args:
            entity_name: 实体名称

        Returns:
            模型类，如果不存在则返回 None
        """
        return self._models.get(entity_name)

    def get_model_map(self) -> Dict[str, Any]:
        """
        获取实体名到 ORM 模型类的映射

        Returns:
            {entity_name: model_class}
        """
        return dict(self._models)

    def get_relationships(self, entity_name: str) -> List[RelationshipMetadata]:
        """
        获取实体的所有关系元数据

        Args:
            entity_name: 实体名称

        Returns:
            关系元数据列表
        """
        return list(self._relationships.get(entity_name, []))

    def get_event(self, name: str) -> Optional[EventMetadata]:
        """
        获取事件元数据

        Args:
            name: 事件名称

        Returns:
            EventMetadata 对象，如果不存在则返回 None
        """
        return self._events.get(name)

    def get_events(self, entity: str = None) -> List[EventMetadata]:
        """
        获取事件元数据

        Args:
            entity: 实体名称，如果为 None 则返回所有事件

        Returns:
            事件元数据列表
        """
        if entity:
            return [
                e for e in self._events.values()
                if e.entity == entity
            ]
        return list(self._events.values())

    def get_relationship_map(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        获取关系映射 - 兼容 query_engine.py 的 RELATIONSHIP_MAP 格式

        Returns:
            {source_entity: {target_entity: {"rel_attr": name, "foreign_key": fk}}}
        """
        result: Dict[str, Dict[str, Dict[str, str]]] = {}
        for entity_name, rels in self._relationships.items():
            if entity_name not in result:
                result[entity_name] = {}
            for rel in rels:
                result[entity_name][rel.target_entity] = {
                    "rel_attr": rel.name,
                    "foreign_key": rel.foreign_key,
                }
        return result

    # Schema Export

    def export_schema(self) -> Dict[str, Any]:
        """
        导出完整本体 schema - JSON 可序列化

        用于:
        - 版本快照
        - AI 上下文注入
        - API 文档生成

        Returns:
            完整 schema 字典
        """
        schema: Dict[str, Any] = {
            "entity_types": {},
            "interfaces": {},
            "actions": {},
            "state_machines": {},
            "relationships": {},
            "events": {},
        }

        # 导出实体类型
        for name, entity in self._entities.items():
            entity_schema = self._export_entity(name, entity)
            schema["entity_types"][name] = entity_schema

        # 导出接口
        for iface_name, iface_cls in self._interfaces.items():
            iface_schema: Dict[str, Any] = {
                "implementations": self.get_implementations(iface_name),
            }
            # 提取接口的 required_properties
            req_props = getattr(iface_cls, "required_properties", {})
            if req_props:
                iface_schema["required_properties"] = {
                    k: v.value if hasattr(v, "value") else str(v)
                    for k, v in req_props.items()
                }
            # 提取接口的 required_actions
            req_actions = getattr(iface_cls, "required_actions", [])
            if req_actions:
                iface_schema["required_actions"] = list(req_actions)

            # 提取描述
            if iface_cls.__doc__:
                iface_schema["description"] = iface_cls.__doc__.strip().split("\n")[0]

            schema["interfaces"][iface_name] = iface_schema

        # 导出动作（按实体分组已在 entity_types 中）
        for entity_name, actions in self._actions.items():
            for action in actions:
                action_key = f"{entity_name}.{action.action_type}"
                schema["actions"][action_key] = self._export_action(action)

        # 导出状态机
        for entity_name, sm in self._state_machines.items():
            schema["state_machines"][entity_name] = self._export_state_machine(sm)

        # 导出关系
        for entity_name, rels in self._relationships.items():
            schema["relationships"][entity_name] = [
                {
                    "name": rel.name,
                    "target_entity": rel.target_entity,
                    "cardinality": rel.cardinality,
                    "foreign_key": rel.foreign_key,
                    "foreign_key_entity": rel.foreign_key_entity,
                    "inverse_name": rel.inverse_name,
                }
                for rel in rels
            ]

        # 导出事件
        for event_name, event in self._events.items():
            schema["events"][event_name] = {
                "name": event.name,
                "description": event.description,
                "entity": event.entity,
                "triggered_by": event.triggered_by,
                "payload_fields": event.payload_fields,
                "subscribers": event.subscribers,
            }

        return schema

    def describe_type(self, entity_name: str) -> Dict[str, Any]:
        """
        返回单个实体的完整描述 - 用于 AI prompt 注入

        Args:
            entity_name: 实体名称

        Returns:
            实体描述字典，如果不存在返回空字典
        """
        entity = self._entities.get(entity_name)
        if not entity:
            return {}
        return self._export_entity(entity_name, entity)

    def _export_entity(self, name: str, entity: EntityMetadata) -> Dict[str, Any]:
        """导出单个实体 schema"""
        entity_schema: Dict[str, Any] = {
            "description": entity.description,
            "table_name": entity.table_name,
            "is_aggregate_root": entity.is_aggregate_root,
        }

        # 相关实体
        if entity.related_entities:
            entity_schema["related_entities"] = entity.related_entities

        # 属性（如果 EntityMetadata 有 properties 字段）
        properties = getattr(entity, "properties", None)
        if properties:
            entity_schema["properties"] = {}
            for prop in properties:
                if isinstance(prop, PropertyMetadata):
                    entity_schema["properties"][prop.name] = self._export_property(prop)

        # 接口
        interfaces = []
        for iface_name, impls in self._interface_implementations.items():
            if name in impls:
                interfaces.append(iface_name)
        if interfaces:
            entity_schema["interfaces"] = interfaces

        # 动作
        actions = self._actions.get(name, [])
        if actions:
            entity_schema["actions"] = [a.action_type for a in actions]

        # 状态机
        sm = self._state_machines.get(name)
        if sm:
            entity_schema["state_machine"] = self._export_state_machine(sm)

        return entity_schema

    def _export_property(self, prop: PropertyMetadata) -> Dict[str, Any]:
        """导出单个属性 schema"""
        result: Dict[str, Any] = {
            "type": prop.type,
        }
        if prop.is_primary_key:
            result["is_primary_key"] = True
        if prop.is_required:
            result["is_required"] = True
        if prop.is_foreign_key:
            result["is_foreign_key"] = True
            if prop.foreign_key_target:
                result["foreign_key_target"] = prop.foreign_key_target
        if prop.security_level and prop.security_level != "INTERNAL":
            result["security_level"] = prop.security_level
        if prop.enum_values:
            result["enum_values"] = prop.enum_values
        if prop.display_name:
            result["display_name"] = prop.display_name
        if prop.description:
            result["description"] = prop.description
        if prop.searchable:
            result["searchable"] = True
        if prop.indexed:
            result["indexed"] = True
        if prop.pii:
            result["pii"] = True
        if prop.phi:
            result["phi"] = True
        if prop.mask_strategy:
            result["mask_strategy"] = prop.mask_strategy
        return result

    def _export_action(self, action: ActionMetadata) -> Dict[str, Any]:
        """导出单个动作 schema"""
        result: Dict[str, Any] = {
            "action_type": action.action_type,
            "entity": action.entity,
            "description": action.description,
            "requires_confirmation": action.requires_confirmation,
        }
        if action.allowed_roles:
            result["allowed_roles"] = sorted(action.allowed_roles)
        if action.params:
            result["params"] = []
            for p in action.params:
                param_dict: Dict[str, Any] = {
                    "name": p.name if hasattr(p, "name") else p.get("name", ""),
                }
                if hasattr(p, "type"):
                    param_dict["type"] = p.type.value if hasattr(p.type, "value") else str(p.type)
                elif isinstance(p, dict):
                    param_dict["type"] = p.get("type", "string")
                if hasattr(p, "required"):
                    param_dict["required"] = p.required
                elif isinstance(p, dict):
                    param_dict["required"] = p.get("required", True)
                if hasattr(p, "description") and p.description:
                    param_dict["description"] = p.description
                elif isinstance(p, dict) and p.get("description"):
                    param_dict["description"] = p["description"]
                result["params"].append(param_dict)
        return result

    def _export_state_machine(self, sm: StateMachine) -> Dict[str, Any]:
        """导出状态机 schema"""
        result: Dict[str, Any] = {
            "states": sm.states,
            "initial_state": sm.initial_state,
        }
        if sm.transitions:
            result["transitions"] = []
            for t in sm.transitions:
                trans: Dict[str, Any] = {
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "trigger": t.trigger,
                }
                if t.condition:
                    trans["condition"] = t.condition
                if t.side_effects:
                    trans["side_effects"] = t.side_effects
                result["transitions"].append(trans)
        return result

    def clear(self) -> None:
        """
        清空注册表（主要用于测试）

        Warning:
            此方法会清空所有已注册的元数据，仅应在测试环境中使用。
        """
        self._entities.clear()
        self._actions.clear()
        self._state_machines.clear()
        self._business_rules.clear()
        self._constraints.clear()  # Framework enhancement
        self._permission_matrix.clear()
        self._interface_implementations.clear()
        self._interfaces.clear()
        self._models.clear()
        self._relationships.clear()
        self._events.clear()

    def to_llm_knowledge_base(self) -> str:
        """
        生成完整的 LLM 知识库

        Returns:
            包含实体、操作、约束、状态机描述的文本
        """
        sections = []

        # 实体
        sections.append("# 实体 (Entities)\n")
        for entity in self._entities.values():
            if hasattr(entity, 'to_llm_summary'):
                sections.append(entity.to_llm_summary())
            else:
                sections.append(f"## {entity.name}\n{entity.description}")
            sections.append("")

        # 操作
        sections.append("\n# 操作 (Actions)\n")
        for entity_actions in self._actions.values():
            for action in entity_actions:
                if hasattr(action, 'to_llm_summary'):
                    sections.append(action.to_llm_summary())
                else:
                    sections.append(f"### {action.action_type}\n{action.description}")
                sections.append("")

        # 约束
        if self._constraints:
            sections.append("\n# 约束 (Constraints)\n")
            for constraint in self._constraints.values():
                if hasattr(constraint, 'to_llm_summary'):
                    sections.append(constraint.to_llm_summary())
                else:
                    sections.append(f"- {constraint.name}: {constraint.description}")
                sections.append("")

        # 业务规则
        if self._business_rules:
            sections.append("\n# 业务规则 (Business Rules)\n")
            for entity_rules in self._business_rules.values():
                for rule in entity_rules:
                    if hasattr(rule, 'to_llm_summary'):
                        sections.append(rule.to_llm_summary())
                    else:
                        sections.append(f"- {rule.rule_name}: {rule.description}")
                    sections.append("")

        # 状态机
        sections.append("\n# 状态机 (State Machines)\n")
        for sm in self._state_machines.values():
            if hasattr(sm, 'to_llm_summary'):
                sections.append(sm.to_llm_summary())
            else:
                sections.append(f"### {sm.entity}\nStates: {', '.join(sm.states)}")
            sections.append("")

        return "\n".join(sections)

    # ============== Searchable 关键字查询方法 ==============

    def find_entities_by_keywords(self, message: str) -> List[str]:
        """
        根据消息中的关键字查找匹配的实体

        Args:
            message: 用户输入的消息

        Returns:
            匹配的实体名称列表（可能有多个，需要 LLM 消歧）
        """
        from core.ontology.metadata import get_searchable_mapping

        keyword_mapping = get_searchable_mapping()
        matched_entities: Set[str] = set()

        # 检查所有注册的关键字
        for keyword, targets in keyword_mapping.items():
            if keyword in message:
                for target_type, target_name in targets:
                    if target_type == 'entity':
                        matched_entities.add(target_name)

        return sorted(list(matched_entities))

    def find_properties_by_keywords(self, message: str) -> List[str]:
        """
        根据消息中的关键字查找匹配的属性

        Args:
            message: 用户输入的消息

        Returns:
            匹配的属性路径列表 (如 ['Room.status', 'Task.status'])
        """
        from core.ontology.metadata import get_searchable_mapping

        keyword_mapping = get_searchable_mapping()
        matched_properties: Set[str] = set()

        for keyword, targets in keyword_mapping.items():
            if keyword in message:
                for target_type, target_name in targets:
                    if target_type == 'property':
                        matched_properties.add(target_name)

        return sorted(list(matched_properties))

    def resolve_keyword_matches(
        self,
        message: str
    ) -> Dict[str, List[str]]:
        """
        解析消息中的关键字，返回匹配的实体和属性

        Args:
            message: 用户输入的消息

        Returns:
            {
                'entities': ['Room', 'Task'],
                'properties': ['Room.status', 'Task.task_type']
            }
        """
        return {
            'entities': self.find_entities_by_keywords(message),
            'properties': self.find_properties_by_keywords(message)
        }

    def export_query_schema(self) -> Dict[str, Any]:
        """
        导出查询专用的 Schema - 为 LLM 提供精确的实体/属性/关系定义

        这个方法生成的 Schema 包含：
        1. 每个实体的精确字段名（包括关联字段）
        2. 字段类型、是否可过滤、是否可聚合
        3. 关系路径（如 guest.name）
        4. 推荐的聚合方式

        Returns:
            {
                "entities": {
                    "StayRecord": {
                        "description": "入住记录",
                        "table": "stay_records",
                        "fields": {
                            "id": {"type": "integer", "filterable": true, "aggregatable": true},
                            "check_in_time": {"type": "datetime", "filterable": true, "description": "入住时间"},
                            "guest_id": {"type": "integer", "filterable": true},
                            "guest.name": {"type": "string", "path": "guest.name", "relationship": "Guest"}
                        },
                        "relationships": {
                            "guest": {"entity": "Guest", "type": "many_to_one", "fields": ["name", "phone"]}
                        }
                    }
                },
                "aggregate_functions": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
                "filter_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "between"]
            }
        """
        schema: Dict[str, Any] = {
            "entities": {},
            "aggregate_functions": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
            "filter_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "between"]
        }

        # 从 registry 模型动态提取字段信息
        try:
            entity_models = self._models
            if not entity_models:
                return schema

            # 从 registry 关系构建关系映射
            relationship_map: Dict[str, Dict] = {}
            for entity_name, rels in self._relationships.items():
                rel_dict: Dict[str, Any] = {}
                for rel in rels:
                    rel_dict[rel.name] = {
                        "entity": rel.target_entity,
                        "type": rel.cardinality,
                        "foreign_key": rel.foreign_key,
                    }
                if rel_dict:
                    relationship_map[entity_name] = rel_dict

            # 为每个实体生成详细的字段信息
            for entity_name, model_class in entity_models.items():
                entity_info: Dict[str, Any] = {
                    "fields": {},
                    "relationships": {}
                }

                # 获取表名
                entity_info["table"] = model_class.__tablename__

                # 从实体元数据获取描述
                entity_metadata = self._entities.get(entity_name)
                if entity_metadata:
                    entity_info["description"] = entity_metadata.description

                # 获取关系
                relationships = relationship_map.get(entity_name, {})
                for rel_name, rel_info in relationships.items():
                    entity_info["relationships"][rel_name] = rel_info

                # 遍历模型的所有列
                for column in model_class.__table__.columns:
                    field_name = column.name
                    field_info: Dict[str, Any] = {
                        "type": str(column.type.python_type.__name__ if hasattr(column.type.python_type, '__name__') else str(column.type.python_type)),
                        "nullable": column.nullable,
                        "primary_key": column.primary_key
                    }

                    # 判断字段是否可过滤（基本类型都可以）
                    field_info["filterable"] = field_name not in ["id", "created_at", "updated_at"]

                    # 判断字段是否可聚合（数值类型）
                    python_type = column.type.python_type if hasattr(column.type, 'python_type') else None
                    field_info["aggregatable"] = python_type in (int, float) if python_type else False

                    entity_info["fields"][field_name] = field_info

                # 添加关系字段（如 guest.name）
                for rel_name, rel_info in relationships.items():
                    target_entity = rel_info["entity"]
                    if target_entity in entity_models:
                        target_model = entity_models[target_entity]
                        # 添加目标实体的关键字段
                        for col in target_model.__table__.columns[:3]:  # 只取前3个字段
                            if col.name in ["name", "phone", "room_number", "status"]:
                                rel_field_name = f"{rel_name}.{col.name}"
                                entity_info["fields"][rel_field_name] = {
                                    "type": "relationship",
                                    "path": rel_field_name,
                                    "relationship": rel_name,
                                    "target_entity": target_entity,
                                    "target_field": col.name,
                                    "filterable": True
                                }

                schema["entities"][entity_name] = entity_info

        except Exception as e:
            # 如果动态提取失败，回退到基本信息
            import logging
            logging.warning(f"Failed to extract schema from ORM: {e}")

        return schema


# 全局注册中心实例
registry = OntologyRegistry()


# 导出
__all__ = ["OntologyRegistry", "registry"]
