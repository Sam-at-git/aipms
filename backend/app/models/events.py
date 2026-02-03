"""
领域事件定义 (Domain Events)
遵循事件驱动架构，定义系统中的核心业务事件
"""
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any


class EventType(str, Enum):
    """事件类型枚举"""
    # 房间相关
    ROOM_STATUS_CHANGED = "room.status_changed"
    ROOM_CREATED = "room.created"
    ROOM_UPDATED = "room.updated"

    # 入住相关
    GUEST_CHECKED_IN = "guest.checked_in"
    GUEST_CHECKED_OUT = "guest.checked_out"
    STAY_EXTENDED = "stay.extended"
    ROOM_CHANGED = "stay.room_changed"

    # 预订相关
    RESERVATION_CREATED = "reservation.created"
    RESERVATION_CANCELLED = "reservation.cancelled"
    RESERVATION_CONFIRMED = "reservation.confirmed"

    # 任务相关
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"

    # 账单相关
    BILL_CREATED = "bill.created"
    PAYMENT_RECEIVED = "payment.received"
    BILL_ADJUSTED = "bill.adjusted"

    # 操作相关
    OPERATION_EXECUTED = "operation.executed"
    OPERATION_UNDONE = "operation.undone"

    # 安全相关
    SECURITY_EVENT = "security.event"


@dataclass
class BaseEventData:
    """事件数据基类"""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        # 处理 datetime 序列化
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        return result


@dataclass
class RoomStatusChangedData(BaseEventData):
    """房间状态变更事件数据"""
    room_id: int = 0
    room_number: str = ""
    old_status: str = ""
    new_status: str = ""
    changed_by: Optional[int] = None
    changed_by_name: str = ""
    reason: str = ""


@dataclass
class GuestCheckedInData(BaseEventData):
    """客人入住事件数据"""
    stay_record_id: int = 0
    guest_id: int = 0
    guest_name: str = ""
    room_id: int = 0
    room_number: str = ""
    reservation_id: Optional[int] = None
    check_in_time: datetime = field(default_factory=datetime.now)
    expected_check_out: str = ""  # date as string
    operator_id: int = 0
    operator_name: str = ""
    is_walkin: bool = False


@dataclass
class GuestCheckedOutData(BaseEventData):
    """客人退房事件数据"""
    stay_record_id: int = 0
    guest_id: int = 0
    guest_name: str = ""
    room_id: int = 0
    room_number: str = ""
    check_out_time: datetime = field(default_factory=datetime.now)
    total_amount: float = 0.0
    paid_amount: float = 0.0
    operator_id: int = 0
    operator_name: str = ""


@dataclass
class StayExtendedData(BaseEventData):
    """续住事件数据"""
    stay_record_id: int = 0
    guest_id: int = 0
    guest_name: str = ""
    room_id: int = 0
    room_number: str = ""
    old_check_out: str = ""  # date as string
    new_check_out: str = ""  # date as string
    operator_id: int = 0
    operator_name: str = ""


@dataclass
class RoomChangedData(BaseEventData):
    """换房事件数据"""
    stay_record_id: int = 0
    guest_id: int = 0
    guest_name: str = ""
    old_room_id: int = 0
    old_room_number: str = ""
    new_room_id: int = 0
    new_room_number: str = ""
    operator_id: int = 0
    operator_name: str = ""


@dataclass
class ReservationCreatedData(BaseEventData):
    """预订创建事件数据"""
    reservation_id: int = 0
    reservation_no: str = ""
    guest_id: int = 0
    guest_name: str = ""
    room_type_id: int = 0
    room_type_name: str = ""
    check_in_date: str = ""  # date as string
    check_out_date: str = ""  # date as string
    total_amount: float = 0.0
    operator_id: int = 0
    operator_name: str = ""


@dataclass
class ReservationCancelledData(BaseEventData):
    """预订取消事件数据"""
    reservation_id: int = 0
    reservation_no: str = ""
    guest_id: int = 0
    guest_name: str = ""
    cancel_reason: str = ""
    operator_id: int = 0
    operator_name: str = ""


@dataclass
class TaskCreatedData(BaseEventData):
    """任务创建事件数据"""
    task_id: int = 0
    task_type: str = ""
    room_id: int = 0
    room_number: str = ""
    priority: int = 1
    notes: str = ""
    created_by: int = 0
    created_by_name: str = ""
    trigger: str = "manual"  # manual, auto_checkout, auto_maintenance


@dataclass
class TaskAssignedData(BaseEventData):
    """任务分配事件数据"""
    task_id: int = 0
    task_type: str = ""
    room_id: int = 0
    room_number: str = ""
    assignee_id: int = 0
    assignee_name: str = ""
    assigned_by: int = 0
    assigned_by_name: str = ""


@dataclass
class TaskStartedData(BaseEventData):
    """任务开始事件数据"""
    task_id: int = 0
    task_type: str = ""
    room_id: int = 0
    room_number: str = ""
    started_by: int = 0
    started_by_name: str = ""


@dataclass
class TaskCompletedData(BaseEventData):
    """任务完成事件数据"""
    task_id: int = 0
    task_type: str = ""
    room_id: int = 0
    room_number: str = ""
    completed_by: int = 0
    completed_by_name: str = ""
    completion_time: datetime = field(default_factory=datetime.now)


@dataclass
class BillCreatedData(BaseEventData):
    """账单创建事件数据"""
    bill_id: int = 0
    stay_record_id: int = 0
    guest_id: int = 0
    guest_name: str = ""
    room_number: str = ""
    total_amount: float = 0.0


@dataclass
class PaymentReceivedData(BaseEventData):
    """收款事件数据"""
    payment_id: int = 0
    bill_id: int = 0
    stay_record_id: int = 0
    amount: float = 0.0
    method: str = ""
    received_by: int = 0
    received_by_name: str = ""


@dataclass
class BillAdjustedData(BaseEventData):
    """账单调整事件数据"""
    bill_id: int = 0
    stay_record_id: int = 0
    adjustment_amount: float = 0.0
    reason: str = ""
    adjusted_by: int = 0
    adjusted_by_name: str = ""


@dataclass
class OperationExecutedData(BaseEventData):
    """操作执行事件数据（用于撤销功能）"""
    operation_id: str = ""
    operation_type: str = ""
    entity_type: str = ""
    entity_id: int = 0
    operator_id: int = 0
    operator_name: str = ""
    snapshot_id: str = ""  # 关联的快照ID


@dataclass
class OperationUndoneData(BaseEventData):
    """操作撤销事件数据"""
    snapshot_id: str = ""
    operation_type: str = ""
    entity_type: str = ""
    entity_id: int = 0
    undone_by: int = 0
    undone_by_name: str = ""


# 事件数据类型映射
EVENT_DATA_CLASSES = {
    EventType.ROOM_STATUS_CHANGED: RoomStatusChangedData,
    EventType.GUEST_CHECKED_IN: GuestCheckedInData,
    EventType.GUEST_CHECKED_OUT: GuestCheckedOutData,
    EventType.STAY_EXTENDED: StayExtendedData,
    EventType.ROOM_CHANGED: RoomChangedData,
    EventType.RESERVATION_CREATED: ReservationCreatedData,
    EventType.RESERVATION_CANCELLED: ReservationCancelledData,
    EventType.TASK_CREATED: TaskCreatedData,
    EventType.TASK_ASSIGNED: TaskAssignedData,
    EventType.TASK_STARTED: TaskStartedData,
    EventType.TASK_COMPLETED: TaskCompletedData,
    EventType.BILL_CREATED: BillCreatedData,
    EventType.PAYMENT_RECEIVED: PaymentReceivedData,
    EventType.BILL_ADJUSTED: BillAdjustedData,
    EventType.OPERATION_EXECUTED: OperationExecutedData,
    EventType.OPERATION_UNDONE: OperationUndoneData,
}
