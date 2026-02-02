"""
入住服务 - 本体操作层
管理 StayRecord 对象（住宿期间的聚合根）
遵循 OODA 循环：入住操作需要人类确认
"""
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    StayRecord, StayRecordStatus, Reservation, ReservationStatus,
    Room, RoomStatus, Guest, Bill
)
from app.models.schemas import CheckInFromReservation, WalkInCheckIn, ExtendStay, ChangeRoom
from app.services.price_service import PriceService


class CheckInService:
    """入住服务"""

    def __init__(self, db: Session):
        self.db = db
        self.price_service = PriceService(db)

    def get_active_stays(self) -> List[StayRecord]:
        """获取所有在住记录"""
        return self.db.query(StayRecord).filter(
            StayRecord.status == StayRecordStatus.ACTIVE
        ).all()

    def get_stay_record(self, stay_record_id: int) -> Optional[StayRecord]:
        """获取单个住宿记录"""
        return self.db.query(StayRecord).filter(StayRecord.id == stay_record_id).first()

    def get_stay_by_room(self, room_id: int) -> Optional[StayRecord]:
        """根据房间获取当前住宿记录"""
        return self.db.query(StayRecord).filter(
            StayRecord.room_id == room_id,
            StayRecord.status == StayRecordStatus.ACTIVE
        ).first()

    def search_active_stays(self, keyword: str) -> List[StayRecord]:
        """搜索在住客人（房间号/客人姓名）"""
        return self.db.query(StayRecord).join(Guest).join(Room).filter(
            StayRecord.status == StayRecordStatus.ACTIVE
        ).filter(
            (Guest.name.contains(keyword)) | (Room.room_number.contains(keyword))
        ).all()

    def check_in_from_reservation(self, data: CheckInFromReservation,
                                   operator_id: int) -> StayRecord:
        """
        预订入住
        业务规则：
        - 验证预订状态
        - 验证房间状态
        - 创建住宿记录和账单
        - 更新房间状态为入住
        - 更新预订状态为已入住
        """
        # 获取预订
        reservation = self.db.query(Reservation).filter(
            Reservation.id == data.reservation_id
        ).first()
        if not reservation:
            raise ValueError("预订不存在")

        if reservation.status != ReservationStatus.CONFIRMED:
            raise ValueError(f"预订状态为 {reservation.status.value}，无法办理入住")

        # 获取房间
        room = self.db.query(Room).filter(Room.id == data.room_id).first()
        if not room:
            raise ValueError("房间不存在")

        if room.status not in [RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]:
            raise ValueError(f"房间状态为 {room.status.value}，无法入住")

        if room.room_type_id != reservation.room_type_id:
            raise ValueError("房间类型与预订不符")

        # 更新客人证件信息
        if data.guest_id_number:
            reservation.guest.id_number = data.guest_id_number

        # 创建住宿记录
        stay_record = StayRecord(
            reservation_id=reservation.id,
            guest_id=reservation.guest_id,
            room_id=room.id,
            check_in_time=datetime.now(),
            expected_check_out=reservation.check_out_date,
            deposit_amount=data.deposit_amount,
            created_by=operator_id
        )
        self.db.add(stay_record)
        self.db.flush()

        # 创建账单
        total_amount = self.price_service.calculate_total_price(
            room.room_type_id,
            date.today(),
            reservation.check_out_date
        )
        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=total_amount,
            paid_amount=reservation.prepaid_amount
        )
        self.db.add(bill)

        # 更新房间状态
        room.status = RoomStatus.OCCUPIED

        # 更新预订状态
        reservation.status = ReservationStatus.CHECKED_IN

        self.db.commit()
        self.db.refresh(stay_record)
        return stay_record

    def walk_in_check_in(self, data: WalkInCheckIn, operator_id: int) -> StayRecord:
        """
        散客入住（Walk-in）
        业务规则：
        - 验证房间状态
        - 创建或更新客人信息
        - 创建住宿记录和账单
        - 更新房间状态为入住
        """
        # 获取房间
        room = self.db.query(Room).filter(Room.id == data.room_id).first()
        if not room:
            raise ValueError("房间不存在")

        if room.status not in [RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]:
            raise ValueError(f"房间状态为 {room.status.value}，无法入住")

        # 验证日期
        if data.expected_check_out <= date.today():
            raise ValueError("离店日期必须晚于今天")

        # 查找或创建客人
        guest = self.db.query(Guest).filter(Guest.phone == data.guest_phone).first()
        if not guest:
            guest = Guest(
                name=data.guest_name,
                phone=data.guest_phone,
                id_type=data.guest_id_type,
                id_number=data.guest_id_number
            )
            self.db.add(guest)
            self.db.flush()
        else:
            guest.name = data.guest_name
            guest.id_type = data.guest_id_type
            guest.id_number = data.guest_id_number

        # 创建住宿记录
        stay_record = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(),
            expected_check_out=data.expected_check_out,
            deposit_amount=data.deposit_amount,
            created_by=operator_id
        )
        self.db.add(stay_record)
        self.db.flush()

        # 创建账单
        total_amount = self.price_service.calculate_total_price(
            room.room_type_id,
            date.today(),
            data.expected_check_out
        )
        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=total_amount
        )
        self.db.add(bill)

        # 更新房间状态
        room.status = RoomStatus.OCCUPIED

        self.db.commit()
        self.db.refresh(stay_record)
        return stay_record

    def extend_stay(self, stay_record_id: int, data: ExtendStay) -> StayRecord:
        """
        续住
        业务规则：
        - 验证新日期有效性
        - 检查房间可用性
        - 更新离店日期
        - 重新计算房费
        """
        stay_record = self.get_stay_record(stay_record_id)
        if not stay_record:
            raise ValueError("住宿记录不存在")

        if stay_record.status != StayRecordStatus.ACTIVE:
            raise ValueError("该住宿记录已退房")

        if data.new_check_out_date <= stay_record.expected_check_out:
            raise ValueError("新离店日期必须晚于原离店日期")

        # 更新离店日期
        old_date = stay_record.expected_check_out
        stay_record.expected_check_out = data.new_check_out_date

        # 计算新增房费
        additional_amount = self.price_service.calculate_total_price(
            stay_record.room.room_type_id,
            old_date,
            data.new_check_out_date
        )
        stay_record.bill.total_amount += additional_amount

        self.db.commit()
        self.db.refresh(stay_record)
        return stay_record

    def change_room(self, stay_record_id: int, data: ChangeRoom,
                    operator_id: int) -> StayRecord:
        """
        换房
        业务规则：
        - 验证新房间可用
        - 原房间变为脏房
        - 新房间变为入住
        - 如果房型不同，重新计算房费
        """
        stay_record = self.get_stay_record(stay_record_id)
        if not stay_record:
            raise ValueError("住宿记录不存在")

        if stay_record.status != StayRecordStatus.ACTIVE:
            raise ValueError("该住宿记录已退房")

        # 获取新房间
        new_room = self.db.query(Room).filter(Room.id == data.new_room_id).first()
        if not new_room:
            raise ValueError("新房间不存在")

        if new_room.status not in [RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]:
            raise ValueError(f"新房间状态为 {new_room.status.value}，无法换入")

        old_room = stay_record.room
        old_room_type_id = old_room.room_type_id

        # 原房间变为脏房
        old_room.status = RoomStatus.VACANT_DIRTY

        # 新房间变为入住
        new_room.status = RoomStatus.OCCUPIED
        stay_record.room_id = new_room.id

        # 如果房型不同，重新计算剩余天数的房费
        if new_room.room_type_id != old_room_type_id:
            remaining_amount = self.price_service.calculate_total_price(
                new_room.room_type_id,
                date.today(),
                stay_record.expected_check_out
            )
            # 计算已消费天数的房费
            consumed_amount = self.price_service.calculate_total_price(
                old_room_type_id,
                stay_record.check_in_time.date(),
                date.today()
            )
            stay_record.bill.total_amount = consumed_amount + remaining_amount

        # 创建原房间的清洁任务（在 checkout_service 中处理更合适，这里简化）

        self.db.commit()
        self.db.refresh(stay_record)
        return stay_record

    def get_stay_detail(self, stay_record_id: int) -> dict:
        """获取住宿详情"""
        stay = self.get_stay_record(stay_record_id)
        if not stay:
            return None

        return {
            'id': stay.id,
            'reservation_id': stay.reservation_id,
            'guest_id': stay.guest_id,
            'guest_name': stay.guest.name,
            'guest_phone': stay.guest.phone,
            'guest_id_number': stay.guest.id_number,
            'room_id': stay.room_id,
            'room_number': stay.room.room_number,
            'room_type_name': stay.room.room_type.name,
            'check_in_time': stay.check_in_time,
            'check_out_time': stay.check_out_time,
            'expected_check_out': stay.expected_check_out,
            'deposit_amount': stay.deposit_amount,
            'status': stay.status,
            'bill_total': stay.bill.total_amount if stay.bill else Decimal('0'),
            'bill_paid': stay.bill.paid_amount if stay.bill else Decimal('0'),
            'bill_balance': stay.bill.balance if stay.bill else Decimal('0')
        }
