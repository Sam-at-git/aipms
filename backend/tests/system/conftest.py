"""
System test fixtures — system management endpoints require sys:* permissions,
so default auth uses sysadmin role (overrides global auth_headers from tests/conftest.py).
"""
import pytest
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token


@pytest.fixture
def auth_headers(db_session):
    """System tests default to sysadmin (system endpoints require sys:* permissions)"""
    admin = Employee(
        username="sysadmin_sys",
        password_hash=get_password_hash("123456"),
        name="系统管理员",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(admin.id, admin.role)
    return {"Authorization": f"Bearer {token}"}
