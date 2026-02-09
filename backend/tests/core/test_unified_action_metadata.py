"""
Tests for SPEC-03: ActionRegistry auto-sync to OntologyRegistry
"""
import pytest
from pydantic import BaseModel, Field
from core.ai.actions import ActionRegistry
from core.ontology.registry import OntologyRegistry


class SampleParams(BaseModel):
    name: str = Field(..., description="Guest name")
    room_id: int = Field(..., description="Room ID")
    notes: str = Field(default="", description="Optional notes")


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def action_registry(clean_registry):
    """ActionRegistry with ontology_registry sync enabled"""
    return ActionRegistry(vector_store=None, ontology_registry=clean_registry)


class TestActionRegistrySyncToOntology:
    """Test automatic sync of ActionDefinition -> ActionMetadata"""

    def test_register_syncs_to_ontology(self, action_registry, clean_registry):
        @action_registry.register(
            name="test_action",
            entity="Guest",
            description="A test action",
            category="mutation",
        )
        def handle(params: SampleParams, **ctx):
            return {"success": True}

        # Check OntologyRegistry has the action
        actions = clean_registry.get_actions("Guest")
        assert len(actions) == 1
        assert actions[0].action_type == "test_action"
        assert actions[0].entity == "Guest"
        assert actions[0].description == "A test action"

    def test_synced_params_match_pydantic_schema(self, action_registry, clean_registry):
        @action_registry.register(
            name="param_test",
            entity="Room",
            description="Test params",
            category="mutation",
        )
        def handle(params: SampleParams, **ctx):
            return {}

        actions = clean_registry.get_actions("Room")
        action_meta = actions[0]
        param_names = [p.name for p in action_meta.params]
        assert "name" in param_names
        assert "room_id" in param_names
        assert "notes" in param_names

        # Check required fields
        name_param = next(p for p in action_meta.params if p.name == "name")
        assert name_param.required is True
        notes_param = next(p for p in action_meta.params if p.name == "notes")
        assert notes_param.required is False

    def test_synced_metadata_preserves_flags(self, action_registry, clean_registry):
        @action_registry.register(
            name="flagged_action",
            entity="Task",
            description="Flagged",
            category="mutation",
            requires_confirmation=True,
            undoable=True,
            side_effects=["creates audit log"],
            allowed_roles={"admin", "manager"},
        )
        def handle(params: SampleParams, **ctx):
            return {}

        actions = clean_registry.get_actions("Task")
        meta = actions[0]
        assert meta.requires_confirmation is True
        assert meta.undoable is True
        assert meta.side_effects == ["creates audit log"]
        assert meta.allowed_roles == {"admin", "manager"}

    def test_no_sync_without_ontology_registry(self):
        """Without ontology_registry, no sync happens (no error)"""
        reg = ActionRegistry(vector_store=None, ontology_registry=None)

        @reg.register(
            name="standalone",
            entity="Guest",
            description="No sync",
            category="query",
        )
        def handle(params: SampleParams, **ctx):
            return {}

        # Just verify it doesn't crash
        assert reg.get_action("standalone") is not None

    def test_multiple_actions_sync(self, action_registry, clean_registry):
        @action_registry.register(
            name="action_a",
            entity="Guest",
            description="Action A",
            category="mutation",
        )
        def handle_a(params: SampleParams, **ctx):
            return {}

        @action_registry.register(
            name="action_b",
            entity="Guest",
            description="Action B",
            category="query",
        )
        def handle_b(params: SampleParams, **ctx):
            return {}

        actions = clean_registry.get_actions("Guest")
        assert len(actions) == 2
        names = {a.action_type for a in actions}
        assert names == {"action_a", "action_b"}

    def test_export_schema_includes_synced_actions(self, action_registry, clean_registry):
        @action_registry.register(
            name="exported_action",
            entity="Room",
            description="Exported",
            category="mutation",
        )
        def handle(params: SampleParams, **ctx):
            return {}

        schema = clean_registry.export_schema()
        assert "Room.exported_action" in schema["actions"]

    def test_dispatch_still_works_with_sync(self, action_registry, clean_registry):
        """Dispatch should work normally even with sync enabled"""

        @action_registry.register(
            name="dispatchable",
            entity="Guest",
            description="Dispatchable",
            category="mutation",
            requires_confirmation=False,
        )
        def handle(params: SampleParams, **ctx):
            return {"success": True, "name": params.name}

        result = action_registry.dispatch(
            "dispatchable",
            {"name": "Test", "room_id": 1},
            {},
        )
        assert result["success"] is True
        assert result["name"] == "Test"
