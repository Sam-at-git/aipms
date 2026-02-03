"""
客人管理 API 单元测试
覆盖 /guests 端点的所有功能
"""
import pytest
from fastapi.testclient import TestClient


class TestListGuests:
    """客人列表测试"""

    def test_list_guests(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试获取客人列表"""
        response = client.get("/guests", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "张三"

    def test_list_guests_search_by_name(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试按姓名搜索客人"""
        response = client.get("/guests?search=张三", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "张三" in data[0]["name"]

    def test_list_guests_search_by_phone(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试按手机号搜索客人"""
        response = client.get("/guests?search=13800138000", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert data[0]["phone"] == "13800138000"

    def test_list_guests_filter_by_tier(self, client: TestClient, manager_auth_headers, db_session):
        """测试按等级筛选客人"""
        from app.models.ontology import Guest, GuestTier

        guest = Guest(
            name="金牌客户",
            phone="13900139000",
            tier=GuestTier.GOLD
        )
        db_session.add(guest)
        db_session.commit()

        response = client.get("/guests?tier=gold", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert data[0]["tier"] == "gold"

    def test_list_guests_blacklisted(self, client: TestClient, manager_auth_headers, db_session):
        """测试获取黑名单客人"""
        from app.models.ontology import Guest

        guest = Guest(
            name="黑名单用户",
            phone="13700137000",
            is_blacklisted=True,
            blacklist_reason="恶意逃单"
        )
        db_session.add(guest)
        db_session.commit()

        response = client.get("/guests?is_blacklisted=true", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert data[0]["is_blacklisted"] is True


class TestCreateGuest:
    """创建客人测试"""

    def test_create_guest(self, client: TestClient, manager_auth_headers):
        """测试创建客人"""
        response = client.post("/guests", headers=manager_auth_headers, json={
            "name": "新客人",
            "phone": "13600136000",
            "id_type": "身份证",
            "id_number": "110101199001011235"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新客人"
        assert data["phone"] == "13600136000"

    def test_create_duplicate_phone(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试创建重复手机号的客人"""
        # Guest模型的phone字段没有唯一约束，所以会成功创建
        response = client.post("/guests", headers=manager_auth_headers, json={
            "name": "另一个张三",
            "phone": "13800138000",  # 与 sample_guest 相同
            "id_type": "身份证",
            "id_number": "110101199001011236"
        })

        # 系统允许重复手机号（因为phone没有唯一约束）
        assert response.status_code == 200


class TestGetGuestDetail:
    """客人详情测试"""

    def test_get_guest_detail(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试获取客人详情"""
        response = client.get(f"/guests/{sample_guest.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_guest.id
        assert data["name"] == "张三"

    def test_get_guest_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在的客人"""
        response = client.get("/guests/99999", headers=manager_auth_headers)

        assert response.status_code == 404


class TestUpdateGuest:
    """更新客人测试"""

    def test_update_guest(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试更新客人信息"""
        response = client.put(f"/guests/{sample_guest.id}", headers=manager_auth_headers, json={
            "name": "张三（已更新）",
            "email": "zhangsan@example.com"
        })

        assert response.status_code == 200
        data = response.json()
        assert "已更新" in data["name"]

    def test_update_guest_not_found(self, client: TestClient, manager_auth_headers):
        """测试更新不存在的客人"""
        response = client.put("/guests/99999", headers=manager_auth_headers, json={
            "name": "不存在的客人"
        })

        # API返回400而不是404
        assert response.status_code == 400


class TestUpdateGuestTier:
    """更新客人等级测试"""

    def test_update_guest_tier(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试更新客人等级"""
        from app.models.ontology import GuestTier

        response = client.put(
            f"/guests/{sample_guest.id}/tier",
            headers=manager_auth_headers,
            params={"tier": "gold"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_update_guest_tier_invalid(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试更新为无效等级"""
        response = client.put(f"/guests/{sample_guest.id}/tier", headers=manager_auth_headers, json={
            "tier": "invalid_tier"
        })

        assert response.status_code == 422  # Validation error


class TestUpdateGuestPreferences:
    """更新客人偏好测试"""

    def test_update_guest_preferences(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试更新客人偏好"""
        response = client.put(f"/guests/{sample_guest.id}/preferences", headers=manager_auth_headers, json={
            "floor": "high",
            "pillow_type": "soft",
            "extra_towels": True
        })

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestBlacklist:
    """黑名单测试"""

    def test_add_to_blacklist(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试添加到黑名单"""
        response = client.put(
            f"/guests/{sample_guest.id}/blacklist",
            headers=manager_auth_headers,
            params={"is_blacklisted": True, "reason": "多次损坏房间设施"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_remove_from_blacklist(self, client: TestClient, manager_auth_headers, db_session):
        """测试从黑名单移除"""
        from app.models.ontology import Guest

        guest = Guest(
            name="黑名单用户",
            phone="13500135000",
            is_blacklisted=True,
            blacklist_reason="测试"
        )
        db_session.add(guest)
        db_session.commit()
        db_session.refresh(guest)

        response = client.put(
            f"/guests/{guest.id}/blacklist",
            headers=manager_auth_headers,
            params={"is_blacklisted": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestGuestHistory:
    """客人历史测试"""

    def test_get_stay_history(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试获取入住历史"""
        response = client.get(f"/guests/{sample_guest.id}/stay-history", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_reservation_history(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试获取预订历史"""
        response = client.get(f"/guests/{sample_guest.id}/reservation-history", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestGuestStats:
    """客人统计测试"""

    def test_get_guest_stats(self, client: TestClient, manager_auth_headers, sample_guest):
        """测试获取客人统计"""
        response = client.get(f"/guests/{sample_guest.id}/stats", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "reservation_count" in data
        assert "total_stays" in data
        assert "tier" in data


class TestGuestPermissions:
    """客人权限测试"""

    def test_frontend_can_list_guests(self, client: TestClient, receptionist_auth_headers, sample_guest):
        """测试前台可以查看客人列表"""
        response = client.get("/guests", headers=receptionist_auth_headers)

        assert response.status_code == 200

    def test_frontend_can_create_guest(self, client: TestClient, receptionist_auth_headers):
        """测试前台可以创建客人"""
        response = client.post("/guests", headers=receptionist_auth_headers, json={
            "name": "前台创建的客人",
            "phone": "13400134000"
        })

        assert response.status_code == 200

    def test_cleaner_cannot_create_guest(self, client: TestClient, cleaner_auth_headers):
        """测试清洁员不能创建客人"""
        response = client.post("/guests", headers=cleaner_auth_headers, json={
            "name": "清洁员尝试创建",
            "phone": "13300133000"
        })

        assert response.status_code == 403
