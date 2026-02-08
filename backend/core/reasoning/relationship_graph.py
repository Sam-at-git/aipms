"""
core/reasoning/relationship_graph.py

Relationship graph engine - Navigates entity relationships
Part of the universal ontology-driven LLM reasoning framework
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, TYPE_CHECKING, Tuple
from enum import Enum
from collections import deque

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry

from core.ontology.metadata import EntityMetadata, PropertyMetadata


class RelationType(Enum):
    """关系类型"""
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"
    REFERENCE = "reference"
    COMPOSITION = "composition"
    AGGREGATION = "aggregation"


@dataclass
class RelationshipEdge:
    """关系边"""
    source: str  # 源实体名称
    target: str  # 目标实体名称
    relation_type: RelationType
    property_name: Optional[str] = None  # 产生此关系的属性名
    description: str = ""

    def __str__(self) -> str:
        if self.property_name:
            return f"{self.source} --[{self.property_name}]--> {self.target}"
        return f"{self.source} --> {self.target}"


@dataclass
class EntityNode:
    """实体节点"""
    name: str
    description: str
    is_aggregate_root: bool = False
    relationships: List[RelationshipEdge] = field(default_factory=list)


class RelationshipGraph:
    """
    关系图引擎 - 领域无关

    从本体注册表构建实体关系图，提供关系查询和遍历功能。
    """

    def __init__(self, registry: "OntologyRegistry"):
        """
        初始化关系图

        Args:
            registry: 本体注册表实例
        """
        self.registry = registry
        self._nodes: Dict[str, EntityNode] = {}
        self._adjacency: Dict[str, List[RelationshipEdge]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        """从注册表构建关系图"""
        # 清空现有数据
        self._nodes.clear()
        self._adjacency.clear()

        # 首先创建所有节点
        for entity in self.registry.get_entities():
            self._nodes[entity.name] = EntityNode(
                name=entity.name,
                description=entity.description,
                is_aggregate_root=entity.is_aggregate_root
            )
            self._adjacency[entity.name] = []

        # 然后添加关系边
        for entity in self.registry.get_entities():
            # 从 related_entities 字段添加关系 (向后兼容)
            for related in entity.related_entities:
                self._add_edge(entity.name, related, RelationType.REFERENCE)

            # 从 properties 中的 relationship_target 添加关系
            for prop in entity.properties.values():
                if hasattr(prop, 'relationship_target') and prop.relationship_target:
                    rel_type = self._parse_relation_type(prop.relationship_cardinality)
                    self._add_edge(
                        entity.name,
                        prop.relationship_target,
                        rel_type,
                        prop.name
                    )

            # 从 get_relationships() 方法添加关系
            if hasattr(entity, 'get_relationships'):
                for prop_name, target, cardinality in entity.get_relationships():
                    rel_type = self._parse_relation_type(cardinality)
                    self._add_edge(entity.name, target, rel_type, prop_name)

    def _parse_relation_type(self, cardinality: Optional[str]) -> RelationType:
        """解析基数字符串为 RelationType"""
        if not cardinality:
            return RelationType.REFERENCE

        cardinality = cardinality.lower().replace("-", "_")
        try:
            return RelationType(cardinality)
        except ValueError:
            return RelationType.REFERENCE

    def _add_edge(
        self,
        source: str,
        target: str,
        relation_type: RelationType,
        property_name: Optional[str] = None
    ) -> None:
        """添加关系边"""
        edge = RelationshipEdge(
            source=source,
            target=target,
            relation_type=relation_type,
            property_name=property_name
        )
        self._adjacency[source].append(edge)
        if source in self._nodes:
            self._nodes[source].relationships.append(edge)

    def get_related_nodes(
        self,
        entity_name: str,
        relation_type: Optional[RelationType] = None,
        max_depth: int = 1
    ) -> List[EntityNode]:
        """
        获取相关实体节点 (BFS 遍历)

        Args:
            entity_name: 起始实体名称
            relation_type: 关系类型过滤 (None 表示所有类型)
            max_depth: 最大遍历深度

        Returns:
            相关实体节点列表
        """
        if entity_name not in self._adjacency:
            return []

        visited: Set[str] = {entity_name}
        result: List[EntityNode] = []
        queue: deque[Tuple[str, int]] = deque([(entity_name, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in self._adjacency.get(current, []):
                if relation_type is not None and edge.relation_type != relation_type:
                    continue
                if edge.target not in visited:
                    visited.add(edge.target)
                    if edge.target in self._nodes:
                        result.append(self._nodes[edge.target])
                    queue.append((edge.target, depth + 1))

        return result

    def find_path(
        self,
        from_entity: str,
        to_entity: str
    ) -> Optional[List[str]]:
        """
        查找两个实体之间的最短路径

        Args:
            from_entity: 起始实体
            to_entity: 目标实体

        Returns:
            路径实体名称列表，如果不存在路径则返回 None
        """
        if from_entity not in self._adjacency or to_entity not in self._adjacency:
            return None

        if from_entity == to_entity:
            return [from_entity]

        # BFS 查找最短路径
        visited: Set[str] = {from_entity}
        parent: Dict[str, Optional[str]] = {from_entity: None}
        queue: deque[str] = deque([from_entity])

        while queue:
            current = queue.popleft()
            if current == to_entity:
                # 重建路径
                path: List[str] = []
                while current is not None:
                    path.append(current)
                    current = parent.get(current)
                return list(reversed(path))

            for edge in self._adjacency.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    parent[edge.target] = current
                    queue.append(edge.target)

        return None

    def get_relationships_for_llm(
        self,
        entity_name: str,
        max_depth: int = 1
    ) -> str:
        """
        获取关系的 LLM 描述

        Args:
            entity_name: 实体名称
            max_depth: 最大深度

        Returns:
            LLM 友好的关系描述文本
        """
        if entity_name not in self._nodes:
            return f"实体 {entity_name} 不存在"

        sections = []
        node = self._nodes[entity_name]

        sections.append(f"## {node.name} 的关系")
        sections.append(node.description)

        if node.relationships:
            sections.append("\n**直接关系:**")
            for edge in node.relationships:
                target_node = self._nodes.get(edge.target)
                target_desc = target_node.description if target_node else ""
                rel_desc = f" {edge.description}" if edge.description else ""
                sections.append(f"- {edge.target}: {target_desc}{rel_desc}")

        # 深度遍历
        if max_depth > 1:
            related = self.get_related_nodes(entity_name, max_depth=max_depth)
            if related:
                sections.append(f"\n**相关实体 (深度 {max_depth}):**")
                for r in related:
                    if r.name != entity_name:
                        sections.append(f"- {r.name}: {r.description}")

        return "\n".join(sections)

    def get_all_paths(
        self,
        from_entity: str,
        to_entity: str,
        max_length: int = 5
    ) -> List[List[str]]:
        """
        获取两个实体之间的所有路径 (DFS)

        Args:
            from_entity: 起始实体
            to_entity: 目标实体
            max_length: 最大路径长度

        Returns:
            路径列表
        """
        if from_entity not in self._adjacency or to_entity not in self._adjacency:
            return []

        result: List[List[str]] = []
        current_path: List[str] = []
        visited: Set[str] = set()

        def _dfs(current: str) -> None:
            if len(current_path) > max_length:
                return
            if current == to_entity:
                result.append(list(current_path))
                return
            for edge in self._adjacency.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    current_path.append(edge.target)
                    _dfs(edge.target)
                    current_path.pop()
                    visited.remove(edge.target)

        visited.add(from_entity)
        current_path.append(from_entity)
        _dfs(from_entity)

        return result


# Export
__all__ = [
    "RelationType",
    "RelationshipEdge",
    "EntityNode",
    "RelationshipGraph",
]
