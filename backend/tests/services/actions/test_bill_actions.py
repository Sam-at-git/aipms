"""
tests/services/actions/test_bill_actions.py

Tests for billing action handlers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from sqlalchemy.orm import Session

import app.services.actions.bill_actions as bill_actions
from app.services.actions.base import AddPaymentParams, AdjustBillParams, RefundPaymentParams
from app.models.ontology import Employee, EmployeeRole, Bill, Payment, PaymentMethod


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "manager"
    user.role = EmployeeRole.MANAGER
    return user


@pytest.fixture
def sample_bill():
    bill = Mock(spec=Bill)
    bill.id = 1
    bill.stay_record_id = 10
    bill.total_amount = Decimal("500.00")
    bill.paid_amount = Decimal("200.00")
    bill.adjustment_amount = Decimal("0.00")
    bill.is_settled = False
    return bill


@pytest.fixture
def sample_payment(sample_bill):
    payment = Mock(spec=Payment)
    payment.id = 1
    payment.bill_id = sample_bill.id
    payment.amount = Decimal("200.00")
    payment.method = PaymentMethod.CASH
    payment.bill = sample_bill
    return payment


class TestRegisterBillActions:
    def test_registers_all_actions(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)

        assert registry.get_action("add_payment") is not None
        assert registry.get_action("adjust_bill") is not None
        assert registry.get_action("refund_payment") is not None

    def test_action_metadata(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)

        action = registry.get_action("add_payment")
        assert action.entity == "Bill"
        assert action.category == "billing"
        assert action.requires_confirmation is True


class TestHandleAddPayment:
    def test_successful_payment_by_bill_id(self, mock_db, mock_user, sample_payment):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.add_payment.return_value = sample_payment

        params = AddPaymentParams(bill_id=1, amount="200", payment_method="cash")

        with patch('app.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("add_payment")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert result["payment_id"] == 1

    def test_payment_by_stay_record_id(self, mock_db, mock_user, sample_payment, sample_bill):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_bill
        mock_service = MagicMock()
        mock_service.add_payment.return_value = sample_payment

        params = AddPaymentParams(stay_record_id=10, amount="200", payment_method="cash")

        with patch('app.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("add_payment")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_payment_missing_identifier(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        params = AddPaymentParams(amount="200", payment_method="cash")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("add_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "missing_identifier"

    def test_payment_invalid_method(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        params = AddPaymentParams(bill_id=1, amount="200", payment_method="bitcoin")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("add_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_payment_business_error(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.add_payment.side_effect = ValueError("账单已结清")

        params = AddPaymentParams(bill_id=1, amount="200", payment_method="cash")

        with patch('app.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("add_payment")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_payment_stay_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = AddPaymentParams(stay_record_id=999, amount="200", payment_method="cash")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("add_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"


class TestHandleAdjustBill:
    def test_successful_adjustment(self, mock_db, mock_user, sample_bill):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.adjust_bill.return_value = sample_bill

        params = AdjustBillParams(bill_id=1, amount="-50", reason="折扣优惠")

        with patch('app.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("adjust_bill")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert result["bill_id"] == 1

    def test_adjust_missing_identifier(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        params = AdjustBillParams(amount="-50", reason="折扣")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("adjust_bill")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "missing_identifier"

    def test_adjust_business_error(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.adjust_bill.side_effect = ValueError("账单不存在")

        params = AdjustBillParams(bill_id=999, amount="-50", reason="折扣")

        with patch('app.services.billing_service.BillingService', return_value=mock_service):
            registry = ActionRegistry()
            bill_actions.register_bill_actions(registry)
            action = registry.get_action("adjust_bill")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"


class TestHandleRefundPayment:
    def test_successful_full_refund(self, mock_db, mock_user, sample_payment, sample_bill):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_payment
        mock_refund = Mock()
        mock_refund.id = 2
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        params = RefundPaymentParams(payment_id=1, reason="客人投诉")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("refund_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert result["refund_amount"] == float(Decimal("200.00"))

    def test_refund_payment_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = RefundPaymentParams(payment_id=999, reason="退款")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("refund_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_refund_exceeds_original(self, mock_db, mock_user, sample_payment):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_payment

        params = RefundPaymentParams(payment_id=1, amount="500", reason="退款")

        registry = ActionRegistry()
        bill_actions.register_bill_actions(registry)
        action = registry.get_action("refund_payment")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "validation_error"


class TestBillActionsModule:
    def test_module_all(self):
        assert "register_bill_actions" in bill_actions.__all__
