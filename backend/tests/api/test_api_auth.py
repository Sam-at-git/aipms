"""
认证 API 单元测试
覆盖 /auth 端点的所有功能
"""
import pytest
from fastapi.testclient import TestClient


class TestAuthLogin:
    """登录接口测试"""

    def test_login_success(self, client: TestClient, db_session):
        """测试成功登录"""
        # 创建测试用户
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        employee = Employee(
            username="manager",
            password_hash=get_password_hash("123456"),
            name="经理",
            role=EmployeeRole.MANAGER,
            is_active=True
        )
        db_session.add(employee)
        db_session.commit()

        # 登录
        response = client.post("/auth/login", json={
            "username": "manager",
            "password": "123456"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["employee"]["username"] == "manager"
        assert data["employee"]["role"] == "manager"

    def test_login_wrong_password(self, client: TestClient, db_session):
        """测试密码错误"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        employee = Employee(
            username="manager",
            password_hash=get_password_hash("123456"),
            name="经理",
            role=EmployeeRole.MANAGER,
            is_active=True
        )
        db_session.add(employee)
        db_session.commit()

        response = client.post("/auth/login", json={
            "username": "manager",
            "password": "wrong_password"
        })

        assert response.status_code == 401

    def test_login_user_not_found(self, client: TestClient):
        """测试用户不存在"""
        response = client.post("/auth/login", json={
            "username": "nonexistent",
            "password": "123456"
        })

        assert response.status_code == 401

    def test_login_inactive_user(self, client: TestClient, db_session):
        """测试停用用户登录"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        employee = Employee(
            username="manager",
            password_hash=get_password_hash("123456"),
            name="经理",
            role=EmployeeRole.MANAGER,
            is_active=False
        )
        db_session.add(employee)
        db_session.commit()

        response = client.post("/auth/login", json={
            "username": "manager",
            "password": "123456"
        })

        assert response.status_code == 401

    def test_login_missing_fields(self, client: TestClient):
        """测试缺少必填字段"""
        # 缺少密码
        response = client.post("/auth/login", json={
            "username": "manager"
        })
        assert response.status_code == 422

        # 缺少用户名
        response = client.post("/auth/login", json={
            "password": "123456"
        })
        assert response.status_code == 422


class TestAuthMe:
    """获取当前用户信息测试"""

    def test_get_current_user(self, client: TestClient, manager_token):
        """测试获取当前用户信息"""
        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {manager_token}"
        })

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "name" in data
        assert "role" in data
        assert data["role"] == "manager"

    def test_get_current_user_no_token(self, client: TestClient):
        """测试无token访问"""
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client: TestClient):
        """测试无效token"""
        response = client.get("/auth/me", headers={
            "Authorization": "Bearer invalid_token"
        })

        assert response.status_code == 401


class TestChangePassword:
    """修改密码测试"""

    def test_change_password_success(self, client: TestClient, manager_token, db_session):
        """测试成功修改密码"""
        response = client.post("/auth/change-password", headers={
            "Authorization": f"Bearer {manager_token}"
        }, json={
            "old_password": "123456",
            "new_password": "new_password123"
        })

        assert response.status_code == 200
        assert "message" in response.json()

    def test_change_password_wrong_old_password(self, client: TestClient, manager_token):
        """测试旧密码错误"""
        response = client.post("/auth/change-password", headers={
            "Authorization": f"Bearer {manager_token}"
        }, json={
            "old_password": "wrong_password",
            "new_password": "new_password123"
        })

        assert response.status_code == 400

    def test_change_password_no_token(self, client: TestClient):
        """测试无token修改密码"""
        response = client.post("/auth/change-password", json={
            "old_password": "123456",
            "new_password": "new_password123"
        })

        assert response.status_code == 401
