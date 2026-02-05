"""
core/ontology/registry.py

本体注册中心 - 运行时元数据管理
提供实体、动作、状态机、业务规则的注册和检索功能
"""
from typing import Dict, List, Set, Optional

from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    StateMachine,
    BusinessRule,
)


class OntologyRegistry:
    """
    本体注册中心 - 单例模式

    提供元数据的注册和检索功能：
    - 实体元数据
    - 动作元数据
    - 状态机定义
    - 业务规则
    - 权限矩阵

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
            cls._instance._permission_matrix: Dict[str, Set[str]] = {}
        return cls._instance

    def register_entity(self, metadata: EntityMetadata) -> None:
        """
        注册实体元数据

        Args:
            metadata: 实体元数据对象
        """
        self._entities[metadata.name] = metadata

    def register_action(self, entity: str, metadata: ActionMetadata) -> None:
        """
        注册动作元数据

        Args:
            entity: 实体名称
            metadata: 动作元数据对象
        """
        if entity not in self._actions:
            self._actions[entity] = []
        self._actions[entity].append(metadata)

    def register_state_machine(self, metadata: StateMachine) -> None:
        """
        注册状态机

        Args:
            metadata: 状态机对象
        """
        self._state_machines[metadata.entity] = metadata

    def register_business_rule(self, entity: str, rule: BusinessRule) -> None:
        """
        注册业务规则

        Args:
            entity: 实体名称
            rule: 业务规则对象
        """
        if entity not in self._business_rules:
            self._business_rules[entity] = []
        self._business_rules[entity].append(rule)

    def register_permission(self, action_type: str, roles: Set[str]) -> None:
        """
        注册权限

        Args:
            action_type: 动作类型
            roles: 允许执行该动作的角色集合
        """
        if action_type not in self._permission_matrix:
            self._permission_matrix[action_type] = set()
        self._permission_matrix[action_type].update(roles)

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

    def get_permissions(self) -> Dict[str, Set[str]]:
        """
        获取权限矩阵

        Returns:
            动作类型到角色集合的映射
        """
        return self._permission_matrix.copy()

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
        self._permission_matrix.clear()


# 全局注册中心实例
registry = OntologyRegistry()


# 导出
__all__ = ["OntologyRegistry", "registry"]
