"""
Tests for undo router (app/routers/undo.py)
Covers listing undoable operations, executing undo, undo history,
snapshot detail, and role-based access control.
"""
import json
import uuid
import pytest
from datetime import datetime, timedelta

from app.models.snapshots import OperationSnapshot, OperationType
from app.hotel.models.ontology import Employee


# ────────────────────────── fixtures ──────────────────────────


@pytest.fixture
def _manager_user(db_session, manager_token):
    """Return the manager Employee object (created by manager_token fixture)."""
    return db_session.query(Employee).filter(Employee.username == "manager").first()


@pytest.fixture
def _receptionist_user(db_session, receptionist_token):
    """Return the receptionist Employee object."""
    return db_session.query(Employee).filter(Employee.username == "front1").first()


@pytest.fixture
def undoable_snapshot(db_session, _manager_user):
    """Create an undoable (not expired, not undone) OperationSnapshot."""
    snapshot = OperationSnapshot(
        snapshot_uuid=str(uuid.uuid4()),
        operation_type=OperationType.CHECK_IN.value,
        operator_id=_manager_user.id,
        operation_time=datetime.now(),
        entity_type="stay_record",
        entity_id=1,
        before_state=json.dumps({
            "room": {"id": 1, "room_number": "101", "status": "vacant_clean"}
        }),
        after_state=json.dumps({"stay_record_id": 1, "room_status": "occupied"}),
        related_snapshots=json.dumps([]),
        is_undone=False,
        expires_at=datetime.now() + timedelta(hours=24),
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


@pytest.fixture
def expired_snapshot(db_session, _manager_user):
    """Create an expired OperationSnapshot."""
    snapshot = OperationSnapshot(
        snapshot_uuid=str(uuid.uuid4()),
        operation_type=OperationType.CHECK_IN.value,
        operator_id=_manager_user.id,
        operation_time=datetime.now() - timedelta(hours=48),
        entity_type="stay_record",
        entity_id=2,
        before_state=json.dumps({"room": {"id": 2, "room_number": "102", "status": "vacant_clean"}}),
        after_state=json.dumps({"stay_record_id": 2}),
        related_snapshots=json.dumps([]),
        is_undone=False,
        expires_at=datetime.now() - timedelta(hours=1),  # expired
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


@pytest.fixture
def undone_snapshot(db_session, _manager_user):
    """Create an already-undone OperationSnapshot."""
    snapshot = OperationSnapshot(
        snapshot_uuid=str(uuid.uuid4()),
        operation_type=OperationType.COMPLETE_TASK.value,
        operator_id=_manager_user.id,
        operation_time=datetime.now() - timedelta(hours=2),
        entity_type="task",
        entity_id=10,
        before_state=json.dumps({"task": {"id": 10, "status": "in_progress"}}),
        after_state=json.dumps({"task_status": "completed"}),
        related_snapshots=json.dumps([]),
        is_undone=True,
        undone_time=datetime.now() - timedelta(hours=1),
        undone_by=_manager_user.id,
        expires_at=datetime.now() + timedelta(hours=20),
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


@pytest.fixture
def multiple_snapshots(db_session, _manager_user):
    """Create multiple snapshots for listing tests."""
    snapshots = []
    for i in range(5):
        s = OperationSnapshot(
            snapshot_uuid=str(uuid.uuid4()),
            operation_type=OperationType.CHECK_IN.value,
            operator_id=_manager_user.id,
            operation_time=datetime.now() - timedelta(hours=i),
            entity_type="stay_record",
            entity_id=100 + i,
            before_state=json.dumps({"room": {"id": 100 + i, "room_number": str(200 + i), "status": "vacant_clean"}}),
            after_state=json.dumps({"stay_record_id": 100 + i}),
            related_snapshots=json.dumps([]),
            is_undone=False,
            expires_at=datetime.now() + timedelta(hours=24),
        )
        db_session.add(s)
        snapshots.append(s)
    db_session.commit()
    for s in snapshots:
        db_session.refresh(s)
    return snapshots


# ────────────────────────── GET /undo/operations ──────────────────────────


class TestListUndoableOperations:
    """GET /undo/operations"""

    def test_list_operations_empty(self, client, manager_auth_headers):
        resp = client.get("/undo/operations", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_operations_with_data(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get("/undo/operations", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["snapshot_uuid"] == undoable_snapshot.snapshot_uuid
        assert data[0]["is_undone"] is False

    def test_list_operations_excludes_expired(self, client, manager_auth_headers, expired_snapshot, undoable_snapshot):
        resp = client.get("/undo/operations", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        uuids = [item["snapshot_uuid"] for item in data]
        # undoable should be present, expired should not
        assert undoable_snapshot.snapshot_uuid in uuids
        assert expired_snapshot.snapshot_uuid not in uuids

    def test_list_operations_excludes_undone(self, client, manager_auth_headers, undone_snapshot, undoable_snapshot):
        resp = client.get("/undo/operations", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        uuids = [item["snapshot_uuid"] for item in data]
        assert undoable_snapshot.snapshot_uuid in uuids
        assert undone_snapshot.snapshot_uuid not in uuids

    def test_list_operations_filter_by_entity_type(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get(
            "/undo/operations?entity_type=stay_record",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_operations_filter_by_entity_type_no_match(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get(
            "/undo/operations?entity_type=bill",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_list_operations_filter_by_entity_id(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get(
            f"/undo/operations?entity_id={undoable_snapshot.entity_id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_operations_with_limit(self, client, manager_auth_headers, multiple_snapshots):
        resp = client.get("/undo/operations?limit=2", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_operations_as_receptionist(self, client, receptionist_auth_headers, undoable_snapshot):
        resp = client.get("/undo/operations", headers=receptionist_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_operations_forbidden_for_cleaner(self, client, cleaner_auth_headers):
        resp = client.get("/undo/operations", headers=cleaner_auth_headers)
        assert resp.status_code == 403

    def test_list_operations_forbidden_for_sysadmin(self, client, sysadmin_auth_headers):
        """Undo operations endpoint checks for manager/receptionist role only."""
        resp = client.get("/undo/operations", headers=sysadmin_auth_headers)
        assert resp.status_code == 403

    def test_list_operations_unauthenticated(self, client):
        resp = client.get("/undo/operations")
        assert resp.status_code in (401, 403)

    def test_list_operations_response_structure(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get("/undo/operations", headers=manager_auth_headers)
        item = resp.json()[0]
        assert "id" in item
        assert "snapshot_uuid" in item
        assert "operation_type" in item
        assert "operator_id" in item
        assert "operation_time" in item
        assert "entity_type" in item
        assert "entity_id" in item
        assert "is_undone" in item
        assert "expires_at" in item


# ────────────────────────── POST /undo/{uuid} ──────────────────────────


class TestUndoOperation:
    """POST /undo/{snapshot_uuid}"""

    def test_undo_already_undone(self, client, manager_auth_headers, undone_snapshot):
        resp = client.post(
            f"/undo/{undone_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400
        assert "已撤销" in resp.json()["detail"]

    def test_undo_expired(self, client, manager_auth_headers, expired_snapshot):
        resp = client.post(
            f"/undo/{expired_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400
        assert "过期" in resp.json()["detail"]

    def test_undo_nonexistent_snapshot(self, client, manager_auth_headers):
        resp = client.post(
            f"/undo/{str(uuid.uuid4())}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400
        assert "不存在" in resp.json()["detail"]

    def test_undo_forbidden_for_cleaner(self, client, cleaner_auth_headers, undoable_snapshot):
        resp = client.post(
            f"/undo/{undoable_snapshot.snapshot_uuid}",
            headers=cleaner_auth_headers,
        )
        assert resp.status_code == 403

    def test_undo_as_receptionist(self, client, receptionist_auth_headers, undone_snapshot):
        """Receptionist can attempt undo (will fail due to already undone, but auth passes)."""
        resp = client.post(
            f"/undo/{undone_snapshot.snapshot_uuid}",
            headers=receptionist_auth_headers,
        )
        # Should be 400 (already undone), not 403
        assert resp.status_code == 400

    def test_undo_checkin_entity_missing(self, client, manager_auth_headers, db_session, _manager_user):
        """Undo check_in when entity doesn't exist returns an error."""
        snapshot = OperationSnapshot(
            snapshot_uuid=str(uuid.uuid4()),
            operation_type=OperationType.CHECK_IN.value,
            operator_id=_manager_user.id,
            operation_time=datetime.now(),
            entity_type="stay_record",
            entity_id=99999,
            before_state=json.dumps({"room": {"id": 1, "room_number": "101", "status": "vacant_clean"}}),
            after_state=json.dumps({"stay_record_id": 99999}),
            related_snapshots=json.dumps([]),
            is_undone=False,
            expires_at=datetime.now() + timedelta(hours=24),
        )
        db_session.add(snapshot)
        db_session.commit()

        resp = client.post(
            f"/undo/{snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        # ValueError is raised for missing entities, caught as 400;
        # other exceptions may be caught as 500
        assert resp.status_code in (400, 500)
        assert "不存在" in resp.json()["detail"] or "撤销失败" in resp.json()["detail"]


# ────────────────────────── GET /undo/history ──────────────────────────


class TestUndoHistory:
    """GET /undo/history"""

    def test_history_empty(self, client, manager_auth_headers):
        resp = client.get("/undo/history", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_with_data(self, client, manager_auth_headers, undone_snapshot):
        resp = client.get("/undo/history", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_undone"] is True

    def test_history_only_shows_undone(self, client, manager_auth_headers, undone_snapshot, undoable_snapshot):
        resp = client.get("/undo/history", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        uuids = [item["snapshot_uuid"] for item in data]
        assert undone_snapshot.snapshot_uuid in uuids
        assert undoable_snapshot.snapshot_uuid not in uuids

    def test_history_with_limit(self, client, manager_auth_headers, undone_snapshot):
        resp = client.get("/undo/history?limit=1", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    def test_history_forbidden_for_receptionist(self, client, receptionist_auth_headers):
        """History is only for manager role."""
        resp = client.get("/undo/history", headers=receptionist_auth_headers)
        assert resp.status_code == 403

    def test_history_forbidden_for_cleaner(self, client, cleaner_auth_headers):
        resp = client.get("/undo/history", headers=cleaner_auth_headers)
        assert resp.status_code == 403

    def test_history_forbidden_for_sysadmin(self, client, sysadmin_auth_headers):
        """Undo history checks for manager role, not sysadmin."""
        resp = client.get("/undo/history", headers=sysadmin_auth_headers)
        assert resp.status_code == 403


# ────────────────────────── GET /undo/{uuid} (detail) ──────────────────────────


class TestSnapshotDetail:
    """GET /undo/{snapshot_uuid}"""

    def test_snapshot_detail_success(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get(
            f"/undo/{undoable_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot_uuid"] == undoable_snapshot.snapshot_uuid
        assert data["operation_type"] == OperationType.CHECK_IN.value
        assert "before_state" in data
        assert "after_state" in data
        assert isinstance(data["before_state"], dict)
        assert isinstance(data["after_state"], dict)
        assert data["can_undo"] is True

    def test_snapshot_detail_undone(self, client, manager_auth_headers, undone_snapshot):
        resp = client.get(
            f"/undo/{undone_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_undone"] is True
        assert data["can_undo"] is False
        assert data["undone_time"] is not None

    def test_snapshot_detail_expired(self, client, manager_auth_headers, expired_snapshot):
        resp = client.get(
            f"/undo/{expired_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_undo"] is False

    def test_snapshot_detail_not_found(self, client, manager_auth_headers):
        resp = client.get(
            f"/undo/{str(uuid.uuid4())}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 404

    def test_snapshot_detail_as_receptionist(self, client, receptionist_auth_headers, undoable_snapshot):
        resp = client.get(
            f"/undo/{undoable_snapshot.snapshot_uuid}",
            headers=receptionist_auth_headers,
        )
        assert resp.status_code == 200

    def test_snapshot_detail_forbidden_for_cleaner(self, client, cleaner_auth_headers, undoable_snapshot):
        resp = client.get(
            f"/undo/{undoable_snapshot.snapshot_uuid}",
            headers=cleaner_auth_headers,
        )
        assert resp.status_code == 403

    def test_snapshot_detail_response_fields(self, client, manager_auth_headers, undoable_snapshot):
        resp = client.get(
            f"/undo/{undoable_snapshot.snapshot_uuid}",
            headers=manager_auth_headers,
        )
        data = resp.json()
        expected_fields = [
            "id", "snapshot_uuid", "operation_type", "operator_id",
            "operator_name", "operation_time", "entity_type", "entity_id",
            "before_state", "after_state", "is_undone", "undone_time",
            "undone_by", "expires_at", "can_undo",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
