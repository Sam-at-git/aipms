"""
撤销服务 - 操作回滚功能
支持入住、退房、换房、续住、任务、支付等操作的撤销
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
import uuid
import json
import logging

from app.models.snapshots import OperationSnapshot, OperationType
from app.models.ontology import (
    StayRecord, StayRecordStatus, Room, RoomStatus,
    Reservation, ReservationStatus, Task, TaskStatus, Bill, Payment
)
from app.services.event_bus import event_bus, Event
from app.models.events import EventType, OperationUndoneData

logger = logging.getLogger(__name__)


class UndoService:
    """
    操作撤销服务

    支持依赖注入以便于测试：
    - event_publisher: 事件发布器
    """

    UNDO_WINDOW_HOURS = 24  # 撤销时间窗口

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        self._publish_event = event_publisher or event_bus.publish

    def create_snapshot(
        self,
        operation_type: OperationType,
        entity_type: str,
        entity_id: int,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        operator_id: int,
        related_snapshots: List[str] = None
    ) -> OperationSnapshot:
        """
        创建操作快照

        Args:
            operation_type: 操作类型
            entity_type: 实体类型（stay_record, reservation, task, etc.）
            entity_id: 实体ID
            before_state: 操作前状态
            after_state: 操作后状态
            operator_id: 操作人ID
            related_snapshots: 关联的快照UUID列表

        Returns:
            创建的快照对象
        """
        snapshot = OperationSnapshot(
            snapshot_uuid=str(uuid.uuid4()),
            operation_type=operation_type.value if isinstance(operation_type, OperationType) else operation_type,
            operator_id=operator_id,
            operation_time=datetime.now(),
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=json.dumps(before_state, default=str, ensure_ascii=False),
            after_state=json.dumps(after_state, default=str, ensure_ascii=False),
            related_snapshots=json.dumps(related_snapshots or []),
            expires_at=datetime.now() + timedelta(hours=self.UNDO_WINDOW_HOURS)
        )
        self.db.add(snapshot)
        self.db.flush()

        logger.info(f"Created snapshot {snapshot.snapshot_uuid} for {operation_type}")
        return snapshot

    def get_snapshot(self, snapshot_uuid: str) -> Optional[OperationSnapshot]:
        """根据UUID获取快照"""
        return self.db.query(OperationSnapshot).filter(
            OperationSnapshot.snapshot_uuid == snapshot_uuid
        ).first()

    def get_snapshot_by_id(self, snapshot_id: int) -> Optional[OperationSnapshot]:
        """根据ID获取快照"""
        return self.db.query(OperationSnapshot).filter(
            OperationSnapshot.id == snapshot_id
        ).first()

    def get_undoable_operations(
        self,
        entity_type: str = None,
        entity_id: int = None,
        limit: int = 20
    ) -> List[OperationSnapshot]:
        """
        获取可撤销的操作列表

        Args:
            entity_type: 可选，筛选实体类型
            entity_id: 可选，筛选实体ID
            limit: 返回数量限制

        Returns:
            可撤销的快照列表
        """
        query = self.db.query(OperationSnapshot).filter(
            OperationSnapshot.is_undone == False,
            OperationSnapshot.expires_at > datetime.now()
        )
        if entity_type:
            query = query.filter(OperationSnapshot.entity_type == entity_type)
        if entity_id:
            query = query.filter(OperationSnapshot.entity_id == entity_id)

        return query.order_by(OperationSnapshot.operation_time.desc()).limit(limit).all()

    def get_undo_history(self, limit: int = 50) -> List[OperationSnapshot]:
        """获取撤销历史"""
        return self.db.query(OperationSnapshot).filter(
            OperationSnapshot.is_undone == True
        ).order_by(OperationSnapshot.undone_time.desc()).limit(limit).all()

    def can_undo(self, snapshot: OperationSnapshot) -> tuple[bool, str]:
        """
        检查操作是否可撤销

        Returns:
            (可否撤销, 原因)
        """
        if not snapshot:
            return False, "快照不存在"
        if snapshot.is_undone:
            return False, "操作已撤销"
        if snapshot.expires_at < datetime.now():
            return False, "撤销时间已过期"
        return True, ""

    def undo_operation(self, snapshot_uuid: str, operator_id: int) -> Dict[str, Any]:
        """
        执行撤销操作

        Args:
            snapshot_uuid: 快照UUID
            operator_id: 执行撤销的操作人ID

        Returns:
            撤销结果
        """
        snapshot = self.get_snapshot(snapshot_uuid)

        can_undo, reason = self.can_undo(snapshot)
        if not can_undo:
            raise ValueError(reason)

        # 根据操作类型执行回滚
        result = self._execute_rollback(snapshot)

        # 标记快照为已撤销
        snapshot.is_undone = True
        snapshot.undone_time = datetime.now()
        snapshot.undone_by = operator_id

        # 发布撤销事件
        self._publish_event(Event(
            event_type=EventType.OPERATION_UNDONE,
            timestamp=datetime.now(),
            data=OperationUndoneData(
                snapshot_id=snapshot.snapshot_uuid,
                operation_type=snapshot.operation_type,
                entity_type=snapshot.entity_type,
                entity_id=snapshot.entity_id,
                undone_by=operator_id
            ).to_dict(),
            source="undo_service"
        ))

        logger.info(f"Undone operation {snapshot.snapshot_uuid}")
        return result

    def _execute_rollback(self, snapshot: OperationSnapshot) -> Dict[str, Any]:
        """根据操作类型执行具体回滚逻辑"""
        operation_type = snapshot.operation_type
        before_state = json.loads(snapshot.before_state)

        if operation_type == OperationType.CHECK_IN.value:
            return self._undo_checkin(snapshot, before_state)
        elif operation_type == OperationType.CHECK_OUT.value:
            return self._undo_checkout(snapshot, before_state)
        elif operation_type == OperationType.EXTEND_STAY.value:
            return self._undo_extend_stay(snapshot, before_state)
        elif operation_type == OperationType.CHANGE_ROOM.value:
            return self._undo_change_room(snapshot, before_state)
        elif operation_type == OperationType.COMPLETE_TASK.value:
            return self._undo_complete_task(snapshot, before_state)
        elif operation_type == OperationType.ADD_PAYMENT.value:
            return self._undo_payment(snapshot, before_state)
        else:
            raise ValueError(f"不支持撤销的操作类型: {operation_type}")

    def _undo_checkin(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销入住"""
        stay_record_id = snapshot.entity_id

        # 获取住宿记录
        stay_record = self.db.query(StayRecord).filter(
            StayRecord.id == stay_record_id
        ).first()

        if not stay_record:
            raise ValueError("住宿记录不存在")

        # 1. 删除账单
        if stay_record.bill:
            self.db.delete(stay_record.bill)

        # 2. 恢复房间状态
        room_state = before_state.get('room', {})
        if room_state:
            room = self.db.query(Room).filter(Room.id == room_state.get('id')).first()
            if room:
                room.status = RoomStatus(room_state.get('status', 'vacant_clean'))

        # 3. 如果是预订入住，恢复预订状态
        reservation_state = before_state.get('reservation')
        if reservation_state:
            reservation = self.db.query(Reservation).filter(
                Reservation.id == reservation_state.get('id')
            ).first()
            if reservation:
                reservation.status = ReservationStatus(
                    reservation_state.get('status', 'confirmed')
                )

        # 4. 删除住宿记录
        self.db.delete(stay_record)

        return {
            "message": "入住已撤销",
            "restored_room": room_state.get('room_number')
        }

    def _undo_checkout(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销退房"""
        stay_record_id = snapshot.entity_id

        stay_record = self.db.query(StayRecord).filter(
            StayRecord.id == stay_record_id
        ).first()

        if not stay_record:
            raise ValueError("住宿记录不存在")

        # 1. 恢复住宿记录状态
        stay_record_state = before_state.get('stay_record', {})
        stay_record.status = StayRecordStatus(stay_record_state.get('status', 'active'))
        stay_record.check_out_time = None

        # 2. 恢复房间状态
        room_state = before_state.get('room', {})
        if room_state:
            room = self.db.query(Room).filter(Room.id == room_state.get('id')).first()
            if room:
                room.status = RoomStatus(room_state.get('status', 'occupied'))

        # 3. 删除自动创建的清洁任务
        after_state = json.loads(snapshot.after_state)
        auto_task_id = after_state.get('created_task_id')
        if auto_task_id:
            task = self.db.query(Task).filter(Task.id == auto_task_id).first()
            if task and task.status == TaskStatus.PENDING:
                self.db.delete(task)

        # 4. 恢复预订状态
        if stay_record.reservation:
            stay_record.reservation.status = ReservationStatus.CHECKED_IN

        return {"message": "退房已撤销", "stay_record_id": stay_record_id}

    def _undo_extend_stay(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销续住"""
        stay_record_id = snapshot.entity_id

        stay_record = self.db.query(StayRecord).filter(
            StayRecord.id == stay_record_id
        ).first()

        if not stay_record:
            raise ValueError("住宿记录不存在")

        # 恢复原预计退房日期
        old_check_out = before_state.get('expected_check_out')
        if old_check_out:
            stay_record.expected_check_out = datetime.fromisoformat(old_check_out).date() \
                if isinstance(old_check_out, str) else old_check_out

        # 恢复账单金额
        bill_state = before_state.get('bill', {})
        if bill_state and stay_record.bill:
            stay_record.bill.total_amount = bill_state.get('total_amount', stay_record.bill.total_amount)

        return {"message": "续住已撤销"}

    def _undo_change_room(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销换房"""
        stay_record_id = snapshot.entity_id

        stay_record = self.db.query(StayRecord).filter(
            StayRecord.id == stay_record_id
        ).first()

        if not stay_record:
            raise ValueError("住宿记录不存在")

        # 1. 恢复住宿记录的房间
        stay_record_state = before_state.get('stay_record', {})
        old_room_id = stay_record_state.get('room_id')
        if old_room_id:
            stay_record.room_id = old_room_id

        # 2. 恢复原房间状态
        old_room_state = before_state.get('old_room', {})
        if old_room_state:
            old_room = self.db.query(Room).filter(Room.id == old_room_state.get('id')).first()
            if old_room:
                old_room.status = RoomStatus(old_room_state.get('status', 'occupied'))

        # 3. 恢复新房间状态
        new_room_state = before_state.get('new_room', {})
        if new_room_state:
            new_room = self.db.query(Room).filter(Room.id == new_room_state.get('id')).first()
            if new_room:
                new_room.status = RoomStatus(new_room_state.get('status', 'vacant_clean'))

        return {"message": "换房已撤销"}

    def _undo_complete_task(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销任务完成"""
        task_id = snapshot.entity_id

        task = self.db.query(Task).filter(Task.id == task_id).first()

        if not task:
            raise ValueError("任务不存在")

        # 1. 恢复任务状态
        task_state = before_state.get('task', {})
        task.status = TaskStatus(task_state.get('status', 'in_progress'))
        task.completed_at = None

        # 2. 如果是清洁任务，恢复房间状态
        room_state = before_state.get('room')
        if room_state:
            room = self.db.query(Room).filter(Room.id == room_state.get('id')).first()
            if room:
                room.status = RoomStatus(room_state.get('status', 'vacant_dirty'))

        return {"message": "任务完成已撤销"}

    def _undo_payment(self, snapshot: OperationSnapshot, before_state: dict) -> dict:
        """撤销支付"""
        payment_id = snapshot.entity_id

        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            raise ValueError("支付记录不存在")

        # 1. 恢复账单已付金额
        bill_state = before_state.get('bill', {})
        if bill_state:
            bill = self.db.query(Bill).filter(Bill.id == bill_state.get('id')).first()
            if bill:
                bill.paid_amount = bill_state.get('paid_amount', 0)

        # 2. 删除支付记录
        self.db.delete(payment)

        return {"message": "支付已撤销"}


def create_checkin_snapshot(
    db: Session,
    stay_record: StayRecord,
    room: Room,
    reservation: Reservation = None,
    operator_id: int = None
) -> OperationSnapshot:
    """创建入住操作快照的辅助函数"""
    undo_service = UndoService(db)

    before_state = {
        "room": {
            "id": room.id,
            "room_number": room.room_number,
            "status": room.status.value if hasattr(room.status, 'value') else str(room.status)
        }
    }

    if reservation:
        before_state["reservation"] = {
            "id": reservation.id,
            "status": reservation.status.value if hasattr(reservation.status, 'value') else str(reservation.status)
        }

    after_state = {
        "stay_record_id": stay_record.id,
        "room_status": "occupied"
    }

    return undo_service.create_snapshot(
        operation_type=OperationType.CHECK_IN,
        entity_type="stay_record",
        entity_id=stay_record.id,
        before_state=before_state,
        after_state=after_state,
        operator_id=operator_id or 0
    )


def create_checkout_snapshot(
    db: Session,
    stay_record: StayRecord,
    room: Room,
    created_task_id: int = None,
    operator_id: int = None
) -> OperationSnapshot:
    """创建退房操作快照的辅助函数"""
    undo_service = UndoService(db)

    before_state = {
        "stay_record": {
            "id": stay_record.id,
            "status": stay_record.status.value if hasattr(stay_record.status, 'value') else str(stay_record.status)
        },
        "room": {
            "id": room.id,
            "room_number": room.room_number,
            "status": room.status.value if hasattr(room.status, 'value') else str(room.status)
        }
    }

    after_state = {
        "stay_record_status": "checked_out",
        "room_status": "vacant_dirty",
        "created_task_id": created_task_id
    }

    return undo_service.create_snapshot(
        operation_type=OperationType.CHECK_OUT,
        entity_type="stay_record",
        entity_id=stay_record.id,
        before_state=before_state,
        after_state=after_state,
        operator_id=operator_id or 0
    )
