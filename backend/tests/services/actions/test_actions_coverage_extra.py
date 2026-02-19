"""
tests/services/actions/test_actions_coverage_extra.py

Additional coverage tests for hotel action handlers - covering uncovered error paths,
edge cases, and exception handling branches.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.hotel.models.ontology import (
    Employee, EmployeeRole, Bill, Payment, PaymentMethod,
    Room, RoomType, RoomStatus, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Task, TaskStatus, TaskType,
)
from app.hotel.actions.base import (
    AddPaymentParams, AdjustBillParams, RefundPaymentParams,
    CreateReservationParams, CancelReservationParams, ModifyReservationParams,
    CheckoutParams, CheckinParams, ExtendStayParams, ChangeRoomParams,
    UpdateRoomStatusParams, CreateRoomTypeParams, UpdateRoomTypeParams,
    UpdateGuestParams, CreateGuestParams, CreateEmployeeParams,
    UpdateEmployeeParams, DeactivateEmployeeParams,
    UpdatePriceParams, CreateRatePlanParams,
)
from app.hotel.services.param_parser_service import ParamParserService, ParseResult


# ============== Shared Fixtures ==============

@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "manager"
    user.name = "经理"
    role_mock = Mock()
    role_mock.value = "manager"
    user.role = role_mock
    return user


@pytest.fixture
def mock_param_parser():
    mock = Mock(spec=ParamParserService)
    mock.parse_room.return_value = ParseResult(
        value=1, confidence=1.0, matched_by='direct', raw_input='1'
    )
    mock.parse_room_type.return_value = ParseResult(
        value=1, confidence=1.0, matched_by='direct', raw_input='1'
    )
    return mock


@pytest.fixture
def mock_param_parser_low_conf():
    mock = Mock(spec=ParamParserService)
    mock.parse_room.return_value = ParseResult(
        value=None, confidence=0.5, matched_by='fuzzy', raw_input='abc',
        candidates=[{'id': 1, 'room_number': '101'}]
    )
    mock.parse_room_type.return_value = ParseResult(
        value=None, confidence=0.3, matched_by='fuzzy', raw_input='xyz',
        candidates=[{'id': 1, 'name': '标间'}]
    )
    return mock


# ============== Bill Actions: _enhance_bill_params + exception paths ==============

class TestBillActionsEnhanceParams:
    """Test the _enhance_bill_params function and exception paths."""

    def test_enhance_bill_params_with_room_number(self, mock_db):
        """Cover lines 21-27: _enhance_bill_params resolves room_number."""
        from app.hotel.actions.bill_actions import _enhance_bill_params

        mock_stay = Mock()
        mock_stay.id = 42

        with patch('app.hotel.services.checkin_service.CheckInService') as MockSvc:
            MockSvc.return_value.search_active_stays.return_value = [mock_stay]
            params = {"room_number": "201"}
            result = _enhance_bill_params(params, mock_db)

        assert result["stay_record_id"] == 42

    def test_enhance_bill_params_no_stays_found(self, mock_db):
        """Cover _enhance_bill_params when no stays found for room_number."""
        from app.hotel.actions.bill_actions import _enhance_bill_params

        with patch('app.hotel.services.checkin_service.CheckInService') as MockSvc:
            MockSvc.return_value.search_active_stays.return_value = []
            params = {"room_number": "999"}
            result = _enhance_bill_params(params, mock_db)

        assert "stay_record_id" not in result

    def test_enhance_bill_params_skip_when_bill_id_present(self, mock_db):
        """_enhance_bill_params should not resolve when bill_id already present."""
        from app.hotel.actions.bill_actions import _enhance_bill_params
        params = {"room_number": "201", "bill_id": 5}
        result = _enhance_bill_params(params, mock_db)
        assert result["bill_id"] == 5

    def test_add_payment_generic_exception(self, mock_db, mock_user):
        """Cover lines 118-120: generic exception in add_payment."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_service = MagicMock()
        mock_service.add_payment.side_effect = RuntimeError("DB connection lost")

        params = AddPaymentParams(bill_id=1, amount="200", payment_method="cash")

        with patch('app.hotel.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("add_payment")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_adjust_bill_by_stay_record_id(self, mock_db, mock_user):
        """Cover lines 155-164: adjust_bill resolves stay_record_id."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_bill = Mock(spec=Bill)
        mock_bill.id = 10
        mock_bill.stay_record_id = 5
        mock_bill.total_amount = Decimal("500.00")
        mock_bill.paid_amount = Decimal("100.00")
        mock_bill.adjustment_amount = Decimal("-50.00")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_bill
        mock_service = MagicMock()
        mock_service.adjust_bill.return_value = mock_bill

        params = AdjustBillParams(stay_record_id=5, amount="-50", reason="折扣")

        with patch('app.hotel.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("adjust_bill")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_adjust_bill_stay_not_found(self, mock_db, mock_user):
        """Cover adjust_bill when stay_record_id has no bill."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = AdjustBillParams(stay_record_id=999, amount="-50", reason="折扣")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("adjust_bill")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_adjust_bill_generic_exception(self, mock_db, mock_user):
        """Cover lines 195-197: generic exception in adjust_bill."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_service = MagicMock()
        mock_service.adjust_bill.side_effect = RuntimeError("DB error")

        params = AdjustBillParams(bill_id=1, amount="-50", reason="test")

        with patch('app.hotel.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("adjust_bill")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_refund_paid_amount_goes_negative(self, mock_db, mock_user):
        """Cover line 255: bill.paid_amount < 0 set to 0."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_bill = Mock(spec=Bill)
        mock_bill.id = 1
        mock_bill.paid_amount = Decimal("50.00")
        mock_bill.is_settled = True

        mock_payment = Mock(spec=Payment)
        mock_payment.id = 1
        mock_payment.bill_id = 1
        mock_payment.amount = Decimal("200.00")
        mock_payment.method = PaymentMethod.CASH
        mock_payment.bill = mock_bill

        mock_db.query.return_value.filter.return_value.first.return_value = mock_payment
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        params = RefundPaymentParams(payment_id=1, reason="退全额")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("refund_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        # paid_amount should be clamped to 0
        assert mock_bill.paid_amount == Decimal('0')

    def test_refund_generic_exception(self, mock_db, mock_user):
        """Cover lines 269-271: generic exception in refund_payment."""
        import app.hotel.actions.bill_actions as bill_actions

        mock_db.query.return_value.filter.return_value.first.side_effect = RuntimeError("boom")

        params = RefundPaymentParams(payment_id=1, reason="test")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("refund_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"


# ============== Reservation Actions: _enhance_reservation_params + exception paths ==============

class TestReservationActionsEnhanceParams:
    """Test _enhance_reservation_params and uncovered paths in reservation actions."""

    def test_enhance_reservation_params_with_guest_name(self, mock_db):
        """Cover lines 27-33: _enhance_reservation_params resolves guest_name."""
        from app.hotel.actions.reservation_actions import _enhance_reservation_params

        mock_res = Mock()
        mock_res.id = 10
        mock_status = Mock()
        mock_status.value = "CONFIRMED"
        mock_res.status = mock_status

        with patch('app.hotel.actions.reservation_actions.ReservationService') as MockSvc:
            MockSvc.return_value.search_reservations.return_value = [mock_res]
            params = {"guest_name": "张三"}
            result = _enhance_reservation_params(params, mock_db)

        assert result["reservation_id"] == 10

    def test_enhance_reservation_params_no_confirmed(self, mock_db):
        """_enhance_reservation_params when no confirmed reservations found."""
        from app.hotel.actions.reservation_actions import _enhance_reservation_params

        mock_res = Mock()
        mock_status = Mock()
        mock_status.value = "CANCELLED"
        mock_res.status = mock_status

        with patch('app.hotel.actions.reservation_actions.ReservationService') as MockSvc:
            MockSvc.return_value.search_reservations.return_value = [mock_res]
            params = {"guest_name": "张三"}
            result = _enhance_reservation_params(params, mock_db)

        assert "reservation_id" not in result

    def test_create_reservation_low_confidence_room_type(self, mock_db, mock_user, mock_param_parser_low_conf):
        """Cover line 88: low confidence room type parsing."""
        import app.hotel.actions.reservation_actions as res_actions

        params = CreateReservationParams(
            guest_name="张三",
            guest_phone="13800138000",
            room_type_id="unknown_type",
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
        )

        with patch.object(res_actions, 'RoomService') as MockRoomSvc:
            MockRoomSvc.return_value.get_room_types.return_value = []
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("create_reservation")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser_low_conf
            )

        assert result["success"] is False
        assert result.get("requires_confirmation") is True

    def test_create_reservation_check_out_before_check_in(self, mock_db, mock_user, mock_param_parser):
        """Cover line 114: check_out_date <= check_in_date."""
        import app.hotel.actions.reservation_actions as res_actions

        ci = date.today() + timedelta(days=5)
        co = ci  # same day

        params = CreateReservationParams(
            guest_name="张三",
            guest_phone="13800138000",
            room_type_id="1",
            check_in_date=ci,
            check_out_date=co + timedelta(days=1),
        )
        # Override params dates to trigger the in-handler validation
        params_dict = params.model_dump()
        params_dict['check_in_date'] = ci
        params_dict['check_out_date'] = ci  # same day

        # We need the handler to see same-day dates. We build params manually with Mock.
        mock_params = Mock()
        mock_params.guest_name = "张三"
        mock_params.guest_phone = "13800138000"
        mock_params.guest_id_number = None
        mock_params.room_type_id = "1"
        mock_params.check_in_date = ci
        mock_params.check_out_date = ci  # same date triggers the validation
        mock_params.adult_count = 1
        mock_params.child_count = 0
        mock_params.room_count = 1
        mock_params.special_requests = None

        registry = ActionRegistry()
        res_actions.register_reservation_actions(registry)
        action = registry.get_action("create_reservation")
        result = action.handler(
            params=mock_params, db=mock_db, user=mock_user,
            param_parser=mock_param_parser
        )

        assert result["success"] is False
        assert "退房日期" in result["message"]

    def test_cancel_reservation_by_reservation_no(self, mock_db, mock_user):
        """Cover lines 276-277: resolve reservation by reservation_no."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_reservation.reservation_no = "RES001"
        mock_status = Mock()
        mock_status.value = "cancelled"
        mock_reservation.status = mock_status

        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation
        mock_service = MagicMock()
        mock_service.cancel_reservation.return_value = mock_reservation

        params = CancelReservationParams(reservation_no="RES001", reason="客人取消")

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("cancel_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_cancel_reservation_not_found(self, mock_db, mock_user):
        """Cover lines 282: reservation not found."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = CancelReservationParams(reservation_id=9999, reason="test")

        registry = ActionRegistry()
        res_actions.register_reservation_actions(registry)
        action = registry.get_action("cancel_reservation")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_cancel_reservation_value_error(self, mock_db, mock_user):
        """Cover lines 233-241: ValueError in cancel."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_reservation.reservation_no = "RES001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation

        mock_service = MagicMock()
        mock_service.cancel_reservation.side_effect = ValueError("不可取消")

        params = CancelReservationParams(reservation_id=5, reason="test")

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("cancel_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_cancel_reservation_generic_exception(self, mock_db, mock_user):
        """Cover lines 239-241: generic exception in cancel."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation

        mock_service = MagicMock()
        mock_service.cancel_reservation.side_effect = RuntimeError("boom")

        params = CancelReservationParams(reservation_id=5, reason="test")

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("cancel_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_modify_reservation_by_reservation_no(self, mock_db, mock_user):
        """Cover lines 293-299: modify reservation by reservation_no with various fields."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_reservation.reservation_no = "RES001"
        mock_reservation.check_in_date = date.today() + timedelta(days=2)
        mock_reservation.check_out_date = date.today() + timedelta(days=5)
        mock_status = Mock()
        mock_status.value = "confirmed"
        mock_reservation.status = mock_status

        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation
        mock_service = MagicMock()
        mock_service.update_reservation.return_value = mock_reservation

        params = ModifyReservationParams(
            reservation_no="RES001",
            check_in_date=date.today() + timedelta(days=3),
            check_out_date=date.today() + timedelta(days=6),
            room_type_id=2,
            adult_count=3,
            special_requests="高楼层",
        )

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("modify_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_modify_reservation_not_found(self, mock_db, mock_user):
        """Cover modify reservation not found."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = ModifyReservationParams(reservation_id=999, adult_count=2)

        registry = ActionRegistry()
        res_actions.register_reservation_actions(registry)
        action = registry.get_action("modify_reservation")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_modify_reservation_no_updates(self, mock_db, mock_user):
        """Cover lines: no update fields provided."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation

        params = ModifyReservationParams(reservation_id=5)

        registry = ActionRegistry()
        res_actions.register_reservation_actions(registry)
        action = registry.get_action("modify_reservation")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "no_updates"

    def test_modify_reservation_value_error(self, mock_db, mock_user):
        """Cover lines 321-329: ValueError in modify."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation

        mock_service = MagicMock()
        mock_service.update_reservation.side_effect = ValueError("日期无效")

        params = ModifyReservationParams(reservation_id=5, adult_count=3)

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("modify_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_modify_reservation_generic_exception(self, mock_db, mock_user):
        """Cover lines 327-329: generic exception in modify."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reservation

        mock_service = MagicMock()
        mock_service.update_reservation.side_effect = RuntimeError("DB error")

        params = ModifyReservationParams(reservation_id=5, adult_count=2)

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("modify_reservation")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_create_reservation_generic_exception(self, mock_db, mock_user, mock_param_parser):
        """Cover create_reservation generic exception path."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_service = MagicMock()
        mock_service.create_reservation.side_effect = RuntimeError("DB error")

        params = CreateReservationParams(
            guest_name="张三",
            guest_phone="13800138000",
            room_type_id="1",
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
        )

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("create_reservation")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_create_reservation_value_error(self, mock_db, mock_user, mock_param_parser):
        """Cover create_reservation ValueError path."""
        import app.hotel.actions.reservation_actions as res_actions

        mock_service = MagicMock()
        mock_service.create_reservation.side_effect = ValueError("房型已满")

        params = CreateReservationParams(
            guest_name="张三",
            guest_phone="13800138000",
            room_type_id="1",
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
        )

        with patch('app.hotel.actions.reservation_actions.ReservationService', return_value=mock_service):
            registry = ActionRegistry()
            res_actions.register_reservation_actions(registry)
            action = registry.get_action("create_reservation")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "business_error"


# ============== Stay Actions: _enhance_stay_params + exception paths ==============

class TestStayActionsExtra:
    """Test uncovered paths in stay actions."""

    def test_enhance_stay_params_with_guest_name(self, mock_db):
        """Cover lines 24-29: _enhance_stay_params resolves guest_name."""
        from app.hotel.actions.stay_actions import _enhance_stay_params

        mock_stay = Mock()
        mock_stay.id = 55

        with patch('app.hotel.actions.stay_actions.CheckInService') as MockSvc:
            MockSvc.return_value.search_active_stays.return_value = [mock_stay]
            params = {"guest_name": "张三"}
            result = _enhance_stay_params(params, mock_db)

        assert result["stay_record_id"] == 55

    def test_enhance_stay_params_no_stays_found(self, mock_db):
        """_enhance_stay_params when no active stays found."""
        from app.hotel.actions.stay_actions import _enhance_stay_params

        with patch('app.hotel.actions.stay_actions.CheckInService') as MockSvc:
            MockSvc.return_value.search_active_stays.return_value = []
            params = {"guest_name": "不存在"}
            result = _enhance_stay_params(params, mock_db)

        assert "stay_record_id" not in result

    def test_checkout_generic_exception(self, mock_db, mock_user):
        """Cover line 174: generic exception in checkout."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_service = MagicMock()
        mock_service.check_out.side_effect = RuntimeError("boom")

        params = CheckoutParams(stay_record_id=1)

        with patch('app.hotel.actions.stay_actions.CheckOutService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("checkout")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_checkin_no_reservation_found(self, mock_db, mock_user):
        """Cover lines 187-201: checkin with no reservation found."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = CheckinParams(reservation_id=999, room_number="101")

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)
        action = registry.get_action("checkin")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_checkin_room_not_found(self, mock_db, mock_user):
        """Cover checkin when room_number not found."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 1
        mock_reservation.room_type_id = 1
        mock_reservation.reservation_no = "RES001"

        # First call returns reservation, second returns None (room not found)
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_reservation, None
        ]

        params = CheckinParams(reservation_id=1, room_number="999")

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)
        action = registry.get_action("checkin")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_checkin_auto_assign_no_available_room(self, mock_db, mock_user):
        """Cover lines 192-205: checkin without room_number and no available rooms."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 1
        mock_reservation.room_type_id = 1
        mock_reservation.reservation_no = "RES001"

        # First query returns reservation; second query (room) returns None
        def query_side_effect(*args):
            mock_q = Mock()
            mock_q.filter.return_value = mock_q
            if Reservation in args:
                mock_q.first.return_value = mock_reservation
            else:
                mock_q.first.return_value = None  # No available room
            return mock_q

        mock_db.query.side_effect = query_side_effect

        params = CheckinParams(reservation_id=1)

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)
        action = registry.get_action("checkin")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False

    def test_checkin_value_error(self, mock_db, mock_user):
        """Cover lines 224-232: ValueError in checkin."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 1
        mock_reservation.reservation_no = "RES001"

        mock_room = Mock(spec=Room)
        mock_room.id = 1

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_reservation, mock_room
        ]

        mock_service = MagicMock()
        mock_service.check_in_from_reservation.side_effect = ValueError("已入住")

        params = CheckinParams(reservation_id=1, room_number="101")

        with patch('app.hotel.actions.stay_actions.CheckInService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("checkin")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_checkin_generic_exception(self, mock_db, mock_user):
        """Cover lines 230-232: generic exception in checkin."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_reservation = Mock(spec=Reservation)
        mock_reservation.id = 1
        mock_reservation.reservation_no = "RES001"

        mock_room = Mock(spec=Room)
        mock_room.id = 1

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_reservation, mock_room
        ]

        mock_service = MagicMock()
        mock_service.check_in_from_reservation.side_effect = RuntimeError("DB error")

        params = CheckinParams(reservation_id=1, room_number="101")

        with patch('app.hotel.actions.stay_actions.CheckInService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("checkin")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_extend_stay_value_error(self, mock_db, mock_user):
        """Cover lines 273-281: ValueError in extend_stay."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_service = MagicMock()
        mock_service.extend_stay.side_effect = ValueError("日期无效")

        params = ExtendStayParams(
            stay_record_id=1,
            new_check_out_date=date.today() + timedelta(days=5)
        )

        with patch('app.hotel.actions.stay_actions.CheckInService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("extend_stay")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_extend_stay_generic_exception(self, mock_db, mock_user):
        """Cover lines 279-281: generic exception in extend_stay."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_service = MagicMock()
        mock_service.extend_stay.side_effect = RuntimeError("DB error")

        params = ExtendStayParams(
            stay_record_id=1,
            new_check_out_date=date.today() + timedelta(days=5)
        )

        with patch('app.hotel.actions.stay_actions.CheckInService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("extend_stay")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_change_room_not_found(self, mock_db, mock_user):
        """Cover change_room when room not found."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = ChangeRoomParams(stay_record_id=1, new_room_number="999")

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)
        action = registry.get_action("change_room")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_change_room_generic_exception(self, mock_db, mock_user):
        """Cover lines 339-341: generic exception in change_room."""
        import app.hotel.actions.stay_actions as stay_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.change_room.side_effect = RuntimeError("DB error")

        params = ChangeRoomParams(stay_record_id=1, new_room_number="102")

        with patch('app.hotel.actions.stay_actions.CheckInService', return_value=mock_service):
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)
            action = registry.get_action("change_room")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"


# ============== Room Actions: exception paths ==============

class TestRoomActionsExtra:
    """Test uncovered exception paths in room actions."""

    def test_update_room_status_generic_exception(self, mock_db, mock_user):
        """Cover lines 95-97: generic exception."""
        import app.hotel.actions.room_actions as room_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = RuntimeError("DB error")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_status")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_mark_room_clean_not_found(self, mock_db, mock_user):
        """Cover line 128: mark_room_clean room not found."""
        import app.hotel.actions.room_actions as room_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateRoomStatusParams(room_number="999", status="vacant_clean")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("mark_room_clean")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_mark_room_clean_value_error(self, mock_db, mock_user):
        """Cover lines 147-155: ValueError in mark_room_clean."""
        import app.hotel.actions.room_actions as room_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = ValueError("不能手动更改状态")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_clean")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_mark_room_clean_generic_exception(self, mock_db, mock_user):
        """Cover lines 153-155: generic exception in mark_room_clean."""
        import app.hotel.actions.room_actions as room_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = RuntimeError("boom")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_clean")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_mark_room_dirty_not_found(self, mock_db, mock_user):
        """Cover line 186: mark_room_dirty room not found."""
        import app.hotel.actions.room_actions as room_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateRoomStatusParams(room_number="888", status="vacant_dirty")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("mark_room_dirty")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_mark_room_dirty_value_error(self, mock_db, mock_user):
        """Cover lines 205-213: ValueError in mark_room_dirty."""
        import app.hotel.actions.room_actions as room_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = ValueError("状态错误")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_dirty")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_dirty")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_mark_room_dirty_generic_exception(self, mock_db, mock_user):
        """Cover lines 211-213: generic exception in mark_room_dirty."""
        import app.hotel.actions.room_actions as room_actions

        mock_room = Mock(spec=Room)
        mock_room.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room

        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = RuntimeError("boom")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_dirty")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_dirty")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_create_room_type_generic_exception(self, mock_db, mock_user):
        """Cover lines 263-265: generic exception in create_room_type."""
        import app.hotel.actions.room_actions as room_actions

        mock_service = MagicMock()
        mock_service.create_room_type.side_effect = RuntimeError("DB error")

        params = CreateRoomTypeParams(name="TestType", base_price="399")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("create_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_update_room_type_by_name(self, mock_db, mock_user):
        """Cover lines 318, 322: update room type by name."""
        import app.hotel.actions.room_actions as room_actions

        mock_rt = Mock(spec=RoomType)
        mock_rt.id = 3
        mock_rt.name = "标间"
        mock_rt.base_price = Decimal("288.00")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_rt

        mock_service = MagicMock()
        mock_service.update_room_type.return_value = mock_rt

        params = UpdateRoomTypeParams(room_type_name="标间", name="标准间")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_update_room_type_name_not_found(self, mock_db, mock_user):
        """Cover update_room_type when name not found."""
        import app.hotel.actions.room_actions as room_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateRoomTypeParams(room_type_name="不存在的房型", name="new")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_update_room_type_no_updates(self, mock_db, mock_user):
        """Cover update_room_type with no fields to update."""
        import app.hotel.actions.room_actions as room_actions

        params = UpdateRoomTypeParams(room_type_id=1)

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "no_updates"

    def test_update_room_type_generic_exception(self, mock_db, mock_user):
        """Cover lines 342-350: generic exception in update_room_type."""
        import app.hotel.actions.room_actions as room_actions

        mock_service = MagicMock()
        mock_service.update_room_type.side_effect = RuntimeError("DB error")

        params = UpdateRoomTypeParams(room_type_id=1, name="newname")

        with patch('app.hotel.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_update_room_type_missing_identifier(self, mock_db, mock_user):
        """Cover update_room_type with no ID or name."""
        import app.hotel.actions.room_actions as room_actions

        params = UpdateRoomTypeParams(name="new")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "missing_identifier"


# ============== Guest Actions: uncovered paths ==============

class TestGuestActionsExtra:
    """Test uncovered paths in guest actions."""

    def test_update_guest_not_found_by_id(self, mock_db, mock_user):
        """Cover lines 177-179: guest not found by ID."""
        import app.hotel.actions.guest_actions as guest_actions

        with patch('app.hotel.services.guest_service.GuestService') as MockGuestSvc:
            MockGuestSvc.return_value.get_guest.return_value = None

            params = UpdateGuestParams(guest_id=999, phone="13900139000")

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("update_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_update_guest_multiple_candidates(self, mock_db, mock_user):
        """Cover lines 202-206: multiple candidates found by name."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_guest1 = Mock(spec=Guest)
        mock_guest1.id = 1
        mock_guest1.name = "张三"
        mock_guest1.phone = "13800001"

        mock_guest2 = Mock(spec=Guest)
        mock_guest2.id = 2
        mock_guest2.name = "张三丰"
        mock_guest2.phone = "13800002"

        # First query (exact match) returns empty, second (like) returns two
        call_count = [0]

        def filter_side_effect(*args, **kwargs):
            mock_q = Mock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_q.all.return_value = []
            else:
                mock_q.all.return_value = [mock_guest1, mock_guest2]
            return mock_q

        mock_db.query.return_value.filter.side_effect = filter_side_effect

        with patch('app.hotel.services.guest_service.GuestService') as MockGuestSvc:
            params = UpdateGuestParams(guest_name="张三", phone="13900000000")

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("update_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert "requires_confirmation" in result

    def test_update_guest_missing_identifier(self, mock_db, mock_user):
        """Cover line 216: no guest_id or guest_name provided."""
        import app.hotel.actions.guest_actions as guest_actions

        params = UpdateGuestParams(phone="13900000000")

        registry = ActionRegistry()
        guest_actions.register_guest_actions(registry)
        action = registry.get_action("update_guest")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "missing_identifier"

    def test_update_guest_no_updates(self, mock_db, mock_user):
        """Cover line 231: no update fields."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_guest = Mock(spec=Guest)
        mock_guest.id = 1
        mock_guest.name = "张三"

        with patch('app.hotel.services.guest_service.GuestService') as MockGuestSvc:
            MockGuestSvc.return_value.get_guest.return_value = mock_guest

            params = UpdateGuestParams(guest_id=1)

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("update_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "no_updates"

    def test_update_guest_constraint_rejection(self, mock_db, mock_user):
        """Cover line 274: constraint engine rejection."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_guest = Mock(spec=Guest)
        mock_guest.id = 1
        mock_guest.name = "张三"
        mock_guest.phone = "13800138000"

        mock_decision = Mock()
        mock_decision.allowed = False
        mock_decision.to_response_dict.return_value = {
            "success": False,
            "message": "号码格式不对",
            "error": "constraint_violation"
        }

        with patch('app.hotel.services.guest_service.GuestService') as MockGuestSvc, \
             patch('core.reasoning.constraint_engine.ConstraintEngine') as MockCE, \
             patch('app.services.actions.get_action_registry') as MockGetReg:
            MockGuestSvc.return_value.get_guest.return_value = mock_guest
            mock_ontology = Mock()
            mock_reg = Mock()
            mock_reg._ontology_registry = mock_ontology
            MockGetReg.return_value = mock_reg
            MockCE.return_value.validate_property_update.return_value = mock_decision

            params = UpdateGuestParams(guest_id=1, phone="invalid")

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("update_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False

    def test_update_guest_exception(self, mock_db, mock_user):
        """Cover lines 300-302: generic exception in update_guest."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_guest = Mock(spec=Guest)
        mock_guest.id = 1
        mock_guest.name = "张三"
        mock_guest.phone = "13800138000"

        mock_decision = Mock()
        mock_decision.allowed = True

        with patch('app.hotel.services.guest_service.GuestService') as MockGuestSvc, \
             patch('core.reasoning.constraint_engine.ConstraintEngine') as MockCE, \
             patch('app.services.actions.get_action_registry') as MockGetReg:
            MockGuestSvc.return_value.get_guest.return_value = mock_guest
            MockGuestSvc.return_value.update_guest.side_effect = RuntimeError("DB error")
            mock_ontology = Mock()
            mock_reg = Mock()
            mock_reg._ontology_registry = mock_ontology
            MockGetReg.return_value = mock_reg
            MockCE.return_value.validate_property_update.return_value = mock_decision

            params = UpdateGuestParams(guest_id=1, phone="13900139000")

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("update_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_create_guest_duplicate_phone(self, mock_db, mock_user):
        """Cover line 337: duplicate phone in create_guest."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_existing = Mock(spec=Guest)
        mock_existing.name = "已有客人"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        params = CreateGuestParams(name="新客人", phone="13800138000")

        registry = ActionRegistry()
        guest_actions.register_guest_actions(registry)
        action = registry.get_action("create_guest")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "duplicate"

    def test_create_guest_generic_exception(self, mock_db, mock_user):
        """Cover lines 360-362: generic exception in create_guest."""
        import app.hotel.actions.guest_actions as guest_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch('app.hotel.services.guest_service.GuestService') as MockSvc:
            MockSvc.return_value.create_guest.side_effect = RuntimeError("DB error")

            params = CreateGuestParams(name="新客人", phone="13900139999")

            registry = ActionRegistry()
            guest_actions.register_guest_actions(registry)
            action = registry.get_action("create_guest")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"


# ============== Employee Actions: exception paths ==============

class TestEmployeeActionsExtra:
    """Test uncovered exception paths in employee actions."""

    def test_create_employee_generic_exception(self, mock_db, mock_user):
        """Cover lines 80-82: generic exception in create_employee."""
        import app.hotel.actions.employee_actions as emp_actions

        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.side_effect = RuntimeError("DB error")

        params = CreateEmployeeParams(
            username="new_emp", name="新员工", role="receptionist"
        )

        registry = ActionRegistry()
        emp_actions.register_employee_actions(registry)
        action = registry.get_action("create_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_update_employee_generic_exception(self, mock_db, mock_user):
        """Cover lines 145-147: generic exception in update_employee."""
        import app.hotel.actions.employee_actions as emp_actions

        # Make the query itself raise an exception
        mock_db.query.side_effect = RuntimeError("DB error")

        params = UpdateEmployeeParams(employee_id=1, name="new_name")

        registry = ActionRegistry()
        emp_actions.register_employee_actions(registry)
        action = registry.get_action("update_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_deactivate_employee_generic_exception(self, mock_db, mock_user):
        """Cover lines 201-203: generic exception in deactivate_employee."""
        import app.hotel.actions.employee_actions as emp_actions

        mock_db.query.side_effect = RuntimeError("DB error")

        params = DeactivateEmployeeParams(employee_id=1)

        registry = ActionRegistry()
        emp_actions.register_employee_actions(registry)
        action = registry.get_action("deactivate_employee")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "execution_error"


# ============== Price Actions: uncovered paths ==============

class TestPriceActionsExtra:
    """Test uncovered paths in price actions."""

    def test_update_price_low_confidence(self, mock_db, mock_user, mock_param_parser_low_conf):
        """Cover line 77: low confidence room type in update_price."""
        import app.hotel.actions.price_actions as price_actions

        params = UpdatePriceParams(room_type="unknown", price=Decimal("300"))

        registry = ActionRegistry()
        price_actions.register_price_actions(registry)
        action = registry.get_action("update_price")
        result = action.handler(
            params=params, db=mock_db, user=mock_user,
            param_parser=mock_param_parser_low_conf
        )

        assert result["success"] is False
        assert result.get("requires_confirmation") is True

    def test_update_price_room_type_not_found(self, mock_db, mock_user, mock_param_parser):
        """Cover line 92: room type not found."""
        import app.hotel.actions.price_actions as price_actions

        with patch('app.hotel.services.room_service.RoomService') as MockRoomSvc, \
             patch('app.hotel.services.price_service.PriceService'):
            MockRoomSvc.return_value.get_room_type.return_value = None

            params = UpdatePriceParams(room_type="1", price=Decimal("300"))

            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("update_price")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False

    def test_update_price_existing_rate_plan(self, mock_db, mock_user, mock_param_parser):
        """Cover lines 124-127: update existing rate plan."""
        import app.hotel.actions.price_actions as price_actions

        mock_rt = Mock()
        mock_rt.id = 1
        mock_rt.name = "标间"
        mock_rt.base_price = Decimal("288.00")

        mock_existing_plan = Mock()
        mock_existing_plan.id = 5

        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_plan

        with patch('app.hotel.services.room_service.RoomService') as MockRoomSvc, \
             patch('app.hotel.services.price_service.PriceService') as MockPriceSvc:
            MockRoomSvc.return_value.get_room_type.return_value = mock_rt

            params = UpdatePriceParams(
                room_type="1", price=Decimal("350"),
                update_type="rate_plan", price_type="weekend"
            )

            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("update_price")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        assert "周末" in result["message"]

    def test_create_rate_plan_low_confidence(self, mock_db, mock_user, mock_param_parser_low_conf):
        """Cover line 203: low confidence in create_rate_plan."""
        import app.hotel.actions.price_actions as price_actions

        params = CreateRatePlanParams(
            room_type="unknown", price=Decimal("300"),
            start_date=date.today(), end_date=date.today() + timedelta(days=30)
        )

        with patch('app.hotel.services.room_service.RoomService'), \
             patch('app.hotel.services.price_service.PriceService'):
            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("create_rate_plan")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser_low_conf
            )

        assert result["success"] is False
        assert result.get("requires_confirmation") is True

    def test_create_rate_plan_room_type_not_found(self, mock_db, mock_user, mock_param_parser):
        """Cover line 216: room type not found in create_rate_plan."""
        import app.hotel.actions.price_actions as price_actions

        with patch('app.hotel.services.room_service.RoomService') as MockRoomSvc, \
             patch('app.hotel.services.price_service.PriceService'):
            MockRoomSvc.return_value.get_room_type.return_value = None

            params = CreateRatePlanParams(
                room_type="1", price=Decimal("300"),
                start_date=date.today(), end_date=date.today() + timedelta(days=30)
            )

            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("create_rate_plan")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False

    def test_create_rate_plan_value_error(self, mock_db, mock_user, mock_param_parser):
        """Cover lines 241-249: ValueError in create_rate_plan."""
        import app.hotel.actions.price_actions as price_actions

        mock_rt = Mock()
        mock_rt.id = 1
        mock_rt.name = "标间"

        with patch('app.hotel.services.room_service.RoomService') as MockRoomSvc, \
             patch('app.hotel.services.price_service.PriceService') as MockPriceSvc:
            MockRoomSvc.return_value.get_room_type.return_value = mock_rt
            MockPriceSvc.return_value.create_rate_plan.side_effect = ValueError("重复策略")

            params = CreateRatePlanParams(
                room_type="1", price=Decimal("300"),
                start_date=date.today(), end_date=date.today() + timedelta(days=30)
            )

            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("create_rate_plan")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_create_rate_plan_generic_exception(self, mock_db, mock_user, mock_param_parser):
        """Cover lines 247-249: generic exception in create_rate_plan."""
        import app.hotel.actions.price_actions as price_actions

        mock_rt = Mock()
        mock_rt.id = 1
        mock_rt.name = "标间"

        with patch('app.hotel.services.room_service.RoomService') as MockRoomSvc, \
             patch('app.hotel.services.price_service.PriceService') as MockPriceSvc:
            MockRoomSvc.return_value.get_room_type.return_value = mock_rt
            MockPriceSvc.return_value.create_rate_plan.side_effect = RuntimeError("DB error")

            params = CreateRatePlanParams(
                room_type="1", price=Decimal("300"),
                start_date=date.today(), end_date=date.today() + timedelta(days=30)
            )

            registry = ActionRegistry()
            price_actions.register_price_actions(registry)
            action = registry.get_action("create_rate_plan")
            result = action.handler(
                params=params, db=mock_db, user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "execution_error"
