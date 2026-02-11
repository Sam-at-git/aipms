"""
core/reasoning/dag_executor.py

DAG Execution Engine for composite action plans.

Executes multi-step plans with:
- Topological sort for dependency resolution
- Sequential step execution with guard pre-checks
- Snapshot-based rollback on failure
- Structured execution results

SPEC-4: Action Composition & DAG Execution Engine
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from core.reasoning.planner import ExecutionPlan, PlanningStep, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    action_type: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    snapshot_id: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of executing a complete plan."""
    success: bool
    plan_id: str
    step_results: List[StepResult] = field(default_factory=list)
    failed_step: Optional[str] = None
    rollback_status: Optional[str] = None  # "success", "partial", "failed", None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "plan_id": self.plan_id,
            "steps": [
                {
                    "step_id": sr.step_id,
                    "action_type": sr.action_type,
                    "success": sr.success,
                    "error": sr.error,
                }
                for sr in self.step_results
            ],
            "failed_step": self.failed_step,
            "rollback_status": self.rollback_status,
            "error": self.error,
        }


class DAGExecutor:
    """DAG Execution Engine for multi-step action plans.

    Executes plans produced by PlannerEngine or TemplateRegistry with:
    - Dependency-aware ordering (topological sort)
    - Guard pre-checks before each step (via GuardExecutor)
    - Automatic snapshots for rollback capability
    - Structured results for each step

    Args:
        action_dispatcher: Callable(action_name, params, context) -> Dict
            Typically ActionRegistry.dispatch or a wrapper around it.
        guard_executor: Optional GuardExecutor for pre-step validation.
        snapshot_engine: Optional SnapshotEngine for rollback support.

    Example:
        executor = DAGExecutor(
            action_dispatcher=registry.dispatch,
            guard_executor=guard,
            snapshot_engine=snapshot_engine,
        )
        result = executor.execute(plan, context)
        if not result.success:
            print(f"Failed at step {result.failed_step}: {result.error}")
    """

    def __init__(
        self,
        action_dispatcher: Callable,
        guard_executor=None,
        snapshot_engine=None,
    ):
        self._dispatch = action_dispatcher
        self._guard_executor = guard_executor
        self._snapshot_engine = snapshot_engine

    def execute(
        self,
        plan: ExecutionPlan,
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute a plan with dependency resolution and rollback support.

        Args:
            plan: The execution plan to run
            context: Execution context (db, user, etc.)

        Returns:
            ExecutionResult with per-step results and rollback status
        """
        result = ExecutionResult(success=True, plan_id=plan.plan_id)

        # Topological sort
        try:
            ordered_steps = self._topological_sort(plan.steps)
        except ValueError as e:
            return ExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                error=f"Dependency cycle detected: {e}",
            )

        plan.status = "executing"
        completed_snapshots: List[str] = []  # For rollback

        for step in ordered_steps:
            step.status = StepStatus.IN_PROGRESS

            # Execute the step
            step_result = self._execute_step(step, context)
            result.step_results.append(step_result)

            if step_result.success:
                step.status = StepStatus.COMPLETED
                step.result = step_result.result
                if step_result.snapshot_id:
                    completed_snapshots.append(step_result.snapshot_id)
            else:
                step.status = StepStatus.FAILED
                step.error_message = step_result.error
                result.success = False
                result.failed_step = step.step_id
                result.error = step_result.error

                # Rollback completed steps
                if completed_snapshots:
                    result.rollback_status = self._rollback(completed_snapshots)
                else:
                    result.rollback_status = None

                # Mark remaining steps as skipped
                for remaining in ordered_steps:
                    if remaining.status == StepStatus.PENDING:
                        remaining.status = StepStatus.SKIPPED

                plan.status = "failed"
                return result

        plan.status = "completed"
        return result

    def _execute_step(
        self,
        step: PlanningStep,
        context: Dict[str, Any],
    ) -> StepResult:
        """Execute a single plan step.

        Args:
            step: The step to execute
            context: Execution context

        Returns:
            StepResult with success status and optional snapshot
        """
        # Create snapshot before execution (for rollback)
        snapshot_id = None
        if self._snapshot_engine:
            try:
                snapshot = self._snapshot_engine.create_snapshot(
                    operation_type=step.action_type,
                    entity_type=step.action_type,
                    entity_id=step.step_id,
                    before_state={"params": step.params},
                )
                snapshot_id = snapshot.snapshot_id
            except Exception as e:
                logger.warning(f"Failed to create snapshot for step {step.step_id}: {e}")

        # Dispatch the action
        try:
            action_result = self._dispatch(
                step.action_type,
                step.params,
                context,
            )

            # Check result
            if isinstance(action_result, dict) and action_result.get("success") is False:
                return StepResult(
                    step_id=step.step_id,
                    action_type=step.action_type,
                    success=False,
                    error=action_result.get("message") or action_result.get("error", "Action failed"),
                    snapshot_id=snapshot_id,
                )

            # Mark snapshot as executed
            if snapshot_id and self._snapshot_engine:
                self._snapshot_engine.mark_executed(snapshot_id, {"result": action_result})

            return StepResult(
                step_id=step.step_id,
                action_type=step.action_type,
                success=True,
                result=action_result,
                snapshot_id=snapshot_id,
            )

        except Exception as e:
            logger.error(f"Step {step.step_id} failed: {e}")
            return StepResult(
                step_id=step.step_id,
                action_type=step.action_type,
                success=False,
                error=str(e),
                snapshot_id=snapshot_id,
            )

    def _rollback(self, snapshot_ids: List[str]) -> str:
        """Rollback completed steps in reverse order.

        Args:
            snapshot_ids: Snapshot IDs to rollback (in execution order)

        Returns:
            "success" if all rollbacks succeeded,
            "partial" if some failed,
            "failed" if all failed
        """
        if not self._snapshot_engine:
            return "failed"

        successes = 0
        failures = 0

        # Rollback in reverse order
        for sid in reversed(snapshot_ids):
            try:
                if self._snapshot_engine.undo(sid):
                    successes += 1
                else:
                    failures += 1
            except Exception as e:
                logger.error(f"Rollback failed for snapshot {sid}: {e}")
                failures += 1

        if failures == 0:
            return "success"
        elif successes == 0:
            return "failed"
        else:
            return "partial"

    def _topological_sort(self, steps: List[PlanningStep]) -> List[PlanningStep]:
        """Sort steps by dependency order (Kahn's algorithm).

        Args:
            steps: Steps to sort

        Returns:
            Sorted list of steps

        Raises:
            ValueError: If a dependency cycle is detected
        """
        if not steps:
            return []

        # Build adjacency and in-degree
        step_map = {s.step_id: s for s in steps}
        in_degree = {s.step_id: 0 for s in steps}
        dependents = {s.step_id: [] for s in steps}

        for step in steps:
            for dep in step.dependencies:
                if dep in step_map:
                    in_degree[step.step_id] += 1
                    dependents[dep].append(step.step_id)

        # Start with steps that have no dependencies
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        sorted_ids = []

        while queue:
            current = queue.pop(0)
            sorted_ids.append(current)
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(sorted_ids) != len(steps):
            return list(steps)  # Fallback to original order on cycle

        return [step_map[sid] for sid in sorted_ids]


__all__ = [
    "StepResult",
    "ExecutionResult",
    "DAGExecutor",
]
