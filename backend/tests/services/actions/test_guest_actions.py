"""
tests/services/actions/test_guest_actions.py

Tests for guest action handlers in app/services/actions/guest_actions.py
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

import app.services.actions.guest_actions as guest_actions
from app.services.actions.base import WalkInCheckInParams
from app.models.ontology import Employee, EmployeeRole, Room, RoomStatus, Guest, StayRecord
from app.services.param_parser_service import ParseResult


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Mock current user"""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "test_user"
    user.role = EmployeeRole.RECEPTIONIST
    return user


@pytest.fixture
def mock_param_parser():
    """Mock parameter parser service"""
    parser = Mock()
    parser.parse_room = Mock()
    return parser


@pytest.fixture
def sample_room():
    """Sample room for testing"""
    room = Mock(spec=Room)
    room.id = 101
    room.room_number = "101"
    room.status = RoomStatus.VACANT_CLEAN
    return room


@pytest.fixture
def sample_guest():
    """Sample guest for testing"""
    guest = Mock(spec=Guest)
    guest.id = 1
    guest.name = "张三"
    guest.phone = "13800138000"
    return guest


@pytest.fixture
def sample_stay(sample_guest, sample_room):
    """Sample stay record for testing"""
    stay = Mock(spec=StayRecord)
    stay.id = 1
    stay.guest = sample_guest
    stay.guest_id = sample_guest.id
    stay.room = sample_room
    stay.room_id = sample_room.id
    stay.check_in_time = "2026-02-07T10:00:00"
    stay.expected_check_out = date.today() + timedelta(days=3)
    return stay


# ==================== register_guest_actions Tests ====================

class TestRegisterGuestActions:
    """Test register_guest_actions function"""

    def test_register_guest_actions(self):
        """Test that register_guest_actions registers walkin_checkin action"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        guest_actions.register_guest_actions(registry)

        # Check that walkin_checkin action was registered
        action = registry.get_action("walkin_checkin")
        assert action is not None
        assert action.name == "walkin_checkin"
        assert action.entity == "Guest"
        assert action.category == "mutation"
        assert action.requires_confirmation is True
        assert "receptionist" in action.allowed_roles
        assert "manager" in action.allowed_roles


# ==================== handle_walkin_checkin Tests ====================

class TestHandleWalkInCheckIn:
    """Test handle_walkin_checkin handler via ActionRegistry"""

    @pytest.fixture
    def action_handler(self, mock_db, mock_user, mock_param_parser, sample_stay):
        """Fixture that provides a callable action handler"""
        def execute_checkin(params):
            mock_param_parser.parse_room.return_value = ParseResult(
                value=101,
                confidence=1.0,
                raw_input="101",
                candidates=None
            )

            mock_checkin_service = MagicMock()
            mock_checkin_service.walk_in_check_in.return_value = sample_stay

            with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
                from core.ai.actions import ActionRegistry
                registry = ActionRegistry()
                guest_actions.register_guest_actions(registry)

                action_def = registry.get_action("walkin_checkin")
                return action_def.handler(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )
        return execute_checkin

    def test_successful_checkin_with_valid_params(
        self, action_handler, sample_stay
    ):
        """Test successful check-in with valid parameters"""
        params = WalkInCheckInParams(
            guest_name="张三",
            guest_phone="13800138000",
            room_id=101,
            expected_check_out=date.today() + timedelta(days=3),
            deposit_amount=Decimal("100")
        )

        result = action_handler(params)

        assert result["success"] is True
        assert "stay_record_id" in result
        assert result["stay_record_id"] == sample_stay.id

    def test_checkin_with_room_number_string(
        self, mock_db, mock_user, mock_param_parser, sample_stay
    ):
        """Test check-in with room number string"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            raw_input="101",
            candidates=None
        )

        mock_checkin_service = MagicMock()
        mock_checkin_service.walk_in_check_in.return_value = sample_stay

        params = WalkInCheckInParams(
            guest_name="李四",
            guest_phone="13900139000",
            room_id="101",  # Room number string
            expected_check_out=date.today() + timedelta(days=2)
        )

        with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)

            action_def = registry.get_action("walkin_checkin")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        mock_param_parser.parse_room.assert_called_once_with("101")

    def test_checkin_low_confidence_returns_candidates(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test check-in with low confidence returns candidates for selection"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=None,
            confidence=0.5,
            raw_input="10",
            candidates=[
                {"id": 101, "room_number": "101"},
                {"id": 102, "room_number": "102"}
            ]
        )

        params = WalkInCheckInParams(
            guest_name="王五",
            room_id="10",  # Ambiguous input
            expected_check_out=date.today() + timedelta(days=2)
        )

        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        guest_actions.register_guest_actions(registry)

        action_def = registry.get_action("walkin_checkin")
        result = action_def.handler(
            params=params,
            db=mock_db,
            user=mock_user,
            param_parser=mock_param_parser
        )

        assert result["success"] is False
        assert result["requires_confirmation"] is True
        assert result["action"] == "select_room"
        assert "candidates" in result
        assert len(result["candidates"]) == 2

    def test_checkin_validation_error_returns_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test check-in with validation error returns error result"""
        from pydantic import ValidationError

        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            raw_input="101",
            candidates=None
        )

        mock_checkin_service = MagicMock()
        mock_checkin_service.walk_in_check_in.side_effect = ValidationError(
            [{"loc": ["guest_phone"], "msg": "Invalid phone format"}]
        )

        params = WalkInCheckInParams(
            guest_name="赵六",
            room_id=101,
            expected_check_out=date.today() + timedelta(days=2)
        )

        with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)

            action_def = registry.get_action("walkin_checkin")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_checkin_business_error_returns_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test check-in with business logic error returns error result"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=999,
            confidence=1.0,
            raw_input="999",
            candidates=None
        )

        mock_checkin_service = MagicMock()
        mock_checkin_service.walk_in_check_in.side_effect = ValueError("房间不存在")

        params = WalkInCheckInParams(
            guest_name="孙七",
            room_id=999,
            expected_check_out=date.today() + timedelta(days=2)
        )

        with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)

            action_def = registry.get_action("walkin_checkin")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_checkin_generic_error_returns_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test check-in with generic error returns error result"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            raw_input="101",
            candidates=None
        )

        mock_checkin_service = MagicMock()
        mock_checkin_service.walk_in_check_in.side_effect = Exception("数据库连接失败")

        params = WalkInCheckInParams(
            guest_name="周八",
            room_id=101,
            expected_check_out=date.today() + timedelta(days=2)
        )

        with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)

            action_def = registry.get_action("walkin_checkin")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_checkin_returns_all_expected_fields(
        self, mock_db, mock_user, mock_param_parser, sample_stay
    ):
        """Test check-in result contains all expected fields"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            raw_input="101",
            candidates=None
        )

        mock_checkin_service = MagicMock()
        mock_checkin_service.walk_in_check_in.return_value = sample_stay

        params = WalkInCheckInParams(
            guest_name="吴九",
            guest_phone="13800138000",
            room_id=101,
            expected_check_out=date.today() + timedelta(days=3),
            deposit_amount=Decimal("200")
        )

        with patch('app.services.actions.guest_actions.CheckInService', return_value=mock_checkin_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)

            action_def = registry.get_action("walkin_checkin")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        # Check all expected fields
        expected_fields = [
            "success",
            "message",
            "stay_record_id",
            "guest_id",
            "room_id",
            "room_number",
            "check_in_time",
            "expected_check_out"
        ]
        for field in expected_fields:
            assert field in result, f"Result should contain {field}"

        assert result["success"] is True


# ==================== Integration Tests ====================

class TestGuestActionsIntegration:
    """Integration tests for guest actions"""

    def test_action_registration_and_dispatch(self):
        """Test that action can be registered and dispatched"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        guest_actions.register_guest_actions(registry)

        # Verify action exists
        action = registry.get_action("walkin_checkin")
        assert action is not None

        # Verify action metadata
        assert action.name == "walkin_checkin"
        assert action.entity == "Guest"
        assert "散客" in action.search_keywords
        assert action.undoable is True

    def test_module_all(self):
        """Test __all__ export"""
        assert "register_guest_actions" in guest_actions.__all__
