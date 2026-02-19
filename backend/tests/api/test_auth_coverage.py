"""
tests/api/test_auth_coverage.py

Additional coverage tests for auth module - covers password change, token validation,
inactive user, and permission checking paths.
"""
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, UTC

from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import (
    get_password_hash, create_access_token, decode_token,
    SECRET_KEY, ALGORITHM, require_permission,
)


class TestDecodeTokenErrors:
    """Cover line 50-54: JWTError in decode_token."""

    def test_decode_invalid_token(self):
        """decode_token with invalid JWT string raises HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.valid.jwt")
        assert exc_info.value.status_code == 401

    def test_decode_expired_token(self):
        """decode_token with expired token raises HTTPException."""
        from fastapi import HTTPException
        expired_payload = {
            "sub": "1",
            "role": "manager",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    """Cover lines 69, 75: user not found and inactive user paths."""

    def test_user_not_found(self, client, db_session):
        """get_current_user returns 401 when user not found in DB (line 69)."""
        # Create a token for a non-existent user
        token = create_access_token(99999, EmployeeRole.MANAGER)
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "用户不存在" in response.json()["detail"]

    def test_inactive_user(self, client, db_session):
        """get_current_user returns 401 when user is inactive (line 75)."""
        # Create inactive user
        inactive_user = Employee(
            username="inactive_test",
            password_hash=get_password_hash("123456"),
            name="Inactive User",
            role=EmployeeRole.RECEPTIONIST,
            is_active=False,
        )
        db_session.add(inactive_user)
        db_session.commit()
        db_session.refresh(inactive_user)

        token = create_access_token(inactive_user.id, inactive_user.role)
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "账号已停用" in response.json()["detail"]


class TestChangePassword:
    """Cover lines 107-124: change password and require_permission paths."""

    def test_change_password_success(self, client, db_session, manager_token):
        """Successful password change."""
        response = client.post(
            "/auth/change-password",
            json={"old_password": "123456", "new_password": "newpass123"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "密码修改成功"

    def test_change_password_wrong_old(self, client, db_session, manager_token):
        """Password change fails with wrong old password."""
        response = client.post(
            "/auth/change-password",
            json={"old_password": "wrongpassword", "new_password": "newpass123"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 400


class TestRequirePermission:
    """Cover lines 107-124: require_permission decorator."""

    def test_sysadmin_always_has_permission(self, client, db_session, sysadmin_token):
        """Sysadmin bypasses permission checks (line 111-112)."""
        # Any auth endpoint should work for sysadmin
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {sysadmin_token}"},
        )
        assert response.status_code == 200

    def test_require_permission_denied(self, client, db_session):
        """Non-sysadmin without permission gets 403 (lines 119-123)."""
        from fastapi import APIRouter, Depends

        # Create a test endpoint with require_permission
        test_router = APIRouter()

        @test_router.get("/test-perm")
        async def test_endpoint(
            user: Employee = Depends(require_permission("super_secret_perm")),
        ):
            return {"ok": True}

        from app.main import app
        app.include_router(test_router)

        # Create a non-sysadmin user
        user = Employee(
            username="perm_test_user",
            password_hash=get_password_hash("123456"),
            name="Perm Test",
            role=EmployeeRole.RECEPTIONIST,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = create_access_token(user.id, user.role)
        response = client.get(
            "/test-perm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "缺少权限" in response.json()["detail"]
