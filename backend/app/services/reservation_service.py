"""
预订服务 - 本体操作层
管理 Reservation 对象（预订阶段的聚合根）
"""
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.ontology import (
    Reservation, Guest, RoomType, ReservationStatus
)
from app.models.schemas import ReservationCreate, ReservationUpdate, ReservationCancel
from app.services.price_service import PriceService


class ReservationService:
    """预订服务"""

    def __init__(self, db: Session):
        self.db = db
        self.price_service = PriceService(db)

    def _generate_reservation_no(self) -> str:
        """生成预订号：日期+序号"""
        today = datetime.now().strftime('%Y%m%d')
        count = self.db.query(Reservation).filter(
            Reservation.reservation_no.like(f'{today}%')
        ).count()
        return f'{today}{str(count + 1).zfill(3)}'

    def get_reservations(self, status: Optional[ReservationStatus] = None,
                         check_in_date: Optional[date] = None,
                         guest_name: Optional[str] = None) -> List[Reservation]:
        """获取预订列表"""
        query = self.db.query(Reservation)

        if status:
            query = query.filter(Reservation.status == status)
        if check_in_date:
            query = query.filter(Reservation.check_in_date == check_in_date)
        if guest_name:
            query = query.join(Guest).filter(Guest.name.contains(guest_name))

        return query.order_by(Reservation.check_in_date.desc()).all()

    def get_reservation(self, reservation_id: int) -> Optional[Reservation]:
        """获取单个预订"""
        return self.db.query(Reservation).filter(Reservation.id == reservation_id).first()

    def get_reservation_by_no(self, reservation_no: str) -> Optional[Reservation]:
        """根据预订号获取预订"""
        return self.db.query(Reservation).filter(
            Reservation.reservation_no == reservation_no
        ).first()

    def search_reservations(self, keyword: str) -> List[Reservation]:
        """搜索预订（预订号/客人姓名/手机号）"""
        return self.db.query(Reservation).join(Guest).filter(
            or_(
                Reservation.reservation_no.contains(keyword),
                Guest.name.contains(keyword),
                Guest.phone.contains(keyword)
            )
        ).all()

    def get_today_arrivals(self) -> List[Reservation]:
        """获取今日预抵"""
        today = date.today()
        return self.db.query(Reservation).filter(
            Reservation.check_in_date == today,
            Reservation.status == ReservationStatus.CONFIRMED
        ).all()

    def create_reservation(self, data: ReservationCreate, created_by: int) -> Reservation:
        """创建预订"""
        # 验证房型
        room_type = self.db.query(RoomType).filter(RoomType.id == data.room_type_id).first()
        if not room_type:
            raise ValueError("房型不存在")

        # 验证日期
        if data.check_out_date <= data.check_in_date:
            raise ValueError("离店日期必须晚于入住日期")

        if data.check_in_date < date.today():
            raise ValueError("入住日期不能早于今天")

        # 查找或创建客人
        guest = self.db.query(Guest).filter(Guest.phone == data.guest_phone).first()
        if not guest:
            guest = Guest(
                name=data.guest_name,
                phone=data.guest_phone,
                id_number=data.guest_id_number
            )
            self.db.add(guest)
            self.db.flush()
        else:
            # 更新客人信息
            guest.name = data.guest_name
            if data.guest_id_number:
                guest.id_number = data.guest_id_number

        # 计算预估总价
        total_amount = self.price_service.calculate_total_price(
            data.room_type_id,
            data.check_in_date,
            data.check_out_date,
            data.room_count
        )

        # 创建预订
        reservation = Reservation(
            reservation_no=self._generate_reservation_no(),
            guest_id=guest.id,
            room_type_id=data.room_type_id,
            check_in_date=data.check_in_date,
            check_out_date=data.check_out_date,
            room_count=data.room_count,
            adult_count=data.adult_count,
            child_count=data.child_count,
            total_amount=total_amount,
            prepaid_amount=data.prepaid_amount,
            special_requests=data.special_requests,
            estimated_arrival=data.estimated_arrival,
            created_by=created_by
        )

        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def update_reservation(self, reservation_id: int, data: ReservationUpdate) -> Reservation:
        """更新预订"""
        reservation = self.get_reservation(reservation_id)
        if not reservation:
            raise ValueError("预订不存在")

        if reservation.status not in [ReservationStatus.CONFIRMED]:
            raise ValueError(f"状态为 {reservation.status.value} 的预订不可修改")

        update_data = data.model_dump(exclude_unset=True)

        # 验证房型
        if 'room_type_id' in update_data:
            room_type = self.db.query(RoomType).filter(
                RoomType.id == update_data['room_type_id']
            ).first()
            if not room_type:
                raise ValueError("房型不存在")

        for key, value in update_data.items():
            setattr(reservation, key, value)

        # 重新计算总价
        reservation.total_amount = self.price_service.calculate_total_price(
            reservation.room_type_id,
            reservation.check_in_date,
            reservation.check_out_date,
            reservation.room_count
        )

        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def cancel_reservation(self, reservation_id: int, data: ReservationCancel) -> Reservation:
        """取消预订"""
        reservation = self.get_reservation(reservation_id)
        if not reservation:
            raise ValueError("预订不存在")

        if reservation.status not in [ReservationStatus.CONFIRMED]:
            raise ValueError(f"状态为 {reservation.status.value} 的预订不可取消")

        reservation.status = ReservationStatus.CANCELLED
        reservation.cancel_reason = data.cancel_reason

        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def mark_no_show(self, reservation_id: int) -> Reservation:
        """标记未到"""
        reservation = self.get_reservation(reservation_id)
        if not reservation:
            raise ValueError("预订不存在")

        if reservation.status != ReservationStatus.CONFIRMED:
            raise ValueError("只有已确认的预订可以标记为未到")

        reservation.status = ReservationStatus.NO_SHOW
        self.db.commit()
        self.db.refresh(reservation)
        return reservation

    def get_reservation_detail(self, reservation_id: int) -> dict:
        """获取预订详情（包含关联信息）"""
        reservation = self.get_reservation(reservation_id)
        if not reservation:
            return None

        return {
            'id': reservation.id,
            'reservation_no': reservation.reservation_no,
            'guest_id': reservation.guest_id,
            'guest_name': reservation.guest.name,
            'guest_phone': reservation.guest.phone,
            'guest_id_number': reservation.guest.id_number,
            'room_type_id': reservation.room_type_id,
            'room_type_name': reservation.room_type.name,
            'check_in_date': reservation.check_in_date,
            'check_out_date': reservation.check_out_date,
            'room_count': reservation.room_count,
            'adult_count': reservation.adult_count,
            'child_count': reservation.child_count,
            'status': reservation.status,
            'total_amount': reservation.total_amount,
            'prepaid_amount': reservation.prepaid_amount,
            'special_requests': reservation.special_requests,
            'estimated_arrival': reservation.estimated_arrival,
            'created_at': reservation.created_at
        }
