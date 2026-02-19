"""
Tests for app/hotel/services/billing_service.py - increasing coverage.
Covers: add_payment, adjust_bill, get_bill_detail, get_payments_by_date,
calculate_daily_revenue, edge cases, settled bill handling.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, StayRecord, StayRecordStatus,
    Bill, Payment, PaymentMethod, Employee, EmployeeRole,
)
from app.hotel.models.schemas import PaymentCreate, BillAdjustment
from app.hotel.services.billing_service import BillingService


@pytest.fixture
def billing_service(db_session):
    """BillingService instance."""
    return BillingService(db_session)


@pytest.fixture
def active_stay_with_bill(db_session, sample_room, sample_guest):
    """Create an active stay with a bill."""
    sample_room.status = RoomStatus.OCCUPIED
    stay = StayRecord(
        guest_id=sample_guest.id,
        room_id=sample_room.id,
        check_in_time=datetime.now(),
        expected_check_out=date.today() + timedelta(days=1),
        status=StayRecordStatus.ACTIVE,
    )
    db_session.add(stay)
    db_session.flush()

    bill = Bill(
        stay_record_id=stay.id,
        total_amount=Decimal("500.00"),
        paid_amount=Decimal("0"),
        adjustment_amount=Decimal("0"),
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(stay)
    db_session.refresh(bill)
    return stay, bill


class TestAddPayment:
    """Test add_payment method."""

    def test_add_payment_cash(self, billing_service, active_stay_with_bill):
        """Add cash payment."""
        stay, bill = active_stay_with_bill
        data = PaymentCreate(
            bill_id=bill.id,
            amount=200.0,
            method="cash",
        )
        result = billing_service.add_payment(data, operator_id=1)
        assert result.amount == Decimal("200")
        assert result.method == PaymentMethod.CASH

    def test_add_payment_card(self, billing_service, active_stay_with_bill):
        """Add card payment."""
        stay, bill = active_stay_with_bill
        data = PaymentCreate(
            bill_id=bill.id,
            amount=300.0,
            method="card",
        )
        result = billing_service.add_payment(data, operator_id=1)
        assert result.method == PaymentMethod.CARD

    def test_add_payment_full_settlement(self, billing_service, db_session, active_stay_with_bill):
        """Full payment settles the bill."""
        stay, bill = active_stay_with_bill
        data = PaymentCreate(
            bill_id=bill.id,
            amount=500.0,
            method="cash",
        )
        billing_service.add_payment(data, operator_id=1)
        db_session.refresh(bill)
        assert bill.paid_amount == Decimal("500.00")
        assert bill.is_settled is True

    def test_add_payment_bill_not_found(self, billing_service):
        """Add payment to non-existent bill."""
        data = PaymentCreate(
            bill_id=99999,
            amount=100.0,
            method="cash",
        )
        with pytest.raises(ValueError, match="账单不存在"):
            billing_service.add_payment(data, operator_id=1)

    def test_add_payment_already_settled(self, billing_service, db_session, active_stay_with_bill):
        """Add payment to already settled bill raises ValueError."""
        stay, bill = active_stay_with_bill
        bill.is_settled = True
        db_session.commit()

        data = PaymentCreate(
            bill_id=bill.id,
            amount=100.0,
            method="cash",
        )
        with pytest.raises(ValueError, match="账单已结清"):
            billing_service.add_payment(data, operator_id=1)


class TestBillAdjustment:
    """Test adjust_bill method."""

    def test_adjust_bill_discount(self, billing_service, db_session, active_stay_with_bill):
        """Apply discount adjustment."""
        stay, bill = active_stay_with_bill
        data = BillAdjustment(
            bill_id=bill.id,
            adjustment_amount=-50.0,
            reason="VIP折扣",
        )
        result = billing_service.adjust_bill(data, operator_id=1)
        assert float(result.adjustment_amount) == -50.0
        assert result.adjustment_reason == "VIP折扣"

    def test_adjust_bill_surcharge(self, billing_service, db_session, active_stay_with_bill):
        """Apply surcharge adjustment."""
        stay, bill = active_stay_with_bill
        data = BillAdjustment(
            bill_id=bill.id,
            adjustment_amount=100.0,
            reason="迷你吧消费",
        )
        result = billing_service.adjust_bill(data, operator_id=1)
        assert float(result.adjustment_amount) == 100.0

    def test_adjust_bill_not_found(self, billing_service):
        """Adjust non-existent bill."""
        data = BillAdjustment(
            bill_id=99999,
            adjustment_amount=-50.0,
            reason="test",
        )
        with pytest.raises(ValueError, match="账单不存在"):
            billing_service.adjust_bill(data, operator_id=1)

    def test_adjust_bill_causes_settlement(self, billing_service, db_session, active_stay_with_bill):
        """Adjustment that makes total <= paid_amount settles the bill."""
        stay, bill = active_stay_with_bill
        # Pay 200 first
        bill.paid_amount = Decimal("200")
        db_session.commit()

        # Adjust by -300 so total 500 + (-300) = 200, which equals paid
        data = BillAdjustment(
            bill_id=bill.id,
            adjustment_amount=-300.0,
            reason="大幅折扣",
        )
        result = billing_service.adjust_bill(data, operator_id=1)
        assert result.is_settled is True


class TestGetBill:
    """Test bill retrieval methods."""

    def test_get_bill(self, billing_service, active_stay_with_bill):
        """Get bill by id."""
        stay, bill = active_stay_with_bill
        result = billing_service.get_bill(bill.id)
        assert result is not None
        assert result.id == bill.id

    def test_get_bill_not_found(self, billing_service):
        """Get non-existent bill."""
        result = billing_service.get_bill(99999)
        assert result is None

    def test_get_bill_by_stay(self, billing_service, active_stay_with_bill):
        """Get bill by stay record id."""
        stay, bill = active_stay_with_bill
        result = billing_service.get_bill_by_stay(stay.id)
        assert result is not None
        assert result.id == bill.id

    def test_get_bill_by_stay_not_found(self, billing_service):
        """Get bill for non-existent stay."""
        result = billing_service.get_bill_by_stay(99999)
        assert result is None

    def test_get_bill_detail(self, billing_service, db_session, active_stay_with_bill):
        """Get bill detail includes payments."""
        stay, bill = active_stay_with_bill

        # Add a payment through service so paid_amount is updated
        data = PaymentCreate(
            bill_id=bill.id,
            amount=100.0,
            method="cash",
        )
        billing_service.add_payment(data, operator_id=1)

        detail = billing_service.get_bill_detail(bill.id)
        assert detail is not None
        assert detail["id"] == bill.id
        assert len(detail["payments"]) == 1
        assert float(detail["balance"]) == 400.0

    def test_get_bill_detail_not_found(self, billing_service):
        """Get detail of non-existent bill."""
        result = billing_service.get_bill_detail(99999)
        assert result is None


class TestRevenueCalculation:
    """Test revenue calculation methods."""

    def test_get_payments_by_date(self, billing_service, db_session, active_stay_with_bill):
        """Get payments by date range."""
        stay, bill = active_stay_with_bill
        payment = Payment(
            bill_id=bill.id,
            amount=Decimal("200.00"),
            method=PaymentMethod.CARD,
            payment_time=datetime.now(),
        )
        db_session.add(payment)
        db_session.commit()

        start = datetime.combine(date.today(), datetime.min.time())
        end = start + timedelta(days=1)
        payments = billing_service.get_payments_by_date(start, end)
        assert len(payments) == 1
        assert float(payments[0].amount) == 200.0

    def test_get_payments_by_date_empty(self, billing_service):
        """Get payments for empty date range."""
        far_future = datetime.combine(date.today() + timedelta(days=365), datetime.min.time())
        end = far_future + timedelta(days=1)
        payments = billing_service.get_payments_by_date(far_future, end)
        assert len(payments) == 0

    def test_calculate_daily_revenue(self, billing_service, db_session, active_stay_with_bill):
        """Calculate daily revenue."""
        stay, bill = active_stay_with_bill

        # Add cash payment
        cash_payment = Payment(
            bill_id=bill.id,
            amount=Decimal("300.00"),
            method=PaymentMethod.CASH,
            payment_time=datetime.now(),
        )
        # Add card payment
        card_payment = Payment(
            bill_id=bill.id,
            amount=Decimal("200.00"),
            method=PaymentMethod.CARD,
            payment_time=datetime.now(),
        )
        db_session.add_all([cash_payment, card_payment])
        db_session.commit()

        revenue = billing_service.calculate_daily_revenue(date.today())
        assert revenue["date"] == date.today()
        assert float(revenue["total"]) == 500.0
        assert float(revenue["cash"]) == 300.0
        assert float(revenue["card"]) == 200.0
        assert revenue["count"] == 2

    def test_calculate_daily_revenue_empty(self, billing_service):
        """Calculate daily revenue for date with no payments."""
        far_future = date.today() + timedelta(days=365)
        revenue = billing_service.calculate_daily_revenue(far_future)
        assert revenue["count"] == 0
        assert float(revenue["total"]) == 0
