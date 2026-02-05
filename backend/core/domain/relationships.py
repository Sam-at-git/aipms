"""
core/domain/relationships.py

本体间关系定义 - 定义实体间的链接和关联规则
"""
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

if TYPE_CHECKING:
    from core.domain.room import RoomEntity
    from core.domain.guest import GuestEntity


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


# ============== 预定义关系 ==============

# Room 相关关系
ROOM_RELATIONSHIPS = [
    EntityLink(
        source_entity="Room",
        target_entity="RoomType",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="房间属于房型",
    ),
    EntityLink(
        source_entity="Room",
        target_entity="StayRecord",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="房间有多个住宿记录",
        bidirectional=True,
    ),
    EntityLink(
        source_entity="Room",
        target_entity="Task",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="房间有多个任务",
        bidirectional=True,
    ),
]

# Guest 相关关系
GUEST_RELATIONSHIPS = [
    EntityLink(
        source_entity="Guest",
        target_entity="Reservation",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="客人有多个预订",
        bidirectional=True,
    ),
    EntityLink(
        source_entity="Guest",
        target_entity="StayRecord",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="客人有多个住宿记录",
        bidirectional=True,
    ),
]

# Reservation 相关关系
RESERVATION_RELATIONSHIPS = [
    EntityLink(
        source_entity="Reservation",
        target_entity="Guest",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="预订属于客人",
    ),
    EntityLink(
        source_entity="Reservation",
        target_entity="RoomType",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="预订房型",
    ),
    EntityLink(
        source_entity="Reservation",
        target_entity="StayRecord",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="预订转为住宿记录",
    ),
]

# StayRecord 相关关系
STAY_RECORD_RELATIONSHIPS = [
    EntityLink(
        source_entity="StayRecord",
        target_entity="Guest",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="住宿记录属于客人",
    ),
    EntityLink(
        source_entity="StayRecord",
        target_entity="Room",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="住宿记录使用房间",
    ),
    EntityLink(
        source_entity="StayRecord",
        target_entity="Reservation",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.OPTIONAL_MANY,
        target_cardinality=Cardinality.ONE,
        description="住宿记录来自预订",
    ),
    EntityLink(
        source_entity="StayRecord",
        target_entity="Bill",
        link_type=LinkType.ONE_TO_ONE,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.OPTIONAL,
        description="住宿记录对应账单",
        bidirectional=True,
    ),
]

# Bill 相关关系
BILL_RELATIONSHIPS = [
    EntityLink(
        source_entity="Bill",
        target_entity="StayRecord",
        link_type=LinkType.ONE_TO_ONE,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.ONE,
        description="账单属于住宿记录",
    ),
    EntityLink(
        source_entity="Bill",
        target_entity="Payment",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="账单有多个支付",
    ),
]

# Task 相关关系
TASK_RELATIONSHIPS = [
    EntityLink(
        source_entity="Task",
        target_entity="Room",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.MANY,
        target_cardinality=Cardinality.ONE,
        description="任务关联房间",
    ),
    EntityLink(
        source_entity="Task",
        target_entity="Employee",
        link_type=LinkType.MANY_TO_ONE,
        source_cardinality=Cardinality.OPTIONAL_MANY,
        target_cardinality=Cardinality.ONE,
        description="任务分配给员工",
    ),
]

# Employee 相关关系
EMPLOYEE_RELATIONSHIPS = [
    EntityLink(
        source_entity="Employee",
        target_entity="Task",
        link_type=LinkType.ONE_TO_MANY,
        source_cardinality=Cardinality.ONE,
        target_cardinality=Cardinality.MANY,
        description="员工负责多个任务",
    ),
]


# ============== 关系注册表 ==============

class RelationshipRegistry:
    """
    关系注册表 - 管理所有实体间的关系
    """

    _relationships: dict[str, List[EntityLink]] = {
        "Room": ROOM_RELATIONSHIPS,
        "Guest": GUEST_RELATIONSHIPS,
        "Reservation": RESERVATION_RELATIONSHIPS,
        "StayRecord": STAY_RECORD_RELATIONSHIPS,
        "Bill": BILL_RELATIONSHIPS,
        "Task": TASK_RELATIONSHIPS,
        "Employee": EMPLOYEE_RELATIONSHIPS,
    }

    @classmethod
    def get_relationships(cls, entity_name: str) -> List[EntityLink]:
        """
        获取实体的所有关系

        Args:
            entity_name: 实体名称

        Returns:
            关系列表
        """
        return cls._relationships.get(entity_name, [])

    @classmethod
    def get_linked_entities(
        cls, entity_name: str
    ) -> List[str]:
        """
        获取与实体关联的所有实体名称

        Args:
            entity_name: 实体名称

        Returns:
            关联实体名称列表
        """
        links = cls.get_relationships(entity_name)
        linked = set()
        for link in links:
            linked.add(link.target_entity)
        return list(linked)

    @classmethod
    def register_relationship(cls, entity_name: str, link: EntityLink) -> None:
        """
        注册新的关系

        Args:
            entity_name: 源实体名称
            link: 关系定义
        """
        if entity_name not in cls._relationships:
            cls._relationships[entity_name] = []
        cls._relationships[entity_name].append(link)


# 全局关系注册表实例
relationship_registry = RelationshipRegistry()


# 导出
__all__ = [
    "LinkType",
    "Cardinality",
    "EntityLink",
    "ROOM_RELATIONSHIPS",
    "GUEST_RELATIONSHIPS",
    "RESERVATION_RELATIONSHIPS",
    "STAY_RECORD_RELATIONSHIPS",
    "BILL_RELATIONSHIPS",
    "TASK_RELATIONSHIPS",
    "EMPLOYEE_RELATIONSHIPS",
    "RelationshipRegistry",
    "relationship_registry",
]
