"""
tests/core/test_planner.py

Unit tests for the multi-step planning engine
Part of the universal ontology-driven LLM reasoning framework
"""
import pytest
from core.reasoning import PlanningStep, ExecutionPlan, PlannerEngine, StepStatus
from core.ontology.registry import registry


class TestPlanningStep:
    """Test PlanningStep dataclass"""

    def test_planning_step_is_ready(self):
        """测试 is_ready() 方法 - Test dependency checking logic"""
        # Step with no dependencies - always ready
        step = PlanningStep(
            step_id="step_1",
            action_type="test_action",
            description="Test step",
            params={}
        )
        assert step.is_ready([]) is True
        assert step.is_ready(["other"]) is True

        # Step with dependencies - ready when deps satisfied
        step_with_deps = PlanningStep(
            step_id="step_2",
            action_type="test_action",
            description="Test step with deps",
            params={},
            dependencies=["step_1", "step_3"]
        )
        # Not ready when no deps completed
        assert step_with_deps.is_ready([]) is False
        # Not ready when only some deps completed
        assert step_with_deps.is_ready(["step_1"]) is False
        # Ready when all deps completed
        assert step_with_deps.is_ready(["step_1", "step_3"]) is True
        # Ready when all deps plus others completed
        assert step_with_deps.is_ready(["step_1", "step_3", "other"]) is True


class TestExecutionPlan:
    """Test ExecutionPlan dataclass"""

    def test_execution_plan_get_next_executable_step(self):
        """测试 get_next_executable_step() 方法 - Test next step retrieval"""
        # Create steps with dependencies
        step1 = PlanningStep(
            step_id="step_1",
            action_type="action1",
            description="First step",
            params={}
        )
        step2 = PlanningStep(
            step_id="step_2",
            action_type="action2",
            description="Second step (depends on step1)",
            params={},
            dependencies=["step_1"]
        )
        step3 = PlanningStep(
            step_id="step_3",
            action_type="action3",
            description="Third step (depends on step2)",
            params={},
            dependencies=["step_2"]
        )

        plan = ExecutionPlan(
            plan_id="test_plan",
            goal="Test goal",
            steps=[step1, step2, step3]
        )

        # Initially, only step1 is ready
        next_step = plan.get_next_executable_step()
        assert next_step is not None
        assert next_step.step_id == "step_1"

        # Mark step1 as completed, now step2 is ready
        step1.status = StepStatus.COMPLETED
        next_step = plan.get_next_executable_step()
        assert next_step is not None
        assert next_step.step_id == "step_2"

        # Mark step2 as completed, now step3 is ready
        step2.status = StepStatus.COMPLETED
        next_step = plan.get_next_executable_step()
        assert next_step is not None
        assert next_step.step_id == "step_3"

        # All steps completed - no next step
        step3.status = StepStatus.COMPLETED
        next_step = plan.get_next_executable_step()
        assert next_step is None


class TestPlannerEngine:
    """Test PlannerEngine class"""

    def test_planner_engine_register_handler(self):
        """测试 register_handler() 方法 - Test handler registration"""
        planner = PlannerEngine(registry)

        # Initially no handlers
        assert len(planner._action_handlers) == 0

        # Register a handler
        def dummy_handler(**kwargs):
            return {"success": True}

        planner.register_handler("test_action", dummy_handler)

        # Handler should be registered
        assert "test_action" in planner._action_handlers
        assert planner._action_handlers["test_action"] == dummy_handler

        # Register multiple handlers
        def another_handler(**kwargs):
            return {"success": True}

        planner.register_handler("another_action", another_handler)
        assert len(planner._action_handlers) == 2

    def test_planner_engine_execute_plan_with_dependencies(self):
        """测试 execute_plan() 方法 - Test plan execution with dependencies"""
        planner = PlannerEngine(registry)

        # Track execution order
        execution_order = []

        # Create handlers that track execution
        def handler_1(**kwargs):
            execution_order.append("step_1")
            return {"success": True, "message": "Step 1 executed"}

        def handler_2(**kwargs):
            execution_order.append("step_2")
            return {"success": True, "message": "Step 2 executed"}

        def handler_3(**kwargs):
            execution_order.append("step_3")
            return {"success": True, "message": "Step 3 executed"}

        planner.register_handler("action1", handler_1)
        planner.register_handler("action2", handler_2)
        planner.register_handler("action3", handler_3)

        # Create plan with dependencies: step3 -> step2 -> step1
        # (step3 depends on step2, step2 depends on step1)
        step1 = PlanningStep(
            step_id="step_1",
            action_type="action1",
            description="First step",
            params={}
        )
        step2 = PlanningStep(
            step_id="step_2",
            action_type="action2",
            description="Second step",
            params={},
            dependencies=["step_1"]
        )
        step3 = PlanningStep(
            step_id="step_3",
            action_type="action3",
            description="Third step",
            params={},
            dependencies=["step_2"]
        )

        plan = ExecutionPlan(
            plan_id="test_plan",
            goal="Test goal with dependencies",
            steps=[step3, step2, step1]  # Intentionally out of order
        )

        # Execute plan
        result = planner.execute_plan(plan, {})

        # Should succeed
        assert result["success"] is True
        assert plan.status == "completed"

        # Steps should execute in dependency order
        assert execution_order == ["step_1", "step_2", "step_3"]

        # All steps should be completed
        assert step1.status == StepStatus.COMPLETED
        assert step2.status == StepStatus.COMPLETED
        assert step3.status == StepStatus.COMPLETED
