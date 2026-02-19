"""
Tests for app/services/metadata.py

Covers:
- ParamType enum
- ActionParam, BusinessRule, StateTransition, StateMachine, ActionMetadata,
  EntityMetadata, AttributeMetadata dataclasses
- MetadataRegistry singleton (register/get for entities, actions, state machines,
  business rules, permissions)
- ontology_entity, ontology_action, business_rule, state_machine, require_role_metadata decorators
- get_model_attributes, get_entity_relationships helper functions
"""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict


class TestParamType:
    def test_values(self):
        from app.services.metadata import ParamType
        assert ParamType.STRING == "string"
        assert ParamType.INTEGER == "integer"
        assert ParamType.NUMBER == "number"
        assert ParamType.BOOLEAN == "boolean"
        assert ParamType.DATE == "date"
        assert ParamType.DATETIME == "datetime"
        assert ParamType.ENUM == "enum"
        assert ParamType.ARRAY == "array"
        assert ParamType.OBJECT == "object"


class TestDataclasses:
    def test_action_param(self):
        from app.services.metadata import ActionParam, ParamType
        p = ActionParam(name="room_id", type=ParamType.INTEGER, required=True, description="Room ID")
        assert p.name == "room_id"
        assert p.type == ParamType.INTEGER
        assert p.required is True
        assert p.default_value is None
        assert p.enum_values is None
        assert p.format is None

    def test_business_rule(self):
        from app.services.metadata import BusinessRule
        rule = BusinessRule(
            rule_id="test_rule",
            entity="Room",
            rule_name="Test Rule",
            description="Test description",
            condition="status == 'occupied'",
            action="raise ValueError",
            severity="error"
        )
        assert rule.rule_id == "test_rule"
        assert rule.severity == "error"

    def test_business_rule_default_severity(self):
        from app.services.metadata import BusinessRule
        rule = BusinessRule(
            rule_id="r1", entity="Room", rule_name="R", description="D",
            condition="c", action="a"
        )
        assert rule.severity == "error"

    def test_state_transition(self):
        from app.services.metadata import StateTransition
        t = StateTransition(
            from_state="vacant_clean", to_state="occupied",
            trigger="check_in", condition=None, side_effects=[]
        )
        assert t.from_state == "vacant_clean"
        assert t.to_state == "occupied"
        assert t.side_effects == []

    def test_state_transition_defaults(self):
        from app.services.metadata import StateTransition
        t = StateTransition(from_state="a", to_state="b", trigger="t")
        assert t.condition is None
        assert t.side_effects == []

    def test_state_machine(self):
        from app.services.metadata import StateMachine, StateTransition
        sm = StateMachine(
            entity="Room",
            states=["vacant_clean", "occupied"],
            transitions=[StateTransition("vacant_clean", "occupied", "check_in")],
            initial_state="vacant_clean"
        )
        assert sm.entity == "Room"
        assert len(sm.transitions) == 1

    def test_action_metadata(self):
        from app.services.metadata import ActionMetadata
        am = ActionMetadata(
            action_type="checkin",
            entity="StayRecord",
            method_name="handle_checkin",
            description="Check in guest"
        )
        assert am.action_type == "checkin"
        assert am.requires_confirmation is False
        assert am.writeback is True
        assert am.undoable is False

    def test_entity_metadata(self):
        from app.services.metadata import EntityMetadata
        em = EntityMetadata(
            name="Room",
            description="Hotel room",
            table_name="rooms",
            is_aggregate_root=False
        )
        assert em.name == "Room"
        assert em.related_entities == []
        assert em.business_rules == []
        assert em.state_machine is None

    def test_attribute_metadata(self):
        from app.services.metadata import AttributeMetadata
        am = AttributeMetadata(
            name="room_number",
            type="VARCHAR(10)",
            python_type="str",
            is_primary_key=False,
            is_required=True,
            description="Room number"
        )
        assert am.name == "room_number"
        assert am.security_level == "INTERNAL"
        assert am.foreign_key_target is None

    def test_attribute_metadata_defaults(self):
        from app.services.metadata import AttributeMetadata
        am = AttributeMetadata(name="id", type="INTEGER", python_type="int")
        assert am.is_primary_key is False
        assert am.is_foreign_key is False
        assert am.is_unique is False
        assert am.is_nullable is True
        assert am.max_length is None
        assert am.enum_values is None


class TestMetadataRegistry:
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        from app.services.metadata import MetadataRegistry
        reg = MetadataRegistry()
        reg._entities.clear()
        reg._actions.clear()
        reg._state_machines.clear()
        reg._business_rules.clear()
        reg._permission_matrix.clear()
        yield reg
        reg._entities.clear()
        reg._actions.clear()
        reg._state_machines.clear()
        reg._business_rules.clear()
        reg._permission_matrix.clear()

    def test_singleton(self):
        from app.services.metadata import MetadataRegistry
        r1 = MetadataRegistry()
        r2 = MetadataRegistry()
        assert r1 is r2

    def test_register_and_get_entity(self, reset_registry):
        from app.services.metadata import MetadataRegistry, EntityMetadata
        reg = reset_registry
        em = EntityMetadata(name="Room", description="Room", table_name="rooms")
        reg.register_entity(em)
        assert reg.get_entity("Room") is em
        assert reg.get_entity("NonExistent") is None
        entities = reg.get_entities()
        assert len(entities) == 1

    def test_register_and_get_action(self, reset_registry):
        from app.services.metadata import MetadataRegistry, ActionMetadata
        reg = reset_registry
        am = ActionMetadata(
            action_type="checkin", entity="StayRecord",
            method_name="handle_checkin", description="Check in"
        )
        reg.register_action("StayRecord", am)
        actions = reg.get_actions("StayRecord")
        assert len(actions) == 1
        assert actions[0].action_type == "checkin"

    def test_get_actions_no_entity(self, reset_registry):
        from app.services.metadata import MetadataRegistry, ActionMetadata
        reg = reset_registry
        am1 = ActionMetadata("a1", "E1", "m1", "d1")
        am2 = ActionMetadata("a2", "E2", "m2", "d2")
        reg.register_action("E1", am1)
        reg.register_action("E2", am2)
        all_actions = reg.get_actions()
        assert len(all_actions) == 2

    def test_get_actions_empty(self, reset_registry):
        reg = reset_registry
        assert reg.get_actions("NonExistent") == []

    def test_register_and_get_state_machine(self, reset_registry):
        from app.services.metadata import MetadataRegistry, StateMachine, StateTransition
        reg = reset_registry
        sm = StateMachine(
            entity="Room",
            states=["vacant_clean", "occupied"],
            transitions=[StateTransition("vacant_clean", "occupied", "check_in")],
            initial_state="vacant_clean"
        )
        reg.register_state_machine(sm)
        assert reg.get_state_machine("Room") is sm
        assert reg.get_state_machine("NonExistent") is None

    def test_register_and_get_business_rules(self, reset_registry):
        from app.services.metadata import MetadataRegistry, BusinessRule
        reg = reset_registry
        rule = BusinessRule("r1", "Room", "Rule 1", "Desc", "cond", "action")
        reg.register_business_rule("Room", rule)
        rules = reg.get_business_rules("Room")
        assert len(rules) == 1
        assert rules[0].rule_id == "r1"

    def test_get_business_rules_all(self, reset_registry):
        from app.services.metadata import MetadataRegistry, BusinessRule
        reg = reset_registry
        r1 = BusinessRule("r1", "Room", "R1", "D1", "c1", "a1")
        r2 = BusinessRule("r2", "Guest", "R2", "D2", "c2", "a2")
        reg.register_business_rule("Room", r1)
        reg.register_business_rule("Guest", r2)
        all_rules = reg.get_business_rules()
        assert len(all_rules) == 2

    def test_get_business_rules_empty(self, reset_registry):
        reg = reset_registry
        assert reg.get_business_rules("NonExistent") == []

    def test_register_and_get_permission(self, reset_registry):
        from app.services.metadata import MetadataRegistry
        reg = reset_registry
        reg.register_permission("checkin", {"manager", "receptionist"})
        perms = reg.get_permissions()
        assert "checkin" in perms
        assert "manager" in perms["checkin"]

    def test_register_permission_adds_to_existing(self, reset_registry):
        from app.services.metadata import MetadataRegistry
        reg = reset_registry
        reg.register_permission("checkin", {"manager"})
        reg.register_permission("checkin", {"receptionist"})
        perms = reg.get_permissions()
        assert "manager" in perms["checkin"]
        assert "receptionist" in perms["checkin"]


class TestDecorators:
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        from app.services.metadata import MetadataRegistry
        reg = MetadataRegistry()
        reg._entities.clear()
        reg._actions.clear()
        reg._state_machines.clear()
        reg._business_rules.clear()
        reg._permission_matrix.clear()
        yield
        reg._entities.clear()
        reg._actions.clear()
        reg._state_machines.clear()
        reg._business_rules.clear()
        reg._permission_matrix.clear()

    def test_ontology_entity_decorator(self):
        from app.services.metadata import ontology_entity, registry

        @ontology_entity(
            name="TestEntity",
            description="Test entity",
            table_name="test_entities",
            is_aggregate_root=True,
            related_entities=["Other"]
        )
        class TestEntity:
            __tablename__ = "test_entities"

        entity = registry.get_entity("TestEntity")
        assert entity is not None
        assert entity.name == "TestEntity"
        assert entity.is_aggregate_root is True
        assert hasattr(TestEntity, '_ontology_metadata')

    def test_ontology_entity_decorator_defaults(self):
        from app.services.metadata import ontology_entity, registry

        @ontology_entity(
            name="TestEntity2",
            description="Test entity 2",
        )
        class TestEntity2:
            __tablename__ = "test_entities_2"

        entity = registry.get_entity("TestEntity2")
        assert entity.table_name == "test_entities_2"
        assert entity.is_aggregate_root is False

    def test_ontology_action_decorator(self):
        from app.services.metadata import ontology_action, registry

        @ontology_action(
            entity="Room",
            action_type="update_status",
            description="Update room status",
            params=[
                {"name": "room_id", "type": "integer", "required": True, "description": "Room ID"},
                {"name": "status", "type": "enum", "enum_values": ["clean", "dirty"], "required": True},
            ],
            requires_confirmation=True,
            allowed_roles=["manager"],
            writeback=True,
            undoable=True,
        )
        def update_room_status(room_id, status):
            return True

        actions = registry.get_actions("Room")
        assert len(actions) >= 1
        action = [a for a in actions if a.action_type == "update_status"][0]
        assert action.requires_confirmation is True
        assert action.undoable is True
        assert hasattr(update_room_status, '_ontology_action')

        # Permission registered
        perms = registry.get_permissions()
        assert "manager" in perms.get("update_status", set())

    def test_ontology_action_all_param_types(self):
        from app.services.metadata import ontology_action, registry, ParamType

        @ontology_action(
            entity="Test",
            action_type="test_all_types",
            description="Test all param types",
            params=[
                {"name": "p_int", "type": "int"},
                {"name": "p_number", "type": "number"},
                {"name": "p_float", "type": "float"},
                {"name": "p_decimal", "type": "decimal"},
                {"name": "p_bool", "type": "boolean"},
                {"name": "p_date", "type": "date"},
                {"name": "p_datetime", "type": "datetime"},
                {"name": "p_enum", "type": "enum"},
                {"name": "p_list", "type": "list"},
                {"name": "p_array", "type": "array"},
                {"name": "p_dict", "type": "dict"},
                {"name": "p_object", "type": "object"},
                {"name": "p_string", "type": "string"},
                {"name": "p_unknown", "type": "custom_type"},
            ]
        )
        def test_func():
            pass

        actions = registry.get_actions("Test")
        action = [a for a in actions if a.action_type == "test_all_types"][0]
        param_types = {p.name: p.type for p in action.params}
        assert param_types["p_int"] == ParamType.INTEGER
        assert param_types["p_number"] == ParamType.NUMBER
        assert param_types["p_float"] == ParamType.NUMBER
        assert param_types["p_decimal"] == ParamType.NUMBER
        assert param_types["p_bool"] == ParamType.BOOLEAN
        assert param_types["p_date"] == ParamType.DATE
        assert param_types["p_datetime"] == ParamType.DATETIME
        assert param_types["p_enum"] == ParamType.ENUM
        assert param_types["p_list"] == ParamType.ARRAY
        assert param_types["p_array"] == ParamType.ARRAY
        assert param_types["p_dict"] == ParamType.OBJECT
        assert param_types["p_object"] == ParamType.OBJECT
        assert param_types["p_string"] == ParamType.STRING
        assert param_types["p_unknown"] == ParamType.STRING  # default

    def test_ontology_action_no_params(self):
        from app.services.metadata import ontology_action, registry

        @ontology_action(
            entity="Room",
            action_type="simple_action",
            description="Simple",
        )
        def simple():
            return True

        result = simple()
        assert result is True

    def test_business_rule_decorator(self):
        from app.services.metadata import business_rule, registry

        @business_rule(
            entity="Room",
            rule_id="test_rule",
            rule_name="Test Rule",
            description="Test",
            condition="status == 'occupied'",
            action="raise ValueError",
            severity="error"
        )
        def check_rule():
            return True

        rules = registry.get_business_rules("Room")
        assert any(r.rule_id == "test_rule" for r in rules)
        assert hasattr(check_rule, '_business_rule')
        assert check_rule() is True

    def test_state_machine_decorator(self):
        from app.services.metadata import state_machine, registry

        @state_machine(
            entity="TestEntity",
            states=["a", "b", "c"],
            transitions=[
                {"from": "a", "to": "b", "trigger": "go", "condition": "ready"},
                {"from": "b", "to": "c", "trigger": "finish", "side_effects": ["notify"]},
            ],
            initial_state="a"
        )
        class TestStateful:
            pass

        sm = registry.get_state_machine("TestEntity")
        assert sm is not None
        assert sm.initial_state == "a"
        assert len(sm.transitions) == 2
        assert sm.transitions[0].condition == "ready"
        assert sm.transitions[1].side_effects == ["notify"]
        assert hasattr(TestStateful, '_state_machine')

    def test_require_role_metadata(self):
        from app.services.metadata import require_role_metadata

        @require_role_metadata(["manager", "admin"])
        def restricted_func():
            return 42

        assert restricted_func._required_roles == {"manager", "admin"}
        assert restricted_func() == 42


class TestGetModelAttributes:
    def test_with_real_model(self, db_session):
        from app.services.metadata import get_model_attributes
        from app.hotel.models.ontology import Room

        attrs = get_model_attributes(Room)
        assert len(attrs) > 0
        names = [a.name for a in attrs]
        assert "room_number" in names
        assert "floor" in names
        assert "status" in names

    def test_primary_key_detected(self, db_session):
        from app.services.metadata import get_model_attributes
        from app.hotel.models.ontology import Room

        attrs = get_model_attributes(Room)
        id_attr = [a for a in attrs if a.name == "id"][0]
        assert id_attr.is_primary_key is True

    def test_foreign_key_detected(self, db_session):
        from app.services.metadata import get_model_attributes
        from app.hotel.models.ontology import Room

        attrs = get_model_attributes(Room)
        fk_attr = [a for a in attrs if a.name == "room_type_id"][0]
        assert fk_attr.is_foreign_key is True
        assert fk_attr.foreign_key_target is not None

    def test_enum_values(self, db_session):
        from app.services.metadata import get_model_attributes
        from app.hotel.models.ontology import Room

        attrs = get_model_attributes(Room)
        status_attr = [a for a in attrs if a.name == "status"][0]
        assert status_attr.enum_values is not None
        assert len(status_attr.enum_values) > 0

    def test_no_table_attribute(self):
        from app.services.metadata import get_model_attributes
        class NoTable:
            pass
        assert get_model_attributes(NoTable) == []


class TestGetEntityRelationships:
    def test_with_real_model(self, db_session):
        from app.services.metadata import get_entity_relationships
        from app.hotel.models.ontology import Room

        rels = get_entity_relationships(Room)
        assert len(rels) > 0
        targets = [r["target"] for r in rels]
        assert "RoomType" in targets

    def test_relationship_type(self, db_session):
        from app.services.metadata import get_entity_relationships
        from app.hotel.models.ontology import Room

        rels = get_entity_relationships(Room)
        for rel in rels:
            assert rel["type"] in ("one_to_many", "many_to_one")

    def test_no_table_attribute(self):
        from app.services.metadata import get_entity_relationships
        class NoTable:
            pass
        assert get_entity_relationships(NoTable) == []
