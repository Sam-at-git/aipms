"""
退房服务 - 本体操作层
遵循 Palantir 原则：退房联动（CheckoutAction -> Room.status -> Task 自动创建）
"""
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    StayRecord, StayRecordStatus, Room, RoomStatus,
    Reservation, ReservationStatus, Task, TaskType, TaskStatus
)
from app.models.schemas import CheckOutRequest


class CheckOutService:
    """退房服务"""

    def __init__(self, db: Session):
        self.db = db

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
        room.status = RoomStatus.VACANT_DIRTY

        # 自动创建清洁任务
        cleaning_task = Task(
            room_id=room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            priority=2,  # 退房清洁优先级较高
            notes=f"退房清洁 - 原住客: {stay_record.guest.name}",
            created_by=operator_id
        )
        self.db.add(cleaning_task)

        # 更新预订状态
        if stay_record.reservation:
            stay_record.reservation.status = ReservationStatus.COMPLETED

        # 处理押金退还
        if data.refund_deposit > 0:
            if data.refund_deposit > stay_record.deposit_amount:
                raise ValueError("退还押金不能超过原押金金额")
            # 押金退还记录可以在这里添加

        self.db.commit()
        self.db.refresh(stay_record)
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
