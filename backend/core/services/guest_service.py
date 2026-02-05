"""
Guest Service Adapter - 集成新领域层与现有服务

这个服务适配器提供了使用新领域实体（GuestEntity, GuestRepository）的接口，
同时保持与现有 API 的兼容性。
"""
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
import json

from core.domain.guest import GuestEntity, GuestRepository, GuestTier as DomainGuestTier
from core.domain.relationships import relationship_registry
from app.models.ontology import Guest, GuestTier, StayRecord, Reservation
from app.models.schemas import GuestCreate, GuestUpdate


class GuestServiceV2:
    """
    客人服务 V2 - 使用新领域层

    主要变化:
    1. 使用 GuestRepository 进行数据访问
    2. 使用 GuestEntity 进行业务操作
    3. 保留 CRM 功能
    4. 支持本体关系查询
    """

    def __init__(self, db: Session):
        self.db = db
        self._guest_repo = GuestRepository(db)

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

    def get_guest_entity(self, guest_id: int) -> Optional[GuestEntity]:
        """获取客人领域实体 (新方法)"""
        return self._guest_repo.get_by_id(guest_id)

    def get_guest_by_phone(self, phone: str) -> Optional[Guest]:
        """根据手机号获取客人"""
        return self._guest_repo.get_by_phone(phone)

    def get_guest_by_id_number(self, id_number: str) -> Optional[Guest]:
        """根据证件号获取客人"""
        return self._guest_repo.get_by_id_number(id_number)

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

        reservation_count = self.db.query(Reservation).filter(
            Reservation.guest_id == guest_id
        ).count()

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

    # ============== 使用领域实体的业务方法 ==============

    def update_tier(self, guest_id: int, tier: GuestTier) -> Guest:
        """更新客人等级 (使用领域实体)"""
        entity = self.get_guest_entity(guest_id)
        if not entity:
            raise ValueError("客人不存在")

        entity.update_tier(tier.value)
        self.db.commit()
        self.db.refresh(entity._orm_model)
        return entity._orm_model

    def add_to_blacklist(self, guest_id: int, reason: str) -> Guest:
        """添加到黑名单 (使用领域实体)"""
        entity = self.get_guest_entity(guest_id)
        if not entity:
            raise ValueError("客人不存在")

        entity.add_to_blacklist(reason)
        self.db.commit()
        self.db.refresh(entity._orm_model)
        return entity._orm_model

    def remove_from_blacklist(self, guest_id: int) -> Guest:
        """从黑名单移除 (使用领域实体)"""
        entity = self.get_guest_entity(guest_id)
        if not entity:
            raise ValueError("客人不存在")

        entity.remove_from_blacklist()
        self.db.commit()
        self.db.refresh(entity._orm_model)
        return entity._orm_model

    def update_preferences(self, guest_id: int, preferences: dict) -> Guest:
        """更新客人偏好 (使用领域实体)"""
        import json
        entity = self.get_guest_entity(guest_id)
        if not entity:
            raise ValueError("客人不存在")

        # 将 dict 转换为 JSON 字符串存储
        preferences_json = json.dumps(preferences) if preferences else None
        entity.update_preferences(preferences_json)
        self.db.commit()
        self.db.refresh(entity._orm_model)
        return entity._orm_model

    def increment_stays(self, guest_id: int, amount: float = 0):
        """增加入住次数和累计消费 (使用领域实体)"""
        entity = self.get_guest_entity(guest_id)
        if entity:
            entity.increment_stays()
            if amount:
                entity.add_amount(amount)

            # 自动升级等级
            self._auto_upgrade_tier(entity)

            self.db.commit()

    def _auto_upgrade_tier(self, entity: GuestEntity):
        """根据消费自动升级等级"""
        total = float(entity.total_amount or 0)

        if total >= 50000:
            entity.update_tier(DomainGuestTier.PLATINUM)
        elif total >= 20000:
            entity.update_tier(DomainGuestTier.GOLD)
        elif total >= 5000:
            entity.update_tier(DomainGuestTier.SILVER)
        else:
            if entity.tier not in [DomainGuestTier.PLATINUM, DomainGuestTier.GOLD]:
                entity.update_tier(DomainGuestTier.NORMAL)

    # ============== 本体关系查询 (新增) ==============

    def get_guest_relationships(self, guest_id: int) -> dict:
        """获取客人的关系网络"""
        entity = self.get_guest_entity(guest_id)
        if not entity:
            return None

        return relationship_registry.get_relationships("Guest")

    def get_linked_entities(self, guest_id: int) -> dict:
        """获取客人关联的实体"""
        entity = self.get_guest_entity(guest_id)
        if not entity:
            return None

        return relationship_registry.get_linked_entities(entity, self.db)

    def get_vip_guests(self, threshold: str = "silver") -> List[GuestEntity]:
        """获取 VIP 客人列表 (新方法)"""
        return self._guest_repo.find_vip_guests(threshold)

    def get_blacklisted_guests(self) -> List[GuestEntity]:
        """获取黑名单客人 (新方法)"""
        return self._guest_repo.find_blacklisted()

    def search_by_name(self, name: str) -> List[GuestEntity]:
        """按姓名搜索客人 (新方法)"""
        return self._guest_repo.search_by_name(name)


def get_guest_service_v2(db: Session) -> GuestServiceV2:
    """获取 GuestServiceV2 实例"""
    return GuestServiceV2(db)


__all__ = ["GuestServiceV2", "get_guest_service_v2"]
