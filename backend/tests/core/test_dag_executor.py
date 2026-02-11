"""
tests/core/test_dag_executor.py

SPEC-4: Tests for DAGExecutor - multi-step plan execution.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from core.reasoning.dag_executor import DAGExecutor, StepResult, ExecutionResult
from core.reasoning.planner import PlanningStep, ExecutionPlan, StepStatus


def _make_plan(steps, goal="test goal"):
    """Helper to create an ExecutionPlan."""
    return ExecutionPlan(plan_id="plan-1", goal=goal, steps=steps)


def _make_step(step_id, action_type="action", params=None, deps=None):
    """Helper to create a PlanningStep."""
    return PlanningStep(
        step_id=step_id,
        action_type=action_type,
        description=f"Step {step_id}",
        params=params or {},
        dependencies=deps or [],
    )


class TestStepResult:
    """Test StepResult data class."""

    def test_success_result(self):
        r = StepResult(step_id="s1", action_type="a", success=True, result={"ok": True})
        assert r.success
        assert r.result == {"ok": True}

    def test_failure_result(self):
        r = StepResult(step_id="s1", action_type="a", success=False, error="boom")
        assert not r.success
        assert r.error == "boom"


class TestExecutionResult:
    """Test ExecutionResult data class."""

    def test_to_dict(self):
        result = ExecutionResult(
            success=False,
            plan_id="p1",
            step_results=[
                StepResult(step_id="s1", action_type="a1", success=True),
                StepResult(step_id="s2", action_type="a2", success=False, error="err"),
            ],
            failed_step="s2",
            error="err",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["plan_id"] == "p1"
        assert len(d["steps"]) == 2
        assert d["steps"][0]["success"] is True
        assert d["steps"][1]["error"] == "err"
        assert d["failed_step"] == "s2"


class TestDAGExecutorBasic:
    """Test basic execution scenarios."""

    def test_empty_plan(self):
        dispatcher = Mock()
        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([])
        result = executor.execute(plan, {})
        assert result.success
        assert len(result.step_results) == 0
        dispatcher.assert_not_called()

    def test_single_step_success(self):
        dispatcher = Mock(return_value={"success": True, "message": "done"})
        executor = DAGExecutor(action_dispatcher=dispatcher)

        plan = _make_plan([_make_step("s1", "checkout", {"id": 1})])
        result = executor.execute(plan, {"db": "mock"})

        assert result.success
        assert len(result.step_results) == 1
        assert result.step_results[0].success
        dispatcher.assert_called_once_with("checkout", {"id": 1}, {"db": "mock"})

    def test_single_step_failure(self):
        dispatcher = Mock(return_value={"success": False, "message": "Room not found"})
        executor = DAGExecutor(action_dispatcher=dispatcher)

        plan = _make_plan([_make_step("s1", "checkout")])
        result = executor.execute(plan, {})

        assert not result.success
        assert result.failed_step == "s1"
        assert "Room not found" in result.error

    def test_single_step_exception(self):
        dispatcher = Mock(side_effect=ValueError("DB error"))
        executor = DAGExecutor(action_dispatcher=dispatcher)

        plan = _make_plan([_make_step("s1", "checkout")])
        result = executor.execute(plan, {})

        assert not result.success
        assert result.failed_step == "s1"
        assert "DB error" in result.error


class TestDAGExecutorDependencies:
    """Test dependency ordering."""

    def test_sequential_dependencies(self):
        """Steps execute in dependency order: s1 -> s2 -> s3."""
        call_order = []

        def dispatcher(action, params, ctx):
            call_order.append(action)
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([
            _make_step("s1", "step_1"),
            _make_step("s2", "step_2", deps=["s1"]),
            _make_step("s3", "step_3", deps=["s2"]),
        ])

        result = executor.execute(plan, {})
        assert result.success
        assert call_order == ["step_1", "step_2", "step_3"]

    def test_parallel_then_join(self):
        """s1 and s2 can run independently, s3 depends on both."""
        call_order = []

        def dispatcher(action, params, ctx):
            call_order.append(action)
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([
            _make_step("s1", "parallel_a"),
            _make_step("s2", "parallel_b"),
            _make_step("s3", "join", deps=["s1", "s2"]),
        ])

        result = executor.execute(plan, {})
        assert result.success
        # s3 must come after both s1 and s2
        assert call_order.index("join") > call_order.index("parallel_a")
        assert call_order.index("join") > call_order.index("parallel_b")

    def test_failure_skips_remaining(self):
        """When s2 fails, s3 should be skipped."""
        def dispatcher(action, params, ctx):
            if action == "fail_action":
                return {"success": False, "message": "failed"}
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([
            _make_step("s1", "ok_action"),
            _make_step("s2", "fail_action", deps=["s1"]),
            _make_step("s3", "never_reached", deps=["s2"]),
        ])

        result = executor.execute(plan, {})
        assert not result.success
        assert result.failed_step == "s2"
        assert len(result.step_results) == 2  # s1 and s2 only
        assert plan.steps[2].status == StepStatus.SKIPPED


class TestDAGExecutorRollback:
    """Test rollback behavior."""

    def test_rollback_on_failure(self):
        """Completed steps get rolled back when a later step fails."""
        call_count = [0]

        def dispatcher(action, params, ctx):
            call_count[0] += 1
            if action == "fail":
                return {"success": False, "message": "boom"}
            return {"success": True}

        mock_snapshot_engine = Mock()
        mock_snapshot_engine.create_snapshot.return_value = Mock(snapshot_id="snap-1")
        mock_snapshot_engine.undo.return_value = True

        executor = DAGExecutor(
            action_dispatcher=dispatcher,
            snapshot_engine=mock_snapshot_engine,
        )

        plan = _make_plan([
            _make_step("s1", "ok"),
            _make_step("s2", "fail", deps=["s1"]),
        ])

        result = executor.execute(plan, {})
        assert not result.success
        assert result.rollback_status == "success"
        mock_snapshot_engine.undo.assert_called_once()

    def test_partial_rollback(self):
        """When some rollbacks fail, status is 'partial'."""
        call_idx = [0]

        def dispatcher(action, params, ctx):
            call_idx[0] += 1
            if action == "fail":
                return {"success": False, "message": "boom"}
            return {"success": True}

        mock_snapshot_engine = Mock()
        # Create distinct snapshot IDs for each step
        mock_snapshot_engine.create_snapshot.side_effect = [
            Mock(snapshot_id="snap-1"),
            Mock(snapshot_id="snap-2"),
            Mock(snapshot_id="snap-3"),
        ]
        # First undo succeeds, second fails
        mock_snapshot_engine.undo.side_effect = [False, True]

        executor = DAGExecutor(
            action_dispatcher=dispatcher,
            snapshot_engine=mock_snapshot_engine,
        )

        plan = _make_plan([
            _make_step("s1", "ok_1"),
            _make_step("s2", "ok_2", deps=["s1"]),
            _make_step("s3", "fail", deps=["s2"]),
        ])

        result = executor.execute(plan, {})
        assert not result.success
        assert result.rollback_status == "partial"

    def test_no_rollback_without_snapshot_engine(self):
        """Without snapshot engine, rollback is None."""
        def dispatcher(action, params, ctx):
            if action == "fail":
                return {"success": False, "message": "boom"}
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([
            _make_step("s1", "ok"),
            _make_step("s2", "fail", deps=["s1"]),
        ])

        result = executor.execute(plan, {})
        assert not result.success
        assert result.rollback_status is None


class TestDAGExecutorTopologicalSort:
    """Test topological sort edge cases."""

    def test_independent_steps_preserve_order(self):
        """Steps with no deps run in original order."""
        call_order = []

        def dispatcher(action, params, ctx):
            call_order.append(action)
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        plan = _make_plan([
            _make_step("s1", "first"),
            _make_step("s2", "second"),
            _make_step("s3", "third"),
        ])

        result = executor.execute(plan, {})
        assert result.success
        assert call_order == ["first", "second", "third"]

    def test_reverse_dependency_order(self):
        """Steps defined in reverse dep order still execute correctly."""
        call_order = []

        def dispatcher(action, params, ctx):
            call_order.append(action)
            return {"success": True}

        executor = DAGExecutor(action_dispatcher=dispatcher)
        # s2 depends on s1, but s2 is listed first
        plan = _make_plan([
            _make_step("s2", "second", deps=["s1"]),
            _make_step("s1", "first"),
        ])

        result = executor.execute(plan, {})
        assert result.success
        assert call_order == ["first", "second"]

    def test_plan_status_updated(self):
        """Plan status changes through execution."""
        dispatcher = Mock(return_value={"success": True})
        executor = DAGExecutor(action_dispatcher=dispatcher)

        plan = _make_plan([_make_step("s1", "action")])
        assert plan.status == "pending"

        result = executor.execute(plan, {})
        assert plan.status == "completed"

    def test_plan_status_failed(self):
        dispatcher = Mock(return_value={"success": False, "message": "err"})
        executor = DAGExecutor(action_dispatcher=dispatcher)

        plan = _make_plan([_make_step("s1", "action")])
        executor.execute(plan, {})
        assert plan.status == "failed"


class TestDAGExecutorSnapshot:
    """Test snapshot integration."""

    def test_snapshot_created_and_marked(self):
        """Successful execution creates and marks snapshot."""
        mock_snapshot = Mock()
        mock_snapshot.create_snapshot.return_value = Mock(snapshot_id="snap-1")

        dispatcher = Mock(return_value={"success": True, "data": "ok"})
        executor = DAGExecutor(
            action_dispatcher=dispatcher,
            snapshot_engine=mock_snapshot,
        )

        plan = _make_plan([_make_step("s1", "action", {"k": "v"})])
        result = executor.execute(plan, {})

        assert result.success
        mock_snapshot.create_snapshot.assert_called_once()
        mock_snapshot.mark_executed.assert_called_once_with(
            "snap-1", {"result": {"success": True, "data": "ok"}}
        )

    def test_snapshot_failure_doesnt_block(self):
        """Snapshot creation failure doesn't prevent step execution."""
        mock_snapshot = Mock()
        mock_snapshot.create_snapshot.side_effect = RuntimeError("snapshot failed")

        dispatcher = Mock(return_value={"success": True})
        executor = DAGExecutor(
            action_dispatcher=dispatcher,
            snapshot_engine=mock_snapshot,
        )

        plan = _make_plan([_make_step("s1", "action")])
        result = executor.execute(plan, {})

        assert result.success  # Step still executed
        dispatcher.assert_called_once()
