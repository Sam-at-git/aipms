"""
app/services/actions/bill_actions.py

Billing-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.hotel.models.ontology import Employee, Payment, PaymentMethod
from app.hotel.actions.base import AddPaymentParams, AdjustBillParams, RefundPaymentParams

import logging

logger = logging.getLogger(__name__)


def _enhance_bill_params(params: Dict[str, Any], db) -> Dict[str, Any]:
    """Enhance bill action params: resolve room_number → stay_record_id."""
    if "room_number" in params and "stay_record_id" not in params and "bill_id" not in params:
        from app.hotel.services.checkin_service import CheckInService
        checkin_svc = CheckInService(db)
        stays = checkin_svc.search_active_stays(params["room_number"])
        if stays:
            params["stay_record_id"] = stays[0].id
    return params


def register_bill_actions(
    registry: ActionRegistry
) -> None:
    """Register all billing-related actions."""

    @registry.register(
        name="add_payment",
        entity="Bill",
        description="添加支付记录。支持现金(cash)和刷卡(card)支付方式。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["adds_payment", "may_settle_bill"],
        search_keywords=["付款", "支付", "收款", "缴费", "add payment", "pay"],
        risk_level="high",
        is_financial=True,
    )
    def handle_add_payment(
        params: AddPaymentParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """添加支付记录"""
        from app.hotel.models.schemas import PaymentCreate
        from app.hotel.services.billing_service import BillingService
        from app.hotel.models.ontology import Bill

        try:
            # Resolve bill: by bill_id or stay_record_id
            bill_id = params.bill_id
            if not bill_id and params.stay_record_id:
                bill = db.query(Bill).filter(
                    Bill.stay_record_id == params.stay_record_id
                ).first()
                if not bill:
                    return {
                        "success": False,
                        "message": f"住宿记录 {params.stay_record_id} 没有关联账单",
                        "error": "not_found"
                    }
                bill_id = bill.id

            if not bill_id:
                return {
                    "success": False,
                    "message": "请提供账单ID或住宿记录ID",
                    "error": "missing_identifier"
                }

            # Parse payment method
            method_map = {
                'cash': PaymentMethod.CASH,
                'card': PaymentMethod.CARD,
                '现金': PaymentMethod.CASH,
                '刷卡': PaymentMethod.CARD,
            }
            method = method_map.get(params.payment_method.lower().strip())
            if not method:
                return {
                    "success": False,
                    "message": f"不支持的支付方式: {params.payment_method}. 支持: cash, card",
                    "error": "validation_error"
                }

            payment_data = PaymentCreate(
                bill_id=bill_id,
                amount=params.amount,
                method=method
            )
            service = BillingService(db)
            payment = service.add_payment(payment_data, user.id)

            return {
                "success": True,
                "message": f"支付 ¥{payment.amount} 成功（{method.value}）",
                "payment_id": payment.id,
                "bill_id": payment.bill_id,
                "amount": float(payment.amount),
                "method": payment.method.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in add_payment: {e}")
            return {
                "success": False,
                "message": f"支付失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="adjust_bill",
        entity="Bill",
        description="调整账单金额。支持加价（正数）和减价（负数）。需要提供调整原因。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["adjusts_bill"],
        search_keywords=["调整账单", "账单调整", "折扣", "加价", "adjust bill"],
        risk_level="critical",
        is_financial=True,
        param_enhancer=_enhance_bill_params,
    )
    def handle_adjust_bill(
        params: AdjustBillParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """调整账单金额"""
        from app.hotel.models.schemas import BillAdjustment
        from app.hotel.services.billing_service import BillingService
        from app.hotel.models.ontology import Bill

        try:
            # Resolve bill
            bill_id = params.bill_id
            if not bill_id and params.stay_record_id:
                bill = db.query(Bill).filter(
                    Bill.stay_record_id == params.stay_record_id
                ).first()
                if not bill:
                    return {
                        "success": False,
                        "message": f"住宿记录 {params.stay_record_id} 没有关联账单",
                        "error": "not_found"
                    }
                bill_id = bill.id

            if not bill_id:
                return {
                    "success": False,
                    "message": "请提供账单ID或住宿记录ID",
                    "error": "missing_identifier"
                }

            adjustment_data = BillAdjustment(
                bill_id=bill_id,
                adjustment_amount=params.amount,
                reason=params.reason
            )
            service = BillingService(db)
            bill = service.adjust_bill(adjustment_data, user.id)

            return {
                "success": True,
                "message": f"账单已调整 ¥{params.amount}，原因：{params.reason}",
                "bill_id": bill.id,
                "total_amount": float(bill.total_amount),
                "adjustment_amount": float(bill.adjustment_amount),
                "paid_amount": float(bill.paid_amount)
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in adjust_bill: {e}")
            return {
                "success": False,
                "message": f"调整账单失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="refund_payment",
        entity="Payment",
        description="退款。对已有支付记录进行全额或部分退款。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["creates_refund_payment"],
        risk_level="high",
        is_financial=True,
        search_keywords=["退款", "退钱", "refund"]
    )
    def handle_refund_payment(
        params: RefundPaymentParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """退款"""
        try:
            # Find original payment
            original = db.query(Payment).filter(Payment.id == params.payment_id).first()
            if not original:
                return {
                    "success": False,
                    "message": f"支付记录 {params.payment_id} 不存在",
                    "error": "not_found"
                }

            refund_amount = params.amount if params.amount else original.amount
            if refund_amount > original.amount:
                return {
                    "success": False,
                    "message": f"退款金额 ¥{refund_amount} 超过原支付金额 ¥{original.amount}",
                    "error": "validation_error"
                }

            # Create negative payment as refund
            refund = Payment(
                bill_id=original.bill_id,
                amount=-refund_amount,
                method=original.method,
                remark=f"退款: {params.reason}（原支付ID: {original.id}）",
                created_by=user.id
            )
            db.add(refund)

            # Update bill paid_amount
            bill = original.bill
            bill.paid_amount -= refund_amount
            if bill.paid_amount < 0:
                bill.paid_amount = Decimal('0')
            bill.is_settled = False

            db.commit()
            db.refresh(refund)

            return {
                "success": True,
                "message": f"已退款 ¥{refund_amount}，原因：{params.reason}",
                "refund_payment_id": refund.id,
                "original_payment_id": original.id,
                "refund_amount": float(refund_amount),
                "bill_id": bill.id
            }
        except Exception as e:
            logger.error(f"Error in refund_payment: {e}")
            return {
                "success": False,
                "message": f"退款失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_bill_actions"]
