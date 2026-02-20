"""
SPEC-21: Auth RBAC migration tests
Tests JWT structure, dynamic permission checking, and role fallback behavior
"""
import pytest
from jose import jwt
from app.security.auth import (
    create_access_token, decode_token, SECRET_KEY, ALGORITHM,
    _get_role_codes, _get_max_data_scope, _get_branch_id,
)
from app.models.ontology import Employee, EmployeeRole


class TestJWTStructure:
    """Test new JWT token structure"""

    def test_jwt_contains_basic_fields(self):
        token = create_access_token(1, EmployeeRole.MANAGER)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "1"
        assert payload["role"] == "manager"
        assert "exp" in payload

    def test_jwt_contains_role_codes(self):
        token = create_access_token(
            1, EmployeeRole.MANAGER,
            role_codes=["manager", "report_viewer"]
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["role_codes"] == ["manager", "report_viewer"]

    def test_jwt_contains_branch_id(self):
        token = create_access_token(
            1, EmployeeRole.MANAGER,
            branch_id=2
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["branch_id"] == 2

    def test_jwt_contains_data_scope(self):
        token = create_access_token(
            1, EmployeeRole.MANAGER,
            data_scope="DEPT_AND_BELOW"
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["data_scope"] == "DEPT_AND_BELOW"

    def test_jwt_full_new_format(self):
        token = create_access_token(
            5, EmployeeRole.RECEPTIONIST,
            role_codes=["receptionist"],
            branch_id=3,
            data_scope="DEPT"
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "5"
        assert payload["role"] == "receptionist"
        assert payload["role_codes"] == ["receptionist"]
        assert payload["branch_id"] == 3
        assert payload["data_scope"] == "DEPT"

    def test_jwt_backward_compatible_no_new_fields(self):
        """Old-format tokens still work"""
        token = create_access_token(1, EmployeeRole.SYSADMIN)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "1"
        assert payload["role"] == "sysadmin"
        assert "role_codes" not in payload
        assert "branch_id" not in payload

    def test_decode_token(self):
        token = create_access_token(42, EmployeeRole.CLEANER)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "cleaner"


class TestPermissionEndpoints:
    """Test require_permission decorator via API endpoints"""

    def test_sysadmin_has_all_permissions(self, client, sysadmin_token):
        headers = {"Authorization": f"Bearer {sysadmin_token}"}
        # sysadmin should access employee list
        response = client.get("/employees", headers=headers)
        assert response.status_code == 200

    def test_manager_has_business_permissions(self, client, manager_token):
        headers = {"Authorization": f"Bearer {manager_token}"}
        # manager should access employee list
        response = client.get("/employees", headers=headers)
        assert response.status_code == 200

    def test_cleaner_denied_employee_access(self, client, cleaner_token):
        headers = {"Authorization": f"Bearer {cleaner_token}"}
        # cleaner should NOT access employee list
        response = client.get("/employees", headers=headers)
        assert response.status_code == 403

    def test_receptionist_has_room_read(self, client, receptionist_token):
        headers = {"Authorization": f"Bearer {receptionist_token}"}
        response = client.get("/rooms/types", headers=headers)
        assert response.status_code == 200

    def test_receptionist_denied_price_write(self, client, receptionist_token):
        headers = {"Authorization": f"Bearer {receptionist_token}"}
        response = client.post("/rooms/types", headers=headers, json={
            "name": "Test", "base_price": 100
        })
        assert response.status_code == 403

    def test_unauthenticated_request(self, client):
        response = client.get("/employees")
        assert response.status_code in (401, 403)


class TestLoginResponse:
    """Test login endpoint returns new fields"""

    def test_login_returns_branch_info(self, client, db_session):
        """Login response includes branch_id, branch_name, role_codes"""
        from app.models.ontology import Employee
        from app.security.auth import get_password_hash

        emp = Employee(
            username="test_login",
            password_hash=get_password_hash("pass123"),
            name="Test User",
            role=EmployeeRole.MANAGER,
            is_active=True,
        )
        db_session.add(emp)
        db_session.commit()

        response = client.post("/auth/login", json={
            "username": "test_login",
            "password": "pass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "employee" in data
        emp_data = data["employee"]
        assert emp_data["username"] == "test_login"
        # New fields should be present (even if None/empty)
        assert "branch_id" in emp_data
        assert "branch_name" in emp_data
        assert "role_codes" in emp_data
        assert "department_id" in emp_data
