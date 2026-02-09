"""
Tests for SPEC-04: Domain Separation - app.hotel.domain re-exports
"""
import pytest


class TestDomainBridgeImports:
    """Verify that app.hotel.domain re-exports work correctly"""

    def test_import_room_from_hotel_domain(self):
        from app.hotel.domain import RoomState, RoomEntity, RoomRepository
        assert RoomState is not None
        assert hasattr(RoomState, "VACANT_CLEAN")

    def test_import_guest_from_hotel_domain(self):
        from app.hotel.domain import GuestTier, GuestEntity, GuestRepository
        assert GuestTier is not None

    def test_import_reservation_from_hotel_domain(self):
        from app.hotel.domain import ReservationState, ReservationEntity, ReservationRepository
        assert ReservationState is not None

    def test_import_stay_record_from_hotel_domain(self):
        from app.hotel.domain import StayRecordState, StayRecordEntity, StayRecordRepository
        assert StayRecordState is not None

    def test_import_bill_from_hotel_domain(self):
        from app.hotel.domain import BillEntity, BillRepository
        assert BillEntity is not None

    def test_import_task_from_hotel_domain(self):
        from app.hotel.domain import TaskState, TaskType, TaskEntity, TaskRepository
        assert TaskState is not None

    def test_import_employee_from_hotel_domain(self):
        from app.hotel.domain import EmployeeRole, EmployeeEntity, EmployeeRepository
        assert EmployeeRole is not None

    def test_import_interfaces_from_hotel_domain(self):
        from app.hotel.domain import BookableResource, Maintainable, Billable, Trackable
        assert BookableResource is not None

    def test_import_relationships_from_hotel_domain(self):
        from app.hotel.domain import (
            LinkType, Cardinality, EntityLink,
            RelationshipRegistry, relationship_registry,
        )
        assert LinkType is not None
        assert relationship_registry is not None

    def test_hotel_domain_types_same_as_core_domain(self):
        """Verify that imports from both paths resolve to same objects"""
        from app.hotel.domain import RoomState as HotelRoomState
        from core.domain.room import RoomState as CoreRoomState
        assert HotelRoomState is CoreRoomState

    def test_hotel_domain_entities_same_as_core(self):
        from app.hotel.domain import GuestEntity as HotelGuest
        from core.domain.guest import GuestEntity as CoreGuest
        assert HotelGuest is CoreGuest

    def test_hotel_domain_all_exports(self):
        """Verify __all__ has expected entries"""
        from app.hotel import domain
        assert hasattr(domain, "__all__")
        expected = ["RoomState", "GuestEntity", "BookableResource", "relationship_registry"]
        for name in expected:
            assert name in domain.__all__
