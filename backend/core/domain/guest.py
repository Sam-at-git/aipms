"""
core/domain/guest.py

Guest 领域实体 - OODA 运行时的领域层
封装现有 ORM 模型，添加框架功能
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
import logging

from core.ontology.base import BaseEntity
from app.services.metadata import ontology_entity, ontology_action

if TYPE_CHECKING:
    from app.models.ontology import Guest

logger = logging.getLogger(__name__)


# ============== 客户等级定义 ==============

class GuestTier(str):
    """客户等级"""
    NORMAL = "normal"       # 普通
    SILVER = "silver"       # 银卡
    GOLD = "gold"           # 金卡
    PLATINUM = "platinum"   # 白金


# ============== Guest 领域实体 ==============

@ontology_entity(
    name="Guest",
    description="客人本体 - 酒店客户信息管理",
    table_name="guests",
)
class GuestEntity(BaseEntity):
    """
    Guest 领域实体

    封装现有 ORM 模型，提供业务方法。

    Attributes:
        _orm_model: 内部 ORM 模型实例
    """

    def __init__(self, orm_model: "Guest"):
        """
        初始化 Guest 实体

        Args:
            orm_model: SQLAlchemy ORM 模型实例
        """
        self._orm_model = orm_model

    # ============== 属性访问 ==============

    @property
    def id(self) -> int:
        """客人 ID"""
        return self._orm_model.id

    @property
    def name(self) -> str:
        """姓名"""
        return self._orm_model.name

    @property
    def id_type(self) -> Optional[str]:
        """证件类型"""
        return self._orm_model.id_type

    @property
    def id_number(self) -> Optional[str]:
        """证件号码"""
        return self._orm_model.id_number

    @property
    def phone(self) -> Optional[str]:
        """手机号"""
        return self._orm_model.phone

    @property
    def email(self) -> Optional[str]:
        """邮箱"""
        return self._orm_model.email

    @property
    def preferences(self) -> Optional[str]:
        """客户偏好 (JSON)"""
        return self._orm_model.preferences

    @property
    def tier(self) -> str:
        """客户等级"""
        return self._orm_model.tier or GuestTier.NORMAL

    @property
    def total_stays(self) -> int:
        """累计入住次数"""
        return self._orm_model.total_stays or 0

    @property
    def total_amount(self) -> float:
        """累计消费金额"""
        return float(self._orm_model.total_amount or 0)

    @property
    def is_blacklisted(self) -> bool:
        """是否黑名单"""
        return self._orm_model.is_blacklisted or False

    @property
    def blacklist_reason(self) -> Optional[str]:
        """黑名单原因"""
        return self._orm_model.blacklist_reason

    @property
    def notes(self) -> Optional[str]:
        """备注信息"""
        return self._orm_model.notes

    @property
    def created_at(self) -> datetime:
        """创建时间"""
        return self._orm_model.created_at

    @property
    def updated_at(self) -> datetime:
        """更新时间"""
        return self._orm_model.updated_at

    # ============== 业务方法 ==============

    @ontology_action(
        entity="Guest",
        action_type="update_tier",
        description="更新客户等级",
        params=[
            {"name": "tier", "type": "enum", "enum_values": ["normal", "silver", "gold", "platinum"], "required": True, "description": "客户等级"},
        ],
        requires_confirmation=False,
        allowed_roles=["manager"],
        writeback=True,
    )
    def update_tier(self, tier: str) -> None:
        """
        更新客户等级

        Args:
            tier: 新的客户等级
        """
        self._orm_model.tier = tier
        logger.info(f"Guest {self.id} tier updated to {tier}")

    @ontology_action(
        entity="Guest",
        action_type="add_to_blacklist",
        description="添加到黑名单",
        params=[
            {"name": "reason", "type": "string", "required": True, "description": "黑名单原因"},
        ],
        requires_confirmation=True,
        allowed_roles=["manager"],
        writeback=True,
    )
    def add_to_blacklist(self, reason: str) -> None:
        """
        添加到黑名单

        Args:
            reason: 黑名单原因
        """
        self._orm_model.is_blacklisted = True
        self._orm_model.blacklist_reason = reason
        logger.info(f"Guest {self.id} added to blacklist: {reason}")

    @ontology_action(
        entity="Guest",
        action_type="remove_from_blacklist",
        description="从黑名单移除",
        params=[],
        requires_confirmation=True,
        allowed_roles=["manager"],
        writeback=True,
    )
    def remove_from_blacklist(self) -> None:
        """从黑名单移除"""
        self._orm_model.is_blacklisted = False
        self._orm_model.blacklist_reason = None
        logger.info(f"Guest {self.id} removed from blacklist")

    @ontology_action(
        entity="Guest",
        action_type="update_preferences",
        description="更新客户偏好",
        params=[
            {"name": "preferences", "type": "object", "required": True, "description": "偏好设置 (JSON)"},
        ],
        requires_confirmation=False,
        allowed_roles=["manager", "receptionist"],
        writeback=True,
    )
    def update_preferences(self, preferences: str) -> None:
        """
        更新客户偏好

        Args:
            preferences: 偏好设置 (JSON 字符串)
        """
        self._orm_model.preferences = preferences
        logger.info(f"Guest {self.id} preferences updated")

    @ontology_action(
        entity="Guest",
        action_type="increment_stays",
        description="增加入住次数",
        params=[],
        requires_confirmation=False,
        allowed_roles=[],  # 内部调用
        writeback=True,
    )
    def increment_stays(self) -> None:
        """增加入住次数（内部方法）"""
        self._orm_model.total_stays = (self._orm_model.total_stays or 0) + 1

    @ontology_action(
        entity="Guest",
        action_type="add_amount",
        description="增加累计消费",
        params=[
            {"name": "amount", "type": "number", "required": True, "description": "消费金额"},
        ],
        requires_confirmation=False,
        allowed_roles=[],  # 内部调用
        writeback=True,
    )
    def add_amount(self, amount: float) -> None:
        """
        增加累计消费（内部方法）

        Args:
            amount: 消费金额
        """
        current = self._orm_model.total_amount or Decimal("0")
        self._orm_model.total_amount = current + Decimal(str(amount))

    # ============== 查询方法 ==============

    def is_vip(self) -> bool:
        """
        检查是否是 VIP 客户

        Returns:
            是否是 VIP（金卡或白金）
        """
        return self.tier in [GuestTier.GOLD, GuestTier.PLATINUM]

    def can_make_reservation(self) -> bool:
        """
        检查是否可以预订

        Returns:
            如果不在黑名单返回 True
        """
        return not self.is_blacklisted

    # ============== 序列化 ==============

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "id_type": self.id_type,
            "id_number": "***" if self.id_number else None,  # 脱敏
            "phone": self.phone,
            "email": self.email,
            "preferences": self.preferences,
            "tier": self.tier,
            "total_stays": self.total_stays,
            "total_amount": float(self.total_amount),
            "is_blacklisted": self.is_blacklisted,
            "blacklist_reason": self.blacklist_reason,
            "notes": self.notes,
            "is_vip": self.is_vip(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============== Guest 仓储 ==============

class GuestRepository:
    """
    Guest 仓储

    负责 Guest 实体的持久化和查询
    """

    def __init__(self, db_session):
        """
        初始化仓储

        Args:
            db_session: SQLAlchemy 数据库会话
        """
        self._db = db_session

    def get_by_id(self, guest_id: int) -> Optional[GuestEntity]:
        """
        根据 ID 获取客人

        Args:
            guest_id: 客人 ID

        Returns:
            GuestEntity 实例，如果不存在返回 None
        """
        from app.models.ontology import Guest

        orm_model = self._db.query(Guest).filter(Guest.id == guest_id).first()
        if orm_model is None:
            return None
        return GuestEntity(orm_model)

    def get_by_phone(self, phone: str) -> Optional[GuestEntity]:
        """
        根据手机号获取客人

        Args:
            phone: 手机号

        Returns:
            GuestEntity 实例，如果不存在返回 None
        """
        from app.models.ontology import Guest

        orm_model = self._db.query(Guest).filter(Guest.phone == phone).first()
        if orm_model is None:
            return None
        return GuestEntity(orm_model)

    def get_by_id_number(self, id_number: str) -> Optional[GuestEntity]:
        """
        根据证件号获取客人

        Args:
            id_number: 证件号

        Returns:
            GuestEntity 实例，如果不存在返回 None
        """
        from app.models.ontology import Guest

        orm_model = self._db.query(Guest).filter(Guest.id_number == id_number).first()
        if orm_model is None:
            return None
        return GuestEntity(orm_model)

    def find_by_tier(self, tier: str) -> List[GuestEntity]:
        """
        根据客户等级查找客人

        Args:
            tier: 客户等级

        Returns:
            客人列表
        """
        from app.models.ontology import Guest

        orm_models = self._db.query(Guest).filter(Guest.tier == tier).all()
        return [GuestEntity(m) for m in orm_models]

    def find_vip_guests(self) -> List[GuestEntity]:
        """
        查找 VIP 客人

        Returns:
            VIP 客人列表
        """
        from app.models.ontology import Guest

        orm_models = self._db.query(Guest).filter(
            Guest.tier.in_([GuestTier.GOLD, GuestTier.PLATINUM])
        ).all()
        return [GuestEntity(m) for m in orm_models]

    def find_blacklisted(self) -> List[GuestEntity]:
        """
        查找黑名单客人

        Returns:
            黑名单客人列表
        """
        from app.models.ontology import Guest

        orm_models = self._db.query(Guest).filter(Guest.is_blacklisted == True).all()
        return [GuestEntity(m) for m in orm_models]

    def search_by_name(self, name: str) -> List[GuestEntity]:
        """
        根据姓名搜索客人

        Args:
            name: 姓名或部分姓名

        Returns:
            匹配的客人列表
        """
        from app.models.ontology import Guest

        orm_models = self._db.query(Guest).filter(
            Guest.name.ilike(f"%{name}%")
        ).all()
        return [GuestEntity(m) for m in orm_models]

    def save(self, guest: GuestEntity) -> None:
        """
        保存客人

        Args:
            guest: GuestEntity 实例
        """
        self._db.add(guest._orm_model)
        self._db.commit()

    def list_all(self) -> List[GuestEntity]:
        """
        列出所有客人

        Returns:
            所有客人列表
        """
        from app.models.ontology import Guest

        orm_models = self._db.query(Guest).all()
        return [GuestEntity(m) for m in orm_models]


# 导出
__all__ = [
    "GuestTier",
    "GuestEntity",
    "GuestRepository",
]
