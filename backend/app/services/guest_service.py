"""
客人服务 - 本体操作层 + CRM功能
管理 Guest 对象和客户关系
"""
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from app.models.ontology import Guest, GuestTier, StayRecord, Reservation
from app.models.schemas import GuestCreate, GuestUpdate
import json


class GuestService:
    """客人服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_guests(
        self,
        search: Optional[str] = None,
        tier: Optional[GuestTier] = None,
        is_blacklisted: Optional[bool] = None,
        limit: int = 100
    ) -> List[Guest]:
        """获取客人列表"""
        query = self.db.query(Guest)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Guest.name.like(search_pattern),
                    Guest.phone.like(search_pattern),
                    Guest.id_number.like(search_pattern)
                )
            )

        if tier:
            query = query.filter(Guest.tier == tier)

        if is_blacklisted is not None:
            query = query.filter(Guest.is_blacklisted == is_blacklisted)

        return query.order_by(desc(Guest.created_at)).limit(limit).all()

    def get_guest(self, guest_id: int) -> Optional[Guest]:
        """获取单个客人"""
        return self.db.query(Guest).filter(Guest.id == guest_id).first()

    def get_guest_by_phone(self, phone: str) -> Optional[Guest]:
        """根据手机号获取客人"""
        return self.db.query(Guest).filter(Guest.phone == phone).first()

    def get_guest_by_id_number(self, id_number: str) -> Optional[Guest]:
        """根据证件号获取客人"""
        return self.db.query(Guest).filter(Guest.id_number == id_number).first()

    def create_guest(self, data: GuestCreate) -> Guest:
        """创建客人"""
        guest = Guest(**data.model_dump())
        self.db.add(guest)
        self.db.commit()
        self.db.refresh(guest)
        return guest

    def update_guest(self, guest_id: int, data: GuestUpdate) -> Guest:
        """更新客人信息"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(guest, key, value)

        self.db.commit()
        self.db.refresh(guest)
        return guest

    def get_or_create_guest(self, name: str, phone: str, **kwargs) -> Guest:
        """获取或创建客人（用于入住/预订时）"""
        guest = self.get_guest_by_phone(phone)
        if not guest:
            create_data = GuestCreate(name=name, phone=phone, **kwargs)
            guest = self.create_guest(create_data)
        return guest

    def get_guest_stay_history(self, guest_id: int, limit: int = 10) -> List[dict]:
        """获取客人入住历史"""
        stays = self.db.query(StayRecord).filter(
            StayRecord.guest_id == guest_id
        ).order_by(desc(StayRecord.check_in_time)).limit(limit).all()

        return [
            {
                "id": s.id,
                "room_number": s.room.room_number,
                "room_type": s.room.room_type.name,
                "check_in_time": s.check_in_time,
                "check_out_time": s.check_out_time,
                "status": s.status
            }
            for s in stays
        ]

    def get_guest_reservation_history(self, guest_id: int, limit: int = 10) -> List[dict]:
        """获取客人预订历史"""
        reservations = self.db.query(Reservation).filter(
            Reservation.guest_id == guest_id
        ).order_by(desc(Reservation.created_at)).limit(limit).all()

        return [
            {
                "id": r.id,
                "reservation_no": r.reservation_no,
                "room_type": r.room_type.name,
                "check_in_date": r.check_in_date,
                "check_out_date": r.check_out_date,
                "status": r.status,
                "created_at": r.created_at
            }
            for r in reservations
        ]

    def get_guest_stats(self, guest_id: int) -> dict:
        """获取客人统计信息"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        # 预订数量
        reservation_count = self.db.query(Reservation).filter(
            Reservation.guest_id == guest_id
        ).count()

        # 最后入住日期和房型
        last_stay = self.db.query(StayRecord).filter(
            StayRecord.guest_id == guest_id,
            StayRecord.status == "checked_out"
        ).order_by(desc(StayRecord.check_out_time)).first()

        last_stay_date = last_stay.check_out_time.date() if last_stay else None
        last_room_type = last_stay.room.room_type.name if last_stay else None

        return {
            "reservation_count": reservation_count,
            "total_stays": guest.total_stays,
            "total_amount": float(guest.total_amount) if guest.total_amount else 0,
            "tier": guest.tier,
            "last_stay_date": last_stay_date,
            "last_room_type": last_room_type
        }

    def update_tier(self, guest_id: int, tier: GuestTier) -> Guest:
        """更新客人等级"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        guest.tier = tier
        self.db.commit()
        self.db.refresh(guest)
        return guest

    def add_to_blacklist(self, guest_id: int, reason: str) -> Guest:
        """添加到黑名单"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        guest.is_blacklisted = True
        guest.blacklist_reason = reason
        self.db.commit()
        self.db.refresh(guest)
        return guest

    def remove_from_blacklist(self, guest_id: int) -> Guest:
        """从黑名单移除"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        guest.is_blacklisted = False
        guest.blacklist_reason = None
        self.db.commit()
        self.db.refresh(guest)
        return guest

    def update_preferences(self, guest_id: int, preferences: dict) -> Guest:
        """更新客人偏好"""
        guest = self.get_guest(guest_id)
        if not guest:
            raise ValueError("客人不存在")

        # 合并现有偏好
        existing_prefs = {}
        if guest.preferences:
            try:
                existing_prefs = json.loads(guest.preferences)
            except:
                pass

        existing_prefs.update(preferences)
        guest.preferences = json.dumps(existing_prefs, ensure_ascii=False)

        self.db.commit()
        self.db.refresh(guest)
        return guest

    def increment_stays(self, guest_id: int, amount: float = 0):
        """增加入住次数和累计消费（入住时调用）"""
        guest = self.get_guest(guest_id)
        if guest:
            guest.total_stays = (guest.total_stays or 0) + 1
            if amount:
                guest.total_amount = (guest.total_amount or 0) + amount

            # 自动升级等级
            self._auto_upgrade_tier(guest)

            self.db.commit()

    def _auto_upgrade_tier(self, guest: Guest):
        """根据消费自动升级等级"""
        total = float(guest.total_amount or 0)

        if total >= 50000:
            guest.tier = GuestTier.PLATINUM
        elif total >= 20000:
            guest.tier = GuestTier.GOLD
        elif total >= 5000:
            guest.tier = GuestTier.SILVER
        else:
            if guest.tier in [GuestTier.PLATINUM, GuestTier.GOLD]:
                # 保持已有等级
                pass
            else:
                guest.tier = GuestTier.NORMAL
