"""
tests/core/test_plan_templates.py

SPEC-4: Tests for CompositeTemplate and TemplateRegistry.
"""
import pytest
from core.reasoning.plan_templates import (
    TemplateStep, CompositeTemplate, TemplateRegistry
)
from core.reasoning.planner import ExecutionPlan, PlanningStep


@pytest.fixture
def registry():
    """Create a TemplateRegistry with a sample template."""
    reg = TemplateRegistry()
    template = CompositeTemplate(
        name="change_room",
        trigger_action="change_room",
        description="Move guest to a different room",
        required_params=["stay_record_id", "new_room_number"],
        steps=[
            TemplateStep(
                step_id="verify",
                action_type="check_room_available",
                description="Verify target room is available",
                param_bindings={"room_number": "$new_room_number"},
            ),
            TemplateStep(
                step_id="checkout",
                action_type="checkout",
                description="Check out from current room",
                param_bindings={"stay_record_id": "$stay_record_id"},
                dependencies=["verify"],
            ),
            TemplateStep(
                step_id="checkin",
                action_type="walkin_checkin",
                description="Check in to new room",
                param_bindings={
                    "room_number": "$new_room_number",
                    "guest_name": "$guest_name",
                    "guest_phone": "$guest_phone",
                },
                dependencies=["checkout"],
            ),
        ],
    )
    reg.register(template)
    return reg


class TestTemplateStep:
    """Test TemplateStep data class."""

    def test_basic_step(self):
        step = TemplateStep(
            step_id="s1",
            action_type="checkout",
            description="Check out guest",
            param_bindings={"stay_record_id": "$stay_id"},
        )
        assert step.step_id == "s1"
        assert step.action_type == "checkout"
        assert step.param_bindings == {"stay_record_id": "$stay_id"}
        assert step.dependencies == []

    def test_step_with_dependencies(self):
        step = TemplateStep(
            step_id="s2",
            action_type="checkin",
            description="Check in",
            dependencies=["s1"],
        )
        assert step.dependencies == ["s1"]


class TestCompositeTemplate:
    """Test CompositeTemplate data class."""

    def test_basic_template(self):
        template = CompositeTemplate(
            name="test",
            trigger_action="test_action",
            description="Test template",
            steps=[
                TemplateStep(step_id="s1", action_type="a1", description="Step 1"),
            ],
        )
        assert template.name == "test"
        assert template.trigger_action == "test_action"
        assert len(template.steps) == 1


class TestTemplateRegistry:
    """Test TemplateRegistry registration and matching."""

    def test_register_and_get(self, registry):
        template = registry.get_template("change_room")
        assert template is not None
        assert template.name == "change_room"
        assert len(template.steps) == 3

    def test_has_template(self, registry):
        assert registry.has_template("change_room")
        assert not registry.has_template("nonexistent")

    def test_get_nonexistent(self, registry):
        assert registry.get_template("nonexistent") is None

    def test_list_templates(self, registry):
        templates = registry.list_templates()
        assert len(templates) == 1
        assert templates[0].name == "change_room"

    def test_clear(self, registry):
        registry.clear()
        assert not registry.has_template("change_room")
        assert len(registry.list_templates()) == 0


class TestTemplateExpansion:
    """Test template expansion into ExecutionPlan."""

    def test_expand_resolves_params(self, registry):
        plan = registry.expand("change_room", {
            "stay_record_id": 42,
            "new_room_number": "305",
            "guest_name": "张三",
            "guest_phone": "13800000000",
        })
        assert plan is not None
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 3

        # Verify step params were resolved
        verify_step = plan.steps[0]
        assert verify_step.action_type == "check_room_available"
        assert verify_step.params == {"room_number": "305"}

        checkout_step = plan.steps[1]
        assert checkout_step.action_type == "checkout"
        assert checkout_step.params == {"stay_record_id": 42}

        checkin_step = plan.steps[2]
        assert checkin_step.action_type == "walkin_checkin"
        assert checkin_step.params["room_number"] == "305"
        assert checkin_step.params["guest_name"] == "张三"

    def test_expand_preserves_dependencies(self, registry):
        plan = registry.expand("change_room", {
            "stay_record_id": 1,
            "new_room_number": "201",
            "guest_name": "Test",
            "guest_phone": "123",
        })
        assert plan.steps[0].dependencies == []
        assert plan.steps[1].dependencies == ["verify"]
        assert plan.steps[2].dependencies == ["checkout"]

    def test_expand_nonexistent_returns_none(self, registry):
        plan = registry.expand("nonexistent", {})
        assert plan is None

    def test_expand_with_custom_goal(self, registry):
        plan = registry.expand(
            "change_room",
            {"stay_record_id": 1, "new_room_number": "305",
             "guest_name": "T", "guest_phone": "1"},
            goal="Move guest from 301 to 305",
        )
        assert plan.goal == "Move guest from 301 to 305"

    def test_expand_default_goal(self, registry):
        plan = registry.expand("change_room", {
            "stay_record_id": 1, "new_room_number": "305",
            "guest_name": "T", "guest_phone": "1",
        })
        assert plan.goal == "Move guest to a different room"

    def test_expand_unresolved_binding_sets_none(self, registry):
        """Missing params produce None values (not crash)."""
        plan = registry.expand("change_room", {
            "stay_record_id": 1,
            "new_room_number": "305",
            # guest_name and guest_phone missing
        })
        assert plan is not None
        checkin_step = plan.steps[2]
        assert checkin_step.params["guest_name"] is None
        assert checkin_step.params["guest_phone"] is None

    def test_expand_literal_values_preserved(self):
        """Non-$ values in bindings are passed through as-is."""
        reg = TemplateRegistry()
        reg.register(CompositeTemplate(
            name="test",
            trigger_action="test_action",
            description="Test",
            steps=[
                TemplateStep(
                    step_id="s1",
                    action_type="do_thing",
                    description="Do",
                    param_bindings={"mode": "auto", "count": "$count"},
                ),
            ],
        ))
        plan = reg.expand("test_action", {"count": 5})
        assert plan.steps[0].params == {"mode": "auto", "count": 5}


class TestMultipleTemplates:
    """Test registry with multiple templates."""

    def test_register_multiple(self):
        reg = TemplateRegistry()
        reg.register(CompositeTemplate(
            name="t1", trigger_action="action_a",
            description="Template A", steps=[],
        ))
        reg.register(CompositeTemplate(
            name="t2", trigger_action="action_b",
            description="Template B", steps=[],
        ))
        assert len(reg.list_templates()) == 2
        assert reg.has_template("action_a")
        assert reg.has_template("action_b")

    def test_overwrite_template(self):
        reg = TemplateRegistry()
        reg.register(CompositeTemplate(
            name="v1", trigger_action="action_a",
            description="Version 1", steps=[],
        ))
        reg.register(CompositeTemplate(
            name="v2", trigger_action="action_a",
            description="Version 2", steps=[],
        ))
        # Latest registration wins
        assert reg.get_template("action_a").name == "v2"
        assert len(reg.list_templates()) == 1
