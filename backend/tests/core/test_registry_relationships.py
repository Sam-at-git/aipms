"""
tests/core/test_registry_relationships.py

Unit tests for OntologyRegistry.get_related_entities().
"""
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import RelationshipMetadata


@pytest.fixture
def clean_registry():
    """Create a fresh OntologyRegistry for each test (reset singleton)."""
    reg = OntologyRegistry()
    # Save and restore state
    old_rels = dict(reg._relationships)
    reg._relationships = {}
    yield reg
    reg._relationships = old_rels


@pytest.fixture
def registry_with_hotel_rels(clean_registry):
    """Registry with hotel-like relationships."""
    reg = clean_registry

    # Room → RoomType
    reg.register_relationship("Room", RelationshipMetadata(
        name="room_type", target_entity="RoomType",
        cardinality="many_to_one", foreign_key="room_type_id",
        foreign_key_entity="Room",
    ))
    # Room → StayRecord
    reg.register_relationship("Room", RelationshipMetadata(
        name="stays", target_entity="StayRecord",
        cardinality="one_to_many", foreign_key="room_id",
        foreign_key_entity="StayRecord",
    ))
    # StayRecord → Guest
    reg.register_relationship("StayRecord", RelationshipMetadata(
        name="guest", target_entity="Guest",
        cardinality="many_to_one", foreign_key="guest_id",
        foreign_key_entity="StayRecord",
    ))
    # StayRecord → Room
    reg.register_relationship("StayRecord", RelationshipMetadata(
        name="room", target_entity="Room",
        cardinality="many_to_one", foreign_key="room_id",
        foreign_key_entity="StayRecord",
    ))
    # Guest → Reservation
    reg.register_relationship("Guest", RelationshipMetadata(
        name="reservations", target_entity="Reservation",
        cardinality="one_to_many", foreign_key="guest_id",
        foreign_key_entity="Reservation",
    ))
    # Bill → StayRecord
    reg.register_relationship("Bill", RelationshipMetadata(
        name="stay_record", target_entity="StayRecord",
        cardinality="many_to_one", foreign_key="stay_record_id",
        foreign_key_entity="Bill",
    ))

    return reg


class TestGetRelatedEntities:

    def test_depth_0(self, registry_with_hotel_rels):
        """depth=0 returns only the entity itself."""
        result = registry_with_hotel_rels.get_related_entities("Room", depth=0)
        assert result == {"Room"}

    def test_depth_1(self, registry_with_hotel_rels):
        """depth=1 returns direct neighbors."""
        result = registry_with_hotel_rels.get_related_entities("Room", depth=1)
        assert result == {"Room", "RoomType", "StayRecord"}

    def test_depth_2(self, registry_with_hotel_rels):
        """depth=2 returns 2-hop neighbors."""
        result = registry_with_hotel_rels.get_related_entities("Room", depth=2)
        # Room → RoomType, StayRecord → Guest, Room (already visited)
        assert "Room" in result
        assert "RoomType" in result
        assert "StayRecord" in result
        assert "Guest" in result  # via StayRecord

    def test_circular_reference(self, registry_with_hotel_rels):
        """Circular references (Room ↔ StayRecord) don't cause infinite loops."""
        # Room → StayRecord → Room (circular), plus StayRecord → Guest
        result = registry_with_hotel_rels.get_related_entities("Room", depth=10)
        # Should terminate and include all reachable entities
        assert "Room" in result
        assert "StayRecord" in result
        assert "Guest" in result
        assert "Reservation" in result  # via Guest
        assert "RoomType" in result

    def test_nonexistent_entity(self, registry_with_hotel_rels):
        """Non-existent entity returns a set containing only itself."""
        result = registry_with_hotel_rels.get_related_entities("NonExistent", depth=1)
        assert result == {"NonExistent"}

    def test_no_relationships(self, clean_registry):
        """Entity with no relationships returns only itself."""
        result = clean_registry.get_related_entities("Isolated", depth=1)
        assert result == {"Isolated"}

    def test_bill_depth_1(self, registry_with_hotel_rels):
        """Bill depth=1 reaches StayRecord."""
        result = registry_with_hotel_rels.get_related_entities("Bill", depth=1)
        assert result == {"Bill", "StayRecord"}

    def test_bill_depth_2(self, registry_with_hotel_rels):
        """Bill depth=2 reaches StayRecord's neighbors."""
        result = registry_with_hotel_rels.get_related_entities("Bill", depth=2)
        assert "Bill" in result
        assert "StayRecord" in result
        assert "Guest" in result  # via StayRecord
        assert "Room" in result   # via StayRecord
