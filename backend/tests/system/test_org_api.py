"""
组织机构 API 测试
覆盖 /system/departments 和 /system/positions 端点
"""
import pytest
from fastapi.testclient import TestClient


class TestDepartmentAPI:
    """部门管理 API 测试"""

    def test_list_departments_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/departments", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_department(self, client: TestClient, auth_headers):
        response = client.post("/system/departments", headers=auth_headers, json={
            "code": "tech", "name": "技术部", "sort_order": 1,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "tech"
        assert data["name"] == "技术部"
        assert data["parent_id"] is None
        assert data["is_active"] is True

    def test_create_department_duplicate_code(self, client: TestClient, auth_headers):
        client.post("/system/departments", headers=auth_headers, json={
            "code": "dup_dept", "name": "重复部门"
        })
        response = client.post("/system/departments", headers=auth_headers, json={
            "code": "dup_dept", "name": "重复2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_create_child_department(self, client: TestClient, auth_headers):
        parent = client.post("/system/departments", headers=auth_headers, json={
            "code": "parent_dept", "name": "父部门"
        })
        parent_id = parent.json()["id"]

        child = client.post("/system/departments", headers=auth_headers, json={
            "code": "child_dept", "name": "子部门", "parent_id": parent_id,
        })
        assert child.status_code == 201
        assert child.json()["parent_id"] == parent_id

    def test_create_department_invalid_parent(self, client: TestClient, auth_headers):
        response = client.post("/system/departments", headers=auth_headers, json={
            "code": "orphan", "name": "孤立部门", "parent_id": 9999,
        })
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]

    def test_get_department(self, client: TestClient, auth_headers):
        create = client.post("/system/departments", headers=auth_headers, json={
            "code": "get_dept", "name": "查询部门"
        })
        dept_id = create.json()["id"]

        response = client.get(f"/system/departments/{dept_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["code"] == "get_dept"

    def test_get_department_not_found(self, client: TestClient, auth_headers):
        response = client.get("/system/departments/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_department(self, client: TestClient, auth_headers):
        create = client.post("/system/departments", headers=auth_headers, json={
            "code": "upd_dept", "name": "旧名称"
        })
        dept_id = create.json()["id"]

        response = client.put(f"/system/departments/{dept_id}", headers=auth_headers, json={
            "name": "新名称"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"

    def test_update_department_self_parent(self, client: TestClient, auth_headers):
        create = client.post("/system/departments", headers=auth_headers, json={
            "code": "self_parent", "name": "自引用"
        })
        dept_id = create.json()["id"]

        response = client.put(f"/system/departments/{dept_id}", headers=auth_headers, json={
            "parent_id": dept_id
        })
        assert response.status_code == 400
        assert "自身" in response.json()["detail"]

    def test_delete_department(self, client: TestClient, auth_headers):
        create = client.post("/system/departments", headers=auth_headers, json={
            "code": "del_dept", "name": "待删除"
        })
        dept_id = create.json()["id"]

        response = client.delete(f"/system/departments/{dept_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/system/departments/{dept_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_department_with_children(self, client: TestClient, auth_headers):
        parent = client.post("/system/departments", headers=auth_headers, json={
            "code": "has_child", "name": "有子部门"
        })
        parent_id = parent.json()["id"]
        client.post("/system/departments", headers=auth_headers, json={
            "code": "child_of", "name": "子", "parent_id": parent_id,
        })

        response = client.delete(f"/system/departments/{parent_id}", headers=auth_headers)
        assert response.status_code == 400
        assert "子部门" in response.json()["detail"]

    def test_department_tree(self, client: TestClient, auth_headers):
        root = client.post("/system/departments", headers=auth_headers, json={
            "code": "tree_root", "name": "根部门"
        })
        root_id = root.json()["id"]
        client.post("/system/departments", headers=auth_headers, json={
            "code": "tree_child", "name": "子部门", "parent_id": root_id,
        })

        response = client.get("/system/departments/tree", headers=auth_headers)
        assert response.status_code == 200
        tree = response.json()
        assert len(tree) >= 1
        root_node = next(n for n in tree if n["code"] == "tree_root")
        assert len(root_node["children"]) == 1
        assert root_node["children"][0]["code"] == "tree_child"


class TestPositionAPI:
    """岗位管理 API 测试"""

    def test_list_positions_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/positions", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_position(self, client: TestClient, auth_headers):
        response = client.post("/system/positions", headers=auth_headers, json={
            "code": "dev", "name": "开发工程师", "sort_order": 1,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "dev"
        assert data["name"] == "开发工程师"
        assert data["is_active"] is True

    def test_create_position_duplicate_code(self, client: TestClient, auth_headers):
        client.post("/system/positions", headers=auth_headers, json={
            "code": "dup_pos", "name": "重复岗位"
        })
        response = client.post("/system/positions", headers=auth_headers, json={
            "code": "dup_pos", "name": "重复2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_create_position_with_department(self, client: TestClient, auth_headers):
        dept = client.post("/system/departments", headers=auth_headers, json={
            "code": "pos_dept", "name": "岗位所在部门"
        })
        dept_id = dept.json()["id"]

        pos = client.post("/system/positions", headers=auth_headers, json={
            "code": "dept_dev", "name": "部门开发", "department_id": dept_id,
        })
        assert pos.status_code == 201
        assert pos.json()["department_id"] == dept_id

    def test_create_position_invalid_department(self, client: TestClient, auth_headers):
        response = client.post("/system/positions", headers=auth_headers, json={
            "code": "bad_dept", "name": "坏部门", "department_id": 9999,
        })
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]

    def test_get_position(self, client: TestClient, auth_headers):
        create = client.post("/system/positions", headers=auth_headers, json={
            "code": "get_pos", "name": "查询岗位"
        })
        pos_id = create.json()["id"]

        response = client.get(f"/system/positions/{pos_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["code"] == "get_pos"

    def test_get_position_not_found(self, client: TestClient, auth_headers):
        response = client.get("/system/positions/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_position(self, client: TestClient, auth_headers):
        create = client.post("/system/positions", headers=auth_headers, json={
            "code": "upd_pos", "name": "旧岗位"
        })
        pos_id = create.json()["id"]

        response = client.put(f"/system/positions/{pos_id}", headers=auth_headers, json={
            "name": "新岗位"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新岗位"

    def test_delete_position(self, client: TestClient, auth_headers):
        create = client.post("/system/positions", headers=auth_headers, json={
            "code": "del_pos", "name": "待删除岗位"
        })
        pos_id = create.json()["id"]

        response = client.delete(f"/system/positions/{pos_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/system/positions/{pos_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_filter_positions_by_department(self, client: TestClient, auth_headers):
        dept = client.post("/system/departments", headers=auth_headers, json={
            "code": "filter_dept", "name": "过滤部门"
        })
        dept_id = dept.json()["id"]

        client.post("/system/positions", headers=auth_headers, json={
            "code": "filter_pos1", "name": "部门岗位1", "department_id": dept_id,
        })
        client.post("/system/positions", headers=auth_headers, json={
            "code": "filter_pos2", "name": "无部门岗位",
        })

        response = client.get(f"/system/positions?department_id={dept_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "filter_pos1"
