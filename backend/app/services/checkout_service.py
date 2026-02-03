"""
退房服务 - 本体操作层
遵循事件驱动架构：退房发布事件，由事件处理器自动创建清洁任务
支持操作撤销：关键操作创建快照
"""
from typing import Optional, Callable
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    StayRecord, StayRecordStatus, Room, RoomStatus,
    Reservation, ReservationStatus, Task, TaskType, TaskStatus
)
from app.models.schemas import CheckOutRequest
from app.services.event_bus import event_bus, Event
from app.models.events import EventType, GuestCheckedOutData, RoomStatusChangedData
from app.models.snapshots import OperationType


class CheckOutService:
    """退房服务"""

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        # 支持依赖注入事件发布器，便于测试
        self._publish_event = event_publisher or event_bus.publish

    def check_out(self, data: CheckOutRequest, operator_id: int) -> StayRecord:
        """
        退房操作
        业务联动规则：
        1. 验证账单状态
        2. 更新住宿记录状态
        3. 更新房间状态为脏房
        4. 自动创建清洁任务
        5. 更新预订状态（如有）
        """
        stay_record = self.db.query(StayRecord).filter(
            StayRecord.id == data.stay_record_id
        ).first()
        if not stay_record:
            raise ValueError("住宿记录不存在")

        if stay_record.status != StayRecordStatus.ACTIVE:
            raise ValueError("该住宿记录已退房")

        # 检查账单
        bill = stay_record.bill
        if bill:
            balance = bill.total_amount + bill.adjustment_amount - bill.paid_amount
            if balance > 0 and not data.allow_unsettled:
                raise ValueError(f"账单未结清，余额 {balance} 元。如需挂账退房请确认")

            if data.allow_unsettled and balance > 0:
                if not data.unsettled_reason:
                    raise ValueError("挂账退房需要填写原因")

            bill.is_settled = (balance <= 0)

        # 更新住宿记录
        stay_record.status = StayRecordStatus.CHECKED_OUT
        stay_record.check_out_time = datetime.now()

        # 更新房间状态为脏房
        room = stay_record.room
        old_room_status = room.status
        room.status = RoomStatus.VACANT_DIRTY

        # 更新预订状态
        if stay_record.reservation:
            stay_record.reservation.status = ReservationStatus.COMPLETED

        # 处理押金退还
        if data.refund_deposit > 0:
            if data.refund_deposit > stay_record.deposit_amount:
                raise ValueError("退还押金不能超过原押金金额")
            # 押金退还记录可以在这里添加

        # 保存客人信息用于事件和快照
        guest_name = stay_record.guest.name
        guest_id = stay_record.guest_id
        room_number = room.room_number
        room_id = room.id

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_OUT,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "stay_record": {
                    "id": stay_record.id,
                    "status": StayRecordStatus.ACTIVE.value
                },
                "room": {
                    "id": room_id,
                    "room_number": room_number,
                    "status": old_room_status.value
                }
            },
            after_state={
                "stay_record_status": StayRecordStatus.CHECKED_OUT.value,
                "room_status": RoomStatus.VACANT_DIRTY.value,
                "created_task_id": None  # 将在事件处理器中更新
            },
            operator_id=operator_id
        )

        self.db.commit()
        self.db.refresh(stay_record)

        # 发布退房事件（事件处理器会自动创建清洁任务）
        self._publish_event(Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data=GuestCheckedOutData(
                stay_record_id=stay_record.id,
                guest_id=guest_id,
                guest_name=guest_name,
                room_id=room_id,
                room_number=room_number,
                check_out_time=stay_record.check_out_time,
                total_amount=float(bill.total_amount) if bill else 0.0,
                paid_amount=float(bill.paid_amount) if bill else 0.0,
                operator_id=operator_id
            ).to_dict(),
            source="checkout_service"
        ))

        return stay_record

    def batch_check_out(self, stay_record_ids: list, operator_id: int) -> list:
        """批量退房"""
        results = []
        for stay_id in stay_record_ids:
            try:
                data = CheckOutRequest(
                    stay_record_id=stay_id,
                    allow_unsettled=False
                )
                result = self.check_out(data, operator_id)
                results.append({
                    'stay_record_id': stay_id,
                    'success': True,
                    'message': '退房成功'
                })
            except ValueError as e:
                results.append({
                    'stay_record_id': stay_id,
                    'success': False,
                    'message': str(e)
                })
        return results

    def get_today_expected_checkouts(self) -> list:
        """获取今日预计退房"""
        from datetime import date
        today = date.today()
        return self.db.query(StayRecord).filter(
            StayRecord.status == StayRecordStatus.ACTIVE,
            StayRecord.expected_check_out == today
        ).all()

    def get_overdue_stays(self) -> list:
        """获取逾期未退房"""
        from datetime import date
        today = date.today()
        return self.db.query(StayRecord).filter(
            StayRecord.status == StayRecordStatus.ACTIVE,
            StayRecord.expected_check_out < today
        ).all()
