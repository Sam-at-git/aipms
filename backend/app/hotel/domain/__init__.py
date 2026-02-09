"""
app/hotel/domain/__init__.py

酒店领域层 - 所有酒店特定的领域实体、状态机、仓储

这是酒店领域代码的规范位置。当前通过 core.domain 桥接，
后续将逐步迁移所有领域代码到此处。
"""
# Re-export all domain types from core.domain (bridge pattern)
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
from core.domain.interfaces import (
    BookableResource,
    Maintainable,
    Billable,
    Trackable,
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
