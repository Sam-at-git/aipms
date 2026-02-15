"""
RBAC API 测试
覆盖 /system/roles, /system/permissions, /system/users 端点
"""
import pytest
from fastapi.testclient import TestClient
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token


@pytest.fixture
def sysadmin_headers(db_session):
    """Create sysadmin user and return auth headers"""
    admin = Employee(
        username="sysadmin_rbac",
        password_hash=get_password_hash("123456"),
        name="系统管理员",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(admin.id, admin.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cleaner_headers(db_session):
    """Create cleaner user and return auth headers"""
    cleaner = Employee(
        username="cleaner_rbac",
        password_hash=get_password_hash("123456"),
        name="清洁员",
        role=EmployeeRole.CLEANER,
        is_active=True,
    )
    db_session.add(cleaner)
    db_session.commit()
    token = create_access_token(cleaner.id, cleaner.role)
    return {"Authorization": f"Bearer {token}"}


# ========== Role API Tests ==========


class TestRoleAPI:
    """角色管理 API 测试"""

    def test_list_roles_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/roles", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_role(self, client: TestClient, auth_headers):
        response = client.post("/system/roles", headers=auth_headers, json={
            "code": "custom_role",
            "name": "自定义角色",
            "description": "测试角色",
            "data_scope": "DEPT",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "custom_role"
        assert data["name"] == "自定义角色"
        assert data["data_scope"] == "DEPT"
        assert data["is_system"] is False
        assert data["is_active"] is True

    def test_create_role_duplicate_code(self, client: TestClient, auth_headers):
        client.post("/system/roles", headers=auth_headers, json={
            "code": "dup_role", "name": "角色1"
        })
        response = client.post("/system/roles", headers=auth_headers, json={
            "code": "dup_role", "name": "角色2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_get_role(self, client: TestClient, auth_headers):
        create = client.post("/system/roles", headers=auth_headers, json={
            "code": "get_test", "name": "获取测试"
        })
        role_id = create.json()["id"]

        response = client.get(f"/system/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "get_test"
        assert "permissions" in data

    def test_get_role_not_found(self, client: TestClient, auth_headers):
        response = client.get("/system/roles/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_role(self, client: TestClient, auth_headers):
        create = client.post("/system/roles", headers=auth_headers, json={
            "code": "upd_role", "name": "旧名称"
        })
        role_id = create.json()["id"]

        response = client.put(f"/system/roles/{role_id}", headers=auth_headers, json={
            "name": "新名称", "data_scope": "SELF"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"
        assert response.json()["data_scope"] == "SELF"

    def test_delete_role(self, client: TestClient, auth_headers):
        create = client.post("/system/roles", headers=auth_headers, json={
            "code": "del_role", "name": "待删除"
        })
        role_id = create.json()["id"]

        response = client.delete(f"/system/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/system/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_system_role_blocked(self, client: TestClient, auth_headers, db_session):
        """系统内置角色不可删除"""
        from app.system.models.rbac import SysRole
        role = SysRole(code="sys_test", name="系统角色", is_system=True)
        db_session.add(role)
        db_session.commit()

        response = client.delete(f"/system/roles/{role.id}", headers=auth_headers)
        assert response.status_code == 400
        assert "不可删除" in response.json()["detail"]

    def test_assign_role_permissions(self, client: TestClient, auth_headers, db_session):
        """分配权限给角色"""
        from app.system.models.rbac import SysPermission
        # Create role
        create = client.post("/system/roles", headers=auth_headers, json={
            "code": "perm_role", "name": "权限测试角色"
        })
        role_id = create.json()["id"]

        # Create permissions
        p1 = SysPermission(code="test:view", name="查看", type="api", resource="test", action="view")
        p2 = SysPermission(code="test:edit", name="编辑", type="api", resource="test", action="edit")
        db_session.add_all([p1, p2])
        db_session.commit()

        # Assign
        response = client.put(
            f"/system/roles/{role_id}/permissions",
            headers=auth_headers,
            json=[p1.id, p2.id],
        )
        assert response.status_code == 200

        # Verify via detail
        detail = client.get(f"/system/roles/{role_id}", headers=auth_headers)
        assert len(detail.json()["permissions"]) == 2

    def test_unauthenticated_access(self, client: TestClient):
        response = client.get("/system/roles")
        assert response.status_code in (401, 403)

    def test_cleaner_cannot_create_role(self, client: TestClient, cleaner_headers):
        """清洁员无权创建角色"""
        response = client.post("/system/roles", headers=cleaner_headers, json={
            "code": "no_way", "name": "不可能"
        })
        assert response.status_code == 403


# ========== Permission API Tests ==========


class TestPermissionAPI:
    """权限管理 API 测试"""

    def test_list_permissions_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/permissions", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_permission(self, client: TestClient, auth_headers):
        response = client.post("/system/permissions", headers=auth_headers, json={
            "code": "room:view",
            "name": "查看房间",
            "type": "api",
            "resource": "room",
            "action": "view",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "room:view"
        assert data["resource"] == "room"
        assert data["action"] == "view"

    def test_create_permission_duplicate(self, client: TestClient, auth_headers):
        client.post("/system/permissions", headers=auth_headers, json={
            "code": "dup:perm", "name": "重复"
        })
        response = client.post("/system/permissions", headers=auth_headers, json={
            "code": "dup:perm", "name": "重复2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_update_permission(self, client: TestClient, auth_headers):
        create = client.post("/system/permissions", headers=auth_headers, json={
            "code": "upd:perm", "name": "旧名称"
        })
        perm_id = create.json()["id"]

        response = client.put(f"/system/permissions/{perm_id}", headers=auth_headers, json={
            "name": "新名称"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"

    def test_delete_permission(self, client: TestClient, auth_headers):
        create = client.post("/system/permissions", headers=auth_headers, json={
            "code": "del:perm", "name": "待删"
        })
        perm_id = create.json()["id"]

        response = client.delete(f"/system/permissions/{perm_id}", headers=auth_headers)
        assert response.status_code == 204

    def test_delete_permission_in_use(self, client: TestClient, auth_headers, db_session):
        """被使用中的权限不可删除"""
        from app.system.models.rbac import SysPermission, SysRole, SysRolePermission

        perm = SysPermission(code="used:perm", name="使用中", type="api")
        role = SysRole(code="using_role", name="使用角色")
        db_session.add_all([perm, role])
        db_session.flush()
        db_session.add(SysRolePermission(role_id=role.id, permission_id=perm.id))
        db_session.commit()

        response = client.delete(f"/system/permissions/{perm.id}", headers=auth_headers)
        assert response.status_code == 400
        assert "仍被" in response.json()["detail"]

    def test_permission_tree(self, client: TestClient, auth_headers, db_session):
        """权限树返回层级结构"""
        from app.system.models.rbac import SysPermission

        parent = SysPermission(code="room", name="房间管理", type="menu")
        db_session.add(parent)
        db_session.flush()
        child = SysPermission(code="room:view", name="查看房间", type="api", parent_id=parent.id)
        db_session.add(child)
        db_session.commit()

        response = client.get("/system/permissions/tree", headers=auth_headers)
        assert response.status_code == 200
        tree = response.json()
        assert len(tree) >= 1
        # Find our parent
        room_node = [n for n in tree if n["code"] == "room"]
        assert len(room_node) == 1
        assert len(room_node[0]["children"]) == 1
        assert room_node[0]["children"][0]["code"] == "room:view"

    def test_filter_by_type(self, client: TestClient, auth_headers, db_session):
        """按类型过滤权限"""
        from app.system.models.rbac import SysPermission

        db_session.add(SysPermission(code="menu:test", name="菜单", type="menu"))
        db_session.add(SysPermission(code="api:test", name="接口", type="api"))
        db_session.commit()

        response = client.get("/system/permissions?perm_type=menu", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(p["type"] == "menu" for p in data)


# ========== User-Role API Tests ==========


class TestUserRoleAPI:
    """用户角色 API 测试"""

    def test_get_user_roles_empty(self, client: TestClient, auth_headers):
        """未分配角色的用户"""
        response = client.get("/system/users/999/roles", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 999
        assert data["roles"] == []

    def test_assign_and_get_user_roles(self, client: TestClient, auth_headers, db_session):
        """分配角色并查询"""
        from app.system.models.rbac import SysRole

        # Create roles
        role1 = SysRole(code="ur_role1", name="角色1")
        role2 = SysRole(code="ur_role2", name="角色2")
        db_session.add_all([role1, role2])
        db_session.commit()

        # Create a user
        user = Employee(
            username="testuser_ur",
            password_hash=get_password_hash("123456"),
            name="测试用户",
            role=EmployeeRole.RECEPTIONIST,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Assign roles
        response = client.put(
            f"/system/users/{user.id}/roles",
            headers=auth_headers,
            json={"role_ids": [role1.id, role2.id]},
        )
        assert response.status_code == 200

        # Query
        response = client.get(f"/system/users/{user.id}/roles", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["roles"]) == 2
        role_codes = {r["code"] for r in data["roles"]}
        assert "ur_role1" in role_codes
        assert "ur_role2" in role_codes

    def test_reassign_user_roles(self, client: TestClient, auth_headers, db_session):
        """重新分配角色（替换）"""
        from app.system.models.rbac import SysRole

        role_a = SysRole(code="ra", name="角色A")
        role_b = SysRole(code="rb", name="角色B")
        db_session.add_all([role_a, role_b])
        db_session.commit()

        user = Employee(
            username="testuser_reassign",
            password_hash=get_password_hash("123456"),
            name="重新分配",
            role=EmployeeRole.RECEPTIONIST,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # First assign
        client.put(
            f"/system/users/{user.id}/roles",
            headers=auth_headers,
            json={"role_ids": [role_a.id]},
        )

        # Reassign to role_b only
        client.put(
            f"/system/users/{user.id}/roles",
            headers=auth_headers,
            json={"role_ids": [role_b.id]},
        )

        response = client.get(f"/system/users/{user.id}/roles", headers=auth_headers)
        data = response.json()
        assert len(data["roles"]) == 1
        assert data["roles"][0]["code"] == "rb"

    def test_cleaner_cannot_assign_roles(self, client: TestClient, cleaner_headers):
        """清洁员无权分配角色"""
        response = client.put(
            "/system/users/1/roles",
            headers=cleaner_headers,
            json={"role_ids": [1]},
        )
        assert response.status_code == 403
