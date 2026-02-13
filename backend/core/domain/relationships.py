"""
core/domain/relationships.py

通用关系类型定义 - 领域无关
酒店特定关系常量在 app.hotel.domain.relationships 中
"""
from typing import List
from dataclasses import dataclass
from enum import Enum


class LinkType(str, Enum):
    """链接类型"""
    ONE_TO_ONE = "one_to_one"           # 一对一
    ONE_TO_MANY = "one_to_many"         # 一对多
    MANY_TO_ONE = "many_to_one"         # 多对一
    MANY_TO_MANY = "many_to_many"       # 多对多
    AGGREGATION = "aggregation"         # 聚合关系
    COMPOSITION = "composition"         # 组合关系


class Cardinality(str, Enum):
    """基数"""
    ONE = "1"
    MANY = "*"
    OPTIONAL = "0..1"
    OPTIONAL_MANY = "0..*"


@dataclass
class EntityLink:
    """
    实体间链接定义

    Attributes:
        source_entity: 源实体名称
        target_entity: 目标实体名称
        link_type: 链接类型
        source_cardinality: 源实体基数
        target_cardinality: 目标实体基数
        description: 关系描述
        bidirectional: 是否双向
    """

    source_entity: str
    target_entity: str
    link_type: LinkType
    source_cardinality: Cardinality
    target_cardinality: Cardinality
    description: str
    bidirectional: bool = False


class RelationshipRegistry:
    """
    关系注册表 - 管理所有实体间的关系
    """

    _relationships: dict[str, List[EntityLink]] = {}

    @classmethod
    def get_relationships(cls, entity_name: str) -> List[EntityLink]:
        return cls._relationships.get(entity_name, [])

    @classmethod
    def get_linked_entities(cls, entity_name: str) -> List[str]:
        links = cls.get_relationships(entity_name)
        linked = set()
        for link in links:
            linked.add(link.target_entity)
        return list(linked)

    @classmethod
    def register_relationship(cls, entity_name: str, link: EntityLink) -> None:
        if entity_name not in cls._relationships:
            cls._relationships[entity_name] = []
        cls._relationships[entity_name].append(link)

    @classmethod
    def register_relationships(cls, entity_name: str, links: List[EntityLink]) -> None:
        """Batch register relationships for an entity"""
        for link in links:
            cls.register_relationship(entity_name, link)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered relationships (for testing)"""
        cls._relationships = {}


# 全局关系注册表实例
relationship_registry = RelationshipRegistry()


# 导出
__all__ = [
    "LinkType",
    "Cardinality",
    "EntityLink",
    "RelationshipRegistry",
    "relationship_registry",
]
