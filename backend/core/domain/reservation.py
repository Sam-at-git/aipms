"""
core/domain/reservation.py

Reservation 领域实体 - OODA 运行时的领域层
封装现有 ORM 模型，添加框架功能
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
import logging

from core.ontology.base import BaseEntity
from core.engine.state_machine import StateMachine, StateMachineConfig, StateTransition

if TYPE_CHECKING:
    from app.models.ontology import Reservation

logger = logging.getLogger(__name__)


# ============== 状态定义 ==============

class ReservationState(str):
    """预订状态"""
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# ============== 状态机配置 ==============

def _create_reservation_state_machine(initial_status: str) -> StateMachine:
    """创建预订状态机"""
    return StateMachine(
        config=StateMachineConfig(
            name="Reservation",
            states=[
                ReservationState.CONFIRMED,
                ReservationState.CHECKED_IN,
                ReservationState.COMPLETED,
                ReservationState.CANCELLED,
                ReservationState.NO_SHOW,
            ],
            transitions=[
                StateTransition(
                    from_state=ReservationState.CONFIRMED,
                    to_state=ReservationState.CHECKED_IN,
                    trigger="check_in",
                ),
                StateTransition(
                    from_state=ReservationState.CHECKED_IN,
                    to_state=ReservationState.COMPLETED,
                    trigger="check_out",
                ),
                StateTransition(
                    from_state=ReservationState.CONFIRMED,
                    to_state=ReservationState.CANCELLED,
                    trigger="cancel",
                ),
                StateTransition(
                    from_state=ReservationState.CONFIRMED,
                    to_state=ReservationState.NO_SHOW,
                    trigger="mark_no_show",
                ),
            ],
            initial_state=initial_status,
        )
    )


# ============== Reservation 领域实体 ==============

class ReservationEntity(BaseEntity):
    """
    Reservation 领域实体

    封装现有 ORM 模型，提供业务方法和状态管理。

    Attributes:
        _orm_model: 内部 ORM 模型实例
        _state_machine: 状态机实例
    """

    def __init__(self, orm_model: "Reservation"):
        """
        初始化 Reservation 实体

        Args:
            orm_model: SQLAlchemy ORM 模型实例
        """
        self._orm_model = orm_model
        initial_status = orm_model.status.value if orm_model.status else ReservationState.CONFIRMED
        self._state_machine = _create_reservation_state_machine(initial_status)

    # ============== 属性访问 ==============

    @property
    def id(self) -> int:
        """预订 ID"""
        return self._orm_model.id

    @property
    def reservation_no(self) -> str:
        """预订号"""
        return self._orm_model.reservation_no

    @property
    def guest_id(self) -> int:
        """客人 ID"""
        return self._orm_model.guest_id

    @property
    def room_type_id(self) -> int:
        """房型 ID"""
        return self._orm_model.room_type_id

    @property
    def check_in_date(self) -> date:
        """入住日期"""
        return self._orm_model.check_in_date

    @property
    def check_out_date(self) -> date:
        """离店日期"""
        return self._orm_model.check_out_date

    @property
    def room_count(self) -> int:
        """房间数"""
        return self._orm_model.room_count or 1

    @property
    def adult_count(self) -> int:
        """成人数"""
        return self._orm_model.adult_count or 1

    @property
    def child_count(self) -> int:
        """儿童数"""
        return self._orm_model.child_count or 0

    @property
    def status(self) -> str:
        """当前状态"""
        return self._orm_model.status.value if self._orm_model.status else ReservationState.CONFIRMED

    @property
    def total_amount(self) -> Optional[Decimal]:
        """预估总价"""
        return self._orm_model.total_amount

    @property
    def prepaid_amount(self) -> Decimal:
        """预付金额"""
        return self._orm_model.prepaid_amount or Decimal("0")

    @property
    def special_requests(self) -> Optional[str]:
        """特殊要求"""
        return self._orm_model.special_requests

    @property
    def estimated_arrival(self) -> Optional[str]:
        """预计到店时间"""
        return self._orm_model.estimated_arrival

    @property
    def cancel_reason(self) -> Optional[str]:
        """取消原因"""
        return self._orm_model.cancel_reason

    @property
    def created_at(self) -> datetime:
        """创建时间"""
        return self._orm_model.created_at

    @property
    def updated_at(self) -> datetime:
        """更新时间"""
        return self._orm_model.updated_at

    # ============== 业务方法 ==============

    def check_in(self, room_id: int, actual_guest_count: Optional[int] = None) -> None:
        """
        预订入住（转换为住宿记录）

        Args:
            room_id: 分配的房间 ID
            actual_guest_count: 实际入住人数

        Raises:
            ValueError: 如果状态不允许入住
        """
        from app.models.ontology import ReservationStatus

        if not self._state_machine.can_transition_to(ReservationState.CHECKED_IN, "check_in"):
            raise ValueError(f"预订状态 {self.status} 不允许办理入住")

        self._state_machine.transition_to(ReservationState.CHECKED_IN, "check_in")
        self._orm_model.status = ReservationStatus.CHECKED_IN
        logger.info(f"Reservation {self.reservation_no} checked in to room {room_id}")

    def cancel(self, reason: str) -> None:
        """
        取消预订

        Args:
            reason: 取消原因

        Raises:
            ValueError: 如果状态不允许取消
        """
        from app.models.ontology import ReservationStatus

        if not self._state_machine.can_transition_to(ReservationState.CANCELLED, "cancel"):
            raise ValueError(f"预订状态 {self.status} 不允许取消")

        self._state_machine.transition_to(ReservationState.CANCELLED, "cancel")
        self._orm_model.status = ReservationStatus.CANCELLED
        self._orm_model.cancel_reason = reason
        logger.info(f"Reservation {self.reservation_no} cancelled: {reason}")

    def mark_no_show(self) -> None:
        """
        标记为未到店

        Raises:
            ValueError: 如果状态不允许标记
        """
        from app.models.ontology import ReservationStatus

        if not self._state_machine.can_transition_to(ReservationState.NO_SHOW, "mark_no_show"):
            raise ValueError(f"预订状态 {self.status} 不允许标记为未到店")

        self._state_machine.transition_to(ReservationState.NO_SHOW, "mark_no_show")
        self._orm_model.status = ReservationStatus.NO_SHOW
        logger.info(f"Reservation {self.reservation_no} marked as no-show")

    def update_amount(self, amount: float) -> None:
        """
        更新预订金额

        Args:
            amount: 预订金额
        """
        self._orm_model.total_amount = Decimal(str(amount))
        logger.info(f"Reservation {self.reservation_no} amount updated to {amount}")

    # ============== 查询方法 ==============

    def is_active(self) -> bool:
        """检查预订是否有效（未取消、未完成）"""
        return self.status in [ReservationState.CONFIRMED, ReservationState.CHECKED_IN]

    def can_cancel(self) -> bool:
        """检查是否可以取消"""
        return self.status == ReservationState.CONFIRMED

    def is_checked_in(self) -> bool:
        """检查是否已入住"""
        return self.status == ReservationState.CHECKED_IN

    def get_nights(self) -> int:
        """获取住宿晚数"""
        if self.check_in_date and self.check_out_date:
            delta = self.check_out_date - self.check_in_date
            return delta.days
        return 0

    # ============== 序列化 ==============

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "reservation_no": self.reservation_no,
            "guest_id": self.guest_id,
            "room_type_id": self.room_type_id,
            "check_in_date": self.check_in_date.isoformat() if self.check_in_date else None,
            "check_out_date": self.check_out_date.isoformat() if self.check_out_date else None,
            "room_count": self.room_count,
            "adult_count": self.adult_count,
            "child_count": self.child_count,
            "status": self.status,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "prepaid_amount": float(self.prepaid_amount),
            "special_requests": self.special_requests,
            "estimated_arrival": self.estimated_arrival,
            "cancel_reason": self.cancel_reason,
            "is_active": self.is_active(),
            "nights": self.get_nights(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============== Reservation 仓储 ==============

class ReservationRepository:
    """Reservation 仓储"""

    def __init__(self, db_session):
        self._db = db_session

    def get_by_id(self, reservation_id: int) -> Optional[ReservationEntity]:
        """根据 ID 获取预订"""
        from app.models.ontology import Reservation

        orm_model = self._db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if orm_model is None:
            return None
        return ReservationEntity(orm_model)

    def get_by_no(self, reservation_no: str) -> Optional[ReservationEntity]:
        """根据预订号获取预订"""
        from app.models.ontology import Reservation

        orm_model = self._db.query(Reservation).filter(Reservation.reservation_no == reservation_no).first()
        if orm_model is None:
            return None
        return ReservationEntity(orm_model)

    def find_by_guest(self, guest_id: int) -> List[ReservationEntity]:
        """根据客人查找预订"""
        from app.models.ontology import Reservation

        orm_models = self._db.query(Reservation).filter(
            Reservation.guest_id == guest_id
        ).order_by(Reservation.created_at.desc()).all()
        return [ReservationEntity(m) for m in orm_models]

    def find_by_status(self, status: str) -> List[ReservationEntity]:
        """根据状态查找预订"""
        from app.models.ontology import Reservation, ReservationStatus

        try:
            status_enum = ReservationStatus(status)
        except ValueError:
            return []

        orm_models = self._db.query(Reservation).filter(Reservation.status == status_enum).all()
        return [ReservationEntity(m) for m in orm_models]

    def find_by_date_range(self, start_date: date, end_date: date) -> List[ReservationEntity]:
        """查找日期范围内的预订"""
        from app.models.ontology import Reservation

        orm_models = self._db.query(Reservation).filter(
            Reservation.check_in_date >= start_date,
            Reservation.check_in_date <= end_date,
        ).order_by(Reservation.check_in_date).all()
        return [ReservationEntity(m) for m in orm_models]

    def find_arrivals(self, check_in_date: date) -> List[ReservationEntity]:
        """查找指定日期的到达预订"""
        from app.models.ontology import Reservation, ReservationStatus

        orm_models = self._db.query(Reservation).filter(
            Reservation.check_in_date == check_in_date,
            Reservation.status == ReservationStatus.CONFIRMED,
        ).order_by(Reservation.created_at).all()
        return [ReservationEntity(m) for m in orm_models]

    def find_departures(self, check_out_date: date) -> List[ReservationEntity]:
        """查找指定日期的离开预订（已入住状态）"""
        from app.models.ontology import Reservation, ReservationStatus

        orm_models = self._db.query(Reservation).filter(
            Reservation.check_out_date == check_out_date,
            Reservation.status == ReservationStatus.CHECKED_IN,
        ).order_by(Reservation.check_out_date).all()
        return [ReservationEntity(m) for m in orm_models]

    def save(self, reservation: ReservationEntity) -> None:
        """保存预订"""
        self._db.add(reservation._orm_model)
        self._db.commit()

    def list_all(self) -> List[ReservationEntity]:
        """列出所有预订"""
        from app.models.ontology import Reservation

        orm_models = self._db.query(Reservation).order_by(Reservation.created_at.desc()).all()
        return [ReservationEntity(m) for m in orm_models]


# 导出
__all__ = [
    "ReservationState",
    "ReservationEntity",
    "ReservationRepository",
]
