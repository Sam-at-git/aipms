"""
房间管理 API 单元测试
覆盖 /rooms 端点的所有功能
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from fastapi.testclient import TestClient


class TestRoomTypes:
    """房型管理测试"""

    def test_list_room_types(self, client: TestClient, manager_auth_headers, sample_room_type):
        """测试获取房型列表"""
        response = client.get("/rooms/types", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "标准间"

    def test_create_room_type(self, client: TestClient, manager_auth_headers):
        """测试创建房型"""
        response = client.post("/rooms/types", headers=manager_auth_headers, json={
            "name": "豪华间",
            "description": "Luxury Room",
            "base_price": "588.00",
            "max_occupancy": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "豪华间"
        assert float(data["base_price"]) == 588.00

    def test_create_duplicate_room_type(self, client: TestClient, manager_auth_headers, sample_room_type):
        """测试创建重复房型"""
        response = client.post("/rooms/types", headers=manager_auth_headers, json={
            "name": "标准间",
            "description": "Duplicate",
            "base_price": "200.00",
            "max_occupancy": 2
        })

        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_update_room_type(self, client: TestClient, manager_auth_headers, sample_room_type):
        """测试更新房型"""
        response = client.put(f"/rooms/types/{sample_room_type.id}", headers=manager_auth_headers, json={
            "name": "标准间（已更新）",
            "base_price": "328.00"
        })

        assert response.status_code == 200
        data = response.json()
        assert "已更新" in data["name"]
        assert float(data["base_price"]) == 328.00

    def test_delete_room_type(self, client: TestClient, manager_auth_headers, db_session):
        """测试删除房型"""
        from app.models.ontology import RoomType

        # 创建一个没有关联房间的房型
        room_type = RoomType(
            name="可删除房型",
            description="To be deleted",
            base_price=Decimal("100.00"),
            max_occupancy=2
        )
        db_session.add(room_type)
        db_session.commit()
        db_session.refresh(room_type)

        response = client.delete(f"/rooms/types/{room_type.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        assert "删除成功" in response.json()["message"]

    def test_delete_room_type_with_rooms(self, client: TestClient, manager_auth_headers, sample_room):
        """测试删除有关联房间的房型"""
        # sample_room 使用了 sample_room_type，所以该房型有关联房间
        response = client.delete(f"/rooms/types/{sample_room.room_type_id}", headers=manager_auth_headers)

        assert response.status_code == 400
        assert "无法删除" in response.json()["detail"]

    def test_create_room_type_unauthorized(self, client: TestClient, receptionist_auth_headers):
        """测试非经理创建房型"""
        response = client.post("/rooms/types", headers=receptionist_auth_headers, json={
            "name": "豪华间",
            "description": "Luxury Room",
            "base_price": "588.00",
            "max_occupancy": 2
        })

        assert response.status_code == 403


class TestRooms:
    """房间管理测试"""

    def test_list_rooms(self, client: TestClient, manager_auth_headers, sample_room):
        """测试获取房间列表"""
        response = client.get("/rooms", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["room_number"] == "101"

    def test_list_rooms_filter_by_floor(self, client: TestClient, manager_auth_headers, sample_room):
        """测试按楼层筛选房间"""
        response = client.get("/rooms?floor=1", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert all(room["floor"] == 1 for room in data)

    def test_list_rooms_filter_by_status(self, client: TestClient, manager_auth_headers, sample_room):
        """测试按状态筛选房间"""
        # 使用字符串格式的状态值
        response = client.get("/rooms?status=vacant_clean", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert all(room["status"] == "vacant_clean" for room in data)

    def test_list_rooms_filter_by_type(self, client: TestClient, manager_auth_headers, sample_room, sample_room_type):
        """测试按房型筛选房间"""
        response = client.get(f"/rooms?room_type_id={sample_room_type.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert all(room["room_type_id"] == sample_room_type.id for room in data)

    def test_get_room_detail(self, client: TestClient, manager_auth_headers, sample_room):
        """测试获取房间详情"""
        response = client.get(f"/rooms/{sample_room.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["room_number"] == "101"
        assert data["floor"] == 1

    def test_get_room_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在的房间"""
        response = client.get("/rooms/99999", headers=manager_auth_headers)

        assert response.status_code == 404

    def test_create_room(self, client: TestClient, manager_auth_headers, sample_room_type):
        """测试创建房间"""
        response = client.post("/rooms", headers=manager_auth_headers, json={
            "room_number": "201",
            "floor": 2,
            "room_type_id": sample_room_type.id,
            "features": "无烟房"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["room_number"] == "201"
        assert data["floor"] == 2

    def test_create_duplicate_room(self, client: TestClient, manager_auth_headers, sample_room, sample_room_type):
        """测试创建重复房间号"""
        response = client.post("/rooms", headers=manager_auth_headers, json={
            "room_number": "101",
            "floor": 1,
            "room_type_id": sample_room_type.id
        })

        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_update_room(self, client: TestClient, manager_auth_headers, sample_room):
        """测试更新房间"""
        response = client.put(f"/rooms/{sample_room.id}", headers=manager_auth_headers, json={
            "features": "海景房"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["features"] == "海景房"

    def test_delete_room(self, client: TestClient, manager_auth_headers, db_session):
        """测试删除房间"""
        from app.models.ontology import Room, RoomType, RoomStatus

        # 创建一个没有历史的房间
        room_type = RoomType(name="临时房型", base_price=Decimal("100"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()

        room = Room(
            room_number="999",
            floor=9,
            room_type_id=room_type.id,
            status=RoomStatus.VACANT_CLEAN
        )
        db_session.add(room)
        db_session.commit()
        db_session.refresh(room)

        response = client.delete(f"/rooms/{room.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "删除成功"

    def test_update_room_status(self, client: TestClient, manager_auth_headers, sample_room):
        """测试更新房间状态"""
        from app.models.ontology import RoomStatus

        response = client.patch(f"/rooms/{sample_room.id}/status", headers=manager_auth_headers, json={
            "status": RoomStatus.VACANT_DIRTY,
            "reason": "客人退房后"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "vacant_dirty"

    def test_update_occupied_room_status(self, client: TestClient, manager_auth_headers, db_session):
        """测试修改入住中房间的状态"""
        from app.models.ontology import Room, RoomType, RoomStatus, Guest, StayRecord, StayRecordStatus
        from datetime import date, datetime

        room_type = RoomType(name="测试房型", base_price=Decimal("100"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()

        room = Room(
            room_number="801",
            floor=8,
            room_type_id=room_type.id,
            status=RoomStatus.OCCUPIED
        )
        db_session.add(room)

        guest = Guest(name="测试客人", phone="13800000000")
        db_session.add(guest)
        db_session.commit()  # 先 commit 获取 guest.id

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(),
            expected_check_out=date.today() + timedelta(days=1),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        # 尝试修改入住中房间的状态
        response = client.patch(f"/rooms/{room.id}/status", headers=manager_auth_headers, json={
            "status": RoomStatus.VACANT_CLEAN
        })

        assert response.status_code == 400
        assert "不能手动更改状态" in response.json()["detail"]

    def test_get_status_summary(self, client: TestClient, manager_auth_headers, multiple_rooms):
        """测试获取房间状态统计"""
        response = client.get("/rooms/status-summary", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "vacant_clean" in data
        assert "occupied" in data
        assert data["total"] >= 5

    def test_get_available_rooms(self, client: TestClient, manager_auth_headers, sample_room, sample_room_type):
        """测试获取可用房间"""
        from datetime import date, timedelta

        check_in = date.today()
        check_out = date.today() + timedelta(days=1)

        response = client.get(
            f"/rooms/available?check_in_date={check_in}&check_out_date={check_out}",
            headers=manager_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_availability_by_type(self, client: TestClient, manager_auth_headers, sample_room, sample_room_type):
        """测试按房型统计可用房间"""
        from datetime import date, timedelta

        check_in = date.today()
        check_out = date.today() + timedelta(days=1)

        response = client.get(
            f"/rooms/availability?check_in_date={check_in}&check_out_date={check_out}",
            headers=manager_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
