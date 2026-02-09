"""
SPEC-R01: Integration tests for HotelDomainAdapter bootstrap at startup.
Verifies that OntologyRegistry is populated with entities, relationships,
state machines, actions, constraints, and events after adapter registration.
"""
import pytest
from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter


@pytest.fixture
def populated_registry():
    """Create a fresh registry populated by HotelDomainAdapter + ActionRegistry sync."""
    registry = OntologyRegistry()
    registry.clear()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(registry)
    # SPEC-R11: Actions now come from ActionRegistry sync instead of adapter
    from app.services.actions import get_action_registry, reset_action_registry
    reset_action_registry()
    action_registry = get_action_registry()
    action_registry.set_ontology_registry(registry)
    yield registry
    registry.clear()
    reset_action_registry()


class TestAdapterBootstrap:
    """Verify HotelDomainAdapter populates OntologyRegistry correctly."""

    def test_entities_registered(self, populated_registry):
        """Registry should have all core domain entities."""
        entities = populated_registry.get_entities()
        entity_names = {e.name for e in entities}
        expected = {"Room", "Guest", "Reservation", "StayRecord", "Task", "Bill"}
        assert expected.issubset(entity_names), f"Missing entities: {expected - entity_names}"
        assert len(entities) >= 8

    def test_relationships_registered(self, populated_registry):
        """Registry should have relationships between entities."""
        rel_map = populated_registry.get_relationship_map()
        assert len(rel_map) > 0, "No relationships registered"
        # Guest should have relationships
        guest_rels = rel_map.get("Guest", [])
        assert len(guest_rels) > 0, "Guest has no relationships"

    def test_state_machines_registered(self, populated_registry):
        """Registry should have state machines for key entities."""
        # Room state machine
        room_sm = populated_registry.get_state_machine("Room")
        assert room_sm is not None, "Room state machine not registered"
        # Reservation state machine
        res_sm = populated_registry.get_state_machine("Reservation")
        assert res_sm is not None, "Reservation state machine not registered"

    def test_actions_registered(self, populated_registry):
        """Registry should have actions for entities."""
        all_actions = []
        for entity in populated_registry.get_entities():
            actions = populated_registry.get_actions(entity.name)
            all_actions.extend(actions)
        assert len(all_actions) > 0, "No actions registered"

    def test_constraints_registered(self, populated_registry):
        """Registry should have business constraints."""
        constraints = populated_registry.get_constraints()
        assert len(constraints) > 0, "No constraints registered"

    def test_events_registered(self, populated_registry):
        """Registry should have domain events."""
        events = populated_registry.get_events()
        assert len(events) > 0, "No events registered"

    def test_room_entity_has_properties(self, populated_registry):
        """Room entity should have property metadata."""
        entities = populated_registry.get_entities()
        room = next((e for e in entities if e.name == "Room"), None)
        assert room is not None
        assert len(room.properties) > 0, "Room has no properties"

    def test_adapter_idempotent(self, populated_registry):
        """Calling register_ontology twice should not cause errors."""
        adapter = HotelDomainAdapter()
        # Should not raise
        adapter.register_ontology(populated_registry)
        entities = populated_registry.get_entities()
        assert len(entities) >= 8


class TestPropertyAutoDiscovery:
    """SPEC-R03: Verify auto-discovered properties match ORM columns."""

    def test_room_has_all_columns(self, populated_registry):
        """Room entity should have properties for all ORM columns."""
        entities = populated_registry.get_entities()
        room = next(e for e in entities if e.name == "Room")
        expected = {"id", "room_number", "floor", "room_type_id", "status",
                    "features", "is_active", "created_at", "updated_at"}
        actual = set(room.properties.keys())
        assert expected.issubset(actual), f"Missing: {expected - actual}"

    def test_guest_has_all_columns(self, populated_registry):
        """Guest entity should have all ORM columns including PII fields."""
        entities = populated_registry.get_entities()
        guest = next(e for e in entities if e.name == "Guest")
        expected = {"id", "name", "phone", "id_number", "id_type", "email",
                    "tier", "total_stays", "is_blacklisted"}
        actual = set(guest.properties.keys())
        assert expected.issubset(actual), f"Missing: {expected - actual}"

    def test_stay_record_has_properties(self, populated_registry):
        """StayRecord (previously zero) should now have all properties."""
        entities = populated_registry.get_entities()
        sr = next(e for e in entities if e.name == "StayRecord")
        assert len(sr.properties) >= 10, f"Only {len(sr.properties)} properties"
        assert "check_in_time" in sr.properties
        assert "status" in sr.properties

    def test_display_names_populated(self, populated_registry):
        """Properties should have Chinese display names."""
        entities = populated_registry.get_entities()
        guest = next(e for e in entities if e.name == "Guest")
        name_prop = guest.properties.get("name")
        assert name_prop is not None
        assert name_prop.display_name == "姓名"

    def test_security_levels_set(self, populated_registry):
        """PII fields should have elevated security levels."""
        entities = populated_registry.get_entities()
        guest = next(e for e in entities if e.name == "Guest")
        phone = guest.properties.get("phone")
        assert phone is not None
        assert phone.security_level == "CONFIDENTIAL"
        id_num = guest.properties.get("id_number")
        assert id_num is not None
        assert id_num.security_level == "RESTRICTED"

    def test_foreign_keys_detected(self, populated_registry):
        """FK columns should have is_foreign_key=True."""
        entities = populated_registry.get_entities()
        room = next(e for e in entities if e.name == "Room")
        rt_id = room.properties.get("room_type_id")
        assert rt_id is not None
        assert rt_id.is_foreign_key is True

    def test_enum_values_detected(self, populated_registry):
        """Enum columns should have enum_values populated."""
        entities = populated_registry.get_entities()
        room = next(e for e in entities if e.name == "Room")
        status = room.properties.get("status")
        assert status is not None
        assert status.enum_values is not None
        assert len(status.enum_values) > 0

    def test_total_property_count(self, populated_registry):
        """Total properties across all entities should be >= 100."""
        total = 0
        for entity in populated_registry.get_entities():
            total += len(entity.properties)
        assert total >= 100, f"Only {total} properties registered"


class TestModelRegistration:
    """SPEC-R02: Verify ORM model classes are registered in registry."""

    def test_model_map_has_all_models(self, populated_registry):
        """get_model_map() should contain all 10 domain models."""
        model_map = populated_registry.get_model_map()
        expected = {"Room", "Guest", "Reservation", "StayRecord", "Bill",
                    "Payment", "Task", "Employee", "RoomType", "RatePlan"}
        assert expected == set(model_map.keys()), f"Missing: {expected - set(model_map.keys())}"

    def test_get_model_returns_orm_class(self, populated_registry):
        """get_model('Room') should return the Room ORM class."""
        from app.models.ontology import Room
        model = populated_registry.get_model("Room")
        assert model is Room

    def test_get_model_returns_none_for_unknown(self, populated_registry):
        """get_model() returns None for unregistered names."""
        assert populated_registry.get_model("NonExistent") is None

    def test_all_models_are_sqlalchemy_classes(self, populated_registry):
        """All registered models should be SQLAlchemy declarative classes."""
        model_map = populated_registry.get_model_map()
        for name, cls in model_map.items():
            assert hasattr(cls, "__tablename__"), f"{name} has no __tablename__"
