"""
tests/services/actions/test_employee_actions.py

Tests for employee action handlers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

import app.services.actions.employee_actions as employee_actions
from app.services.actions.base import (
    CreateEmployeeParams, UpdateEmployeeParams, DeactivateEmployeeParams,
)
from app.models.ontology import Employee, EmployeeRole


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "sysadmin"
    user.role = EmployeeRole.SYSADMIN
    return user


@pytest.fixture
def sample_employee():
    emp = Mock(spec=Employee)
    emp.id = 10
    emp.username = "newuser"
    emp.name = "新员工"
    emp.role = EmployeeRole.RECEPTIONIST
    emp.phone = "13800000001"
    emp.is_active = True
    return emp


class TestRegisterEmployeeActions:
    def test_registers_all_actions(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)

        assert registry.get_action("create_employee") is not None
        assert registry.get_action("update_employee") is not None
        assert registry.get_action("deactivate_employee") is not None

    def test_action_metadata(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)

        action = registry.get_action("create_employee")
        assert action.entity == "Employee"
        assert action.category == "mutation"
        assert "sysadmin" in action.allowed_roles


class TestHandleCreateEmployee:
    def test_successful_create(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        # Username check returns None (not duplicate)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda e: setattr(e, 'id', 10))

        params = CreateEmployeeParams(
            username="newuser", name="新员工", role="receptionist"
        )

        with patch('app.security.auth.get_password_hash', return_value="hashed"):
            registry = ActionRegistry()
            employee_actions.register_employee_actions(registry)
            action = registry.get_action("create_employee")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert result["username"] == "newuser"
        mock_db.add.assert_called_once()

    def test_duplicate_username(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_employee

        params = CreateEmployeeParams(
            username="newuser", name="新员工", role="receptionist"
        )

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("create_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "duplicate"

    def test_invalid_role(self):
        with pytest.raises(Exception):
            CreateEmployeeParams(
                username="test", name="Test", role="invalid_role"
            )


class TestHandleUpdateEmployee:
    def test_successful_update(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_employee
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        params = UpdateEmployeeParams(employee_id=10, name="新名字", phone="13900000001")

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("update_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert "新名字" in result["message"]

    def test_employee_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateEmployeeParams(employee_id=999, name="新名字")

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("update_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_update_no_fields(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_employee

        params = UpdateEmployeeParams(employee_id=10)

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("update_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "no_updates"


class TestHandleDeactivateEmployee:
    def test_successful_deactivate(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_employee
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        params = DeactivateEmployeeParams(employee_id=10)

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("deactivate_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_employee_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = DeactivateEmployeeParams(employee_id=999)

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("deactivate_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_already_deactivated(self, mock_db, mock_user, sample_employee):
        from core.ai.actions import ActionRegistry

        sample_employee.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_employee

        params = DeactivateEmployeeParams(employee_id=10)

        registry = ActionRegistry()
        employee_actions.register_employee_actions(registry)
        action = registry.get_action("deactivate_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "already_deactivated"


class TestEmployeeActionsModule:
    def test_module_all(self):
        assert "register_employee_actions" in employee_actions.__all__
