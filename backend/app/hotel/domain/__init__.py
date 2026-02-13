"""
app/hotel/domain/__init__.py

酒店领域层 - 所有酒店特定的领域实体、状态机、仓储
"""
# Import from local domain files
from app.hotel.domain.room import RoomState, RoomEntity, RoomRepository
from app.hotel.domain.guest import GuestTier, GuestEntity, GuestRepository
from app.hotel.domain.reservation import (
    ReservationState,
    ReservationEntity,
    ReservationRepository,
)
from app.hotel.domain.stay_record import (
    StayRecordState,
    StayRecordEntity,
    StayRecordRepository,
)
from app.hotel.domain.bill import BillEntity, BillRepository
from app.hotel.domain.task import (
    TaskState,
    TaskType,
    TaskEntity,
    TaskRepository,
)
from app.hotel.domain.employee import (
    EmployeeRole,
    EmployeeEntity,
    EmployeeRepository,
)
from app.hotel.domain.interfaces import (
    BookableResource,
    Maintainable,
    Billable,
    Trackable,
)
# Relationship generic types from core
from core.domain.relationships import (
    LinkType,
    Cardinality,
    EntityLink,
    RelationshipRegistry,
    relationship_registry,
)
# Hotel-specific relationship constants
from app.hotel.domain.relationships import (
    ROOM_RELATIONSHIPS,
    GUEST_RELATIONSHIPS,
    RESERVATION_RELATIONSHIPS,
    STAY_RECORD_RELATIONSHIPS,
    BILL_RELATIONSHIPS,
    TASK_RELATIONSHIPS,
    EMPLOYEE_RELATIONSHIPS,
    register_hotel_relationships,
)

__all__ = [
    # Room
    "RoomState", "RoomEntity", "RoomRepository",
    # Guest
    "GuestTier", "GuestEntity", "GuestRepository",
    # Reservation
    "ReservationState", "ReservationEntity", "ReservationRepository",
    # StayRecord
    "StayRecordState", "StayRecordEntity", "StayRecordRepository",
    # Bill
    "BillEntity", "BillRepository",
    # Task
    "TaskState", "TaskType", "TaskEntity", "TaskRepository",
    # Employee
    "EmployeeRole", "EmployeeEntity", "EmployeeRepository",
    # Interfaces
    "BookableResource", "Maintainable", "Billable", "Trackable",
    # Relationships
    "LinkType", "Cardinality", "EntityLink",
    "ROOM_RELATIONSHIPS", "GUEST_RELATIONSHIPS",
    "RESERVATION_RELATIONSHIPS", "STAY_RECORD_RELATIONSHIPS",
    "BILL_RELATIONSHIPS", "TASK_RELATIONSHIPS", "EMPLOYEE_RELATIONSHIPS",
    "RelationshipRegistry", "relationship_registry",
]
