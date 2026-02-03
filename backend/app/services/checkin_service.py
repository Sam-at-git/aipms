"""
入住服务 - 本体操作层
管理 StayRecord 对象（住宿期间的聚合根）
遵循 OODA 循环：入住操作需要人类确认
支持事件驱动：发布入住、续住、换房等领域事件
支持操作撤销：关键操作创建快照
"""
from typing import List, Optional, Callable
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    StayRecord, StayRecordStatus, Reservation, ReservationStatus,
    Room, RoomStatus, Guest, Bill
)
from app.models.schemas import CheckInFromReservation, WalkInCheckIn, ExtendStay, ChangeRoom
from app.services.price_service import PriceService
from app.services.param_parser_service import ParamParserService
from app.services.event_bus import event_bus, Event
from app.models.events import (
    EventType, GuestCheckedInData, StayExtendedData, RoomChangedData,
    RoomStatusChangedData, BillCreatedData
)
from app.models.snapshots import OperationType


class CheckInService:
    """入住服务"""

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        self.price_service = PriceService(db)
        self.param_parser = ParamParserService(db)
        # 支持依赖注入事件发布器，便于测试
        self._publish_event = event_publisher or event_bus.publish

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
        old_room_status = room.status
        room.status = RoomStatus.OCCUPIED

        # 更新预订状态
        reservation.status = ReservationStatus.CHECKED_IN

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "room": {
                    "id": room.id,
                    "room_number": room.room_number,
                    "status": old_room_status.value
                },
                "reservation": {
                    "id": reservation.id,
                    "status": ReservationStatus.CONFIRMED.value
                }
            },
            after_state={
                "stay_record_id": stay_record.id,
                "room_status": RoomStatus.OCCUPIED.value
            },
            operator_id=operator_id
        )

        self.db.commit()
        self.db.refresh(stay_record)

        # 发布入住事件
        self._publish_event(Event(
            event_type=EventType.GUEST_CHECKED_IN,
            timestamp=datetime.now(),
            data=GuestCheckedInData(
                stay_record_id=stay_record.id,
                guest_id=reservation.guest_id,
                guest_name=reservation.guest.name,
                room_id=room.id,
                room_number=room.room_number,
                reservation_id=reservation.id,
                check_in_time=stay_record.check_in_time,
                expected_check_out=str(stay_record.expected_check_out),
                operator_id=operator_id,
                is_walkin=False
            ).to_dict(),
            source="checkin_service"
        ))

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

        # 解析离店日期（支持相对日期）
        print(f"DEBUG walkin_checkin: expected_check_out={data.expected_check_out}, type={type(data.expected_check_out)}, today={date.today()}")

        checkout_result = self.param_parser.parse_date(data.expected_check_out)
        print(f"DEBUG walkin_checkin: parse_result.value={checkout_result.value}, confidence={checkout_result.confidence}")

        if checkout_result.confidence == 0:
            raise ValueError(f"无法理解离店日期：{data.expected_check_out}。请使用格式如：明天、后天、2026-02-11")

        expected_check_out = checkout_result.value
        print(f"DEBUG walkin_checkin: final expected_check_out={expected_check_out}, compare with today: {expected_check_out > date.today()}")

        # 验证日期
        if expected_check_out <= date.today():
            raise ValueError(f"离店日期必须晚于今天（输入: {data.expected_check_out}, 解析: {expected_check_out.isoformat()}）")

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
            expected_check_out=expected_check_out,
            deposit_amount=data.deposit_amount,
            created_by=operator_id
        )
        self.db.add(stay_record)
        self.db.flush()

        # 创建账单
        total_amount = self.price_service.calculate_total_price(
            room.room_type_id,
            date.today(),
            expected_check_out
        )
        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=total_amount
        )
        self.db.add(bill)

        # 更新房间状态
        old_room_status = room.status
        room.status = RoomStatus.OCCUPIED

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "room": {
                    "id": room.id,
                    "room_number": room.room_number,
                    "status": old_room_status.value
                }
            },
            after_state={
                "stay_record_id": stay_record.id,
                "room_status": RoomStatus.OCCUPIED.value
            },
            operator_id=operator_id
        )

        self.db.commit()
        self.db.refresh(stay_record)

        # 发布入住事件
        self._publish_event(Event(
            event_type=EventType.GUEST_CHECKED_IN,
            timestamp=datetime.now(),
            data=GuestCheckedInData(
                stay_record_id=stay_record.id,
                guest_id=guest.id,
                guest_name=guest.name,
                room_id=room.id,
                room_number=room.room_number,
                reservation_id=None,
                check_in_time=stay_record.check_in_time,
                expected_check_out=str(stay_record.expected_check_out),
                operator_id=operator_id,
                is_walkin=True
            ).to_dict(),
            source="checkin_service"
        ))

        return stay_record

    def extend_stay(self, stay_record_id: int, data: ExtendStay, operator_id: int = None) -> StayRecord:
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

        # 保存快照所需的旧状态
        old_date = stay_record.expected_check_out
        old_bill_amount = float(stay_record.bill.total_amount) if stay_record.bill else 0

        # 更新离店日期
        stay_record.expected_check_out = data.new_check_out_date

        # 计算新增房费
        additional_amount = self.price_service.calculate_total_price(
            stay_record.room.room_type_id,
            old_date,
            data.new_check_out_date
        )
        stay_record.bill.total_amount += additional_amount

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        undo_service.create_snapshot(
            operation_type=OperationType.EXTEND_STAY,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "expected_check_out": str(old_date),
                "bill": {
                    "total_amount": old_bill_amount
                }
            },
            after_state={
                "expected_check_out": str(data.new_check_out_date),
                "bill": {
                    "total_amount": float(stay_record.bill.total_amount)
                }
            },
            operator_id=operator_id or 0
        )

        self.db.commit()
        self.db.refresh(stay_record)

        # 发布续住事件
        self._publish_event(Event(
            event_type=EventType.STAY_EXTENDED,
            timestamp=datetime.now(),
            data=StayExtendedData(
                stay_record_id=stay_record.id,
                guest_id=stay_record.guest_id,
                guest_name=stay_record.guest.name,
                room_id=stay_record.room_id,
                room_number=stay_record.room.room_number,
                old_check_out=str(old_date),
                new_check_out=str(data.new_check_out_date),
                operator_id=operator_id or 0
            ).to_dict(),
            source="checkin_service"
        ))

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

        # 保存快照所需的旧状态
        old_room_status = old_room.status.value
        new_room_status = new_room.status.value
        old_room_id = old_room.id

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

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        undo_service.create_snapshot(
            operation_type=OperationType.CHANGE_ROOM,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "stay_record": {
                    "room_id": old_room_id
                },
                "old_room": {
                    "id": old_room.id,
                    "room_number": old_room.room_number,
                    "status": old_room_status
                },
                "new_room": {
                    "id": new_room.id,
                    "room_number": new_room.room_number,
                    "status": new_room_status
                }
            },
            after_state={
                "stay_record": {
                    "room_id": new_room.id
                },
                "old_room_status": RoomStatus.VACANT_DIRTY.value,
                "new_room_status": RoomStatus.OCCUPIED.value
            },
            operator_id=operator_id
        )

        self.db.commit()
        self.db.refresh(stay_record)

        # 发布换房事件
        self._publish_event(Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data=RoomChangedData(
                stay_record_id=stay_record.id,
                guest_id=stay_record.guest_id,
                guest_name=stay_record.guest.name,
                old_room_id=old_room.id,
                old_room_number=old_room.room_number,
                new_room_id=new_room.id,
                new_room_number=new_room.room_number,
                operator_id=operator_id
            ).to_dict(),
            source="checkin_service"
        ))

        # 发布原房间状态变更事件（用于触发清洁任务）
        self._publish_event(Event(
            event_type=EventType.ROOM_STATUS_CHANGED,
            timestamp=datetime.now(),
            data=RoomStatusChangedData(
                room_id=old_room.id,
                room_number=old_room.room_number,
                old_status=RoomStatus.OCCUPIED.value,
                new_status=RoomStatus.VACANT_DIRTY.value,
                changed_by=operator_id,
                reason="换房"
            ).to_dict(),
            source="checkin_service"
        ))

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
