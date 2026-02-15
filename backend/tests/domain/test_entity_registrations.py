"""
Tests for app/hotel/entities/ module — entity registration protocol completeness.
"""
import pytest
from app.hotel.entities import (
    EntityRegistration,
    get_all_entity_registrations,
    get_all_relationships,
)


EXPECTED_ENTITIES = {
    "Room", "Guest", "Reservation", "StayRecord", "Task",
    "Bill", "Payment", "Employee", "RoomType", "RatePlan",
}

ENTITIES_WITH_STATE_MACHINES = {"Room", "Reservation", "StayRecord", "Task"}


class TestEntityRegistrations:
    def test_all_entities_registered(self):
        """All 10 hotel entities are registered."""
        regs = get_all_entity_registrations()
        names = {r.metadata.name for r in regs}
        assert names == EXPECTED_ENTITIES

    def test_registration_protocol_completeness(self):
        """Each registration has metadata and model_class."""
        for reg in get_all_entity_registrations():
            assert isinstance(reg, EntityRegistration)
            assert reg.metadata is not None
            assert reg.metadata.name != ""
            assert reg.model_class is not None

    def test_state_machines_present(self):
        """Entities with lifecycles have state machines."""
        regs = get_all_entity_registrations()
        sm_entities = {r.metadata.name for r in regs if r.state_machine is not None}
        assert sm_entities == ENTITIES_WITH_STATE_MACHINES

    def test_constraints_present(self):
        """At least some entities have constraints."""
        regs = get_all_entity_registrations()
        total = sum(len(r.constraints) for r in regs)
        assert total >= 20  # we have 20 constraints

    def test_events_present(self):
        """At least some entities have events."""
        regs = get_all_entity_registrations()
        total = sum(len(r.events) for r in regs)
        assert total >= 9  # we have 9 events

    def test_relationships_present(self):
        """Relationships are defined."""
        rels = get_all_relationships()
        assert len(rels) >= 15  # we have 15 relationship pairs

    def test_model_classes_are_orm_models(self):
        """Model classes have __tablename__ (SQLAlchemy ORM models)."""
        for reg in get_all_entity_registrations():
            assert hasattr(reg.model_class, '__tablename__'), \
                f"{reg.metadata.name} model_class missing __tablename__"

    def test_entity_metadata_has_table_name(self):
        """Each entity metadata has a table_name."""
        for reg in get_all_entity_registrations():
            assert reg.metadata.table_name, \
                f"{reg.metadata.name} missing table_name"
