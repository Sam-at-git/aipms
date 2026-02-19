"""
Scheduler router API tests.

Covers all /system/schedulers endpoints:
- GET  /system/schedulers           (list jobs)
- POST /system/schedulers           (create job)
- GET  /system/schedulers/{id}      (get job detail)
- PUT  /system/schedulers/{id}      (update job)
- DELETE /system/schedulers/{id}    (delete job)
- POST /system/schedulers/{id}/start   (start job)
- POST /system/schedulers/{id}/stop    (stop job)
- POST /system/schedulers/{id}/trigger (trigger job immediately)
- GET  /system/schedulers/{id}/logs    (execution logs)

Verifies:
- sysadmin access required
- non-sysadmin (manager) is denied (403)
- proper HTTP status codes and error responses
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.system.models.scheduler import SysJob, SysJobLog
from core.scheduler import SchedulerRegistry


@pytest.fixture(autouse=True)
def clear_scheduler_registry():
    """No real scheduler backend during router tests."""
    registry = SchedulerRegistry()
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def _seed_job(db_session) -> SysJob:
    """Insert a SysJob row directly into the DB for API tests."""
    job = SysJob(
        name="Seeded Job",
        code="seeded_job",
        invoke_target="os.path:exists",
        cron_expression="0 * * * *",
        group="default",
        misfire_policy="ignore",
        is_concurrent=False,
        is_active=True,
        description="Seeded for testing",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ── Auth Tests ──────────────────────────────────────────


class TestSchedulerRouterAuth:
    """Only sysadmin can access scheduler endpoints."""

    def test_list_requires_sysadmin(self, client: TestClient, manager_auth_headers):
        resp = client.get("/system/schedulers", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_list_no_auth(self, client: TestClient):
        resp = client.get("/system/schedulers")
        assert resp.status_code in (401, 403)

    def test_create_requires_sysadmin(self, client: TestClient, manager_auth_headers):
        resp = client.post("/system/schedulers", headers=manager_auth_headers, json={
            "name": "X", "code": "x", "invoke_target": "a:b", "cron_expression": "0 * * * *",
        })
        assert resp.status_code == 403


# ── CRUD Tests ──────────────────────────────────────────


class TestSchedulerRouterCRUD:
    """Standard CRUD endpoints."""

    def test_list_jobs_empty(self, client: TestClient, sysadmin_auth_headers):
        resp = client.get("/system/schedulers", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_jobs(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.get("/system/schedulers", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["code"] == "seeded_job"

    def test_list_jobs_filter_group(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.get("/system/schedulers?group=default", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        resp = client.get("/system/schedulers?group=nonexistent", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_jobs_filter_active(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.get("/system/schedulers?is_active=true", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_create_job(self, client: TestClient, sysadmin_auth_headers):
        resp = client.post("/system/schedulers", headers=sysadmin_auth_headers, json={
            "name": "API Created Job",
            "code": "api_created",
            "invoke_target": "os.path:exists",
            "cron_expression": "*/10 * * * *",
            "group": "test",
            "description": "Created via API",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "api_created"
        assert data["name"] == "API Created Job"
        assert data["group"] == "test"
        assert data["is_active"] is True

    def test_create_job_duplicate_code(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.post("/system/schedulers", headers=sysadmin_auth_headers, json={
            "name": "Dup",
            "code": "seeded_job",
            "invoke_target": "os.path:exists",
            "cron_expression": "0 * * * *",
        })
        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

    def test_get_job(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.get(f"/system/schedulers/{_seed_job.id}", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "seeded_job"

    def test_get_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.get("/system/schedulers/99999", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_update_job(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.put(
            f"/system/schedulers/{_seed_job.id}",
            headers=sysadmin_auth_headers,
            json={"name": "Updated Name", "description": "Updated desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.put(
            "/system/schedulers/99999",
            headers=sysadmin_auth_headers,
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_job(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.delete(f"/system/schedulers/{_seed_job.id}", headers=sysadmin_auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/system/schedulers/{_seed_job.id}", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_delete_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.delete("/system/schedulers/99999", headers=sysadmin_auth_headers)
        assert resp.status_code == 404


# ── Scheduling Operation Tests ────────────────────────────


class TestSchedulerRouterOperations:
    """start, stop, trigger endpoints."""

    def test_start_job(self, client: TestClient, sysadmin_auth_headers, db_session):
        # Create an inactive job
        job = SysJob(
            name="Stopped",
            code="stopped_job",
            invoke_target="os.path:exists",
            cron_expression="0 * * * *",
            is_active=False,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        resp = client.post(f"/system/schedulers/{job.id}/start", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_start_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.post("/system/schedulers/99999/start", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_stop_job(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.post(f"/system/schedulers/{_seed_job.id}/stop", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_stop_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.post("/system/schedulers/99999/stop", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_trigger_job(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        """Trigger should invoke the target function (mocked)."""
        with patch(
            "app.system.services.scheduler_service.SchedulerService._resolve_target",
            return_value=lambda: "triggered",
        ):
            resp = client.post(
                f"/system/schedulers/{_seed_job.id}/trigger",
                headers=sysadmin_auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "success"

    def test_trigger_job_not_found(self, client: TestClient, sysadmin_auth_headers):
        resp = client.post("/system/schedulers/99999/trigger", headers=sysadmin_auth_headers)
        assert resp.status_code == 404


# ── Log Tests ─────────────────────────────────────────────


class TestSchedulerRouterLogs:
    """Execution log endpoint."""

    def test_get_logs_empty(self, client: TestClient, sysadmin_auth_headers, _seed_job):
        resp = client.get(
            f"/system/schedulers/{_seed_job.id}/logs",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_logs_with_data(self, client: TestClient, sysadmin_auth_headers, _seed_job, db_session):
        from datetime import datetime
        log = SysJobLog(
            job_id=_seed_job.id,
            status="success",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=42,
            result="OK",
        )
        db_session.add(log)
        db_session.commit()

        resp = client.get(
            f"/system/schedulers/{_seed_job.id}/logs",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "success"
        assert data[0]["duration_ms"] == 42

    def test_get_logs_with_status_filter(self, client: TestClient, sysadmin_auth_headers, _seed_job, db_session):
        from datetime import datetime
        db_session.add(SysJobLog(job_id=_seed_job.id, status="success", start_time=datetime.utcnow()))
        db_session.add(SysJobLog(job_id=_seed_job.id, status="fail", start_time=datetime.utcnow()))
        db_session.commit()

        resp = client.get(
            f"/system/schedulers/{_seed_job.id}/logs?status=fail",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "fail"

    def test_get_logs_limit(self, client: TestClient, sysadmin_auth_headers, _seed_job, db_session):
        from datetime import datetime
        for _ in range(5):
            db_session.add(SysJobLog(job_id=_seed_job.id, status="success", start_time=datetime.utcnow()))
        db_session.commit()

        resp = client.get(
            f"/system/schedulers/{_seed_job.id}/logs?limit=2",
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
