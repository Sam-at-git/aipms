"""
房间服务 - 本体操作层
管理 Room 和 RoomType 对象
支持事件发布：房间状态变更时发布事件
SPEC-R13: State machine validation before status changes
"""
from typing import List, Optional, Callable
from datetime import date, datetime
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.ontology import Room, RoomType, RoomStatus, StayRecord, StayRecordStatus
from app.models.schemas import (
    RoomCreate, RoomUpdate, RoomTypeCreate, RoomTypeUpdate, RoomStatusUpdate
)
from app.services.event_bus import event_bus, Event
from app.models.events import EventType, RoomStatusChangedData

logger = logging.getLogger(__name__)


def _validate_state_transition(entity_type: str, current_state: str, target_state: str) -> None:
    """SPEC-R13: Validate state transition against registry state machine."""
    try:
        from core.ontology.state_machine_executor import StateMachineExecutor
        executor = StateMachineExecutor()
        result = executor.validate_transition(entity_type, current_state, target_state)
        if not result.allowed:
            logger.warning(
                f"State transition validation: {entity_type} "
                f"'{current_state}' → '{target_state}': {result.reason}"
            )
    except Exception as e:
        logger.debug(f"State machine validation skipped: {e}")


class RoomService:
    """房间服务"""

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        # 支持依赖注入事件发布器，便于测试
        self._publish_event = event_publisher or event_bus.publish

    # ============== 房型操作 ==============

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

        # 检查是否有关联房间
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

    # ============== 房间操作 ==============

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

    def get_room_by_number(self, room_number: str) -> Optional[Room]:
        """根据房间号获取房间"""
        return self.db.query(Room).filter(Room.room_number == room_number).first()

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
        """更新房间状态"""
        room = self.get_room(room_id)
        if not room:
            raise ValueError("房间不存在")

        # 入住中的房间不能手动改状态
        if room.status == RoomStatus.OCCUPIED and status != RoomStatus.OCCUPIED:
            raise ValueError("入住中的房间不能手动更改状态，请通过退房操作")

        old_status = room.status
        _validate_state_transition("Room", old_status.value, status.value)
        room.status = status
        room_number = room.room_number

        self.db.commit()
        self.db.refresh(room)

        # 发布房间状态变更事件
        if old_status != status:
            self._publish_event(Event(
                event_type=EventType.ROOM_STATUS_CHANGED,
                timestamp=datetime.now(),
                data=RoomStatusChangedData(
                    room_id=room_id,
                    room_number=room_number,
                    old_status=old_status.value,
                    new_status=status.value,
                    changed_by=changed_by,
                    reason=reason
                ).to_dict(),
                source="room_service"
            ))

        return room

    def delete_room(self, room_id: int) -> bool:
        """删除房间"""
        room = self.get_room(room_id)
        if not room:
            raise ValueError("房间不存在")

        # 检查是否有入住记录
        stay_count = self.db.query(StayRecord).filter(StayRecord.room_id == room_id).count()
        if stay_count > 0:
            raise ValueError("该房间有历史入住记录，无法删除，请停用")

        self.db.delete(room)
        self.db.commit()
        return True

    # ============== 可用性查询 ==============

    def get_available_rooms(self, check_in_date: date, check_out_date: date,
                            room_type_id: Optional[int] = None) -> List[Room]:
        """获取指定日期范围内的可用房间"""
        # 获取在该日期范围内已被预订或在住的房间ID
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
            'status': room.status.value,  # 转换为字符串值
            'features': room.features,
            'is_active': room.is_active,
            'current_guest': current_guest,
            'created_at': room.created_at
        }

    def get_room_status_summary(self) -> dict:
        """获取房态统计"""
        rooms = self.get_rooms(is_active=True)
        summary = {
            'total': len(rooms),
            'vacant_clean': 0,
            'occupied': 0,
            'vacant_dirty': 0,
            'out_of_order': 0
        }

        for room in rooms:
            if room.status == RoomStatus.VACANT_CLEAN:
                summary['vacant_clean'] += 1
            elif room.status == RoomStatus.OCCUPIED:
                summary['occupied'] += 1
            elif room.status == RoomStatus.VACANT_DIRTY:
                summary['vacant_dirty'] += 1
            elif room.status == RoomStatus.OUT_OF_ORDER:
                summary['out_of_order'] += 1

        return summary
