"""
报表服务 - 本体操作层
提供经营数据统计
"""
from typing import List
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.ontology import (
    Room, RoomStatus, StayRecord, StayRecordStatus,
    Payment, RoomType, Reservation, ReservationStatus
)


class ReportService:
    """报表服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_stats(self) -> dict:
        """获取仪表盘统计数据"""
        today = date.today()

        # 房间统计
        rooms = self.db.query(Room).filter(Room.is_active == True).all()
        total_rooms = len(rooms)
        vacant_clean = len([r for r in rooms if r.status == RoomStatus.VACANT_CLEAN])
        occupied = len([r for r in rooms if r.status == RoomStatus.OCCUPIED])
        vacant_dirty = len([r for r in rooms if r.status == RoomStatus.VACANT_DIRTY])
        out_of_order = len([r for r in rooms if r.status == RoomStatus.OUT_OF_ORDER])

        # 今日入住/退房
        today_checkins = self.db.query(StayRecord).filter(
            func.date(StayRecord.check_in_time) == today
        ).count()

        today_checkouts = self.db.query(StayRecord).filter(
            func.date(StayRecord.check_out_time) == today
        ).count()

        # 入住率
        sellable_rooms = total_rooms - out_of_order
        occupancy_rate = (occupied / sellable_rooms * 100) if sellable_rooms > 0 else 0

        # 今日营收
        today_start = datetime.combine(today, datetime.min.time())
        today_end = today_start + timedelta(days=1)
        today_revenue = self.db.query(func.sum(Payment.amount)).filter(
            Payment.payment_time >= today_start,
            Payment.payment_time < today_end
        ).scalar() or Decimal('0')

        return {
            'total_rooms': total_rooms,
            'vacant_clean': vacant_clean,
            'occupied': occupied,
            'vacant_dirty': vacant_dirty,
            'out_of_order': out_of_order,
            'today_checkins': today_checkins,
            'today_checkouts': today_checkouts,
            'occupancy_rate': round(occupancy_rate, 1),
            'today_revenue': today_revenue
        }

    def get_occupancy_report(self, start_date: date, end_date: date) -> List[dict]:
        """获取入住率报表"""
        result = []
        current = start_date
        total_rooms = self.db.query(Room).filter(
            Room.is_active == True,
            Room.status != RoomStatus.OUT_OF_ORDER
        ).count()

        while current <= end_date:
            # 统计当天入住的房间数
            occupied = self.db.query(StayRecord).filter(
                StayRecord.status == StayRecordStatus.ACTIVE,
                func.date(StayRecord.check_in_time) <= current,
                StayRecord.expected_check_out > current
            ).count()

            # 加上当天已退房但之前在住的
            checked_out = self.db.query(StayRecord).filter(
                StayRecord.status == StayRecordStatus.CHECKED_OUT,
                func.date(StayRecord.check_in_time) <= current,
                func.date(StayRecord.check_out_time) == current
            ).count()

            total_occupied = occupied + checked_out
            rate = (total_occupied / total_rooms * 100) if total_rooms > 0 else 0

            result.append({
                'date': current,
                'total_rooms': total_rooms,
                'occupied_rooms': total_occupied,
                'occupancy_rate': round(rate, 1)
            })

            current += timedelta(days=1)

        return result

    def get_revenue_report(self, start_date: date, end_date: date) -> List[dict]:
        """获取营收报表"""
        result = []
        current = start_date

        while current <= end_date:
            day_start = datetime.combine(current, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            payments = self.db.query(Payment).filter(
                Payment.payment_time >= day_start,
                Payment.payment_time < day_end
            ).all()

            total = sum(p.amount for p in payments)

            result.append({
                'date': current,
                'revenue': total,
                'payment_count': len(payments)
            })

            current += timedelta(days=1)

        return result

    def get_room_type_report(self, start_date: date, end_date: date) -> List[dict]:
        """获取房型销售统计"""
        room_types = self.db.query(RoomType).all()
        result = []

        for rt in room_types:
            # 统计该房型的间夜数
            stays = self.db.query(StayRecord).join(Room).filter(
                Room.room_type_id == rt.id,
                StayRecord.check_in_time >= datetime.combine(start_date, datetime.min.time()),
                StayRecord.check_in_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            ).all()

            room_nights = 0
            revenue = Decimal('0')

            for stay in stays:
                check_in = stay.check_in_time.date()
                check_out = stay.check_out_time.date() if stay.check_out_time else stay.expected_check_out
                nights = (check_out - check_in).days
                room_nights += nights

                if stay.bill:
                    revenue += stay.bill.paid_amount

            result.append({
                'room_type_id': rt.id,
                'room_type_name': rt.name,
                'room_nights': room_nights,
                'revenue': revenue
            })

        return result

    def get_today_arrivals_count(self) -> int:
        """今日预抵数"""
        today = date.today()
        return self.db.query(Reservation).filter(
            Reservation.check_in_date == today,
            Reservation.status == ReservationStatus.CONFIRMED
        ).count()

    def get_today_departures_count(self) -> int:
        """今日预离数"""
        today = date.today()
        return self.db.query(StayRecord).filter(
            StayRecord.expected_check_out == today,
            StayRecord.status == StayRecordStatus.ACTIVE
        ).count()
