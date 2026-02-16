"""
core/reasoning/planner.py

Multi-step planning engine - Decomposes complex tasks into executable steps
Part of the universal ontology-driven LLM reasoning framework
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry


class StepStatus(Enum):
    """Status of a planning step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanningStep:
    """A single step in an execution plan.

    Args:
        step_id: Unique identifier for this step
        action_type: Type of action to execute
        description: Human-readable description of the step
        params: Parameters to pass to the action handler
        dependencies: List of step_ids that must complete before this step
        status: Current status of the step
        result: Execution result after completion
        error_message: Error message if the step failed
    """
    step_id: str
    action_type: str
    description: str
    params: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def is_ready(self, completed_steps: List[str]) -> bool:
        """Check if all dependencies are satisfied and the step is ready to execute.

        Args:
            completed_steps: List of step_ids that have been completed

        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        return all(dep in completed_steps for dep in self.dependencies)


@dataclass
class ExecutionPlan:
    """A complete execution plan with multiple steps.

    Args:
        plan_id: Unique identifier for this plan
        goal: Original goal description
        steps: List of planning steps to execute
        current_step_index: Index of the current step being executed
        status: Overall plan status (pending, executing, completed, failed)
    """
    plan_id: str
    goal: str
    steps: List[PlanningStep]
    current_step_index: int = 0
    status: str = "pending"  # pending, executing, completed, failed

    def get_next_executable_step(self) -> Optional[PlanningStep]:
        """Get the next executable step.

        Returns:
            The next PENDING step whose dependencies are all satisfied,
            or None if no such step exists
        """
        completed = [s.step_id for s in self.steps if s.status == StepStatus.COMPLETED]
        for step in self.steps:
            if step.status == StepStatus.PENDING and step.is_ready(completed):
                return step
        return None

    def to_llm_summary(self) -> str:
        """Generate an LLM-readable plan summary.

        Returns:
            A formatted string with emoji icons showing plan status
        """
        lines = [f"## Execution Plan: {self.goal}\n"]
        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.COMPLETED: "✅",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.FAILED: "❌",
                StepStatus.PENDING: "⏳",
            }.get(step.status, "⏳")
            lines.append(f"{i}. {status_icon} {step.description}")
            if step.dependencies:
                lines.append(f"   Dependencies: {', '.join(step.dependencies)}")
        return "\n".join(lines)


class PlannerEngine:
    """Multi-step planning engine.

    Decomposes complex tasks into multiple executable steps with
    dependency resolution and step-by-step execution.

    The engine uses a three-tier strategy (SPEC-4):
    1. Template matching (deterministic, for known composite operations)
    2. Ontology reasoning (future: precondition/effect graph search)
    3. LLM plan generation (fallback for novel combinations)
    """

    def __init__(self, registry: "OntologyRegistry", template_registry=None):
        """Initialize the planning engine.

        Args:
            registry: Ontology registry instance
            template_registry: Optional TemplateRegistry for composite templates (SPEC-4)
        """
        self.registry = registry
        self._template_registry = template_registry
        self._action_handlers: Dict[str, Callable] = {}

    def register_handler(self, action_type: str, handler: Callable) -> None:
        """Register an action handler.

        Args:
            action_type: Action type identifier
            handler: Handler function with signature (params, context) -> Dict[str, Any]
        """
        self._action_handlers[action_type] = handler

    def create_plan(
        self,
        goal: str,
        context: Dict[str, Any],
        action_type: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Create an execution plan from a goal.

        Uses three-tier strategy (SPEC-4):
        1. Template matching if action_type is provided
        2. (Future) Ontology reasoning via precondition/effect search
        3. LLM plan generation as fallback

        Args:
            goal: User goal description
            context: Current context (user info, entity states, etc.)
            action_type: Optional action type to match against templates
            params: Optional parameters for template expansion

        Returns:
            Execution plan with steps
        """
        # Tier 1: Template matching (SPEC-4)
        if action_type and self._template_registry:
            plan = self._template_registry.expand(action_type, params or {}, goal)
            if plan:
                return plan

        # Tier 2: (Future) Ontology reasoning

        # Tier 3: LLM plan generation (fallback)
        return self._llm_generate_plan(goal, context)

    def _llm_generate_plan(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate execution plan using LLM.

        Args:
            goal: User goal
            context: Context

        Returns:
            Execution plan
        """
        import uuid
        from core.ai.llm_client import LLMClient

        prompt = self._build_planning_prompt(goal, context)

        llm_client = LLMClient()
        response = llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        plan_data = response.to_json() or {}
        return self._parse_plan(plan_data, goal)

    def _build_example_steps(self) -> str:
        """Build example steps dynamically from registered actions.

        Picks up to 2 actions from the registry that have params defined,
        and generates JSON example steps using their metadata. Falls back
        to a generic placeholder if no actions are registered.

        Returns:
            JSON string with example steps
        """
        from core.ontology.metadata import ParamType

        type_placeholders = {
            ParamType.INTEGER: 123,
            ParamType.STRING: '"example"',
            ParamType.BOOLEAN: "true",
            ParamType.DATE: '"2024-01-15"',
            ParamType.NUMBER: 3.14,
        }

        all_actions = self.registry.get_actions()
        actions_with_params = [a for a in all_actions if a.params]

        if not actions_with_params:
            return json.dumps({
                "step_id": "step_1",
                "action_type": "generic_action",
                "description": "Describe what this step does",
                "params": {"id": 123},
                "dependencies": []
            }, indent=6)

        examples = []
        for i, action in enumerate(actions_with_params[:2], 1):
            param_examples = {}
            for p in action.params:
                placeholder = type_placeholders.get(p.type, "null")
                param_examples[p.name] = placeholder
            examples.append({
                "step_id": f"step_{i}",
                "action_type": action.action_type,
                "description": "Describe what this step does",
                "params": param_examples,
                "dependencies": [f"step_{j}" for j in range(1, i)]
            })

        return ",\n    ".join(json.dumps(ex, indent=6) for ex in examples)

    def _build_planning_prompt(self, goal: str, context: Dict[str, Any]) -> str:
        """Build planning prompt for LLM.

        Args:
            goal: User goal
            context: Context

        Returns:
            Prompt string
        """
        available_actions = self._get_available_actions_summary()
        context_str = self._format_context(context)
        example_steps = self._build_example_steps()

        return f"""You are a task planning expert. Decompose the user's goal into executable steps.

**User Goal**: {goal}

**Current Context**:
{context_str}

**Available Actions**:
{available_actions}

**Output Format**:
{{
  "goal": "Restate the goal",
  "steps": [
    {example_steps}
  ]
}}

**Rules**:
1. Steps must be ordered by their dependencies
2. Only use the available actions listed above
3. Parameters must match the action definitions
4. Use null for any uncertain parameters
"""

    def _get_available_actions_summary(self) -> str:
        """Get summary of available actions.

        Returns:
            Formatted list of available actions
        """
        actions = []
        # Get all registered actions from registry
        all_actions = self.registry.get_actions()

        # Build a mapping of action_type to description
        action_descriptions = {action.action_type: action.description for action in all_actions}

        for action_type in self._action_handlers.keys():
            description = action_descriptions.get(action_type, "")
            if description:
                actions.append(f"- {action_type}: {description}")
            else:
                actions.append(f"- {action_type}")
        return "\n".join(actions) if actions else "(no actions available)"

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context as a readable string.

        Args:
            context: Context dictionary

        Returns:
            Formatted context string
        """
        lines = []
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            elif isinstance(value, (list, tuple)):
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines) if lines else "(no context)"

    def _parse_plan(self, plan_data: Dict[str, Any], goal: str) -> ExecutionPlan:
        """Parse plan data from LLM response.

        Args:
            plan_data: Plan data from LLM
            goal: Original goal

        Returns:
            Parsed execution plan
        """
        import uuid
        plan_id = str(uuid.uuid4())
        steps = []

        for step_data in plan_data.get("steps", []):
            step = PlanningStep(
                step_id=step_data.get("step_id", str(uuid.uuid4())),
                action_type=step_data.get("action_type", ""),
                description=step_data.get("description", ""),
                params=step_data.get("params", {}),
                dependencies=step_data.get("dependencies", [])
            )
            steps.append(step)

        return ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps
        )

    def execute_plan(
        self,
        plan: ExecutionPlan,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the execution plan.

        Args:
            plan: Execution plan
            context: Execution context (contains user, db, etc.)

        Returns:
            Dict with success status, plan summary, results, and optional error
        """
        plan.status = "executing"
        results = []

        while True:
            # Get next executable step
            next_step = plan.get_next_executable_step()
            if not next_step:
                break  # No more executable steps

            # Check if any step has failed
            if any(s.status == StepStatus.FAILED for s in plan.steps):
                plan.status = "failed"
                return {
                    "success": False,
                    "plan": plan.to_llm_summary(),
                    "error": "Some steps failed"
                }

            # Execute step
            next_step.status = StepStatus.IN_PROGRESS
            result = self._execute_step(next_step, context)

            if result.get("success"):
                next_step.status = StepStatus.COMPLETED
                next_step.result = result
                results.append(result)
            else:
                next_step.status = StepStatus.FAILED
                next_step.error_message = result.get("error", "Unknown error")

        # Check if all steps completed
        if all(s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for s in plan.steps):
            plan.status = "completed"
            return {
                "success": True,
                "plan": plan.to_llm_summary(),
                "results": results
            }

        return {
            "success": False,
            "plan": plan.to_llm_summary(),
            "error": "Plan did not complete"
        }

    def _execute_step(
        self,
        step: PlanningStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single planning step.

        Args:
            step: Planning step to execute
            context: Execution context

        Returns:
            Dict with success status and optional error
        """
        handler = self._action_handlers.get(step.action_type)
        if not handler:
            return {
                "success": False,
                "error": f"No handler found for action: {step.action_type}"
            }

        try:
            return handler(**step.params, context=context)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Export
__all__ = [
    "StepStatus",
    "PlanningStep",
    "ExecutionPlan",
    "PlannerEngine",
]
