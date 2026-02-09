"""
Tests for SPEC-07: HotelDomainAdapter relationship registration
"""
import pytest
from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter


@pytest.fixture
def hotel_registry():
    reg = OntologyRegistry()
    reg.clear()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(reg)
    yield reg
    reg.clear()


class TestRelationshipRegistration:
    """Test all entity pair relationships are registered"""

    def test_guest_to_stay_record(self, hotel_registry):
        rels = hotel_registry.get_relationships("Guest")
        names = [r.name for r in rels]
        assert "stays" in names

    def test_stay_record_to_guest(self, hotel_registry):
        rels = hotel_registry.get_relationships("StayRecord")
        names = [r.name for r in rels]
        assert "guest" in names

    def test_guest_to_reservation(self, hotel_registry):
        rels = hotel_registry.get_relationships("Guest")
        names = [r.name for r in rels]
        assert "reservations" in names

    def test_room_to_stay_records(self, hotel_registry):
        rels = hotel_registry.get_relationships("Room")
        names = [r.name for r in rels]
        assert "stay_records" in names

    def test_room_to_tasks(self, hotel_registry):
        rels = hotel_registry.get_relationships("Room")
        names = [r.name for r in rels]
        assert "tasks" in names

    def test_room_to_room_type(self, hotel_registry):
        rels = hotel_registry.get_relationships("Room")
        names = [r.name for r in rels]
        assert "room_type" in names

    def test_stay_record_to_bill(self, hotel_registry):
        rels = hotel_registry.get_relationships("StayRecord")
        names = [r.name for r in rels]
        assert "bill" in names

    def test_bill_to_payments(self, hotel_registry):
        rels = hotel_registry.get_relationships("Bill")
        names = [r.name for r in rels]
        assert "payments" in names

    def test_task_to_employee(self, hotel_registry):
        rels = hotel_registry.get_relationships("Task")
        names = [r.name for r in rels]
        assert "assignee" in names

    def test_reservation_to_room_type(self, hotel_registry):
        rels = hotel_registry.get_relationships("Reservation")
        names = [r.name for r in rels]
        assert "room_type" in names


class TestEntityRegistrationCompletion:
    """Test all 10 entities are registered"""

    def test_all_entities_registered(self, hotel_registry):
        expected = {"Room", "Guest", "Reservation", "StayRecord",
                    "Task", "Bill", "Payment", "Employee", "RoomType", "RatePlan"}
        entities = {e.name for e in hotel_registry.get_entities()}
        assert expected.issubset(entities)

    def test_bill_has_properties(self, hotel_registry):
        bill = hotel_registry.get_entity("Bill")
        assert bill is not None
        assert "total_amount" in bill.properties
        assert "is_settled" in bill.properties

    def test_employee_has_role(self, hotel_registry):
        emp = hotel_registry.get_entity("Employee")
        assert emp is not None
        assert "role" in emp.properties
        role = emp.properties["role"]
        assert role.enum_values is not None


class TestRelationshipMapFormat:
    """Test get_relationship_map() returns expected format"""

    def test_relationship_map_has_guest(self, hotel_registry):
        rmap = hotel_registry.get_relationship_map()
        assert "Guest" in rmap
        assert "StayRecord" in rmap["Guest"]

    def test_relationship_map_has_room(self, hotel_registry):
        rmap = hotel_registry.get_relationship_map()
        assert "Room" in rmap
        assert "Task" in rmap["Room"]

    def test_export_schema_includes_relationships(self, hotel_registry):
        schema = hotel_registry.export_schema()
        assert "relationships" in schema
        assert "Guest" in schema["relationships"]
