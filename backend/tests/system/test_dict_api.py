"""
数据字典 API 测试
覆盖 /system/dicts 端点的所有功能
"""
import pytest
from fastapi.testclient import TestClient


class TestDictTypeAPI:
    """字典类型 API 测试"""

    def test_list_dict_types_empty(self, client: TestClient, auth_headers):
        """测试空列表"""
        response = client.get("/system/dicts", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_dict_type(self, client: TestClient, auth_headers):
        """测试创建字典类型"""
        response = client.post("/system/dicts", headers=auth_headers, json={
            "code": "room_status",
            "name": "房间状态",
            "description": "房间的当前状态",
            "is_system": True,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "room_status"
        assert data["name"] == "房间状态"
        assert data["is_system"] is True
        assert data["is_active"] is True

    def test_create_dict_type_duplicate_code(self, client: TestClient, auth_headers):
        """测试重复编码"""
        client.post("/system/dicts", headers=auth_headers, json={
            "code": "dup_test", "name": "测试"
        })
        response = client.post("/system/dicts", headers=auth_headers, json={
            "code": "dup_test", "name": "测试2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_get_dict_type(self, client: TestClient, auth_headers):
        """测试获取字典类型详情"""
        create = client.post("/system/dicts", headers=auth_headers, json={
            "code": "task_type", "name": "任务类型"
        })
        type_id = create.json()["id"]

        response = client.get(f"/system/dicts/{type_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["code"] == "task_type"

    def test_get_dict_type_not_found(self, client: TestClient, auth_headers):
        """测试获取不存在的字典类型"""
        response = client.get("/system/dicts/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_dict_type(self, client: TestClient, auth_headers):
        """测试更新字典类型"""
        create = client.post("/system/dicts", headers=auth_headers, json={
            "code": "test_update", "name": "原名称"
        })
        type_id = create.json()["id"]

        response = client.put(f"/system/dicts/{type_id}", headers=auth_headers, json={
            "name": "新名称", "description": "新描述"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"
        assert response.json()["description"] == "新描述"

    def test_delete_dict_type(self, client: TestClient, auth_headers):
        """测试删除字典类型"""
        create = client.post("/system/dicts", headers=auth_headers, json={
            "code": "deletable", "name": "可删除"
        })
        type_id = create.json()["id"]

        response = client.delete(f"/system/dicts/{type_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_system_dict_type_blocked(self, client: TestClient, auth_headers):
        """测试删除系统内置字典类型被阻止"""
        create = client.post("/system/dicts", headers=auth_headers, json={
            "code": "system_type", "name": "系统类型", "is_system": True
        })
        type_id = create.json()["id"]

        response = client.delete(f"/system/dicts/{type_id}", headers=auth_headers)
        assert response.status_code == 400
        assert "不可删除" in response.json()["detail"]

    def test_list_dict_types_filter_active(self, client: TestClient, auth_headers):
        """测试按活跃状态过滤"""
        client.post("/system/dicts", headers=auth_headers, json={
            "code": "active1", "name": "活跃"
        })

        response = client.get("/system/dicts?is_active=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(t["is_active"] for t in data)

    def test_unauthorized_access(self, client: TestClient):
        """测试未认证访问"""
        response = client.get("/system/dicts")
        assert response.status_code in (401, 403)

    def test_cleaner_cannot_create(self, client: TestClient, cleaner_auth_headers):
        """测试清洁员无法创建字典类型"""
        response = client.post("/system/dicts", headers=cleaner_auth_headers, json={
            "code": "test", "name": "测试"
        })
        assert response.status_code == 403


class TestDictItemAPI:
    """字典项 API 测试"""

    def _create_dict_type(self, client, auth_headers, code="test_type", name="测试类型"):
        response = client.post("/system/dicts", headers=auth_headers, json={
            "code": code, "name": name
        })
        return response.json()["id"]

    def test_create_dict_item(self, client: TestClient, auth_headers):
        """测试创建字典项"""
        type_id = self._create_dict_type(client, auth_headers)

        response = client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "空闲-已清洁", "value": "vacant_clean",
            "color": "green", "sort_order": 1,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "空闲-已清洁"
        assert data["value"] == "vacant_clean"
        assert data["color"] == "green"
        assert data["dict_type_id"] == type_id

    def test_create_dict_item_duplicate_value(self, client: TestClient, auth_headers):
        """测试重复值"""
        type_id = self._create_dict_type(client, auth_headers, code="dup_item_test")

        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "值1", "value": "val1"
        })
        response = client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "值1重复", "value": "val1"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_list_dict_items(self, client: TestClient, auth_headers):
        """测试获取字典项列表"""
        type_id = self._create_dict_type(client, auth_headers, code="list_items_test")

        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "项目1", "value": "item1", "sort_order": 2
        })
        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "项目2", "value": "item2", "sort_order": 1
        })

        response = client.get(f"/system/dicts/{type_id}/items", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Verify sort order
        assert data[0]["sort_order"] <= data[1]["sort_order"]

    def test_list_dict_items_by_code(self, client: TestClient, auth_headers):
        """测试按编码获取字典项列表"""
        type_id = self._create_dict_type(client, auth_headers, code="code_lookup_test")

        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "测试项", "value": "test_val"
        })

        response = client.get("/system/dicts/code/code_lookup_test/items", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["value"] == "test_val"

    def test_list_dict_items_by_code_not_found(self, client: TestClient, auth_headers):
        """测试按不存在的编码查询"""
        response = client.get("/system/dicts/code/nonexistent/items", headers=auth_headers)
        assert response.status_code == 404

    def test_update_dict_item(self, client: TestClient, auth_headers):
        """测试更新字典项"""
        type_id = self._create_dict_type(client, auth_headers, code="update_item_test")

        create = client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "原标签", "value": "orig"
        })
        item_id = create.json()["id"]

        response = client.put(f"/system/dicts/items/{item_id}", headers=auth_headers, json={
            "label": "新标签", "color": "blue"
        })
        assert response.status_code == 200
        assert response.json()["label"] == "新标签"
        assert response.json()["color"] == "blue"

    def test_delete_dict_item(self, client: TestClient, auth_headers):
        """测试删除字典项"""
        type_id = self._create_dict_type(client, auth_headers, code="delete_item_test")

        create = client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "删除项", "value": "del"
        })
        item_id = create.json()["id"]

        response = client.delete(f"/system/dicts/items/{item_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_dict_type_item_count(self, client: TestClient, auth_headers):
        """测试字典类型的 item_count 字段"""
        type_id = self._create_dict_type(client, auth_headers, code="count_test")

        # No items yet
        response = client.get(f"/system/dicts/{type_id}", headers=auth_headers)
        assert response.json()["item_count"] == 0

        # Add items
        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "项1", "value": "v1"
        })
        client.post(f"/system/dicts/{type_id}/items", headers=auth_headers, json={
            "label": "项2", "value": "v2"
        })

        response = client.get(f"/system/dicts/{type_id}", headers=auth_headers)
        assert response.json()["item_count"] == 2
