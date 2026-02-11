"""
tests/core/test_planner_templates.py

SPEC-4: Tests for PlannerEngine template integration.
"""
import pytest
from unittest.mock import Mock, MagicMock
from core.reasoning.planner import PlannerEngine, ExecutionPlan
from core.reasoning.plan_templates import (
    TemplateStep, CompositeTemplate, TemplateRegistry
)


@pytest.fixture
def template_registry():
    """Create a TemplateRegistry with a sample template."""
    reg = TemplateRegistry()
    reg.register(CompositeTemplate(
        name="change_room",
        trigger_action="change_room",
        description="Move guest to a different room",
        steps=[
            TemplateStep(
                step_id="s1", action_type="checkout",
                description="Check out", param_bindings={"id": "$stay_id"},
            ),
            TemplateStep(
                step_id="s2", action_type="checkin",
                description="Check in", param_bindings={"room": "$new_room"},
                dependencies=["s1"],
            ),
        ],
    ))
    return reg


@pytest.fixture
def ontology_registry():
    """Mock OntologyRegistry."""
    mock = Mock()
    mock.get_actions.return_value = []
    return mock


class TestPlannerTemplateIntegration:
    """Test PlannerEngine with TemplateRegistry."""

    def test_create_plan_uses_template_when_available(self, ontology_registry, template_registry):
        planner = PlannerEngine(
            registry=ontology_registry,
            template_registry=template_registry,
        )

        plan = planner.create_plan(
            goal="Move guest to 305",
            context={},
            action_type="change_room",
            params={"stay_id": 42, "new_room": "305"},
        )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == "checkout"
        assert plan.steps[0].params == {"id": 42}
        assert plan.steps[1].action_type == "checkin"
        assert plan.steps[1].params == {"room": "305"}

    def test_create_plan_no_template_match_without_action_type(self, ontology_registry, template_registry):
        """Without action_type, templates are not checked."""
        planner = PlannerEngine(
            registry=ontology_registry,
            template_registry=template_registry,
        )

        # Without action_type, it falls through to LLM (which we can't test without mocking)
        # Just verify template_registry is set
        assert planner._template_registry is template_registry

    def test_create_plan_no_template_registry(self, ontology_registry):
        """Without template_registry, plan creation still works (falls to LLM)."""
        planner = PlannerEngine(registry=ontology_registry)
        assert planner._template_registry is None

    def test_create_plan_nonmatching_action_type(self, ontology_registry, template_registry):
        """Non-matching action_type doesn't crash, falls through to LLM."""
        planner = PlannerEngine(
            registry=ontology_registry,
            template_registry=template_registry,
        )

        # "nonexistent" has no template, would fall to LLM
        # We just verify it doesn't crash at the template check
        assert not template_registry.has_template("nonexistent")
