"""
服务迁移测试 - 验证新服务适配器与现有 API 的兼容性

这些测试确保新的服务层（使用领域实体）与现有系统兼容。
"""
import pytest
from datetime import date, datetime

from app.services.room_service_v2 import RoomServiceV2, get_room_service_v2
from app.services.guest_service_v2 import GuestServiceV2, get_guest_service_v2
from app.hotel.domain.room import RoomState
from app.hotel.domain.guest import GuestTier as DomainGuestTier
from app.models.ontology import Room, RoomStatus, Guest, RoomType, StayRecord


class TestRoomServiceV2:
    """测试 RoomServiceV2 兼容性"""

    def test_get_room_types(self, db_session):
        service = get_room_service_v2(db_session)
        room_types = service.get_room_types()
        assert isinstance(room_types, list)

    def test_create_and_get_room_type(self, db_session):
        service = get_room_service_v2(db_session)
        from app.models.schemas import RoomTypeCreate

        data = RoomTypeCreate(name="Test Type", base_price=100.00, max_occupancy=2)
        room_type = service.create_room_type(data)
        assert room_type.name == "Test Type"

        retrieved = service.get_room_type(room_type.id)
        assert retrieved is not None
        assert retrieved.name == "Test Type"

    def test_create_room(self, db_session):
        service = get_room_service_v2(db_session)
        from app.models.schemas import RoomCreate

        # First create a room type
        rt = RoomType(name="Standard", base_price=100.00, max_occupancy=2)
        db_session.add(rt)
        db_session.commit()

        data = RoomCreate(room_number="999", floor=9, room_type_id=rt.id)
        room = service.create_room(data)
        assert room.room_number == "999"

    def test_get_room_entity(self, db_session):
        service = get_room_service_v2(db_session)
        entity = service.get_room_entity(1)
        if entity:
            assert entity.id == 1
            assert hasattr(entity, 'room_number')

    def test_update_room_status_with_entity(self, db_session):
        service = get_room_service_v2(db_session)

        # Create a test room
        rt = RoomType(name="Test", base_price=100.00, max_occupancy=2)
        db_session.add(rt)
        db_session.commit()

        room = Room(room_number="998", floor=9, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
        db_session.add(room)
        db_session.commit()

        # Update status using entity method
        updated = service.update_room_status(room.id, RoomStatus.OCCUPIED)
        assert updated.status == RoomStatus.OCCUPIED

    def test_get_room_status_summary(self, db_session):
        service = get_room_service_v2(db_session)
        summary = service.get_room_status_summary()
        assert 'total' in summary
        assert 'vacant_clean' in summary
        assert 'occupied' in summary

    def test_get_room_relationships(self, db_session):
        service = get_room_service_v2(db_session)
        relationships = service.get_room_relationships(1)
        if relationships:
            assert 'Room' in relationships


class TestGuestServiceV2:
    """测试 GuestServiceV2 兼容性"""

    def test_get_guests(self, db_session):
        service = get_guest_service_v2(db_session)
        guests = service.get_guests(limit=10)
        assert isinstance(guests, list)

    def test_create_and_get_guest(self, db_session):
        service = get_guest_service_v2(db_session)
        from app.models.schemas import GuestCreate

        data = GuestCreate(name="Test Guest", phone="13900000000")
        guest = service.create_guest(data)
        assert guest.name == "Test Guest"

        retrieved = service.get_guest(guest.id)
        assert retrieved is not None
        assert retrieved.name == "Test Guest"

    def test_get_guest_entity(self, db_session):
        service = get_guest_service_v2(db_session)
        entity = service.get_guest_entity(1)
        if entity:
            assert entity.id == 1
            assert hasattr(entity, 'name')

    def test_update_tier_with_entity(self, db_session):
        service = get_guest_service_v2(db_session)
        from app.models.schemas import GuestCreate
        from app.models.ontology import GuestTier

        data = GuestCreate(name="VIP Guest", phone="13900000001")
        guest = service.create_guest(data)

        updated = service.update_tier(guest.id, GuestTier.GOLD)
        assert updated.tier == GuestTier.GOLD

    def test_add_to_blacklist_with_entity(self, db_session):
        service = get_guest_service_v2(db_session)
        from app.models.schemas import GuestCreate

        data = GuestCreate(name="Bad Guest", phone="13900000002")
        guest = service.create_guest(data)

        updated = service.add_to_blacklist(guest.id, "Test blacklist")
        assert updated.is_blacklisted is True
        assert updated.blacklist_reason == "Test blacklist"

    def test_get_guest_stats(self, db_session):
        service = get_guest_service_v2(db_session)
        from app.models.schemas import GuestCreate

        data = GuestCreate(name="Stats Guest", phone="13900000003")
        guest = service.create_guest(data)

        stats = service.get_guest_stats(guest.id)
        assert 'reservation_count' in stats
        assert 'total_stays' in stats
        assert 'tier' in stats

    def test_get_guest_relationships(self, db_session):
        service = get_guest_service_v2(db_session)
        relationships = service.get_guest_relationships(1)
        if relationships:
            assert 'Guest' in relationships


class TestServiceIntegration:
    """测试服务集成"""

    def test_room_and_guest_integration(self, db_session):
        """测试房间和客人服务的集成"""
        room_service = get_room_service_v2(db_session)
        guest_service = get_guest_service_v2(db_session)

        # Create guest
        from app.models.schemas import GuestCreate
        guest_data = GuestCreate(name="Integration Guest", phone="13900000004")
        guest = guest_service.create_guest(guest_data)

        # Create room
        rt = RoomType(name="Integration", base_price=100.00, max_occupancy=2)
        db_session.add(rt)
        db_session.commit()

        from app.models.schemas import RoomCreate
        room_data = RoomCreate(room_number="997", floor=9, room_type_id=rt.id)
        room = room_service.create_room(room_data)

        # Verify both exist
        assert guest_service.get_guest(guest.id) is not None
        assert room_service.get_room(room.id) is not None

    def test_relationships_integration(self, db_session):
        """测试关系注册表集成"""
        from core.domain.relationships import relationship_registry

        # Test getting relationships for different entities
        room_rels = relationship_registry.get_relationships("Room")
        guest_rels = relationship_registry.get_relationships("Guest")

        # Verify relationships exist
        assert room_rels is not None or "Room" not in relationship_registry._entity_relationships
        assert guest_rels is not None or "Guest" not in relationship_registry._entity_relationships
