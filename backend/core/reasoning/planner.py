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
    """规划步骤状态 - Status of a planning step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanningStep:
    """规划步骤 - A single step in an execution plan

    Args:
        step_id: Unique identifier for this step
        action_type: Type of action to execute (e.g., "change_room", "create_task")
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
        """检查是否准备好执行（所有依赖都已完成）

        Args:
            completed_steps: List of step_ids that have been completed

        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        return all(dep in completed_steps for dep in self.dependencies)


@dataclass
class ExecutionPlan:
    """执行计划 - A complete execution plan with multiple steps

    Args:
        plan_id: Unique identifier for this plan
        goal: Original goal description (e.g., "把201房客人换到305房间")
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
        """获取下一个可执行的步骤

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
        """生成 LLM 可理解的计划摘要

        Returns:
            A formatted string with emoji icons showing plan status
        """
        lines = [f"## 执行计划: {self.goal}\n"]
        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.COMPLETED: "✅",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.FAILED: "❌",
                StepStatus.PENDING: "⏳",
            }.get(step.status, "⏳")
            lines.append(f"{i}. {status_icon} {step.description}")
            if step.dependencies:
                lines.append(f"   依赖: {', '.join(step.dependencies)}")
        return "\n".join(lines)


class PlannerEngine:
    """多步规划引擎 - Multi-step planning engine

    Decomposes complex tasks into multiple executable steps with
    dependency resolution and step-by-step execution.

    The engine uses LLM to generate execution plans and executes them
    with proper dependency tracking.
    """

    def __init__(self, registry: "OntologyRegistry"):
        """初始化规划引擎 - Initialize the planning engine

        Args:
            registry: 本体注册表实例 - Ontology registry instance
        """
        self.registry = registry
        self._action_handlers: Dict[str, Callable] = {}

    def register_handler(self, action_type: str, handler: Callable) -> None:
        """注册操作处理器 - Register an action handler

        Args:
            action_type: 操作类型 - Action type (e.g., "change_room", "create_task")
            handler: 处理函数 - Handler function with signature (params, context) -> Dict[str, Any]
        """
        self._action_handlers[action_type] = handler

    def create_plan(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """根据目标创建执行计划 - Create an execution plan from a goal

        Args:
            goal: 用户目标描述 - User goal description (e.g., "把201房客人换到305房间")
            context: 当前上下文 - Current context (user info, room states, etc.)

        Returns:
            ExecutionPlan 执行计划 - Execution plan with steps
        """
        return self._llm_generate_plan(goal, context)

    def _llm_generate_plan(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """使用 LLM 生成执行计划 - Generate execution plan using LLM

        Args:
            goal: 用户目标 - User goal
            context: 上下文 - Context

        Returns:
            ExecutionPlan 执行计划 - Execution plan
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

    def _build_planning_prompt(self, goal: str, context: Dict[str, Any]) -> str:
        """构建规划提示词 - Build planning prompt for LLM

        Args:
            goal: 用户目标 - User goal
            context: 上下文 - Context

        Returns:
            str 提示词 - Prompt string
        """
        available_actions = self._get_available_actions_summary()
        context_str = self._format_context(context)

        return f"""你是任务规划专家。将用户目标分解为可执行的步骤。

**用户目标**: {goal}

**当前上下文**:
{context_str}

**可用操作**:
{available_actions}

**输出格式**:
{{
  "goal": "重述目标",
  "steps": [
    {{
      "step_id": "step_1",
      "action_type": "change_room",
      "description": "将客人从201房间搬到305房间",
      "params": {{"stay_record_id": 123, "new_room_id": 305}},
      "dependencies": []
    }},
    {{
      "step_id": "step_2",
      "action_type": "update_card_key",
      "description": "更新305房间的房卡信息",
      "params": {{"room_id": 305}},
      "dependencies": ["step_1"]
    }},
    {{
      "step_id": "step_3",
      "action_type": "create_task",
      "description": "为201房间创建清洁任务",
      "params": {{"room_id": 201, "task_type": "CLEANING"}},
      "dependencies": ["step_1"]
    }}
  ]
}}

**规则**:
1. 步骤必须按依赖顺序排列
2. 只使用上面列出的可用操作
3. 参数必须与操作定义匹配
4. 如有不确定的参数，使用 null 标记
"""

    def _get_available_actions_summary(self) -> str:
        """获取可用操作摘要 - Get summary of available actions

        Returns:
            str 操作列表 - Formatted list of available actions
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
        return "\n".join(actions) if actions else "(无可用操作)"

    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文为可读字符串 - Format context as readable string

        Args:
            context: 上下文字典 - Context dictionary

        Returns:
            str 格式化的上下文 - Formatted context string
        """
        lines = []
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            elif isinstance(value, (list, tuple)):
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines) if lines else "(无上下文信息)"

    def _parse_plan(self, plan_data: Dict[str, Any], goal: str) -> ExecutionPlan:
        """解析 LLM 返回的计划数据 - Parse plan data from LLM response

        Args:
            plan_data: LLM 返回的计划数据 - Plan data from LLM
            goal: 原始目标 - Original goal

        Returns:
            ExecutionPlan 执行计划 - Parsed execution plan
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
        """执行计划 - Execute the execution plan

        Args:
            plan: 执行计划 - Execution plan
            context: 执行上下文 - Execution context (contains user, db, etc.)

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
                    "error": "部分步骤执行失败"
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
                next_step.error_message = result.get("error", "未知错误")

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
            "error": "计划未能完全执行"
        }

    def _execute_step(
        self,
        step: PlanningStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个步骤 - Execute a single planning step

        Args:
            step: 规划步骤 - Planning step to execute
            context: 执行上下文 - Execution context

        Returns:
            Dict with success status and optional error
        """
        handler = self._action_handlers.get(step.action_type)
        if not handler:
            return {
                "success": False,
                "error": f"未找到操作处理器: {step.action_type}"
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
