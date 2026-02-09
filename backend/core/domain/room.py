"""
core/domain/room.py

Room 领域实体 - OODA 运行时的领域层
封装现有 ORM 模型，添加框架功能
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import logging

from core.ontology.base import BaseEntity
from core.engine.state_machine import StateMachine, StateMachineConfig, StateTransition
from core.ontology.interface import implements
from core.domain.interfaces import BookableResource, Maintainable

if TYPE_CHECKING:
    from app.models.ontology import Room, RoomType, RoomStatus

logger = logging.getLogger(__name__)


# ============== 状态定义 ==============

class RoomState(str):
    """房间状态"""
    VACANT_CLEAN = "vacant_clean"      # 空闲-已清洁
    OCCUPIED = "occupied"              # 入住中
    VACANT_DIRTY = "vacant_dirty"      # 空闲-待清洁
    OUT_OF_ORDER = "out_of_order"      # 维修中


# ============== 辅助函数 ==============

def _create_room_state_machine(initial_status: str) -> StateMachine:
    """创建房间状态机"""
    return StateMachine(
        config=StateMachineConfig(
            name="Room",
            states=[
                RoomState.VACANT_CLEAN,
                RoomState.OCCUPIED,
                RoomState.VACANT_DIRTY,
                RoomState.OUT_OF_ORDER,
            ],
            transitions=[
                StateTransition(
                    from_state=RoomState.VACANT_CLEAN,
                    to_state=RoomState.OCCUPIED,
                    trigger="check_in",
                ),
                StateTransition(
                    from_state=RoomState.OCCUPIED,
                    to_state=RoomState.VACANT_DIRTY,
                    trigger="check_out",
                ),
                StateTransition(
                    from_state=RoomState.VACANT_DIRTY,
                    to_state=RoomState.VACANT_CLEAN,
                    trigger="mark_clean",
                ),
                StateTransition(
                    from_state=RoomState.VACANT_CLEAN,
                    to_state=RoomState.OUT_OF_ORDER,
                    trigger="mark_maintenance",
                ),
                StateTransition(
                    from_state=RoomState.VACANT_DIRTY,
                    to_state=RoomState.OUT_OF_ORDER,
                    trigger="mark_maintenance",
                ),
                StateTransition(
                    from_state=RoomState.OUT_OF_ORDER,
                    to_state=RoomState.VACANT_CLEAN,
                    trigger="complete_maintenance",
                ),
            ],
            initial_state=initial_status,
        )
    )


# ============== Room 领域实体 ==============

@implements(BookableResource, Maintainable)
class RoomEntity(BaseEntity):
    """
    Room 领域实体

    封装现有 ORM 模型，提供业务方法和状态管理。

    Attributes:
        _orm_model: 内部 ORM 模型实例
        _state_machine: 状态机实例
    """

    __ontology_actions__ = [
        "check_in", "check_out", "mark_clean",
        "mark_maintenance", "complete_maintenance",
    ]

    def __init__(self, orm_model: "Room"):
        """
        初始化 Room 实体

        Args:
            orm_model: SQLAlchemy ORM 模型实例
        """
        self._orm_model = orm_model
        initial_status = orm_model.status.value if orm_model.status else RoomState.VACANT_CLEAN
        self._state_machine = _create_room_state_machine(initial_status)

    # ============== 属性访问 ==============

    @property
    def id(self) -> int:
        """房间 ID"""
        return self._orm_model.id

    @property
    def room_number(self) -> str:
        """房间号"""
        return self._orm_model.room_number

    @property
    def floor(self) -> int:
        """楼层"""
        return self._orm_model.floor

    @property
    def room_type_id(self) -> int:
        """房型 ID"""
        return self._orm_model.room_type_id

    @property
    def status(self) -> str:
        """当前状态"""
        return self._orm_model.status.value if self._orm_model.status else RoomState.VACANT_CLEAN

    @property
    def features(self) -> Optional[str]:
        """特征描述"""
        return self._orm_model.features

    @property
    def is_active(self) -> bool:
        """是否启用"""
        return self._orm_model.is_active

    @property
    def created_at(self) -> datetime:
        """创建时间"""
        return self._orm_model.created_at

    @property
    def updated_at(self) -> datetime:
        """更新时间"""
        return self._orm_model.updated_at

    # ============== 业务方法 ==============

    def check_in(self, guest_id: int, expected_check_out: Optional[str] = None) -> None:
        """
        办理入住

        Args:
            guest_id: 客人 ID
            expected_check_out: 预计退房日期

        Raises:
            ValueError: 如果状态不允许入住
        """
        from app.models.ontology import RoomStatus

        if not self._state_machine.can_transition_to(RoomState.OCCUPIED, "check_in"):
            raise ValueError(f"房间状态 {self.status} 不允许办理入住")

        # 执行状态转换
        self._state_machine.transition_to(RoomState.OCCUPIED, "check_in")
        self._orm_model.status = RoomStatus.OCCUPIED
        logger.info(f"Room {self.room_number} checked in by guest {guest_id}")

    def check_out(self, stay_record_id: int) -> None:
        """
        办理退房

        Args:
            stay_record_id: 住宿记录 ID

        Raises:
            ValueError: 如果状态不允许退房
        """
        from app.models.ontology import RoomStatus

        if not self._state_machine.can_transition_to(RoomState.VACANT_DIRTY, "check_out"):
            raise ValueError(f"房间状态 {self.status} 不允许办理退房")

        # 执行状态转换
        self._state_machine.transition_to(RoomState.VACANT_DIRTY, "check_out")
        self._orm_model.status = RoomStatus.VACANT_DIRTY
        logger.info(f"Room {self.room_number} checked out (stay_record: {stay_record_id})")

    def mark_clean(self) -> None:
        """
        标记为已清洁

        Raises:
            ValueError: 如果状态不允许标记清洁
        """
        from app.models.ontology import RoomStatus

        if not self._state_machine.can_transition_to(RoomState.VACANT_CLEAN, "mark_clean"):
            # 保持与原服务相同的错误消息
            raise ValueError("不能手动更改状态")

        # 执行状态转换
        self._state_machine.transition_to(RoomState.VACANT_CLEAN, "mark_clean")
        self._orm_model.status = RoomStatus.VACANT_CLEAN
        logger.info(f"Room {self.room_number} marked as clean")

    def mark_maintenance(self, reason: Optional[str] = None) -> None:
        """
        标记为维修中

        Args:
            reason: 维修原因

        Raises:
            ValueError: 如果状态不允许标记维修
        """
        from app.models.ontology import RoomStatus

        if not self._state_machine.can_transition_to(RoomState.OUT_OF_ORDER, "mark_maintenance"):
            raise ValueError(f"房间状态 {self.status} 不允许标记为维修中")

        # 执行状态转换
        self._state_machine.transition_to(RoomState.OUT_OF_ORDER, "mark_maintenance")
        self._orm_model.status = RoomStatus.OUT_OF_ORDER
        logger.info(f"Room {self.room_number} marked for maintenance: {reason}")

    def complete_maintenance(self) -> None:
        """
        完成维修

        Raises:
            ValueError: 如果状态不允许完成维修
        """
        from app.models.ontology import RoomStatus

        if not self._state_machine.can_transition_to(RoomState.VACANT_CLEAN, "complete_maintenance"):
            raise ValueError(f"房间状态 {self.status} 不允许完成维修")

        # 执行状态转换
        self._state_machine.transition_to(RoomState.VACANT_CLEAN, "complete_maintenance")
        self._orm_model.status = RoomStatus.VACANT_CLEAN
        logger.info(f"Room {self.room_number} maintenance completed")

    # ============== 查询方法 ==============

    def is_available(self) -> bool:
        """
        检查房间是否可用（空闲且已清洁）

        Returns:
            是否可用
        """
        return self.status == RoomState.VACANT_CLEAN and self.is_active

    def is_occupied(self) -> bool:
        """
        检查房间是否已入住

        Returns:
            是否已入住
        """
        return self.status == RoomState.OCCUPIED

    def needs_cleaning(self) -> bool:
        """
        检查房间是否需要清洁

        Returns:
            是否需要清洁
        """
        return self.status == RoomState.VACANT_DIRTY

    # ============== 序列化 ==============

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "room_number": self.room_number,
            "floor": self.floor,
            "room_type_id": self.room_type_id,
            "status": self.status,
            "features": self.features,
            "is_active": self.is_active,
            "is_available": self.is_available(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============== Room 仓储 ==============

class RoomRepository:
    """
    Room 仓储

    负责 Room 实体的持久化和查询
    """

    def __init__(self, db_session):
        """
        初始化仓储

        Args:
            db_session: SQLAlchemy 数据库会话
        """
        self._db = db_session

    def get_by_id(self, room_id: int) -> Optional[RoomEntity]:
        """
        根据 ID 获取房间

        Args:
            room_id: 房间 ID

        Returns:
            RoomEntity 实例，如果不存在返回 None
        """
        from app.models.ontology import Room

        orm_model = self._db.query(Room).filter(Room.id == room_id).first()
        if orm_model is None:
            return None
        return RoomEntity(orm_model)

    def get_by_number(self, room_number: str) -> Optional[RoomEntity]:
        """
        根据房间号获取房间

        Args:
            room_number: 房间号

        Returns:
            RoomEntity 实例，如果不存在返回 None
        """
        from app.models.ontology import Room

        orm_model = self._db.query(Room).filter(Room.room_number == room_number).first()
        if orm_model is None:
            return None
        return RoomEntity(orm_model)

    def find_available(self, room_type_id: Optional[int] = None) -> List[RoomEntity]:
        """
        查找可用房间

        Args:
            room_type_id: 房型 ID（可选），如果指定则只返回该类型的可用房间

        Returns:
            可用房间列表
        """
        from app.models.ontology import Room, RoomStatus

        query = self._db.query(Room).filter(
            Room.status == RoomStatus.VACANT_CLEAN,
            Room.is_active == True
        )

        if room_type_id is not None:
            query = query.filter(Room.room_type_id == room_type_id)

        return [RoomEntity(m) for m in query.all()]

    def find_by_status(self, status: str) -> List[RoomEntity]:
        """
        根据状态查找房间

        Args:
            status: 房间状态

        Returns:
            房间列表
        """
        from app.models.ontology import Room, RoomStatus

        try:
            status_enum = RoomStatus(status)
        except ValueError:
            return []

        orm_models = self._db.query(Room).filter(Room.status == status_enum).all()
        return [RoomEntity(m) for m in orm_models]

    def find_dirty_rooms(self) -> List[RoomEntity]:
        """
        查找需要清洁的房间

        Returns:
            需要清洁的房间列表
        """
        return self.find_by_status(RoomState.VACANT_DIRTY)

    def find_occupied_rooms(self) -> List[RoomEntity]:
        """
        查找已入住的房间

        Returns:
            已入住的房间列表
        """
        return self.find_by_status(RoomState.OCCUPIED)

    def save(self, room: RoomEntity) -> None:
        """
        保存房间

        Args:
            room: RoomEntity 实例
        """
        self._db.add(room._orm_model)
        self._db.commit()

    def list_all(self) -> List[RoomEntity]:
        """
        列出所有房间

        Returns:
            所有房间列表
        """
        from app.models.ontology import Room

        orm_models = self._db.query(Room).all()
        return [RoomEntity(m) for m in orm_models]


# 导出
__all__ = [
    "RoomState",
    "RoomEntity",
    "RoomRepository",
]
