"""
测试 core.domain.room 模块 - Room 领域实体单元测试
"""
import pytest
from datetime import datetime

from core.domain.room import (
    RoomState,
    RoomEntity,
    RoomRepository,
)
from app.models.ontology import Room, RoomStatus, RoomType


# ============== Fixtures ==============

@pytest.fixture
def sample_room_type(db_session):
    """创建示例房型"""
    room_type = RoomType(
        name="Standard",
        description="标准间",
        base_price=100.00,
        max_occupancy=2,
    )
    db_session.add(room_type)
    db_session.commit()
    return room_type


@pytest.fixture
def sample_room(db_session, sample_room_type):
    """创建示例房间"""
    room = Room(
        room_number="101",
        floor=1,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN,
        is_active=True,
    )
    db_session.add(room)
    db_session.commit()
    return room


# ============== RoomEntity Tests ==============

class TestRoomEntity:
    def test_creation(self, sample_room):
        """测试创建房间实体"""
        entity = RoomEntity(sample_room)

        assert entity.id == sample_room.id
        assert entity.room_number == "101"
        assert entity.floor == 1
        assert entity.status == RoomState.VACANT_CLEAN
        assert entity.is_active is True

    def test_is_available_when_vacant_clean(self, sample_room):
        """测试空闲已清洁房间可用"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        assert entity.is_available() is True
        assert entity.is_occupied() is False
        assert entity.needs_cleaning() is False

    def test_is_not_available_when_occupied(self, sample_room):
        """测试已入住房间不可用"""
        sample_room.status = RoomStatus.OCCUPIED
        entity = RoomEntity(sample_room)

        assert entity.is_available() is False
        assert entity.is_occupied() is True
        assert entity.needs_cleaning() is False

    def test_is_not_available_when_dirty(self, sample_room):
        """测试待清洁房间不可用"""
        sample_room.status = RoomStatus.VACANT_DIRTY
        entity = RoomEntity(sample_room)

        assert entity.is_available() is False
        assert entity.is_occupied() is False
        assert entity.needs_cleaning() is True

    def test_is_not_available_when_inactive(self, sample_room):
        """测试未启用房间不可用"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        sample_room.is_active = False
        entity = RoomEntity(sample_room)

        assert entity.is_available() is False

    def test_check_in_from_vacant_clean(self, sample_room):
        """测试从空闲已清洁状态办理入住"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        entity.check_in(guest_id=1)

        assert entity.status == RoomState.OCCUPIED
        assert sample_room.status == RoomStatus.OCCUPIED

    def test_check_in_fails_when_occupied(self, sample_room):
        """测试已入住状态无法再次办理入住"""
        sample_room.status = RoomStatus.OCCUPIED
        entity = RoomEntity(sample_room)

        with pytest.raises(ValueError, match="不允许办理入住"):
            entity.check_in(guest_id=1)

    def test_check_out_from_occupied(self, sample_room):
        """测试从入住状态办理退房"""
        sample_room.status = RoomStatus.OCCUPIED
        entity = RoomEntity(sample_room)

        entity.check_out(stay_record_id=1)

        assert entity.status == RoomState.VACANT_DIRTY
        assert sample_room.status == RoomStatus.VACANT_DIRTY

    def test_check_out_fails_when_not_occupied(self, sample_room):
        """测试非入住状态无法办理退房"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        with pytest.raises(ValueError, match="不允许办理退房"):
            entity.check_out(stay_record_id=1)

    def test_mark_clean_from_dirty(self, sample_room):
        """测试从待清洁状态标记为已清洁"""
        sample_room.status = RoomStatus.VACANT_DIRTY
        entity = RoomEntity(sample_room)

        entity.mark_clean()

        assert entity.status == RoomState.VACANT_CLEAN
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_mark_clean_fails_when_not_dirty(self, sample_room):
        """测试非待清洁状态无法标记为已清洁"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        with pytest.raises(ValueError, match="不能手动更改状态"):
            entity.mark_clean()

    def test_mark_maintenance_from_vacant_clean(self, sample_room):
        """测试从空闲已清洁状态标记为维修中"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        entity.mark_maintenance(reason="空调故障")

        assert entity.status == RoomState.OUT_OF_ORDER
        assert sample_room.status == RoomStatus.OUT_OF_ORDER

    def test_mark_maintenance_from_dirty(self, sample_room):
        """测试从待清洁状态标记为维修中"""
        sample_room.status = RoomStatus.VACANT_DIRTY
        entity = RoomEntity(sample_room)

        entity.mark_maintenance(reason="管道维修")

        assert entity.status == RoomState.OUT_OF_ORDER

    def test_complete_maintenance(self, sample_room):
        """测试完成维修"""
        sample_room.status = RoomStatus.OUT_OF_ORDER
        entity = RoomEntity(sample_room)

        entity.complete_maintenance()

        assert entity.status == RoomState.VACANT_CLEAN
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_complete_maintenance_fails_when_not_maintenance(self, sample_room):
        """测试非维修状态无法完成维修"""
        sample_room.status = RoomStatus.VACANT_CLEAN
        entity = RoomEntity(sample_room)

        with pytest.raises(ValueError, match="不允许完成维修"):
            entity.complete_maintenance()

    def test_to_dict(self, sample_room):
        """测试转换为字典"""
        entity = RoomEntity(sample_room)

        d = entity.to_dict()

        assert d["id"] == sample_room.id
        assert d["room_number"] == "101"
        assert d["floor"] == 1
        assert d["status"] == RoomState.VACANT_CLEAN
        assert d["is_available"] is True
        assert "is_active" in d


# ============== RoomRepository Tests ==============

class TestRoomRepository:
    def test_get_by_id(self, db_session, sample_room):
        """测试根据 ID 获取房间"""
        repo = RoomRepository(db_session)

        entity = repo.get_by_id(sample_room.id)

        assert entity is not None
        assert entity.id == sample_room.id
        assert entity.room_number == "101"

    def test_get_by_id_not_found(self, db_session):
        """测试获取不存在的房间"""
        repo = RoomRepository(db_session)

        entity = repo.get_by_id(99999)

        assert entity is None

    def test_get_by_number(self, db_session, sample_room):
        """测试根据房间号获取房间"""
        repo = RoomRepository(db_session)

        entity = repo.get_by_number("101")

        assert entity is not None
        assert entity.room_number == "101"

    def test_get_by_number_not_found(self, db_session):
        """测试获取不存在的房间号"""
        repo = RoomRepository(db_session)

        entity = repo.get_by_number("999")

        assert entity is None

    def test_find_available(self, db_session, sample_room_type):
        """测试查找可用房间"""
        repo = RoomRepository(db_session)

        # 创建可用房间
        room1 = Room(room_number="201", floor=2, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_CLEAN, is_active=True)
        room2 = Room(room_number="202", floor=2, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_CLEAN, is_active=True)
        # 创建已入住房间
        room3 = Room(room_number="203", floor=2, room_type_id=sample_room_type.id,
                     status=RoomStatus.OCCUPIED, is_active=True)
        # 创建未启用房间
        room4 = Room(room_number="204", floor=2, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_CLEAN, is_active=False)

        db_session.add_all([room1, room2, room3, room4])
        db_session.commit()

        available = repo.find_available()

        assert len(available) >= 2
        room_numbers = [r.room_number for r in available]
        assert "201" in room_numbers
        assert "202" in room_numbers

    def test_find_available_by_type(self, db_session, sample_room, sample_room_type):
        """测试按类型查找可用房间"""
        repo = RoomRepository(db_session)

        available = repo.find_available(room_type_id=sample_room_type.id)

        assert len(available) >= 1
        assert all(r.room_type_id == sample_room_type.id for r in available)

    def test_find_by_status(self, db_session, sample_room_type):
        """测试根据状态查找房间"""
        repo = RoomRepository(db_session)

        # 创建不同状态的房间
        room1 = Room(room_number="301", floor=3, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_DIRTY, is_active=True)
        room2 = Room(room_number="302", floor=3, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_DIRTY, is_active=True)

        db_session.add_all([room1, room2])
        db_session.commit()

        dirty_rooms = repo.find_by_status(RoomState.VACANT_DIRTY)

        assert len(dirty_rooms) >= 2
        room_numbers = [r.room_number for r in dirty_rooms]
        assert "301" in room_numbers
        assert "302" in room_numbers

    def test_find_dirty_rooms(self, db_session, sample_room_type):
        """测试查找需要清洁的房间"""
        repo = RoomRepository(db_session)

        room1 = Room(room_number="401", floor=4, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_DIRTY, is_active=True)
        room2 = Room(room_number="402", floor=4, room_type_id=sample_room_type.id,
                     status=RoomStatus.VACANT_DIRTY, is_active=True)

        db_session.add_all([room1, room2])
        db_session.commit()

        dirty_rooms = repo.find_dirty_rooms()

        assert len(dirty_rooms) >= 2

    def test_find_occupied_rooms(self, db_session, sample_room_type):
        """测试查找已入住房间"""
        repo = RoomRepository(db_session)

        room1 = Room(room_number="501", floor=5, room_type_id=sample_room_type.id,
                     status=RoomStatus.OCCUPIED, is_active=True)

        db_session.add(room1)
        db_session.commit()

        occupied_rooms = repo.find_occupied_rooms()

        assert len(occupied_rooms) >= 1
        assert any(r.room_number == "501" for r in occupied_rooms)

    def test_list_all(self, db_session, sample_room):
        """测试列出所有房间"""
        repo = RoomRepository(db_session)

        all_rooms = repo.list_all()

        assert len(all_rooms) >= 1
        assert any(r.room_number == "101" for r in all_rooms)

    def test_save(self, db_session, sample_room_type):
        """测试保存房间"""
        repo = RoomRepository(db_session)

        room = Room(room_number="601", floor=6, room_type_id=sample_room_type.id,
                    status=RoomStatus.VACANT_CLEAN, is_active=True)
        entity = RoomEntity(room)

        repo.save(entity)

        # 验证已保存
        saved = repo.get_by_number("601")
        assert saved is not None
        assert saved.floor == 6


class TestRoomState:
    def test_state_values(self):
        """测试状态值"""
        assert RoomState.VACANT_CLEAN == "vacant_clean"
        assert RoomState.OCCUPIED == "occupied"
        assert RoomState.VACANT_DIRTY == "vacant_dirty"
        assert RoomState.OUT_OF_ORDER == "out_of_order"
