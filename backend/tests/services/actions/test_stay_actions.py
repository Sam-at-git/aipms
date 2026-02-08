"""
tests/services/actions/test_stay_actions.py

Tests for stay action handlers in app/services/actions/stay_actions.py
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

import app.services.actions.stay_actions as stay_actions
from app.services.actions.base import CheckoutParams
from app.models.ontology import Employee, EmployeeRole, Guest, Room, Bill, StayRecord
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
    return parser


@pytest.fixture
def sample_guest():
    """Sample guest"""
    guest = Mock(spec=Guest)
    guest.id = 1
    guest.name = "张三"
    return guest


@pytest.fixture
def sample_room():
    """Sample room"""
    room = Mock(spec=Room)
    room.id = 101
    room.room_number = "101"
    return room


@pytest.fixture
def sample_bill():
    """Sample bill"""
    bill = Mock(spec=Bill)
    bill.id = 1
    bill.total_amount = Decimal("500.00")
    bill.adjustment_amount = Decimal("0.00")
    bill.paid_amount = Decimal("200.00")
    return bill


@pytest.fixture
def sample_stay(sample_guest, sample_room, sample_bill):
    """Sample stay record"""
    stay = Mock(spec=StayRecord)
    stay.id = 1
    stay.guest = sample_guest
    stay.room = sample_room
    stay.room_id = sample_room.id
    stay.check_out_time = "2026-02-07T14:00:00"
    stay.bill = sample_bill
    return stay


# ==================== register_stay_actions Tests ====================

class TestRegisterStayActions:
    """Test register_stay_actions function"""

    def test_register_stay_actions(self):
        """Test that register_stay_actions registers checkout action"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)

        action = registry.get_action("checkout")
        assert action is not None
        assert action.name == "checkout"
        assert action.entity == "StayRecord"
        assert action.category == "mutation"
        assert action.requires_confirmation is True
        assert "receptionist" in action.allowed_roles
        assert action.undoable is True


# ==================== handle_checkout Tests ====================

class TestHandleCheckout:
    """Test handle_checkout handler via ActionRegistry"""

    @pytest.fixture
    def checkout_action(self, mock_db, mock_user, mock_param_parser, sample_stay):
        """Fixture that provides the checkout action handler"""
        def execute_checkout(params):
            mock_checkout_service = MagicMock()
            mock_checkout_service.check_out.return_value = sample_stay

            with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
                from core.ai.actions import ActionRegistry
                registry = ActionRegistry()
                stay_actions.register_stay_actions(registry)

                action_def = registry.get_action("checkout")
                return action_def.handler(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )
        return execute_checkout

    def test_successful_checkout_default_params(
        self, checkout_action, sample_stay
    ):
        """Test successful checkout with default parameters"""
        params = CheckoutParams(stay_record_id=1)

        result = checkout_action(params)

        assert result["success"] is True
        assert result["stay_record_id"] == sample_stay.id

    def test_successful_checkout_with_refund(
        self, checkout_action
    ):
        """Test successful checkout with refund deposit"""
        params = CheckoutParams(
            stay_record_id=1,
            refund_deposit=Decimal("100.50")
        )

        result = checkout_action(params)

        assert result["success"] is True

    def test_successful_checkout_unsettled(
        self, mock_db, mock_user, mock_param_parser, sample_stay
    ):
        """Test successful checkout with unsettled amount allowed"""
        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.return_value = sample_stay

        params = CheckoutParams(
            stay_record_id=1,
            allow_unsettled=True,
            unsettled_reason="客人稍后在线支付"
        )

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True

    def test_checkout_with_balance_due(
        self, mock_db, mock_user, mock_param_parser, sample_stay, sample_bill
    ):
        """Test checkout message includes balance when due"""
        sample_bill.total_amount = Decimal("500.00")
        sample_bill.paid_amount = Decimal("200.00")

        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.return_value = sample_stay

        params = CheckoutParams(stay_record_id=1)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        assert "账单余额" in result["message"]

    def test_checkout_no_bill(
        self, mock_db, mock_user, mock_param_parser, sample_stay
    ):
        """Test checkout when stay has no bill"""
        sample_stay.bill = None

        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.return_value = sample_stay

        params = CheckoutParams(stay_record_id=1)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        assert result["bill_id"] is None

    def test_checkout_validation_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test checkout with validation error returns error result"""
        from pydantic import ValidationError

        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.side_effect = ValidationError(
            [{"loc": ["stay_record_id"], "msg": "Stay record not found"}]
        )

        params = CheckoutParams(stay_record_id=999)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_checkout_business_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test checkout with business logic error returns error result"""
        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.side_effect = ValueError("住宿记录不存在")

        params = CheckoutParams(stay_record_id=999)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_checkout_generic_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test checkout with generic error returns error result"""
        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.side_effect = Exception("数据库错误")

        params = CheckoutParams(stay_record_id=1)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "execution_error"

    def test_checkout_without_param_parser(
        self, mock_db, mock_user, sample_stay
    ):
        """Test checkout works without param_parser (optional parameter)"""
        mock_checkout_service = MagicMock()
        mock_checkout_service.check_out.return_value = sample_stay

        params = CheckoutParams(stay_record_id=1)

        with patch('app.services.actions.stay_actions.CheckOutService', return_value=mock_checkout_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            stay_actions.register_stay_actions(registry)

            action_def = registry.get_action("checkout")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=None
            )

        assert result["success"] is True


# ==================== Integration Tests ====================

class TestStayActionsIntegration:
    """Integration tests for stay actions"""

    def test_action_registration_and_metadata(self):
        """Test checkout action registration and metadata"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)

        action = registry.get_action("checkout")
        assert action is not None
        assert "退房" in action.search_keywords
        assert "结算" in action.search_keywords

    def test_module_exports(self):
        """Test that stay_actions module exports correctly"""
        assert hasattr(stay_actions, "register_stay_actions")
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        stay_actions.register_stay_actions(registry)
        assert registry.get_action("checkout") is not None

    def test_module_all(self):
        """Test __all__ export"""
        assert "register_stay_actions" in stay_actions.__all__
