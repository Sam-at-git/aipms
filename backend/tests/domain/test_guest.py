"""
测试 core.domain.guest 模块 - Guest 领域实体单元测试
"""
import pytest
from datetime import datetime

from core.domain.guest import (
    GuestTier,
    GuestEntity,
    GuestRepository,
)
from app.models.ontology import Guest


# ============== Fixtures ==============

@pytest.fixture
def sample_guest(db_session):
    """创建示例客人"""
    guest = Guest(
        name="张三",
        phone="13800138000",
        tier="normal",
        total_stays=5,
        total_amount=2500.00,
    )
    db_session.add(guest)
    db_session.commit()
    return guest


@pytest.fixture
def vip_guest(db_session):
    """创建 VIP 客人"""
    guest = Guest(
        name="李四",
        phone="13900139000",
        tier="gold",
        total_stays=20,
        total_amount=50000.00,
    )
    db_session.add(guest)
    db_session.commit()
    return guest


# ============== GuestEntity Tests ==============

class TestGuestEntity:
    def test_creation(self, sample_guest):
        """测试创建客人实体"""
        entity = GuestEntity(sample_guest)

        assert entity.id == sample_guest.id
        assert entity.name == "张三"
        assert entity.phone == "13800138000"
        assert entity.tier == GuestTier.NORMAL
        assert entity.total_stays == 5
        assert entity.total_amount == 2500.00

    def test_is_vip_when_gold(self, vip_guest):
        """测试金卡客户是 VIP"""
        entity = GuestEntity(vip_guest)

        assert entity.is_vip() is True

    def test_is_vip_when_normal(self, sample_guest):
        """测试普通客户不是 VIP"""
        entity = GuestEntity(sample_guest)

        assert entity.is_vip() is False

    def test_is_vip_when_platinum(self, db_session):
        """测试白金客户是 VIP"""
        guest = Guest(
            name="王五",
            phone="13700137000",
            tier="platinum",
        )
        db_session.add(guest)
        db_session.commit()

        entity = GuestEntity(guest)

        assert entity.is_vip() is True

    def test_can_make_reservation_when_not_blacklisted(self, sample_guest):
        """测试未黑名单客户可以预订"""
        entity = GuestEntity(sample_guest)

        assert entity.can_make_reservation() is True

    def test_cannot_make_reservation_when_blacklisted(self, sample_guest):
        """测试黑名单客户不能预订"""
        sample_guest.is_blacklisted = True
        entity = GuestEntity(sample_guest)

        assert entity.can_make_reservation() is False

    def test_update_tier(self, sample_guest):
        """测试更新客户等级"""
        entity = GuestEntity(sample_guest)

        entity.update_tier("silver")

        assert entity.tier == "silver"
        assert sample_guest.tier == "silver"

    def test_add_to_blacklist(self, sample_guest):
        """测试添加到黑名单"""
        entity = GuestEntity(sample_guest)

        entity.add_to_blacklist("不良行为")

        assert entity.is_blacklisted is True
        assert entity.blacklist_reason == "不良行为"
        assert sample_guest.is_blacklisted is True

    def test_remove_from_blacklist(self, sample_guest):
        """测试从黑名单移除"""
        sample_guest.is_blacklisted = True
        sample_guest.blacklist_reason = "测试"
        entity = GuestEntity(sample_guest)

        entity.remove_from_blacklist()

        assert entity.is_blacklisted is False
        assert entity.blacklist_reason is None
        assert sample_guest.is_blacklisted is False

    def test_update_preferences(self, sample_guest):
        """测试更新偏好"""
        entity = GuestEntity(sample_guest)

        entity.update_preferences('{"floor_preference": "high"}')

        assert entity.preferences == '{"floor_preference": "high"}'

    def test_increment_stays(self, sample_guest):
        """测试增加入住次数"""
        entity = GuestEntity(sample_guest)

        entity.increment_stays()

        assert entity.total_stays == 6
        assert sample_guest.total_stays == 6

    def test_add_amount(self, sample_guest):
        """测试增加累计消费"""
        entity = GuestEntity(sample_guest)

        entity.add_amount(500.00)

        assert entity.total_amount == 3000.00
        assert sample_guest.total_amount == 3000.00

    def test_to_dict(self, sample_guest):
        """测试转换为字典"""
        entity = GuestEntity(sample_guest)

        d = entity.to_dict()

        assert d["id"] == sample_guest.id
        assert d["name"] == "张三"
        assert d["phone"] == "13800138000"
        assert d["tier"] == "normal"
        assert d["is_vip"] is False
        # id_number 为 None 时应该是 None
        assert d.get("id_number") is None or d.get("id_number") == "***"


# ============== GuestRepository Tests ==============

class TestGuestRepository:
    def test_get_by_id(self, db_session, sample_guest):
        """测试根据 ID 获取客人"""
        repo = GuestRepository(db_session)

        entity = repo.get_by_id(sample_guest.id)

        assert entity is not None
        assert entity.id == sample_guest.id
        assert entity.name == "张三"

    def test_get_by_id_not_found(self, db_session):
        """测试获取不存在的客人"""
        repo = GuestRepository(db_session)

        entity = repo.get_by_id(99999)

        assert entity is None

    def test_get_by_phone(self, db_session, sample_guest):
        """测试根据手机号获取客人"""
        repo = GuestRepository(db_session)

        entity = repo.get_by_phone("13800138000")

        assert entity is not None
        assert entity.phone == "13800138000"

    def test_get_by_phone_not_found(self, db_session):
        """测试获取不存在的手机号"""
        repo = GuestRepository(db_session)

        entity = repo.get_by_phone("99999999999")

        assert entity is None

    def test_get_by_id_number(self, db_session):
        """测试根据证件号获取客人"""
        guest = Guest(
            name="赵六",
            id_number="110101199001011234",
            phone="13600136000",
        )
        db_session.add(guest)
        db_session.commit()

        repo = GuestRepository(db_session)

        entity = repo.get_by_id_number("110101199001011234")

        assert entity is not None
        assert entity.name == "赵六"

    def test_find_by_tier(self, db_session):
        """测试根据等级查找客人"""
        repo = GuestRepository(db_session)

        # 创建多个银卡客户
        for i in range(3):
            guest = Guest(
                name=f"银卡客户{i}",
                phone=f"138{i:08d}",
                tier="silver",
            )
            db_session.add(guest)
        db_session.commit()

        silver_guests = repo.find_by_tier("silver")

        assert len(silver_guests) >= 3

    def test_find_vip_guests(self, db_session, vip_guest):
        """测试查找 VIP 客人"""
        repo = GuestRepository(db_session)

        # 创建更多 VIP 客人
        platinum = Guest(
            name="白金客户",
            phone="13500135000",
            tier="platinum",
        )
        db_session.add(platinum)
        db_session.commit()

        vip_guests = repo.find_vip_guests()

        assert len(vip_guests) >= 2

    def test_find_blacklisted(self, db_session):
        """测试查找黑名单客人"""
        repo = GuestRepository(db_session)

        # 创建黑名单客人
        blacklisted = Guest(
            name="黑名单用户",
            phone="13300133000",
            is_blacklisted=True,
            blacklist_reason="逃单",
        )
        db_session.add(blacklisted)
        db_session.commit()

        blacklist = repo.find_blacklisted()

        assert len(blacklist) >= 1
        assert any(g.name == "黑名单用户" for g in blacklist)

    def test_search_by_name(self, db_session, sample_guest):
        """测试根据姓名搜索"""
        repo = GuestRepository(db_session)

        results = repo.search_by_name("张")

        assert len(results) >= 1
        assert any("张" in r.name for r in results)

    def test_save(self, db_session):
        """测试保存客人"""
        repo = GuestRepository(db_session)

        guest = Guest(
            name="新客户",
            phone="13200132000",
        )
        entity = GuestEntity(guest)

        repo.save(entity)

        # 验证已保存
        saved = repo.get_by_phone("13200132000")
        assert saved is not None
        assert saved.name == "新客户"

    def test_list_all(self, db_session, sample_guest, vip_guest):
        """测试列出所有客人"""
        repo = GuestRepository(db_session)

        all_guests = repo.list_all()

        assert len(all_guests) >= 2


class TestGuestTier:
    def test_tier_values(self):
        """测试等级值"""
        assert GuestTier.NORMAL == "normal"
        assert GuestTier.SILVER == "silver"
        assert GuestTier.GOLD == "gold"
        assert GuestTier.PLATINUM == "platinum"
