"""
Room Service Adapter - 集成新领域层与现有服务

这个服务适配器提供了使用新领域实体（RoomEntity, RoomRepository）的接口，
同时保持与现有 API 的兼容性。
"""
from typing import List, Optional, Callable
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.hotel.domain.room import RoomEntity, RoomRepository, RoomState
from app.hotel.domain import relationship_registry
from app.hotel.models.ontology import Room, RoomType, RoomStatus, StayRecord, StayRecordStatus
from app.hotel.models.schemas import (
    RoomCreate, RoomUpdate, RoomTypeCreate, RoomTypeUpdate, RoomStatusUpdate
)
from app.services.event_bus import event_bus, Event
from app.models.events import EventType, RoomStatusChangedData


class RoomServiceV2:
    """
    房间服务 V2 - 使用新领域层

    主要变化:
    1. 使用 RoomRepository 进行数据访问
    2. 使用 RoomEntity 进行业务操作
    3. 保留事件发布机制
    4. 支持本体关系查询
    """

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        self._room_repo = RoomRepository(db)
        self._publish_event = event_publisher or event_bus.publish

    # ============== 房型操作 (保持原有实现) ==============

    def get_room_types(self) -> List[RoomType]:
        """获取所有房型"""
        return self.db.query(RoomType).all()

    def get_room_type(self, room_type_id: int) -> Optional[RoomType]:
        """获取单个房型"""
        return self.db.query(RoomType).filter(RoomType.id == room_type_id).first()

    def get_room_type_by_name(self, name: str) -> Optional[RoomType]:
        """根据名称获取房型"""
        return self.db.query(RoomType).filter(RoomType.name == name).first()

    def create_room_type(self, data: RoomTypeCreate) -> RoomType:
        """创建房型"""
        if self.get_room_type_by_name(data.name):
            raise ValueError(f"房型名称 '{data.name}' 已存在")

        room_type = RoomType(**data.model_dump())
        self.db.add(room_type)
        self.db.commit()
        self.db.refresh(room_type)
        return room_type

    def update_room_type(self, room_type_id: int, data: RoomTypeUpdate) -> RoomType:
        """更新房型"""
        room_type = self.get_room_type(room_type_id)
        if not room_type:
            raise ValueError("房型不存在")

        update_data = data.model_dump(exclude_unset=True)
        if 'name' in update_data:
            existing = self.get_room_type_by_name(update_data['name'])
            if existing and existing.id != room_type_id:
                raise ValueError(f"房型名称 '{update_data['name']}' 已存在")

        for key, value in update_data.items():
            setattr(room_type, key, value)

        self.db.commit()
        self.db.refresh(room_type)
        return room_type

    def delete_room_type(self, room_type_id: int) -> bool:
        """删除房型"""
        room_type = self.get_room_type(room_type_id)
        if not room_type:
            raise ValueError("房型不存在")

        room_count = self.db.query(Room).filter(Room.room_type_id == room_type_id).count()
        if room_count > 0:
            raise ValueError(f"该房型下有 {room_count} 间房间，无法删除")

        self.db.delete(room_type)
        self.db.commit()
        return True

    def get_room_type_with_count(self, room_type_id: int) -> dict:
        """获取房型及房间数量"""
        room_type = self.get_room_type(room_type_id)
        if not room_type:
            return None

        room_count = self.db.query(Room).filter(
            Room.room_type_id == room_type_id,
            Room.is_active == True
        ).count()

        return {
            **room_type.__dict__,
            'room_count': room_count
        }

    # ============== 房间操作 (使用新领域层) ==============

    def get_rooms(self, floor: Optional[int] = None, room_type_id: Optional[int] = None,
                  status: Optional[RoomStatus] = None, is_active: Optional[bool] = True) -> List[Room]:
        """获取房间列表"""
        query = self.db.query(Room)

        if floor is not None:
            query = query.filter(Room.floor == floor)
        if room_type_id is not None:
            query = query.filter(Room.room_type_id == room_type_id)
        if status is not None:
            query = query.filter(Room.status == status)
        if is_active is not None:
            query = query.filter(Room.is_active == is_active)

        return query.order_by(Room.floor, Room.room_number).all()

    def get_room(self, room_id: int) -> Optional[Room]:
        """获取单个房间"""
        return self.db.query(Room).filter(Room.id == room_id).first()

    def get_room_entity(self, room_id: int) -> Optional[RoomEntity]:
        """获取房间领域实体 (新方法)"""
        return self._room_repo.get_by_id(room_id)

    def get_room_by_number(self, room_number: str) -> Optional[Room]:
        """根据房间号获取房间"""
        return self._room_repo.get_by_number(room_number)

    def create_room(self, data: RoomCreate) -> Room:
        """创建房间"""
        if self.get_room_by_number(data.room_number):
            raise ValueError(f"房间号 '{data.room_number}' 已存在")

        if not self.get_room_type(data.room_type_id):
            raise ValueError("房型不存在")

        room = Room(**data.model_dump())
        self.db.add(room)
        self.db.commit()
        self.db.refresh(room)
        return room

    def update_room(self, room_id: int, data: RoomUpdate) -> Room:
        """更新房间"""
        room = self.get_room(room_id)
        if not room:
            raise ValueError("房间不存在")

        update_data = data.model_dump(exclude_unset=True)

        if 'room_type_id' in update_data:
            if not self.get_room_type(update_data['room_type_id']):
                raise ValueError("房型不存在")

        for key, value in update_data.items():
            setattr(room, key, value)

        self.db.commit()
        self.db.refresh(room)
        return room

    def update_room_status(self, room_id: int, status: RoomStatus,
                           changed_by: int = None, reason: str = "") -> Room:
        """更新房间状态 (使用领域实体)"""
        from app.hotel.models.ontology import Room as ORMRoom

        old_orm_room = self.db.query(ORMRoom).filter(ORMRoom.id == room_id).first()
        if not old_orm_room:
            raise ValueError("房间不存在")

        old_status = old_orm_room.status.value

        # 使用领域实体进行状态转换（如果适用）
        room_entity = self.get_room_entity(room_id)

        if status == RoomStatus.VACANT_CLEAN:
            room_entity.mark_clean()
        elif status == RoomStatus.OUT_OF_ORDER:
            room_entity.mark_maintenance()
        elif status == RoomStatus.VACANT_DIRTY:
            if old_status == RoomState.OCCUPIED:
                room_entity.check_out()
            else:
                # 直接修改状态（手动标记为待清洁）
                old_orm_room.status = RoomStatus.VACANT_DIRTY
        elif status == RoomStatus.OCCUPIED:
            # 对于直接设置为 OCCUPIED 的情况（非正常入住流程），直接修改状态
            # 正常入住应该通过 checkin_service，这里允许手动设置用于特殊情况
            old_orm_room.status = RoomStatus.OCCUPIED

        self.db.commit()
        self.db.refresh(old_orm_room)

        # 发布房间状态变更事件
        if old_status != status.value:
            self._publish_event(Event(
                event_type=EventType.ROOM_STATUS_CHANGED,
                timestamp=datetime.now(),
                data=RoomStatusChangedData(
                    room_id=room_id,
                    room_number=old_orm_room.room_number,
                    old_status=old_status,
                    new_status=status.value,
                    changed_by=changed_by,
                    reason=reason
                ).to_dict(),
                source="room_service_v2"
            ))

        return old_orm_room

    def delete_room(self, room_id: int) -> bool:
        """删除房间"""
        room = self.get_room(room_id)
        if not room:
            raise ValueError("房间不存在")

        stay_count = self.db.query(StayRecord).filter(StayRecord.room_id == room_id).count()
        if stay_count > 0:
            raise ValueError("该房间有历史入住记录，无法删除，请停用")

        self.db.delete(room)
        self.db.commit()
        return True

    # ============== 可用性查询 (使用新领域层) ==============

    def get_available_rooms(self, check_in_date: date, check_out_date: date,
                            room_type_id: Optional[int] = None) -> List[Room]:
        """获取指定日期范围内的可用房间"""
        occupied_rooms = self.db.query(StayRecord.room_id).filter(
            StayRecord.status == StayRecordStatus.ACTIVE,
            StayRecord.expected_check_out > check_in_date
        ).subquery()

        query = self.db.query(Room).filter(
            Room.is_active == True,
            Room.status.in_([RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]),
            ~Room.id.in_(occupied_rooms)
        )

        if room_type_id:
            query = query.filter(Room.room_type_id == room_type_id)

        return query.order_by(Room.floor, Room.room_number).all()

    def get_available_entities(self, check_in_date: date, check_out_date: date,
                               room_type_id: Optional[int] = None) -> List[RoomEntity]:
        """获取指定日期范围内的可用房间 (返回领域实体)"""
        rooms = self.get_available_rooms(check_in_date, check_out_date, room_type_id)
        return [RoomEntity(r) for r in rooms]

    def get_availability_by_room_type(self, check_in_date: date, check_out_date: date) -> dict:
        """按房型统计可用房间数"""
        room_types = self.get_room_types()
        result = {}

        for rt in room_types:
            total = self.db.query(Room).filter(
                Room.room_type_id == rt.id,
                Room.is_active == True,
                Room.status != RoomStatus.OUT_OF_ORDER
            ).count()

            available = len(self.get_available_rooms(check_in_date, check_out_date, rt.id))

            result[rt.id] = {
                'room_type_id': rt.id,
                'room_type_name': rt.name,
                'total': total,
                'available': available
            }

        return result

    def get_room_with_guest(self, room_id: int) -> dict:
        """获取房间及当前住客信息"""
        room = self.get_room(room_id)
        if not room:
            return None

        current_guest = None
        if room.status == RoomStatus.OCCUPIED:
            stay = self.db.query(StayRecord).filter(
                StayRecord.room_id == room_id,
                StayRecord.status == StayRecordStatus.ACTIVE
            ).first()
            if stay:
                current_guest = stay.guest.name

        return {
            'id': room.id,
            'room_number': room.room_number,
            'floor': room.floor,
            'room_type_id': room.room_type_id,
            'room_type_name': room.room_type.name,
            'status': room.status.value,
            'features': room.features,
            'is_active': room.is_active,
            'current_guest': current_guest,
            'created_at': room.created_at
        }

    def get_room_status_summary(self) -> dict:
        """获取房态统计 (使用新领域层)"""
        vacant_clean = self._room_repo.find_by_status(RoomState.VACANT_CLEAN)
        occupied = self._room_repo.find_by_status(RoomState.OCCUPIED)
        dirty = self._room_repo.find_dirty_rooms()
        ooo = self._room_repo.find_by_status(RoomState.OUT_OF_ORDER)

        return {
            'total': len(vacant_clean) + len(occupied) + len(dirty) + len(ooo),
            'vacant_clean': len(vacant_clean),
            'occupied': len(occupied),
            'vacant_dirty': len(dirty),
            'out_of_order': len(ooo)
        }

    # ============== 本体关系查询 (新增) ==============

    def get_room_relationships(self, room_id: int) -> dict:
        """获取房间的关系网络"""
        entity = self.get_room_entity(room_id)
        if not entity:
            return None

        return relationship_registry.get_relationships("Room")

    def get_linked_entities(self, room_id: int) -> dict:
        """获取房间关联的实体"""
        entity = self.get_room_entity(room_id)
        if not entity:
            return None

        return relationship_registry.get_linked_entities(entity, self.db)


# 为了向后兼容，创建默认实例
def get_room_service_v2(db: Session) -> RoomServiceV2:
    """获取 RoomServiceV2 实例"""
    return RoomServiceV2(db)


__all__ = ["RoomServiceV2", "get_room_service_v2"]
