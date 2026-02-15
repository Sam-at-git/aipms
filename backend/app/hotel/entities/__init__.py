"""
app/hotel/entities — Hotel entity registration module

Each entity file exports a `get_registration()` function returning an EntityRegistration.
This module aggregates all registrations for use by HotelDomainAdapter.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.ontology.metadata import (
    EntityMetadata,
    ConstraintMetadata,
    RelationshipMetadata,
    StateMachine,
    EventMetadata,
)


@dataclass
class EntityRegistration:
    """单个实体的完整注册信息"""
    metadata: EntityMetadata
    model_class: type
    state_machine: Optional[StateMachine] = None
    constraints: List[ConstraintMetadata] = field(default_factory=list)
    events: List[EventMetadata] = field(default_factory=list)


def get_all_entity_registrations() -> List[EntityRegistration]:
    """Collect all hotel entity registrations."""
    from app.hotel.entities.room import get_registration as room_reg
    from app.hotel.entities.guest import get_registration as guest_reg
    from app.hotel.entities.reservation import get_registration as reservation_reg
    from app.hotel.entities.stay_record import get_registration as stay_record_reg
    from app.hotel.entities.task import get_registration as task_reg
    from app.hotel.entities.bill import get_registration as bill_reg
    from app.hotel.entities.payment import get_registration as payment_reg
    from app.hotel.entities.employee import get_registration as employee_reg
    from app.hotel.entities.room_type import get_registration as room_type_reg
    from app.hotel.entities.rate_plan import get_registration as rate_plan_reg

    return [
        room_reg(),
        guest_reg(),
        reservation_reg(),
        stay_record_reg(),
        task_reg(),
        bill_reg(),
        payment_reg(),
        employee_reg(),
        room_type_reg(),
        rate_plan_reg(),
    ]


def get_all_relationships() -> List[Tuple[str, RelationshipMetadata]]:
    """Collect all hotel entity relationships as (entity_name, metadata) tuples."""
    from app.hotel.entities.relationships import get_relationships
    return get_relationships()
