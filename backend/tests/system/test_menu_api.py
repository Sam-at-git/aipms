"""
菜单管理 API 测试
覆盖 /system/menus 端点
"""
import pytest
from fastapi.testclient import TestClient
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token
from app.system.models.menu import SysMenu


@pytest.fixture
def cleaner_headers(db_session):
    """Create cleaner user and return auth headers"""
    cleaner = Employee(
        username="cleaner_menu",
        password_hash=get_password_hash("123456"),
        name="清洁员",
        role=EmployeeRole.CLEANER,
        is_active=True,
    )
    db_session.add(cleaner)
    db_session.commit()
    token = create_access_token(cleaner.id, cleaner.role)
    return {"Authorization": f"Bearer {token}"}


class TestMenuAPI:
    """菜单管理 API 测试"""

    def test_list_menus_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/menus", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_menu(self, client: TestClient, auth_headers):
        response = client.post("/system/menus", headers=auth_headers, json={
            "code": "test_menu",
            "name": "测试菜单",
            "path": "/test",
            "icon": "Star",
            "menu_type": "menu",
            "sort_order": 10,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "test_menu"
        assert data["name"] == "测试菜单"
        assert data["path"] == "/test"
        assert data["icon"] == "Star"
        assert data["menu_type"] == "menu"

    def test_create_menu_duplicate(self, client: TestClient, auth_headers):
        client.post("/system/menus", headers=auth_headers, json={
            "code": "dup_menu", "name": "重复菜单"
        })
        response = client.post("/system/menus", headers=auth_headers, json={
            "code": "dup_menu", "name": "重复2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_update_menu(self, client: TestClient, auth_headers):
        create = client.post("/system/menus", headers=auth_headers, json={
            "code": "upd_menu", "name": "旧名称"
        })
        menu_id = create.json()["id"]

        response = client.put(f"/system/menus/{menu_id}", headers=auth_headers, json={
            "name": "新名称", "icon": "Home"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"
        assert response.json()["icon"] == "Home"

    def test_delete_menu(self, client: TestClient, auth_headers):
        create = client.post("/system/menus", headers=auth_headers, json={
            "code": "del_menu", "name": "待删除"
        })
        menu_id = create.json()["id"]

        response = client.delete(f"/system/menus/{menu_id}", headers=auth_headers)
        assert response.status_code == 204

    def test_delete_menu_with_children(self, client: TestClient, auth_headers):
        """有子菜单时不可删除"""
        parent = client.post("/system/menus", headers=auth_headers, json={
            "code": "parent_menu", "name": "父菜单", "menu_type": "directory"
        })
        parent_id = parent.json()["id"]

        client.post("/system/menus", headers=auth_headers, json={
            "code": "child_menu", "name": "子菜单", "parent_id": parent_id
        })

        response = client.delete(f"/system/menus/{parent_id}", headers=auth_headers)
        assert response.status_code == 400
        assert "子菜单" in response.json()["detail"]

    def test_get_menu_tree(self, client: TestClient, auth_headers):
        """获取菜单树"""
        parent = client.post("/system/menus", headers=auth_headers, json={
            "code": "tree_parent", "name": "父菜单", "menu_type": "directory"
        })
        parent_id = parent.json()["id"]

        client.post("/system/menus", headers=auth_headers, json={
            "code": "tree_child", "name": "子菜单", "parent_id": parent_id
        })

        response = client.get("/system/menus/tree", headers=auth_headers)
        assert response.status_code == 200
        tree = response.json()
        parent_node = [n for n in tree if n["code"] == "tree_parent"]
        assert len(parent_node) == 1
        assert len(parent_node[0]["children"]) == 1

    def test_get_user_menus(self, client: TestClient, auth_headers):
        """获取用户菜单"""
        client.post("/system/menus", headers=auth_headers, json={
            "code": "user_menu", "name": "用户菜单", "is_visible": True
        })

        response = client.get("/system/menus/user", headers=auth_headers)
        assert response.status_code == 200
        # Manager can see menus with no permission_code requirement
        data = response.json()
        assert isinstance(data, list)

    def test_cleaner_cannot_create_menu(self, client: TestClient, cleaner_headers):
        """清洁员无权创建菜单"""
        response = client.post("/system/menus", headers=cleaner_headers, json={
            "code": "no_way", "name": "不行"
        })
        assert response.status_code == 403

    def test_unauthenticated_access(self, client: TestClient):
        response = client.get("/system/menus")
        assert response.status_code in (401, 403)

    def test_menu_with_permission(self, client: TestClient, db_session):
        """带权限码的菜单在用户菜单中正确过滤（经理用户）"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash, create_access_token

        mgr = Employee(
            username="mgr_menu_perm",
            password_hash=get_password_hash("123456"),
            name="经理",
            role=EmployeeRole.MANAGER,
            is_active=True,
        )
        db_session.add(mgr)
        db_session.commit()
        token = create_access_token(mgr.id, mgr.role)
        mgr_headers = {"Authorization": f"Bearer {token}"}

        # Create menus with different permission requirements
        db_session.add(SysMenu(code="perm_menu1", name="无权限菜单", is_visible=True, sort_order=1))
        db_session.add(SysMenu(code="perm_menu2", name="需权限菜单", permission_code="secret:access", is_visible=True, sort_order=2))
        db_session.commit()

        response = client.get("/system/menus/user", headers=mgr_headers)
        data = response.json()
        codes = [m["code"] for m in data]
        # No-permission menu should show; permission-required menu should be filtered
        assert "perm_menu1" in codes
        # perm_menu2 requires "secret:access" which manager doesn't have
        assert "perm_menu2" not in codes


class TestMenuSeed:
    """菜单种子数据测试"""

    def test_seed_menu_data(self, db_session):
        from app.system.services.menu_seed import seed_menu_data
        stats = seed_menu_data(db_session)
        assert stats["menus"] > 0

        # Verify system menu exists
        system_menu = db_session.query(SysMenu).filter(SysMenu.code == "system").first()
        assert system_menu is not None
        assert system_menu.menu_type == "directory"

        # Verify sub-menus under system
        sub_menus = db_session.query(SysMenu).filter(SysMenu.parent_id == system_menu.id).all()
        assert len(sub_menus) >= 3  # dicts, configs, rbac, settings, debug

    def test_seed_idempotent(self, db_session):
        from app.system.services.menu_seed import seed_menu_data
        stats1 = seed_menu_data(db_session)
        stats2 = seed_menu_data(db_session)
        assert stats2["menus"] == 0  # All already exist
