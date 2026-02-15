"""Hotel entity relationships."""
from typing import List, Tuple

from core.ontology.metadata import RelationshipMetadata


def get_relationships() -> List[Tuple[str, RelationshipMetadata]]:
    """Return all hotel entity relationships as (entity_name, metadata) tuples."""
    return [
        # Guest ↔ StayRecord
        ("Guest", RelationshipMetadata(
            name="stays", target_entity="StayRecord", cardinality="one_to_many",
            foreign_key="guest_id", foreign_key_entity="StayRecord", inverse_name="guest",
        )),
        ("StayRecord", RelationshipMetadata(
            name="guest", target_entity="Guest", cardinality="many_to_one",
            foreign_key="guest_id", foreign_key_entity="StayRecord", inverse_name="stays",
        )),
        # Guest ↔ Reservation
        ("Guest", RelationshipMetadata(
            name="reservations", target_entity="Reservation", cardinality="one_to_many",
            foreign_key="guest_id", foreign_key_entity="Reservation", inverse_name="guest",
        )),
        ("Reservation", RelationshipMetadata(
            name="guest", target_entity="Guest", cardinality="many_to_one",
            foreign_key="guest_id", foreign_key_entity="Reservation", inverse_name="reservations",
        )),
        # Room ↔ StayRecord
        ("Room", RelationshipMetadata(
            name="stay_records", target_entity="StayRecord", cardinality="one_to_many",
            foreign_key="room_id", foreign_key_entity="StayRecord", inverse_name="room",
        )),
        ("StayRecord", RelationshipMetadata(
            name="room", target_entity="Room", cardinality="many_to_one",
            foreign_key="room_id", foreign_key_entity="StayRecord", inverse_name="stay_records",
        )),
        # Room ↔ Task
        ("Room", RelationshipMetadata(
            name="tasks", target_entity="Task", cardinality="one_to_many",
            foreign_key="room_id", foreign_key_entity="Task", inverse_name="room",
        )),
        ("Task", RelationshipMetadata(
            name="room", target_entity="Room", cardinality="many_to_one",
            foreign_key="room_id", foreign_key_entity="Task", inverse_name="tasks",
        )),
        # Room → RoomType
        ("Room", RelationshipMetadata(
            name="room_type", target_entity="RoomType", cardinality="many_to_one",
            foreign_key="room_type_id", foreign_key_entity="Room",
        )),
        # StayRecord ↔ Bill
        ("StayRecord", RelationshipMetadata(
            name="bill", target_entity="Bill", cardinality="one_to_one",
            foreign_key="stay_record_id", foreign_key_entity="Bill", inverse_name="stay_record",
        )),
        ("Bill", RelationshipMetadata(
            name="stay_record", target_entity="StayRecord", cardinality="one_to_one",
            foreign_key="stay_record_id", foreign_key_entity="Bill", inverse_name="bill",
        )),
        # Bill ↔ Payment
        ("Bill", RelationshipMetadata(
            name="payments", target_entity="Payment", cardinality="one_to_many",
            foreign_key="bill_id", foreign_key_entity="Payment", inverse_name="bill",
        )),
        ("Payment", RelationshipMetadata(
            name="bill", target_entity="Bill", cardinality="many_to_one",
            foreign_key="bill_id", foreign_key_entity="Payment", inverse_name="payments",
        )),
        # Task → Employee
        ("Task", RelationshipMetadata(
            name="assignee", target_entity="Employee", cardinality="many_to_one",
            foreign_key="assignee_id", foreign_key_entity="Task",
        )),
        # Reservation → RoomType
        ("Reservation", RelationshipMetadata(
            name="room_type", target_entity="RoomType", cardinality="many_to_one",
            foreign_key="room_type_id", foreign_key_entity="Reservation",
        )),
    ]
