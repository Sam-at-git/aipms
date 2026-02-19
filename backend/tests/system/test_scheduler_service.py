"""
SchedulerService + APSchedulerBackend unit tests.

Covers:
- SchedulerService CRUD (list, get, create, update, delete)
- SchedulerService scheduling operations (start, stop, trigger)
- SchedulerService log querying and active-job loading
- SchedulerService internal helpers (_register_job, _unregister_job, _resolve_target)
- APSchedulerBackend: start, shutdown, add_job, remove_job, pause, resume, get_jobs, get_job, trigger_job
"""
import importlib
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy.orm import Session

from app.system.models.scheduler import SysJob, SysJobLog
from app.system.services.scheduler_service import SchedulerService
from app.system.services.scheduler_backend import APSchedulerBackend
from core.scheduler import SchedulerRegistry


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_scheduler_registry():
    """Ensure a clean SchedulerRegistry singleton between tests."""
    registry = SchedulerRegistry()
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def mock_backend():
    """Create a mock ISchedulerBackend."""
    backend = MagicMock()
    backend.add_job = MagicMock()
    backend.remove_job = MagicMock()
    return backend


@pytest.fixture
def service_with_backend(db_session, mock_backend):
    """SchedulerService with a registered mock backend."""
    SchedulerRegistry().set_backend(mock_backend)
    return SchedulerService(db_session)


@pytest.fixture
def sample_job(db_session) -> SysJob:
    """Create and return a sample SysJob in the DB."""
    job = SysJob(
        name="Test Job",
        code="test_job_1",
        invoke_target="os.path:exists",
        cron_expression="0 * * * *",
        group="default",
        misfire_policy="ignore",
        is_concurrent=False,
        is_active=True,
        description="A test job",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def sample_inactive_job(db_session) -> SysJob:
    """Create an inactive SysJob."""
    job = SysJob(
        name="Inactive Job",
        code="inactive_job",
        invoke_target="os.path:exists",
        cron_expression="0 0 * * *",
        is_active=False,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ── SchedulerService CRUD Tests ──────────────────────────


class TestSchedulerServiceCRUD:
    """CRUD operations on SysJob rows."""

    def test_list_jobs_empty(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.list_jobs() == []

    def test_list_jobs_all(self, db_session, sample_job, sample_inactive_job):
        svc = SchedulerService(db_session)
        jobs = svc.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_filter_by_group(self, db_session, sample_job):
        svc = SchedulerService(db_session)
        assert len(svc.list_jobs(group="default")) == 1
        assert len(svc.list_jobs(group="nonexistent")) == 0

    def test_list_jobs_filter_by_active(self, db_session, sample_job, sample_inactive_job):
        svc = SchedulerService(db_session)
        active = svc.list_jobs(is_active=True)
        assert len(active) == 1
        assert active[0].code == "test_job_1"

        inactive = svc.list_jobs(is_active=False)
        assert len(inactive) == 1
        assert inactive[0].code == "inactive_job"

    def test_get_job_exists(self, db_session, sample_job):
        svc = SchedulerService(db_session)
        job = svc.get_job(sample_job.id)
        assert job is not None
        assert job.code == "test_job_1"

    def test_get_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.get_job(99999) is None

    def test_get_job_by_code(self, db_session, sample_job):
        svc = SchedulerService(db_session)
        job = svc.get_job_by_code("test_job_1")
        assert job is not None
        assert job.id == sample_job.id

    def test_get_job_by_code_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.get_job_by_code("nope") is None

    def test_create_job_active(self, service_with_backend, mock_backend):
        """Creating an active job should register it with the backend."""
        svc = service_with_backend
        job = svc.create_job(
            name="New Job",
            code="new_job",
            invoke_target="os.path:exists",
            cron_expression="*/5 * * * *",
            is_active=True,
        )
        assert job.id is not None
        assert job.code == "new_job"
        assert job.is_active is True
        mock_backend.add_job.assert_called_once()

    def test_create_job_inactive(self, service_with_backend, mock_backend):
        """Creating an inactive job should NOT register with the backend."""
        svc = service_with_backend
        job = svc.create_job(
            name="Dormant",
            code="dormant",
            invoke_target="os.path:exists",
            cron_expression="0 0 * * *",
            is_active=False,
        )
        assert job.is_active is False
        mock_backend.add_job.assert_not_called()

    def test_update_job(self, service_with_backend, mock_backend, sample_job):
        """Updating a job should re-register with the backend."""
        svc = service_with_backend
        updated = svc.update_job(sample_job.id, name="Renamed")
        assert updated is not None
        assert updated.name == "Renamed"
        # Should unregister then re-register (since still active)
        mock_backend.remove_job.assert_called_once_with("test_job_1")
        mock_backend.add_job.assert_called_once()

    def test_update_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.update_job(99999, name="X") is None

    def test_update_job_deactivate(self, service_with_backend, mock_backend, sample_job):
        """Deactivating a job via update should unregister but not re-register."""
        svc = service_with_backend
        updated = svc.update_job(sample_job.id, is_active=False)
        assert updated.is_active is False
        mock_backend.remove_job.assert_called_once()
        mock_backend.add_job.assert_not_called()

    def test_delete_job(self, service_with_backend, mock_backend, sample_job):
        svc = service_with_backend
        assert svc.delete_job(sample_job.id) is True
        mock_backend.remove_job.assert_called_once_with("test_job_1")
        # Verify actually deleted from DB
        assert svc.get_job(sample_job.id) is None

    def test_delete_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.delete_job(99999) is False


# ── SchedulerService Scheduling Operations ────────────────


class TestSchedulerServiceOperations:
    """start, stop, trigger operations."""

    def test_start_job(self, service_with_backend, mock_backend, sample_inactive_job):
        svc = service_with_backend
        job = svc.start_job(sample_inactive_job.id)
        assert job is not None
        assert job.is_active is True
        mock_backend.add_job.assert_called_once()

    def test_start_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.start_job(99999) is None

    def test_stop_job(self, service_with_backend, mock_backend, sample_job):
        svc = service_with_backend
        job = svc.stop_job(sample_job.id)
        assert job is not None
        assert job.is_active is False
        mock_backend.remove_job.assert_called_once_with("test_job_1")

    def test_stop_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.stop_job(99999) is None

    def test_trigger_job_success(self, db_session, sample_job):
        """trigger_job executes the target function and logs success."""
        svc = SchedulerService(db_session)
        with patch.object(svc, "_resolve_target", return_value=lambda: "done"):
            result = svc.trigger_job(sample_job.id)
        assert result["success"] is True
        assert result["status"] == "success"
        assert result["result"] == "done"
        assert result["duration_ms"] >= 0

        # Verify log was created
        logs = svc.get_job_logs(job_id=sample_job.id)
        assert len(logs) == 1
        assert logs[0].status == "success"

    def test_trigger_job_returns_none(self, db_session, sample_job):
        """trigger_job with a function that returns None should log 'OK'."""
        svc = SchedulerService(db_session)
        with patch.object(svc, "_resolve_target", return_value=lambda: None):
            result = svc.trigger_job(sample_job.id)
        assert result["success"] is True
        assert result["result"] == "OK"

    def test_trigger_job_failure(self, db_session, sample_job):
        """trigger_job catches exceptions and logs failure."""
        svc = SchedulerService(db_session)

        def failing_func():
            raise RuntimeError("boom")

        with patch.object(svc, "_resolve_target", return_value=failing_func):
            result = svc.trigger_job(sample_job.id)
        assert result["success"] is False
        assert result["status"] == "fail"
        assert "boom" in result["result"]

        logs = svc.get_job_logs(job_id=sample_job.id)
        assert len(logs) == 1
        assert logs[0].status == "fail"

    def test_trigger_job_not_found(self, db_session):
        svc = SchedulerService(db_session)
        with pytest.raises(ValueError, match="任务不存在"):
            svc.trigger_job(99999)


# ── SchedulerService Logs ─────────────────────────────────


class TestSchedulerServiceLogs:
    """Execution log querying."""

    def test_get_job_logs_empty(self, db_session):
        svc = SchedulerService(db_session)
        assert svc.get_job_logs() == []

    def test_get_job_logs_filter_by_job_id(self, db_session, sample_job):
        log1 = SysJobLog(job_id=sample_job.id, status="success", start_time=datetime.utcnow())
        db_session.add(log1)
        db_session.commit()

        svc = SchedulerService(db_session)
        logs = svc.get_job_logs(job_id=sample_job.id)
        assert len(logs) == 1

        logs_other = svc.get_job_logs(job_id=99999)
        assert len(logs_other) == 0

    def test_get_job_logs_filter_by_status(self, db_session, sample_job):
        db_session.add(SysJobLog(job_id=sample_job.id, status="success", start_time=datetime.utcnow()))
        db_session.add(SysJobLog(job_id=sample_job.id, status="fail", start_time=datetime.utcnow()))
        db_session.commit()

        svc = SchedulerService(db_session)
        assert len(svc.get_job_logs(status="success")) == 1
        assert len(svc.get_job_logs(status="fail")) == 1

    def test_get_job_logs_limit(self, db_session, sample_job):
        for i in range(5):
            db_session.add(SysJobLog(job_id=sample_job.id, status="success", start_time=datetime.utcnow()))
        db_session.commit()

        svc = SchedulerService(db_session)
        assert len(svc.get_job_logs(limit=3)) == 3
        assert len(svc.get_job_logs(limit=50)) == 5


# ── SchedulerService load_active_jobs ─────────────────────


class TestSchedulerServiceLoadActive:
    """Loading active jobs at startup."""

    def test_load_active_jobs(self, service_with_backend, mock_backend, sample_job, sample_inactive_job):
        svc = service_with_backend
        count = svc.load_active_jobs()
        assert count == 1
        mock_backend.add_job.assert_called_once()

    def test_load_active_jobs_with_error(self, service_with_backend, mock_backend, sample_job):
        """If _register_job raises, load_active_jobs should continue."""
        svc = service_with_backend
        mock_backend.add_job.side_effect = RuntimeError("scheduler not ready")
        # _register_job calls backend.add_job which raises; the error is caught
        count = svc.load_active_jobs()
        # The error is caught, count stays 0
        assert count == 0


# ── SchedulerService Internal Helpers ─────────────────────


class TestSchedulerServiceHelpers:
    """_register_job, _unregister_job, _resolve_target"""

    def test_register_job_no_backend(self, db_session, sample_job):
        """When no backend is registered, _register_job should be a no-op."""
        svc = SchedulerService(db_session)
        # Should not raise
        svc._register_job(sample_job)

    def test_unregister_job_no_backend(self, db_session):
        """When no backend is registered, _unregister_job should be a no-op."""
        svc = SchedulerService(db_session)
        svc._unregister_job("any_code")

    def test_resolve_target_success(self):
        func = SchedulerService._resolve_target("os.path:exists")
        import os.path
        assert func is os.path.exists

    def test_resolve_target_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid invoke_target format"):
            SchedulerService._resolve_target("no_colon_here")

    def test_resolve_target_function_not_found(self):
        with pytest.raises(ValueError, match="not found in module"):
            SchedulerService._resolve_target("os.path:nonexistent_function_xyz")


# ── APSchedulerBackend Tests ──────────────────────────────


class TestAPSchedulerBackend:
    """Unit tests for APSchedulerBackend."""

    def test_start_when_not_running(self):
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.start()
        mock_scheduler.start.assert_called_once()

    def test_start_when_already_running(self):
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.start()
        mock_scheduler.start.assert_not_called()

    def test_shutdown_when_running(self):
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.shutdown()
        mock_scheduler.shutdown.assert_called_once_with(wait=False)

    def test_shutdown_when_not_running(self):
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.shutdown()
        mock_scheduler.shutdown.assert_not_called()

    def test_add_job_with_cron_expression(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)

        func = lambda: None
        with patch("app.system.services.scheduler_backend.CronTrigger") as MockCron:
            MockCron.from_crontab.return_value = "cron_trigger_obj"
            backend.add_job(
                job_id="test_cron",
                func=func,
                trigger="cron",
                cron_expression="*/5 * * * *",
            )
            MockCron.from_crontab.assert_called_once_with("*/5 * * * *")
            mock_scheduler.add_job.assert_called_once_with(
                func,
                trigger="cron_trigger_obj",
                id="test_cron",
                replace_existing=True,
            )

    def test_add_job_non_cron(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)

        func = lambda: None
        backend.add_job(
            job_id="test_interval",
            func=func,
            trigger="interval",
            seconds=30,
        )
        mock_scheduler.add_job.assert_called_once_with(
            func,
            trigger="interval",
            id="test_interval",
            replace_existing=True,
            seconds=30,
        )

    def test_remove_job_success(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.remove_job("job1")
        mock_scheduler.remove_job.assert_called_once_with("job1")

    def test_remove_job_not_found(self):
        mock_scheduler = MagicMock()
        mock_scheduler.remove_job.side_effect = Exception("not found")
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        # Should not raise
        backend.remove_job("missing_job")

    def test_pause_job(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.pause_job("j1")
        mock_scheduler.pause_job.assert_called_once_with("j1")

    def test_resume_job(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.resume_job("j1")
        mock_scheduler.resume_job.assert_called_once_with("j1")

    def test_get_jobs(self):
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "j1"
        mock_job.name = "Job 1"
        mock_job.trigger = "cron[*/5]"
        mock_job.next_run_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_scheduler.get_jobs.return_value = [mock_job]

        backend = APSchedulerBackend(scheduler=mock_scheduler)
        jobs = backend.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "j1"
        assert jobs[0]["status"] == "active"

    def test_get_jobs_paused(self):
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "j1"
        mock_job.name = None
        mock_job.trigger = "cron"
        mock_job.next_run_time = None  # paused
        mock_scheduler.get_jobs.return_value = [mock_job]

        backend = APSchedulerBackend(scheduler=mock_scheduler)
        jobs = backend.get_jobs()
        assert jobs[0]["status"] == "paused"
        assert jobs[0]["name"] == "j1"  # fallback to id
        assert jobs[0]["next_run_time"] is None

    def test_get_job_found(self):
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "j1"
        mock_job.name = "Job 1"
        mock_job.trigger = "cron"
        mock_job.next_run_time = datetime(2025, 6, 1, 0, 0, 0)
        mock_scheduler.get_job.return_value = mock_job

        backend = APSchedulerBackend(scheduler=mock_scheduler)
        result = backend.get_job("j1")
        assert result is not None
        assert result["id"] == "j1"

    def test_get_job_not_found(self):
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        assert backend.get_job("missing") is None

    def test_trigger_job_success(self):
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_scheduler.get_job.return_value = mock_job
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        backend.trigger_job("j1")
        mock_job.func.assert_called_once()

    def test_trigger_job_not_found(self):
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        with pytest.raises(ValueError, match="Job not found"):
            backend.trigger_job("missing")

    def test_scheduler_property(self):
        mock_scheduler = MagicMock()
        backend = APSchedulerBackend(scheduler=mock_scheduler)
        assert backend.scheduler is mock_scheduler

    def test_default_scheduler_created(self):
        """When no scheduler is passed, a BackgroundScheduler is created."""
        backend = APSchedulerBackend()
        from apscheduler.schedulers.background import BackgroundScheduler
        assert isinstance(backend.scheduler, BackgroundScheduler)
