"""
系统配置 API 测试
覆盖 /system/configs 端点
"""
import pytest
from fastapi.testclient import TestClient

from app.system.services.config_service import ConfigService


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache between tests"""
    ConfigService.reset_cache()
    yield
    ConfigService.reset_cache()


def _sysadmin_headers(client, db_session):
    """Create sysadmin and return auth headers"""
    from app.models.ontology import Employee, EmployeeRole
    from app.security.auth import get_password_hash, create_access_token

    admin = Employee(
        username="sysadmin_cfg",
        password_hash=get_password_hash("123456"),
        name="系统管理员",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = create_access_token(admin.id, admin.role)
    return {"Authorization": f"Bearer {token}"}


class TestConfigAPI:
    """系统配置 API 测试"""

    def test_list_configs_empty(self, client: TestClient, db_session):
        """空配置列表"""
        headers = _sysadmin_headers(client, db_session)
        response = client.get("/system/configs", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_config(self, client: TestClient, db_session):
        """创建配置"""
        headers = _sysadmin_headers(client, db_session)
        response = client.post("/system/configs", headers=headers, json={
            "group": "system",
            "key": "site.name",
            "value": "AIPMS",
            "name": "站点名称",
            "is_public": True,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "site.name"
        assert data["value"] == "AIPMS"
        assert data["is_public"] is True

    def test_create_config_duplicate_key(self, client: TestClient, db_session):
        """重复 key"""
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "dup.key", "value": "v1", "name": "Test"
        })
        response = client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "dup.key", "value": "v2", "name": "Test2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_get_config_by_key(self, client: TestClient, db_session):
        """按 key 获取"""
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "llm", "key": "llm.model", "value": "deepseek-chat", "name": "LLM Model"
        })
        response = client.get("/system/configs/llm.model", headers=headers)
        assert response.status_code == 200
        assert response.json()["value"] == "deepseek-chat"

    def test_get_config_not_found(self, client: TestClient, db_session):
        """不存在的 key"""
        headers = _sysadmin_headers(client, db_session)
        response = client.get("/system/configs/nonexistent", headers=headers)
        assert response.status_code == 404

    def test_sensitive_value_masked(self, client: TestClient, db_session):
        """敏感值脱敏"""
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "llm", "key": "llm.api_key", "value": "sk-abc123xyz789", "name": "API Key"
        })
        response = client.get("/system/configs/llm.api_key", headers=headers)
        assert response.status_code == 200
        assert response.json()["value"] == "sk****89"

    def test_list_configs_by_group(self, client: TestClient, db_session):
        """按分组过滤"""
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "sys.a", "value": "1", "name": "A"
        })
        client.post("/system/configs", headers=headers, json={
            "group": "llm", "key": "llm.b", "value": "2", "name": "B"
        })

        response = client.get("/system/configs?group=llm", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "llm.b"

    def test_list_config_groups(self, client: TestClient, db_session):
        """获取分组列表"""
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "x", "value": "", "name": "X"
        })
        client.post("/system/configs", headers=headers, json={
            "group": "llm", "key": "y", "value": "", "name": "Y"
        })

        response = client.get("/system/configs/groups", headers=headers)
        assert response.status_code == 200
        groups = response.json()
        assert "system" in groups
        assert "llm" in groups

    def test_update_config(self, client: TestClient, db_session):
        """更新配置"""
        headers = _sysadmin_headers(client, db_session)
        create = client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "upd.test", "value": "old", "name": "Update Test"
        })
        config_id = create.json()["id"]

        response = client.put(f"/system/configs/{config_id}", headers=headers, json={
            "value": "new", "description": "Updated"
        })
        assert response.status_code == 200
        assert response.json()["value"] == "new"
        assert response.json()["description"] == "Updated"

    def test_delete_config(self, client: TestClient, db_session):
        """删除配置"""
        headers = _sysadmin_headers(client, db_session)
        create = client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "del.test", "value": "", "name": "Delete Test"
        })
        config_id = create.json()["id"]

        response = client.delete(f"/system/configs/{config_id}", headers=headers)
        assert response.status_code == 200

    def test_public_configs_no_auth(self, client: TestClient, db_session):
        """公开配置无需认证"""
        # Create public config with sysadmin
        headers = _sysadmin_headers(client, db_session)
        client.post("/system/configs", headers=headers, json={
            "group": "system", "key": "public.site_name", "value": "AIPMS",
            "name": "站点名称", "is_public": True,
        })

        # Access without auth
        response = client.get("/system/configs/public")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["value"] == "AIPMS"

    def test_manager_cannot_access(self, client: TestClient, db_session):
        """经理无法访问系统配置"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash, create_access_token

        mgr = Employee(
            username="mgr_config_test",
            password_hash=get_password_hash("123456"),
            name="经理",
            role=EmployeeRole.MANAGER,
            is_active=True,
        )
        db_session.add(mgr)
        db_session.commit()
        token = create_access_token(mgr.id, mgr.role)
        mgr_headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/system/configs", headers=mgr_headers)
        assert response.status_code == 403
