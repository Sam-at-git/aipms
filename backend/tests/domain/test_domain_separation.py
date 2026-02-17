"""
Tests for Domain Separation - app.hotel.domain structure and architecture guard
"""
import os
import pytest


class TestDomainBridgeImports:
    """Verify that app.hotel.domain exports work correctly"""

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

    def test_hotel_domain_all_exports(self):
        """Verify __all__ has expected entries"""
        from app.hotel import domain
        assert hasattr(domain, "__all__")
        expected = ["RoomState", "GuestEntity", "BookableResource", "relationship_registry"]
        for name in expected:
            assert name in domain.__all__


class TestArchitectureGuard:
    """Ensure core/ has no imports from app/ (except backward-compat domain stubs)"""

    def test_core_has_no_app_imports(self):
        """Scan all core/*.py files and ensure none import from app."""
        core_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'core')
        core_dir = os.path.normpath(core_dir)

        violations = []
        for root, dirs, files in os.walk(core_dir):
            rel = os.path.relpath(root, core_dir)
            if '__pycache__' in root:
                continue
            for f in files:
                if not f.endswith('.py'):
                    continue
                filepath = os.path.join(root, f)
                with open(filepath) as fh:
                    for i, line in enumerate(fh, 1):
                        stripped = line.strip()
                        if stripped.startswith('#'):
                            continue
                        if 'from app.' in stripped or 'import app.' in stripped:
                            violations.append(f"{filepath}:{i}: {stripped}")

        assert violations == [], (
            f"core/ has {len(violations)} import(s) from app/:\n" +
            "\n".join(violations)
        )
