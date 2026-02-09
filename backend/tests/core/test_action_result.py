"""
Tests for SPEC-02: ActionResult + ExecutionContext
"""
import pytest
from core.ai.result import ActionResult, AffectedEntity
from core.ai.context import ExecutionContext


class TestAffectedEntity:
    def test_create(self):
        ae = AffectedEntity(entity_type="Room", entity_id=1, change_type="updated")
        assert ae.entity_type == "Room"
        assert ae.entity_id == 1
        assert ae.change_type == "updated"


class TestActionResult:
    def test_success_result(self):
        result = ActionResult(success=True, message="Done")
        assert result.success is True
        assert result.message == "Done"
        assert result.data == {}
        assert result.affected_entities == []
        assert result.events_emitted == []
        assert result.error_code is None
        assert result.valid_alternatives == []

    def test_failure_result_with_error_code(self):
        result = ActionResult(
            success=False,
            message="Room occupied",
            error_code="state_error",
            valid_alternatives=["checkout", "change_room"],
        )
        assert result.success is False
        assert result.error_code == "state_error"
        assert len(result.valid_alternatives) == 2

    def test_result_with_affected_entities(self):
        result = ActionResult(
            success=True,
            message="Checked in",
            entity_type="StayRecord",
            entity_id=42,
            affected_entities=[
                AffectedEntity("StayRecord", 42, "created"),
                AffectedEntity("Room", 5, "updated"),
            ],
            events_emitted=["GUEST_CHECKED_IN", "ROOM_STATUS_CHANGED"],
        )
        assert result.entity_type == "StayRecord"
        assert result.entity_id == 42
        assert len(result.affected_entities) == 2
        assert len(result.events_emitted) == 2

    def test_ok_factory(self):
        result = ActionResult.ok("Success", data={"key": "value"})
        assert result.success is True
        assert result.message == "Success"
        assert result.data == {"key": "value"}

    def test_fail_factory(self):
        result = ActionResult.fail("Error", error_code="validation_error")
        assert result.success is False
        assert result.error_code == "validation_error"

    def test_data_isolation(self):
        """Ensure mutable defaults don't leak"""
        r1 = ActionResult(success=True, message="a")
        r2 = ActionResult(success=True, message="b")
        r1.data["key"] = "value"
        assert "key" not in r2.data

    def test_affected_entities_isolation(self):
        r1 = ActionResult(success=True, message="a")
        r2 = ActionResult(success=True, message="b")
        r1.affected_entities.append(AffectedEntity("X", 1, "created"))
        assert len(r2.affected_entities) == 0


class TestExecutionContext:
    def test_create_minimal(self):
        ctx = ExecutionContext(
            db="fake_db",
            user_id=1,
            user_role="admin",
            user_name="Admin",
        )
        assert ctx.db == "fake_db"
        assert ctx.user_id == 1
        assert ctx.user_role == "admin"
        assert ctx.user_name == "Admin"
        assert ctx.param_parser is None
        assert ctx.event_bus is None
        assert ctx.audit_logger is None
        assert ctx.state_machine is None

    def test_create_full(self):
        ctx = ExecutionContext(
            db="db",
            user_id=2,
            user_role="manager",
            user_name="Manager",
            param_parser="parser",
            event_bus="bus",
            audit_logger="logger",
            state_machine="sm",
        )
        assert ctx.param_parser == "parser"
        assert ctx.event_bus == "bus"
        assert ctx.audit_logger == "logger"
        assert ctx.state_machine == "sm"
