"""
测试 core.domain.relationships 模块 - 本体间关系单元测试
"""
import pytest

from core.domain.relationships import (
    LinkType,
    Cardinality,
    EntityLink,
    RelationshipRegistry,
    relationship_registry,
)
from app.hotel.domain.relationships import (
    ROOM_RELATIONSHIPS,
    GUEST_RELATIONSHIPS,
    RESERVATION_RELATIONSHIPS,
    STAY_RECORD_RELATIONSHIPS,
    BILL_RELATIONSHIPS,
    TASK_RELATIONSHIPS,
    EMPLOYEE_RELATIONSHIPS,
    register_hotel_relationships,
)


@pytest.fixture(autouse=True)
def _setup_relationships():
    """Ensure hotel relationships are registered for tests"""
    RelationshipRegistry.clear()
    register_hotel_relationships(relationship_registry)
    yield
    RelationshipRegistry.clear()


class TestLinkType:
    def test_link_type_values(self):
        """测试链接类型值"""
        assert LinkType.ONE_TO_ONE == "one_to_one"
        assert LinkType.ONE_TO_MANY == "one_to_many"
        assert LinkType.MANY_TO_ONE == "many_to_one"
        assert LinkType.MANY_TO_MANY == "many_to_many"
        assert LinkType.AGGREGATION == "aggregation"
        assert LinkType.COMPOSITION == "composition"


class TestCardinality:
    def test_cardinality_values(self):
        """测试基数值"""
        assert Cardinality.ONE == "1"
        assert Cardinality.MANY == "*"
        assert Cardinality.OPTIONAL == "0..1"
        assert Cardinality.OPTIONAL_MANY == "0..*"


class TestEntityLink:
    def test_creation(self):
        """测试创建关系"""
        link = EntityLink(
            source_entity="Room",
            target_entity="Guest",
            link_type=LinkType.MANY_TO_MANY,
            source_cardinality=Cardinality.MANY,
            target_cardinality=Cardinality.MANY,
            description="房间和客人关系",
        )

        assert link.source_entity == "Room"
        assert link.target_entity == "Guest"
        assert link.link_type == LinkType.MANY_TO_MANY
        assert link.bidirectional is False


class TestRoomRelationships:
    def test_room_to_room_type(self):
        """测试房间到房型的关系"""
        room_type_links = [r for r in ROOM_RELATIONSHIPS if r.target_entity == "RoomType"]
        assert len(room_type_links) == 1
        assert room_type_links[0].link_type == LinkType.MANY_TO_ONE

    def test_room_to_stay_record(self):
        """测试房间到住宿记录的关系"""
        stay_links = [r for r in ROOM_RELATIONSHIPS if r.target_entity == "StayRecord"]
        assert len(stay_links) == 1
        assert stay_links[0].link_type == LinkType.ONE_TO_MANY
        assert stay_links[0].bidirectional is True

    def test_room_to_task(self):
        """测试房间到任务的关系"""
        task_links = [r for r in ROOM_RELATIONSHIPS if r.target_entity == "Task"]
        assert len(task_links) == 1
        assert task_links[0].link_type == LinkType.ONE_TO_MANY


class TestGuestRelationships:
    def test_guest_to_reservation(self):
        """测试客人到预订的关系"""
        reservation_links = [r for r in GUEST_RELATIONSHIPS if r.target_entity == "Reservation"]
        assert len(reservation_links) == 1
        assert reservation_links[0].link_type == LinkType.ONE_TO_MANY

    def test_guest_to_stay_record(self):
        """测试客人到住宿记录的关系"""
        stay_links = [r for r in GUEST_RELATIONSHIPS if r.target_entity == "StayRecord"]
        assert len(stay_links) == 1
        assert stay_links[0].link_type == LinkType.ONE_TO_MANY


class TestReservationRelationships:
    def test_reservation_to_guest(self):
        """测试预订到客人的关系"""
        guest_links = [r for r in RESERVATION_RELATIONSHIPS if r.target_entity == "Guest"]
        assert len(guest_links) == 1
        assert guest_links[0].link_type == LinkType.MANY_TO_ONE

    def test_reservation_to_room_type(self):
        """测试预订到房型的关系"""
        room_type_links = [r for r in RESERVATION_RELATIONSHIPS if r.target_entity == "RoomType"]
        assert len(room_type_links) == 1


class TestStayRecordRelationships:
    def test_stay_record_to_bill(self):
        """测试住宿记录到账单的关系"""
        bill_links = [r for r in STAY_RECORD_RELATIONSHIPS if r.target_entity == "Bill"]
        assert len(bill_links) == 1
        assert bill_links[0].link_type == LinkType.ONE_TO_ONE
        assert bill_links[0].bidirectional is True


class TestTaskRelationships:
    def test_task_to_room(self):
        """测试任务到房间的关系"""
        room_links = [r for r in TASK_RELATIONSHIPS if r.target_entity == "Room"]
        assert len(room_links) == 1
        assert room_links[0].link_type == LinkType.MANY_TO_ONE


class TestEmployeeRelationships:
    def test_employee_to_task(self):
        """测试员工到任务的关系"""
        task_links = [r for r in EMPLOYEE_RELATIONSHIPS if r.target_entity == "Task"]
        assert len(task_links) == 1
        assert task_links[0].link_type == LinkType.ONE_TO_MANY


class TestRelationshipRegistry:
    def test_get_relationships_for_known_entity(self):
        """测试获取已知实体的关系"""
        relationships = relationship_registry.get_relationships("Room")

        assert len(relationships) >= 2
        assert any(r.target_entity == "RoomType" for r in relationships)
        assert any(r.target_entity == "StayRecord" for r in relationships)

    def test_get_relationships_for_unknown_entity(self):
        """测试获取未知实体的关系"""
        relationships = relationship_registry.get_relationships("UnknownEntity")

        assert relationships == []

    def test_get_linked_entities(self):
        """测试获取关联实体"""
        linked = relationship_registry.get_linked_entities("Room")

        assert "RoomType" in linked
        assert "StayRecord" in linked
        assert "Task" in linked

    def test_register_relationship(self):
        """测试注册新关系"""
        new_link = EntityLink(
            source_entity="TestEntity",
            target_entity="AnotherEntity",
            link_type=LinkType.ONE_TO_MANY,
            source_cardinality=Cardinality.ONE,
            target_cardinality=Cardinality.MANY,
            description="测试关系",
        )

        relationship_registry.register_relationship("TestEntity", new_link)

        relationships = relationship_registry.get_relationships("TestEntity")
        assert len(relationships) == 1
        assert relationships[0].target_entity == "AnotherEntity"
