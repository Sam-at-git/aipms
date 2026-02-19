"""
System mutation and query action handler tests.

Covers:
- system_mutation_actions: start_scheduler_job, stop_scheduler_job, trigger_scheduler_job
- system_query_actions: query_system, _check_system_query_permission, SYSTEM_ENTITIES
"""
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy.orm import Session

from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash
from app.system.actions.system_mutation_actions import (
    SchedulerJobParams,
    register_system_mutation_actions,
)
from app.system.actions.system_query_actions import (
    SYSTEM_ENTITIES,
    _check_system_query_permission,
    handle_query_system,
    register_system_query_actions,
)
from app.system.models.scheduler import SysJob
from core.ai.actions import ActionRegistry


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def action_registry():
    """A fresh ActionRegistry for testing."""
    return ActionRegistry()


@pytest.fixture
def sysadmin_user(db_session) -> Employee:
    admin = Employee(
        username="sysadmin_action",
        password_hash=get_password_hash("123456"),
        name="System Admin",
        role=EmployeeRole.SYSADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def cleaner_user(db_session) -> Employee:
    cleaner = Employee(
        username="cleaner_action",
        password_hash=get_password_hash("123456"),
        name="Cleaner",
        role=EmployeeRole.CLEANER,
        is_active=True,
    )
    db_session.add(cleaner)
    db_session.commit()
    db_session.refresh(cleaner)
    return cleaner


@pytest.fixture
def sample_job(db_session) -> SysJob:
    job = SysJob(
        name="Action Test Job",
        code="action_test",
        invoke_target="os.path:exists",
        cron_expression="0 * * * *",
        is_active=True,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def inactive_job(db_session) -> SysJob:
    job = SysJob(
        name="Inactive Job",
        code="inactive_action",
        invoke_target="os.path:exists",
        cron_expression="0 0 * * *",
        is_active=False,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ── Mutation Action Registration ──────────────────────────


class TestSystemMutationActionRegistration:
    """Verify actions are registered with ActionRegistry."""

    def test_register_system_mutation_actions(self, action_registry):
        register_system_mutation_actions(action_registry)
        assert action_registry.get_action("start_scheduler_job") is not None
        assert action_registry.get_action("stop_scheduler_job") is not None
        assert action_registry.get_action("trigger_scheduler_job") is not None


# ── Start Job Action ──────────────────────────────────────


class TestStartJobAction:

    def test_start_job_success(self, db_session, sysadmin_user, inactive_job, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("start_scheduler_job")

        params = SchedulerJobParams(job_id=inactive_job.id)
        result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is True
        assert "已启动" in result["message"]
        assert result["data"]["is_active"] is True

    def test_start_job_not_found(self, db_session, sysadmin_user, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("start_scheduler_job")

        params = SchedulerJobParams(job_id=99999)
        result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is False
        assert "不存在" in result["message"]


# ── Stop Job Action ───────────────────────────────────────


class TestStopJobAction:

    def test_stop_job_success(self, db_session, sysadmin_user, sample_job, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("stop_scheduler_job")

        params = SchedulerJobParams(job_id=sample_job.id)
        result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is True
        assert "已停止" in result["message"]
        assert result["data"]["is_active"] is False

    def test_stop_job_not_found(self, db_session, sysadmin_user, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("stop_scheduler_job")

        params = SchedulerJobParams(job_id=99999)
        result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is False
        assert "不存在" in result["message"]


# ── Trigger Job Action ────────────────────────────────────


class TestTriggerJobAction:

    def test_trigger_job_success(self, db_session, sysadmin_user, sample_job, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("trigger_scheduler_job")

        params = SchedulerJobParams(job_id=sample_job.id)
        with patch(
            "app.system.services.scheduler_service.SchedulerService._resolve_target",
            return_value=lambda: "ok",
        ):
            result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is True
        assert "成功" in result["message"]
        assert "duration_ms" in result["data"]

    def test_trigger_job_failure(self, db_session, sysadmin_user, sample_job, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("trigger_scheduler_job")

        def boom():
            raise RuntimeError("explosion")

        params = SchedulerJobParams(job_id=sample_job.id)
        with patch(
            "app.system.services.scheduler_service.SchedulerService._resolve_target",
            return_value=boom,
        ):
            result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is False
        assert "失败" in result["message"]

    def test_trigger_job_not_found(self, db_session, sysadmin_user, action_registry):
        register_system_mutation_actions(action_registry)
        action_def = action_registry.get_action("trigger_scheduler_job")

        params = SchedulerJobParams(job_id=99999)
        result = action_def.handler(params=params, db=db_session, user=sysadmin_user)

        assert result["success"] is False
        assert "任务不存在" in result["message"]


# ── Query Action Registration ─────────────────────────────


class TestSystemQueryActionRegistration:

    def test_register_system_query_actions(self, action_registry):
        register_system_query_actions(action_registry)
        assert action_registry.get_action("query_system") is not None


# ── System Entities Constant ──────────────────────────────


class TestSystemEntities:

    def test_system_entities_is_a_set(self):
        assert isinstance(SYSTEM_ENTITIES, set)
        assert "SysRole" in SYSTEM_ENTITIES
        assert "SysJob" in SYSTEM_ENTITIES


# ── _check_system_query_permission ────────────────────────


class TestCheckSystemQueryPermission:

    def test_unknown_entity_returns_none(self, sysadmin_user):
        """Unknown entity should be allowed through (let ontology_query handle it)."""
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = None
            result = _check_system_query_permission("NonExistent", sysadmin_user)
        assert result is None

    def test_entity_without_chat_access_returns_none(self, sysadmin_user):
        """Entity without chat_access extension should be allowed."""
        mock_entity = MagicMock()
        mock_entity.extensions = {}
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = mock_entity
            result = _check_system_query_permission("SysRole", sysadmin_user)
        assert result is None

    def test_entity_not_queryable(self, sysadmin_user):
        """Entity with queryable=False should be denied."""
        mock_entity = MagicMock()
        mock_entity.extensions = {"chat_access": {"queryable": False}}
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = mock_entity
            result = _check_system_query_permission("SysConfig", sysadmin_user)
        assert result is not None
        assert "不支持" in result

    def test_entity_with_role_restriction_allowed(self, sysadmin_user):
        """sysadmin should pass role check."""
        mock_entity = MagicMock()
        mock_entity.extensions = {
            "chat_access": {"queryable": True, "allowed_query_roles": ["sysadmin"]}
        }
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = mock_entity
            result = _check_system_query_permission("SysConfig", sysadmin_user)
        assert result is None

    def test_entity_with_role_restriction_denied(self, cleaner_user):
        """cleaner should fail role check."""
        mock_entity = MagicMock()
        mock_entity.extensions = {
            "chat_access": {"queryable": True, "allowed_query_roles": ["sysadmin"]}
        }
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = mock_entity
            result = _check_system_query_permission("SysConfig", cleaner_user)
        assert result is not None
        assert "权限不足" in result

    def test_entity_no_extensions_attr(self, sysadmin_user):
        """Entity metadata without 'extensions' attribute should be allowed."""
        mock_entity = MagicMock(spec=[])
        with patch(
            "app.system.actions.system_query_actions.ontology_registry"
        ) as mock_reg:
            mock_reg.get_entity.return_value = mock_entity
            result = _check_system_query_permission("SysRole", sysadmin_user)
        assert result is None


# ── handle_query_system ───────────────────────────────────


class TestHandleQuerySystem:

    def test_query_non_system_entity_delegates(self, db_session, sysadmin_user):
        """Non-system entity queries bypass permission check and delegate to ontology_query."""
        from app.services.actions.base import OntologyQueryParams

        params = OntologyQueryParams(entity="Room", fields=["room_number"])
        with patch(
            "app.system.actions.system_query_actions.handle_ontology_query",
            return_value={"success": True, "message": "ok"},
        ) as mock_handler:
            result = handle_query_system(params, db_session, sysadmin_user)
        assert result["success"] is True
        mock_handler.assert_called_once()

    def test_query_system_entity_permission_denied(self, db_session, cleaner_user):
        """System entity query denied by permission check."""
        from app.services.actions.base import OntologyQueryParams

        params = OntologyQueryParams(entity="SysConfig", fields=["key", "value"])
        with patch(
            "app.system.actions.system_query_actions._check_system_query_permission",
            return_value="权限不足，无法查询 SysConfig",
        ):
            result = handle_query_system(params, db_session, cleaner_user)
        assert result["success"] is False
        assert "权限不足" in result["message"]

    def test_query_system_entity_allowed(self, db_session, sysadmin_user):
        """System entity query allowed by permission check."""
        from app.services.actions.base import OntologyQueryParams

        params = OntologyQueryParams(entity="SysRole", fields=["code", "name"])
        with patch(
            "app.system.actions.system_query_actions._check_system_query_permission",
            return_value=None,
        ), patch(
            "app.system.actions.system_query_actions.handle_ontology_query",
            return_value={"success": True, "message": "2 roles"},
        ) as mock_handler:
            result = handle_query_system(params, db_session, sysadmin_user)
        assert result["success"] is True
        mock_handler.assert_called_once()


# ── SchedulerJobParams Validation ─────────────────────────


class TestSchedulerJobParams:

    def test_valid_params(self):
        p = SchedulerJobParams(job_id=1)
        assert p.job_id == 1

    def test_invalid_params(self):
        with pytest.raises(Exception):
            SchedulerJobParams()  # job_id is required
