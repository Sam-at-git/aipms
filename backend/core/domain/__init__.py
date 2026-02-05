"""
core/domain/__init__.py

领域层入口点
"""
from core.domain.room import RoomState, RoomEntity, RoomRepository
from core.domain.guest import GuestTier, GuestEntity, GuestRepository
from core.domain.reservation import (
    ReservationState,
    ReservationEntity,
    ReservationRepository,
)
from core.domain.stay_record import (
    StayRecordState,
    StayRecordEntity,
    StayRecordRepository,
)
from core.domain.bill import BillEntity, BillRepository
from core.domain.task import (
    TaskState,
    TaskType,
    TaskEntity,
    TaskRepository,
)
from core.domain.employee import (
    EmployeeRole,
    EmployeeEntity,
    EmployeeRepository,
)
from core.domain.relationships import (
    LinkType,
    Cardinality,
    EntityLink,
    ROOM_RELATIONSHIPS,
    GUEST_RELATIONSHIPS,
    RESERVATION_RELATIONSHIPS,
    STAY_RECORD_RELATIONSHIPS,
    BILL_RELATIONSHIPS,
    TASK_RELATIONSHIPS,
    EMPLOYEE_RELATIONSHIPS,
    RelationshipRegistry,
    relationship_registry,
)

__all__ = [
    "RoomState",
    "RoomEntity",
    "RoomRepository",
    "GuestTier",
    "GuestEntity",
    "GuestRepository",
    "ReservationState",
    "ReservationEntity",
    "ReservationRepository",
    "StayRecordState",
    "StayRecordEntity",
    "StayRecordRepository",
    "BillEntity",
    "BillRepository",
    "TaskState",
    "TaskType",
    "TaskEntity",
    "TaskRepository",
    "EmployeeRole",
    "EmployeeEntity",
    "EmployeeRepository",
    "LinkType",
    "Cardinality",
    "EntityLink",
    "ROOM_RELATIONSHIPS",
    "GUEST_RELATIONSHIPS",
    "RESERVATION_RELATIONSHIPS",
    "STAY_RECORD_RELATIONSHIPS",
    "BILL_RELATIONSHIPS",
    "TASK_RELATIONSHIPS",
    "EMPLOYEE_RELATIONSHIPS",
    "RelationshipRegistry",
    "relationship_registry",
]
