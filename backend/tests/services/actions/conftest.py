"""
tests/services/actions/conftest.py

Fixtures for action handler tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

from app.models.ontology import Employee, EmployeeRole, Room, RoomType, RoomStatus
from app.services.param_parser_service import ParamParserService, ParseResult
from app.services.actions import get_action_registry, reset_action_registry


@pytest.fixture
def clean_registry():
    """Provide a clean registry for each test."""
    reset_action_registry()
    return get_action_registry()


@pytest.fixture
def mock_user():
    """Mock user (employee)."""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "test_user"
    user.name = "测试用户"
    # Create a proper mock role with value attribute
    role_mock = Mock()
    role_mock.value = "receptionist"
    user.role = role_mock
    return user


@pytest.fixture
def mock_manager():
    """Mock manager user."""
    user = Mock(spec=Employee)
    user.id = 2
    user.username = "test_manager"
    user.name = "测试经理"
    # Create a proper mock role with value attribute
    role_mock = Mock()
    role_mock.value = "manager"
    user.role = role_mock
    return user


@pytest.fixture
def mock_param_parser(db_session):
    """Mock ParamParserService."""
    mock = Mock(spec=ParamParserService)

    # Default room parsing returns success
    mock.parse_room.return_value = ParseResult(
        value=1,
        confidence=1.0,
        matched_by='direct',
        raw_input='1'
    )

    # Default room type parsing returns success
    mock.parse_room_type.return_value = ParseResult(
        value=1,
        confidence=1.0,
        matched_by='direct',
        raw_input='1'
    )

    return mock


@pytest.fixture
def mock_param_parser_low_conf():
    """Mock ParamParserService with low confidence."""
    mock = Mock(spec=ParamParserService)

    # Low confidence room result
    mock.parse_room.return_value = ParseResult(
        value=None,
        confidence=0.5,
        matched_by='fuzzy',
        raw_input='abc',
        candidates=[
            {'id': 1, 'room_number': '101', 'room_type': '标间'},
            {'id': 2, 'room_number': '102', 'room_type': '大床房'}
        ]
    )

    return mock


@pytest.fixture
def sample_room(db_session):
    """Create a sample room for testing."""
    room_type = RoomType(
        name="标间",
        base_price=Decimal("288.00"),
        max_occupancy=2
    )
    db_session.add(room_type)
    db_session.flush()

    room = Room(
        room_number="101",
        floor=1,
        room_type_id=room_type.id,
        status=RoomStatus.VACANT_CLEAN
    )
    db_session.add(room)
    db_session.commit()

    return room


@pytest.fixture
def sample_guest(db_session):
    """Create a sample guest for testing."""
    from app.models.ontology import Guest

    guest = Guest(
        name="张三",
        phone="13800138000",
        id_type="身份证",
        id_number="110101199001011234"
    )
    db_session.add(guest)
    db_session.commit()

    return guest


@pytest.fixture
def sample_stay_record(db_session, sample_guest, sample_room):
    """Create a sample stay record for testing."""
    from app.models.ontology import StayRecord, StayRecordStatus, Bill
    from datetime import datetime

    stay = StayRecord(
        guest_id=sample_guest.id,
        room_id=sample_room.id,
        expected_check_out=date.today(),
        status=StayRecordStatus.ACTIVE,
        check_in_time=datetime.now()
    )
    db_session.add(stay)
    db_session.flush()

    # Create bill
    bill = Bill(
        stay_record_id=stay.id,
        total_amount=Decimal("288.00"),
        paid_amount=Decimal("0.00")
    )
    db_session.add(bill)
    db_session.commit()

    return stay
