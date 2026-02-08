"""Tests for SystemCommandHandler"""
import pytest
from app.services.ai_service import SystemCommandHandler
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash


@pytest.fixture
def handler():
    return SystemCommandHandler()


@pytest.fixture
def sysadmin_user(db_session):
    admin = Employee(
        username="admin_cmd",
        password_hash=get_password_hash("123456"),
        name="系统管理员",
        role=EmployeeRole.SYSADMIN,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def receptionist_user(db_session):
    user = Employee(
        username="front_cmd",
        password_hash=get_password_hash("123456"),
        name="前台",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestIsSystemCommand:
    def test_hash_with_letters(self, handler):
        assert handler.is_system_command("#ROOM") is True

    def test_hash_with_chinese(self, handler):
        assert handler.is_system_command("#房间") is True

    def test_hash_with_query(self, handler):
        assert handler.is_system_command("#查询Room对象定义") is True

    def test_hash_with_number_not_command(self, handler):
        """#123 should NOT be a system command"""
        assert handler.is_system_command("#123") is False

    def test_no_hash_not_command(self, handler):
        assert handler.is_system_command("查询房间") is False

    def test_hash_alone_not_command(self, handler):
        assert handler.is_system_command("#") is False

    def test_hash_logs(self, handler):
        assert handler.is_system_command("#日志") is True


class TestExecute:
    def test_non_sysadmin_denied(self, handler, receptionist_user, db_session):
        result = handler.execute("#ROOM", receptionist_user, db_session)
        assert "系统管理员" in result["message"]

    def test_sysadmin_can_query_entity(self, handler, sysadmin_user, db_session):
        result = handler.execute("#Room", sysadmin_user, db_session)
        # Should return some response (may be entity data or "not found" depending on metadata service)
        assert "message" in result
        assert "suggested_actions" in result

    def test_query_entity_chinese_pattern(self, handler, sysadmin_user, db_session):
        result = handler.execute("#查询Room对象定义", sysadmin_user, db_session)
        assert "message" in result

    def test_query_logs(self, handler, sysadmin_user, db_session):
        result = handler.execute("#日志", sysadmin_user, db_session)
        assert "message" in result
        assert result["context"]["command"] == "logs"
