"""
Tests for app/hotel/services/employee_service.py - increasing coverage.
Covers: create, update, deactivate, password reset, change password,
authentication, last-manager guard, sysadmin password guard.
"""
import pytest

from app.hotel.models.ontology import Employee, EmployeeRole
from app.hotel.models.schemas import EmployeeCreate, EmployeeUpdate, PasswordReset, PasswordChange
from app.hotel.services.employee_service import EmployeeService
from app.security.auth import get_password_hash, verify_password


class TestGetEmployees:
    """Test employee list/get methods."""

    def test_get_employees_no_filter(self, db_session, sample_cleaner):
        """Get all employees (at least the cleaner from fixture)."""
        svc = EmployeeService(db_session)
        employees = svc.get_employees()
        assert len(employees) >= 1

    def test_get_employees_filter_by_role(self, db_session, sample_cleaner):
        """Get employees filtered by role."""
        svc = EmployeeService(db_session)
        cleaners = svc.get_employees(role=EmployeeRole.CLEANER)
        assert len(cleaners) >= 1
        for e in cleaners:
            assert e.role == EmployeeRole.CLEANER

    def test_get_employees_filter_by_active(self, db_session):
        """Get employees filtered by is_active."""
        svc = EmployeeService(db_session)
        active = svc.get_employees(is_active=True)
        for e in active:
            assert e.is_active is True

    def test_get_employee_by_id(self, db_session, sample_cleaner):
        """Get employee by id."""
        svc = EmployeeService(db_session)
        emp = svc.get_employee(sample_cleaner.id)
        assert emp is not None
        assert emp.role == EmployeeRole.CLEANER

    def test_get_employee_not_found(self, db_session):
        """Get non-existent employee."""
        svc = EmployeeService(db_session)
        emp = svc.get_employee(99999)
        assert emp is None

    def test_get_employee_by_username(self, db_session, sample_cleaner):
        """Get employee by username."""
        svc = EmployeeService(db_session)
        emp = svc.get_employee_by_username(sample_cleaner.username)
        assert emp is not None
        assert emp.id == sample_cleaner.id

    def test_get_employee_by_username_not_found(self, db_session):
        """Get employee by non-existent username."""
        svc = EmployeeService(db_session)
        emp = svc.get_employee_by_username("no_such_user")
        assert emp is None


class TestCreateEmployee:
    """Test employee creation."""

    def test_create_employee_success(self, db_session):
        """Create employee successfully."""
        svc = EmployeeService(db_session)
        data = EmployeeCreate(
            username="newuser",
            password="password123",
            name="新员工",
            role=EmployeeRole.RECEPTIONIST,
        )
        emp = svc.create_employee(data)
        assert emp.id is not None
        assert emp.username == "newuser"
        assert emp.role == EmployeeRole.RECEPTIONIST
        assert verify_password("password123", emp.password_hash)

    def test_create_employee_with_phone(self, db_session):
        """Create employee with phone."""
        svc = EmployeeService(db_session)
        data = EmployeeCreate(
            username="withphone",
            password="pass123",
            name="有电话的员工",
            role=EmployeeRole.CLEANER,
            phone="13700137000",
        )
        emp = svc.create_employee(data)
        assert emp.phone == "13700137000"

    def test_create_employee_duplicate_username(self, db_session, sample_cleaner):
        """Create employee with duplicate username raises ValueError."""
        svc = EmployeeService(db_session)
        data = EmployeeCreate(
            username=sample_cleaner.username,
            password="pass123",
            name="重名用户",
            role=EmployeeRole.RECEPTIONIST,
        )
        with pytest.raises(ValueError, match="已存在"):
            svc.create_employee(data)


class TestUpdateEmployee:
    """Test employee update."""

    def test_update_employee_name(self, db_session, sample_cleaner):
        """Update employee name."""
        svc = EmployeeService(db_session)
        data = EmployeeUpdate(name="改名了")
        emp = svc.update_employee(sample_cleaner.id, data)
        assert emp.name == "改名了"

    def test_update_employee_phone(self, db_session, sample_cleaner):
        """Update employee phone."""
        svc = EmployeeService(db_session)
        data = EmployeeUpdate(phone="13800138999")
        emp = svc.update_employee(sample_cleaner.id, data)
        assert emp.phone == "13800138999"

    def test_update_employee_role(self, db_session, sample_cleaner):
        """Update employee role."""
        svc = EmployeeService(db_session)
        data = EmployeeUpdate(role=EmployeeRole.RECEPTIONIST)
        emp = svc.update_employee(sample_cleaner.id, data)
        assert emp.role == EmployeeRole.RECEPTIONIST

    def test_update_employee_not_found(self, db_session):
        """Update non-existent employee."""
        svc = EmployeeService(db_session)
        data = EmployeeUpdate(name="Nobody")
        with pytest.raises(ValueError, match="员工不存在"):
            svc.update_employee(99999, data)

    def test_update_employee_no_changes(self, db_session, sample_cleaner):
        """Update employee with no actual changes."""
        svc = EmployeeService(db_session)
        data = EmployeeUpdate()
        emp = svc.update_employee(sample_cleaner.id, data)
        assert emp.id == sample_cleaner.id

    def test_update_last_manager_role_guard(self, db_session):
        """Changing role of the last manager raises ValueError."""
        # Create a manager
        mgr = Employee(
            username="sole_manager",
            password_hash=get_password_hash("pass"),
            name="唯一经理",
            role=EmployeeRole.MANAGER,
        )
        db_session.add(mgr)
        db_session.commit()

        # Ensure it's the only active manager
        other_managers = db_session.query(Employee).filter(
            Employee.role == EmployeeRole.MANAGER,
            Employee.is_active == True,
            Employee.id != mgr.id,
        ).all()
        for m in other_managers:
            m.is_active = False
        db_session.commit()

        svc = EmployeeService(db_session)
        data = EmployeeUpdate(role=EmployeeRole.RECEPTIONIST)
        with pytest.raises(ValueError, match="至少保留一个经理"):
            svc.update_employee(mgr.id, data)

    def test_update_last_manager_deactivate_guard(self, db_session):
        """Deactivating the last manager via update raises ValueError."""
        mgr = Employee(
            username="sole_manager2",
            password_hash=get_password_hash("pass"),
            name="唯一经理2",
            role=EmployeeRole.MANAGER,
        )
        db_session.add(mgr)
        db_session.commit()

        # Ensure it's the only active manager
        other_managers = db_session.query(Employee).filter(
            Employee.role == EmployeeRole.MANAGER,
            Employee.is_active == True,
            Employee.id != mgr.id,
        ).all()
        for m in other_managers:
            m.is_active = False
        db_session.commit()

        svc = EmployeeService(db_session)
        data = EmployeeUpdate(is_active=False)
        with pytest.raises(ValueError, match="至少保留一个"):
            svc.update_employee(mgr.id, data)


class TestDeleteEmployee:
    """Test employee deactivation (soft delete)."""

    def test_delete_employee(self, db_session, sample_cleaner):
        """Deactivate (soft delete) employee."""
        svc = EmployeeService(db_session)
        result = svc.delete_employee(sample_cleaner.id)
        assert result is True
        db_session.refresh(sample_cleaner)
        assert sample_cleaner.is_active is False

    def test_delete_employee_not_found(self, db_session):
        """Delete non-existent employee."""
        svc = EmployeeService(db_session)
        with pytest.raises(ValueError, match="员工不存在"):
            svc.delete_employee(99999)

    def test_delete_last_manager_guard(self, db_session):
        """Delete last manager raises ValueError."""
        mgr = Employee(
            username="last_mgr",
            password_hash=get_password_hash("pass"),
            name="最后经理",
            role=EmployeeRole.MANAGER,
        )
        db_session.add(mgr)
        db_session.commit()

        # Ensure only manager
        other_managers = db_session.query(Employee).filter(
            Employee.role == EmployeeRole.MANAGER,
            Employee.is_active == True,
            Employee.id != mgr.id,
        ).all()
        for m in other_managers:
            m.is_active = False
        db_session.commit()

        svc = EmployeeService(db_session)
        with pytest.raises(ValueError, match="至少保留一个经理"):
            svc.delete_employee(mgr.id)


class TestPasswordReset:
    """Test password reset."""

    def test_reset_password(self, db_session, sample_cleaner):
        """Reset password successfully."""
        svc = EmployeeService(db_session)
        data = PasswordReset(new_password="newpass123")

        operator = Employee(
            username="op_manager_pw",
            password_hash=get_password_hash("pass"),
            name="操作经理",
            role=EmployeeRole.MANAGER,
        )
        db_session.add(operator)
        db_session.commit()

        result = svc.reset_password(sample_cleaner.id, data, operator=operator)
        assert result is True
        db_session.refresh(sample_cleaner)
        assert verify_password("newpass123", sample_cleaner.password_hash)

    def test_reset_password_not_found(self, db_session):
        """Reset password for non-existent employee."""
        svc = EmployeeService(db_session)
        data = PasswordReset(new_password="newpass")
        with pytest.raises(ValueError, match="员工不存在"):
            svc.reset_password(99999, data)

    def test_reset_sysadmin_by_non_sysadmin(self, db_session):
        """Non-sysadmin trying to reset sysadmin password fails."""
        sysadmin = Employee(
            username="sysadmin_pw",
            password_hash=get_password_hash("oldpass"),
            name="系统管理员",
            role=EmployeeRole.SYSADMIN,
        )
        operator = Employee(
            username="mgr_pw",
            password_hash=get_password_hash("pass"),
            name="经理",
            role=EmployeeRole.MANAGER,
        )
        db_session.add_all([sysadmin, operator])
        db_session.commit()

        svc = EmployeeService(db_session)
        data = PasswordReset(new_password="newpass")
        with pytest.raises(ValueError, match="只有系统管理员"):
            svc.reset_password(sysadmin.id, data, operator=operator)

    def test_reset_sysadmin_by_sysadmin(self, db_session):
        """Sysadmin can reset sysadmin password."""
        sysadmin = Employee(
            username="sysadmin_pw2",
            password_hash=get_password_hash("oldpass"),
            name="系统管理员2",
            role=EmployeeRole.SYSADMIN,
        )
        operator = Employee(
            username="sysadmin_op",
            password_hash=get_password_hash("pass"),
            name="另一个管理员",
            role=EmployeeRole.SYSADMIN,
        )
        db_session.add_all([sysadmin, operator])
        db_session.commit()

        svc = EmployeeService(db_session)
        data = PasswordReset(new_password="newpass456")
        result = svc.reset_password(sysadmin.id, data, operator=operator)
        assert result is True

    def test_reset_sysadmin_no_operator(self, db_session):
        """Resetting sysadmin password with no operator fails."""
        sysadmin = Employee(
            username="sysadmin_pw3",
            password_hash=get_password_hash("oldpass"),
            name="系统管理员3",
            role=EmployeeRole.SYSADMIN,
        )
        db_session.add(sysadmin)
        db_session.commit()

        svc = EmployeeService(db_session)
        data = PasswordReset(new_password="newpass")
        with pytest.raises(ValueError, match="只有系统管理员"):
            svc.reset_password(sysadmin.id, data, operator=None)


class TestChangePassword:
    """Test change password (self-service)."""

    def test_change_password_success(self, db_session):
        """Change password successfully."""
        emp = Employee(
            username="change_pw",
            password_hash=get_password_hash("oldpass"),
            name="自改密码",
            role=EmployeeRole.RECEPTIONIST,
        )
        db_session.add(emp)
        db_session.commit()

        svc = EmployeeService(db_session)
        data = PasswordChange(old_password="oldpass", new_password="newpass789")
        result = svc.change_password(emp.id, data)
        assert result is True
        db_session.refresh(emp)
        assert verify_password("newpass789", emp.password_hash)

    def test_change_password_wrong_old(self, db_session):
        """Change password with wrong old password."""
        emp = Employee(
            username="change_pw_wrong",
            password_hash=get_password_hash("correctpass"),
            name="密码错误",
            role=EmployeeRole.RECEPTIONIST,
        )
        db_session.add(emp)
        db_session.commit()

        svc = EmployeeService(db_session)
        data = PasswordChange(old_password="wrongpass", new_password="newpass123")
        with pytest.raises(ValueError, match="原密码错误"):
            svc.change_password(emp.id, data)

    def test_change_password_not_found(self, db_session):
        """Change password for non-existent employee."""
        svc = EmployeeService(db_session)
        data = PasswordChange(old_password="oldpass", new_password="newpass123")
        with pytest.raises(ValueError, match="员工不存在"):
            svc.change_password(99999, data)


class TestAuthenticate:
    """Test authentication."""

    def test_authenticate_success(self, db_session):
        """Successful authentication."""
        emp = Employee(
            username="auth_user",
            password_hash=get_password_hash("mypass"),
            name="认证用户",
            role=EmployeeRole.RECEPTIONIST,
        )
        db_session.add(emp)
        db_session.commit()

        svc = EmployeeService(db_session)
        result = svc.authenticate("auth_user", "mypass")
        assert result is not None
        assert "access_token" in result
        assert result["employee"]["username"] == "auth_user"

    def test_authenticate_wrong_password(self, db_session):
        """Authentication with wrong password."""
        emp = Employee(
            username="auth_user_bad",
            password_hash=get_password_hash("correct"),
            name="密码错误",
            role=EmployeeRole.RECEPTIONIST,
        )
        db_session.add(emp)
        db_session.commit()

        svc = EmployeeService(db_session)
        result = svc.authenticate("auth_user_bad", "wrong")
        assert result is None

    def test_authenticate_user_not_found(self, db_session):
        """Authentication with non-existent user."""
        svc = EmployeeService(db_session)
        result = svc.authenticate("not_exist", "pass")
        assert result is None

    def test_authenticate_inactive_user(self, db_session):
        """Authentication with inactive user raises ValueError."""
        emp = Employee(
            username="inactive_auth",
            password_hash=get_password_hash("pass"),
            name="已停用",
            role=EmployeeRole.RECEPTIONIST,
            is_active=False,
        )
        db_session.add(emp)
        db_session.commit()

        svc = EmployeeService(db_session)
        with pytest.raises(ValueError, match="账号已停用"):
            svc.authenticate("inactive_auth", "pass")
