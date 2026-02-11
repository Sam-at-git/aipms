"""
core/reasoning/plan_templates.py

Composite operation templates for action composition.

Provides pre-defined multi-step templates for common composite operations
(e.g., change_room = verify_available + checkout + walkin_checkin).
Templates are registered by the domain layer, keeping this framework domain-agnostic.

SPEC-4: Action Composition & DAG Execution Engine
"""
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from core.reasoning.planner import PlanningStep, ExecutionPlan

logger = logging.getLogger(__name__)


@dataclass
class TemplateStep:
    """A single step in a composite template.

    Args:
        step_id: Unique step identifier within the template
        action_type: Action to execute (must be registered in ActionRegistry)
        description: Human-readable description
        param_bindings: Parameter mapping using $variable references
            e.g. {"stay_record_id": "$stay_record_id", "room_number": "$new_room_number"}
        dependencies: List of step_ids that must complete first
    """
    step_id: str
    action_type: str
    description: str
    param_bindings: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class CompositeTemplate:
    """A pre-defined composite operation template.

    Args:
        name: Template identifier (matches the trigger action name)
        trigger_action: The action that triggers this template
        description: Human-readable description of the composite operation
        steps: Ordered list of template steps
        required_params: Parameters required from the caller
    """
    name: str
    trigger_action: str
    description: str
    steps: List[TemplateStep]
    required_params: List[str] = field(default_factory=list)


class TemplateRegistry:
    """Registry for composite operation templates.

    Domain layers register templates here. The PlannerEngine checks
    templates before falling back to LLM-based planning.

    Example:
        registry = TemplateRegistry()
        registry.register(CompositeTemplate(
            name="change_room",
            trigger_action="change_room",
            description="Move guest to a different room",
            steps=[...],
        ))
        plan = registry.expand("change_room", {"stay_record_id": 1, "new_room_number": "305"})
    """

    def __init__(self):
        self._templates: Dict[str, CompositeTemplate] = {}

    def register(self, template: CompositeTemplate) -> None:
        """Register a composite template."""
        self._templates[template.trigger_action] = template
        logger.info(f"Registered composite template: {template.name} ({len(template.steps)} steps)")

    def get_template(self, trigger_action: str) -> Optional[CompositeTemplate]:
        """Get template by trigger action name."""
        return self._templates.get(trigger_action)

    def has_template(self, trigger_action: str) -> bool:
        """Check if a template exists for the given action."""
        return trigger_action in self._templates

    def list_templates(self) -> List[CompositeTemplate]:
        """List all registered templates."""
        return list(self._templates.values())

    def expand(
        self,
        trigger_action: str,
        params: Dict[str, Any],
        goal: Optional[str] = None,
    ) -> Optional[ExecutionPlan]:
        """Expand a template into an ExecutionPlan.

        Resolves $variable references in param_bindings using provided params.

        Args:
            trigger_action: The action that triggers this template
            params: Parameters to bind into the template steps
            goal: Optional goal description (defaults to template description)

        Returns:
            ExecutionPlan if template exists, None otherwise
        """
        template = self._templates.get(trigger_action)
        if not template:
            return None

        steps = []
        for tmpl_step in template.steps:
            resolved_params = self._resolve_bindings(tmpl_step.param_bindings, params)
            step = PlanningStep(
                step_id=tmpl_step.step_id,
                action_type=tmpl_step.action_type,
                description=tmpl_step.description,
                params=resolved_params,
                dependencies=list(tmpl_step.dependencies),
            )
            steps.append(step)

        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            goal=goal or template.description,
            steps=steps,
        )

    def _resolve_bindings(
        self,
        bindings: Dict[str, str],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve $variable references in parameter bindings.

        Args:
            bindings: Template bindings like {"room_number": "$new_room_number"}
            params: Actual values like {"new_room_number": "305"}

        Returns:
            Resolved parameters like {"room_number": "305"}
        """
        resolved = {}
        for key, value in bindings.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]  # Strip $
                if var_name in params:
                    resolved[key] = params[var_name]
                else:
                    # Keep as-is if no binding found (handler may provide defaults)
                    logger.warning(f"Unresolved binding: {value} (available: {list(params.keys())})")
                    resolved[key] = None
            else:
                resolved[key] = value
        return resolved

    def clear(self) -> None:
        """Clear all templates (for testing)."""
        self._templates.clear()


__all__ = [
    "TemplateStep",
    "CompositeTemplate",
    "TemplateRegistry",
]
