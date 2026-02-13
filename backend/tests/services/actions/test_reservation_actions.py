"""
tests/services/actions/test_reservation_actions.py

Tests for reservation action handlers in app/services/actions/reservation_actions.py
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

import app.services.actions.reservation_actions as reservation_actions
from app.services.actions.base import CreateReservationParams
from app.models.ontology import (
    Employee, EmployeeRole, Guest, RoomType, Reservation, ReservationStatus
)
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
    user.username = "receptionist"
    user.role = EmployeeRole.RECEPTIONIST
    return user


@pytest.fixture
def mock_param_parser():
    """Mock parameter parser service"""
    parser = Mock()
    parser.parse_room_type = Mock()
    return parser


@pytest.fixture
def sample_room_type():
    """Sample room type"""
    rt = Mock(spec=RoomType)
    rt.id = 1
    rt.name = "标准大床房"
    rt.base_price = Decimal("288.00")
    return rt


@pytest.fixture
def sample_reservation(sample_room_type):
    """Sample reservation"""
    res = Mock(spec=Reservation)
    res.id = 1
    res.reservation_no = "RES20260207001"
    res.guest_id = 1
    res.guest_name = "张三"
    res.guest = Mock(spec=Guest)
    res.guest.name = "张三"
    res.room_type_id = sample_room_type.id
    res.room_type = sample_room_type
    res.room_type_name = sample_room_type.name
    res.check_in_date = date(2026, 6, 1)
    res.check_out_date = date(2026, 6, 5)
    res.adult_count = 2
    res.child_count = 1
    res.room_count = 1
    res.total_amount = Decimal("1152.00")
    res.status = ReservationStatus.CONFIRMED
    return res


# ==================== register_reservation_actions Tests ====================

class TestRegisterReservationActions:
    """Test register_reservation_actions function"""

    def test_register_reservation_actions(self):
        """Test that register_reservation_actions registers create_reservation action"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        reservation_actions.register_reservation_actions(registry)

        action = registry.get_action("create_reservation")
        assert action is not None
        assert action.name == "create_reservation"
        assert action.entity == "Reservation"
        assert action.undoable is True


# ==================== handle_create_reservation Tests ====================

class TestHandleCreateReservation:
    """Test handle_create_reservation handler via ActionRegistry"""

    @pytest.fixture
    def reservation_action(self, mock_db, mock_user, mock_param_parser, sample_reservation):
        """Fixture that provides the reservation action handler"""
        def execute_reservation(params):
            mock_param_parser.parse_room_type.return_value = ParseResult(
                value=1,
                confidence=1.0,
                matched_by='direct',
                raw_input="1",
                candidates=None
            )

            mock_reservation_service = MagicMock()
            mock_reservation_service.create_reservation.return_value = sample_reservation

            with patch('app.services.actions.reservation_actions.ReservationService',
                      return_value=mock_reservation_service):
                from core.ai.actions import ActionRegistry
                registry = ActionRegistry()
                reservation_actions.register_reservation_actions(registry)

                action_def = registry.get_action("create_reservation")
                return action_def.handler(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )
        return execute_reservation

    def test_successful_reservation_minimal(
        self, reservation_action, sample_reservation
    ):
        """Test successful reservation with minimal params"""
        params = CreateReservationParams(
            guest_name="张三",
            room_type_id=1,
            check_in_date="2026-06-01",
            check_out_date="2026-06-05"
        )

        result = reservation_action(params)

        assert result["success"] is True
        assert result["reservation_id"] == sample_reservation.id

    def test_successful_reservation_all_params(
        self, reservation_action
    ):
        """Test successful reservation with all params"""
        params = CreateReservationParams(
            guest_name="李四",
            guest_phone="13800138000",
            guest_id_number="A12345678",
            room_type_id="标准大床房",
            check_in_date="2026-06-01",
            check_out_date="2026-06-05",
            adult_count=2,
            child_count=1,
            room_count=2,
            special_requests="高层房间"
        )

        result = reservation_action(params)

        assert result["success"] is True

    def test_reservation_with_room_type_name(
        self, mock_db, mock_user, mock_param_parser, sample_reservation
    ):
        """Test reservation with room type name instead of ID"""
        mock_param_parser.parse_room_type.return_value = ParseResult(
            value=1,
            confidence=1.0,
            matched_by='exact',
            raw_input="豪华大床房",
            candidates=None
        )

        mock_reservation_service = MagicMock()
        mock_reservation_service.create_reservation.return_value = sample_reservation

        params = CreateReservationParams(
            guest_name="王五",
            room_type_id="豪华大床房",
            check_in_date="2026-07-01",
            check_out_date="2026-07-03"
        )

        with patch('app.services.actions.reservation_actions.ReservationService',
                  return_value=mock_reservation_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            reservation_actions.register_reservation_actions(registry)

            action_def = registry.get_action("create_reservation")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        mock_param_parser.parse_room_type.assert_called_once()

    def test_reservation_low_confidence_returns_candidates(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test reservation with low confidence returns candidates"""
        mock_param_parser.parse_room_type.return_value = ParseResult(
            value=None,
            confidence=0.5,
            matched_by='fuzzy',
            raw_input="标",
            candidates=None
        )

        mock_room_service = MagicMock()
        mock_room_service.get_room_types.return_value = []

        params = CreateReservationParams(
            guest_name="赵六",
            room_type_id="标",
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )

        with patch('app.services.actions.reservation_actions.RoomService',
                  return_value=mock_room_service):
            result = self._execute_with_registry(params, mock_db, mock_user, mock_param_parser)

        assert result["success"] is False
        assert result["requires_confirmation"] is True
        assert result["action"] == "select_room_type"

    def test_reservation_validation_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test reservation with validation error returns error result"""
        from pydantic import ValidationError

        mock_param_parser.parse_room_type.return_value = ParseResult(
            value=1,
            confidence=1.0,
            matched_by='direct',
            raw_input="1",
            candidates=None
        )

        mock_reservation_service = MagicMock()
        mock_reservation_service.create_reservation.side_effect = ValidationError.from_exception_data(
            title="ReservationCreate",
            line_errors=[{"type": "value_error", "loc": ("guest_phone",), "msg": "Invalid phone", "input": "bad", "ctx": {"error": ValueError("Invalid phone")}}]
        )

        params = CreateReservationParams(
            guest_name="孙七",
            room_type_id=1,
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )

        with patch('app.services.actions.reservation_actions.ReservationService',
                  return_value=mock_reservation_service):
            result = self._execute_with_registry(params, mock_db, mock_user, mock_param_parser)

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_reservation_business_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test reservation with business error returns error result"""
        mock_param_parser.parse_room_type.return_value = ParseResult(
            value=999,
            confidence=1.0,
            matched_by='direct',
            raw_input="999",
            candidates=None
        )

        mock_reservation_service = MagicMock()
        mock_reservation_service.create_reservation.side_effect = ValueError("房型不存在")

        params = CreateReservationParams(
            guest_name="周八",
            room_type_id=999,
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )

        with patch('app.services.actions.reservation_actions.ReservationService',
                  return_value=mock_reservation_service):
            result = self._execute_with_registry(params, mock_db, mock_user, mock_param_parser)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_reservation_generic_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test reservation with generic error returns error result"""
        mock_param_parser.parse_room_type.return_value = ParseResult(
            value=1,
            confidence=1.0,
            matched_by='direct',
            raw_input="1",
            candidates=None
        )

        mock_reservation_service = MagicMock()
        mock_reservation_service.create_reservation.side_effect = Exception("数据库错误")

        params = CreateReservationParams(
            guest_name="吴九",
            room_type_id=1,
            check_in_date="2026-06-01",
            check_out_date="2026-06-03"
        )

        with patch('app.services.actions.reservation_actions.ReservationService',
                  return_value=mock_reservation_service):
            result = self._execute_with_registry(params, mock_db, mock_user, mock_param_parser)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_reservation_date_validation_at_pydantic_level(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test reservation date validation is caught at Pydantic model level"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="退房日期必须晚于入住日期"):
            CreateReservationParams(
                guest_name="郑十",
                room_type_id=1,
                check_in_date="2026-06-05",
                check_out_date="2026-06-01"
            )

    def _execute_with_registry(self, params, db, user, param_parser):
        """Helper to execute action via registry"""
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        reservation_actions.register_reservation_actions(registry)

        action_def = registry.get_action("create_reservation")
        return action_def.handler(
            params=params,
            db=db,
            user=user,
            param_parser=param_parser
        )


# ==================== Integration Tests ====================

class TestReservationActionsIntegration:
    """Integration tests for reservation actions"""

    def test_action_registration_and_metadata(self):
        """Test create_reservation action registration and metadata"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        reservation_actions.register_reservation_actions(registry)

        action = registry.get_action("create_reservation")
        assert action is not None
        assert "预订" in action.search_keywords

    def test_module_exports(self):
        """Test that reservation_actions module exports correctly"""
        assert hasattr(reservation_actions, "register_reservation_actions")
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        reservation_actions.register_reservation_actions(registry)
        assert registry.get_action("create_reservation") is not None

    def test_module_all(self):
        """Test __all__ export"""
        assert "register_reservation_actions" in reservation_actions.__all__
