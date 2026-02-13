"""
app/hotel/domain/relationships.py

酒店领域关系常量定义
"""
from core.domain.relationships import (
    LinkType,
    Cardinality,
    EntityLink,
    RelationshipRegistry,
)


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


def register_hotel_relationships(registry: RelationshipRegistry = None) -> None:
    """Register all hotel domain relationships into the registry"""
    if registry is None:
        from core.domain.relationships import relationship_registry
        registry = relationship_registry

    registry.register_relationships("Room", ROOM_RELATIONSHIPS)
    registry.register_relationships("Guest", GUEST_RELATIONSHIPS)
    registry.register_relationships("Reservation", RESERVATION_RELATIONSHIPS)
    registry.register_relationships("StayRecord", STAY_RECORD_RELATIONSHIPS)
    registry.register_relationships("Bill", BILL_RELATIONSHIPS)
    registry.register_relationships("Task", TASK_RELATIONSHIPS)
    registry.register_relationships("Employee", EMPLOYEE_RELATIONSHIPS)


__all__ = [
    "ROOM_RELATIONSHIPS",
    "GUEST_RELATIONSHIPS",
    "RESERVATION_RELATIONSHIPS",
    "STAY_RECORD_RELATIONSHIPS",
    "BILL_RELATIONSHIPS",
    "TASK_RELATIONSHIPS",
    "EMPLOYEE_RELATIONSHIPS",
    "register_hotel_relationships",
]
