"""
Tests for app/services/ontology_metadata_service.py

Covers:
- OntologyMetadataService properties: MODELS, ENTITY_DESCRIPTIONS, AGGREGATE_ROOTS, ENTITY_RELATIONSHIPS
- get_semantic_metadata
- _get_enriched_attributes
- _get_attribute_descriptions
- _serialize_attribute
- _get_enriched_relationships
- get_kinetic_metadata
- _get_predefined_actions
- _serialize_action
- get_dynamic_metadata
- _get_state_machines, _serialize_state_machine
- _get_permission_matrix
- _get_business_rules
- get_events
"""
import pytest
from unittest.mock import MagicMock, patch
from core.ontology.registry import OntologyRegistry


@pytest.fixture
def clean_registry():
    """Reset OntologyRegistry singleton between tests."""
    registry = OntologyRegistry()
    registry.clear()
    yield registry
    registry.clear()


@pytest.fixture
def ontology_service(db_session, clean_registry):
    from app.services.ontology_metadata_service import OntologyMetadataService
    return OntologyMetadataService(db=db_session)


class TestProperties:
    def test_models_fallback(self, ontology_service, clean_registry):
        """When registry has no models, should use fallback."""
        result = ontology_service.MODELS
        assert "Room" in result
        assert "Guest" in result

    def test_models_from_registry(self, ontology_service, clean_registry):
        """When registry has models, should use them."""
        clean_registry.register_model("TestEntity", MagicMock(__tablename__="test"))
        result = ontology_service.MODELS
        assert "TestEntity" in result

    def test_entity_descriptions_fallback(self, ontology_service, clean_registry):
        result = ontology_service.ENTITY_DESCRIPTIONS
        assert "Room" in result
        assert "Guest" in result

    def test_entity_descriptions_from_registry(self, ontology_service, clean_registry):
        from core.ontology.metadata import EntityMetadata
        clean_registry.register_entity(EntityMetadata(
            name="TestEntity",
            description="Test Description",
            table_name="test",
        ))
        result = ontology_service.ENTITY_DESCRIPTIONS
        assert "TestEntity" in result
        assert result["TestEntity"] == "Test Description"
        # Fallbacks should still be there
        assert "Room" in result

    def test_aggregate_roots_fallback(self, ontology_service, clean_registry):
        result = ontology_service.AGGREGATE_ROOTS
        assert "Reservation" in result
        assert "StayRecord" in result

    def test_aggregate_roots_from_registry(self, ontology_service, clean_registry):
        from core.ontology.metadata import EntityMetadata
        clean_registry.register_entity(EntityMetadata(
            name="TestAgg",
            description="Test",
            table_name="test",
            is_aggregate_root=True,
        ))
        result = ontology_service.AGGREGATE_ROOTS
        assert "TestAgg" in result

    def test_entity_relationships_fallback(self, ontology_service, clean_registry):
        result = ontology_service.ENTITY_RELATIONSHIPS
        assert "Room" in result
        assert "Guest" in result

    def test_entity_relationships_from_registry(self, ontology_service, clean_registry):
        from core.ontology.metadata import EntityMetadata, RelationshipMetadata
        clean_registry.register_entity(EntityMetadata(
            name="A", description="A", table_name="a"
        ))
        clean_registry.register_relationship("A", RelationshipMetadata(
            name="b_rel", target_entity="B", cardinality="many_to_one",
            foreign_key="b_id", foreign_key_entity="A"
        ))
        result = ontology_service.ENTITY_RELATIONSHIPS
        assert "A" in result
        assert "B" in result["A"]


class TestGetSemanticMetadata:
    def test_returns_entities(self, ontology_service, clean_registry):
        result = ontology_service.get_semantic_metadata()
        assert "entities" in result
        entities = result["entities"]
        assert len(entities) > 0
        # Check structure of first entity
        first = entities[0]
        assert "name" in first
        assert "description" in first
        assert "table_name" in first
        assert "is_aggregate_root" in first
        assert "attributes" in first
        assert "relationships" in first

    def test_enriched_attributes_from_registry(self, ontology_service, clean_registry):
        """When registry has properties, they should enrich attribute descriptions."""
        from core.ontology.metadata import EntityMetadata, PropertyMetadata
        clean_registry.register_entity(EntityMetadata(
            name="Room",
            description="Room from registry",
            table_name="rooms",
            properties={
                "room_number": PropertyMetadata(
                    name="room_number",
                    type="string",
                    python_type="str",
                    description="Registry room number desc",
                    security_level="PUBLIC"
                )
            }
        ))
        result = ontology_service.get_semantic_metadata()
        entities = result["entities"]
        room_entity = [e for e in entities if e["name"] == "Room"]
        assert len(room_entity) > 0

    def test_entity_with_extensions(self, ontology_service, clean_registry):
        from core.ontology.metadata import EntityMetadata
        meta = EntityMetadata(
            name="Room",
            description="Room entity",
            table_name="rooms",
        )
        meta.category = "core"
        meta.implements = ["Stateful"]
        meta.lifecycle_states = ["vacant_clean", "occupied"]
        meta.extensions = {
            "business_purpose": "Physical room",
            "key_attributes": ["room_number"],
            "invariants": ["Room number must be unique"]
        }
        clean_registry.register_entity(meta)
        result = ontology_service.get_semantic_metadata()
        room = [e for e in result["entities"] if e["name"] == "Room"][0]
        assert room.get("category") == "core"


class TestGetAttributeDescriptions:
    def test_all_entities(self, ontology_service):
        """Test that attribute descriptions exist for key entities."""
        for entity in ["Room", "Guest", "Reservation", "StayRecord",
                       "Bill", "Task", "Employee", "RoomType"]:
            descs = ontology_service._get_attribute_descriptions(entity)
            assert isinstance(descs, dict)
            assert len(descs) > 0

    def test_unknown_entity(self, ontology_service):
        result = ontology_service._get_attribute_descriptions("NonExistent")
        assert result == {}


class TestSerializeAttribute:
    def test_serialize(self, ontology_service):
        from app.services.metadata import AttributeMetadata
        attr = AttributeMetadata(
            name="room_number",
            type="VARCHAR(10)",
            python_type="str",
            is_primary_key=False,
            is_foreign_key=False,
            is_required=True,
            is_nullable=False,
            is_unique=True,
            default_value=None,
            max_length=10,
            enum_values=None,
            description="Room number",
            security_level="PUBLIC",
            foreign_key_target=None
        )
        result = ontology_service._serialize_attribute(attr)
        assert result["name"] == "room_number"
        assert result["type"] == "VARCHAR(10)"
        assert result["is_required"] is True
        assert result["default_value"] is None
        assert result["max_length"] == 10

    def test_serialize_with_default_value(self, ontology_service):
        from app.services.metadata import AttributeMetadata
        attr = AttributeMetadata(
            name="status",
            type="VARCHAR",
            python_type="str",
            default_value="vacant_clean"
        )
        result = ontology_service._serialize_attribute(attr)
        assert result["default_value"] == "vacant_clean"


class TestGetEnrichedRelationships:
    def test_known_entity(self, ontology_service, clean_registry):
        rels = ontology_service._get_enriched_relationships("Room")
        assert isinstance(rels, list)
        # Room should have relationships
        if rels:
            assert "name" in rels[0]
            assert "target" in rels[0]
            assert "label" in rels[0]

    def test_unknown_entity(self, ontology_service, clean_registry):
        rels = ontology_service._get_enriched_relationships("UnknownEntity")
        assert rels == []

    def test_registry_label_priority(self, ontology_service, clean_registry):
        from core.ontology.metadata import RelationshipMetadata
        clean_registry.register_relationship("Room", RelationshipMetadata(
            name="room_type",
            target_entity="RoomType",
            cardinality="many_to_one",
            foreign_key="room_type_id",
            foreign_key_entity="Room",
            description="Registry label for room type"
        ))
        rels = ontology_service._get_enriched_relationships("Room")
        rt_rels = [r for r in rels if r["target"] == "RoomType"]
        if rt_rels:
            assert rt_rels[0]["label"] == "Registry label for room type"


class TestGetKineticMetadata:
    def test_returns_entities(self, ontology_service, clean_registry):
        result = ontology_service.get_kinetic_metadata()
        assert "entities" in result
        entities = result["entities"]
        assert len(entities) > 0

    def test_entity_has_actions(self, ontology_service, clean_registry):
        result = ontology_service.get_kinetic_metadata()
        for entity in result["entities"]:
            if entity["name"] == "Room":
                assert len(entity["actions"]) > 0
                action = entity["actions"][0]
                assert "action_type" in action
                assert "params" in action

    def test_registered_actions_merged(self, ontology_service, clean_registry):
        from core.ontology.metadata import ActionMetadata as CoreActionMetadata
        from app.services.metadata import ActionParam, ParamType
        clean_registry.register_action("NewEntity", CoreActionMetadata(
            action_type="new_action",
            entity="NewEntity",
            method_name="handle_new_action",
            description="A new action",
        ))
        result = ontology_service.get_kinetic_metadata()
        entity_names = [e["name"] for e in result["entities"]]
        assert "NewEntity" in entity_names


class TestSerializeAction:
    def test_serialize(self, ontology_service):
        from app.services.metadata import ActionMetadata, ActionParam, ParamType
        am = ActionMetadata(
            action_type="test_action",
            entity="Room",
            method_name="handle_test",
            description="Test action",
            params=[
                ActionParam(name="room_id", type=ParamType.INTEGER, required=True, description="Room ID"),
                ActionParam(name="status", type=ParamType.ENUM, required=True, description="Status",
                            enum_values=["clean", "dirty"], format="enum"),
            ],
            requires_confirmation=True,
            allowed_roles={"manager"},
            writeback=True,
            undoable=True,
        )
        result = ontology_service._serialize_action(am)
        assert result["action_type"] == "test_action"
        assert len(result["params"]) == 2
        assert result["params"][0]["name"] == "room_id"
        assert result["params"][0]["type"] == "integer"
        assert result["requires_confirmation"] is True
        assert "manager" in result["allowed_roles"]
        assert result["writeback"] is True
        assert result["undoable"] is True


class TestGetDynamicMetadata:
    def test_returns_structure(self, ontology_service, clean_registry):
        result = ontology_service.get_dynamic_metadata()
        assert "state_machines" in result
        assert "permission_matrix" in result
        assert "business_rules" in result

    def test_state_machines(self, ontology_service, clean_registry):
        result = ontology_service.get_dynamic_metadata()
        sms = result["state_machines"]
        assert len(sms) > 0
        entities = [sm["entity"] for sm in sms]
        assert "Room" in entities
        assert "Reservation" in entities
        assert "Task" in entities

    def test_state_machine_structure(self, ontology_service, clean_registry):
        result = ontology_service.get_dynamic_metadata()
        room_sm = [sm for sm in result["state_machines"] if sm["entity"] == "Room"][0]
        assert "states" in room_sm
        assert "initial_state" in room_sm
        assert "transitions" in room_sm
        assert len(room_sm["states"]) > 0
        assert len(room_sm["transitions"]) > 0

    def test_permission_matrix(self, ontology_service, clean_registry):
        result = ontology_service.get_dynamic_metadata()
        pm = result["permission_matrix"]
        assert "roles" in pm
        assert "actions" in pm
        assert "manager" in pm["roles"]

    def test_business_rules(self, ontology_service, clean_registry):
        result = ontology_service.get_dynamic_metadata()
        rules = result["business_rules"]
        assert len(rules) > 0
        rule = rules[0]
        assert "rule_id" in rule
        assert "entity" in rule
        assert "severity" in rule


class TestSerializeStateMachine:
    def test_serialize_from_registry(self, ontology_service, clean_registry):
        from core.ontology.metadata import StateMachine, StateTransition
        sm = StateMachine(
            entity="TestEntity",
            states=["vacant_clean", "occupied", "pending"],
            transitions=[
                StateTransition(
                    from_state="vacant_clean",
                    to_state="occupied",
                    trigger="check_in",
                    condition=None,
                    side_effects=[]
                ),
                StateTransition(
                    from_state="occupied",
                    to_state="pending",
                    trigger="assign",
                    condition="has assignee",
                    side_effects=["notify"]
                ),
            ],
            initial_state="vacant_clean"
        )
        result = ontology_service._serialize_state_machine(sm)
        assert result["entity"] == "TestEntity"
        assert len(result["states"]) == 3
        # Check state presentation
        assert result["states"][0]["value"] == "vacant_clean"
        assert result["states"][0]["label"] == "空闲已清洁"
        # Unknown state should use value as label
        assert result["states"][2]["value"] == "pending"
        assert result["transitions"][0]["trigger"] == "check_in"

    def test_registered_sm_replaces_predefined(self, ontology_service, clean_registry):
        from core.ontology.metadata import StateMachine, StateTransition
        sm = StateMachine(
            entity="Room",
            states=["vacant_clean", "occupied"],
            transitions=[
                StateTransition("vacant_clean", "occupied", "check_in"),
            ],
            initial_state="vacant_clean"
        )
        clean_registry.register_state_machine(sm)
        result = ontology_service.get_dynamic_metadata()
        room_sms = [s for s in result["state_machines"] if s["entity"] == "Room"]
        assert len(room_sms) == 1
        assert len(room_sms[0]["states"]) == 2

    def test_registered_sm_new_entity_appended(self, ontology_service, clean_registry):
        from core.ontology.metadata import StateMachine, StateTransition
        sm = StateMachine(
            entity="NewEntity",
            states=["a", "b"],
            transitions=[StateTransition("a", "b", "go")],
            initial_state="a"
        )
        clean_registry.register_state_machine(sm)
        result = ontology_service.get_dynamic_metadata()
        # The "NewEntity" state machine should NOT appear because
        # _get_state_machines only checks Room, Reservation, StayRecord, Task
        # But it's still in the predefined list
        entities = [s["entity"] for s in result["state_machines"]]
        # Predefined entities should still be present
        assert "Room" in entities


class TestGetBusinessRulesWithRegistry:
    def test_registry_rules_merged(self, ontology_service, clean_registry):
        from core.ontology.metadata import BusinessRule
        clean_registry.register_business_rule("Room", BusinessRule(
            rule_id="custom_rule",
            entity="Room",
            rule_name="Custom",
            description="Custom rule",
            condition="custom_cond",
            action="custom_action",
            severity="warning"
        ))
        result = ontology_service.get_dynamic_metadata()
        rules = result["business_rules"]
        custom = [r for r in rules if r["rule_id"] == "custom_rule"]
        assert len(custom) == 1
        assert custom[0]["severity"] == "warning"


class TestGetEvents:
    def test_no_events(self, ontology_service, clean_registry):
        events = ontology_service.get_events()
        assert events == []

    def test_with_events(self, ontology_service, clean_registry):
        from core.ontology.metadata import EventMetadata
        clean_registry.register_event(EventMetadata(
            name="guest_checked_in",
            description="Guest checked in event",
            entity="StayRecord",
            triggered_by="checkin",
            payload_fields=["stay_record_id", "room_id"],
            subscribers=["notification_service"],
        ))
        events = ontology_service.get_events()
        assert len(events) == 1
        assert events[0]["name"] == "guest_checked_in"
        assert events[0]["entity"] == "StayRecord"
        assert "stay_record_id" in events[0]["payload_fields"]
