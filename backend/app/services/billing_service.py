"""
账单服务 - 本体操作层
管理 Bill 和 Payment 对象
支持操作撤销：关键操作创建快照
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import Bill, Payment, StayRecord, PaymentMethod
from app.models.schemas import PaymentCreate, BillAdjustment
from app.models.snapshots import OperationType


class BillingService:
    """账单服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_bill(self, bill_id: int) -> Optional[Bill]:
        """获取账单"""
        return self.db.query(Bill).filter(Bill.id == bill_id).first()

    def get_bill_by_stay(self, stay_record_id: int) -> Optional[Bill]:
        """根据住宿记录获取账单"""
        return self.db.query(Bill).filter(Bill.stay_record_id == stay_record_id).first()

    def add_payment(self, data: PaymentCreate, operator_id: int) -> Payment:
        """添加支付记录"""
        bill = self.get_bill(data.bill_id)
        if not bill:
            raise ValueError("账单不存在")

        if bill.is_settled:
            raise ValueError("账单已结清")

        # 保存快照所需的旧状态
        old_paid_amount = float(bill.paid_amount)

        payment = Payment(
            bill_id=data.bill_id,
            amount=data.amount,
            method=data.method,
            remark=data.remark,
            created_by=operator_id
        )
        self.db.add(payment)
        self.db.flush()  # 获取 payment.id

        # 更新账单已付金额
        bill.paid_amount += data.amount

        # 检查是否结清
        balance = bill.total_amount + bill.adjustment_amount - bill.paid_amount
        if balance <= 0:
            bill.is_settled = True

        # 创建操作快照（用于撤销）
        from app.services.undo_service import UndoService
        undo_service = UndoService(self.db)
        undo_service.create_snapshot(
            operation_type=OperationType.ADD_PAYMENT,
            entity_type="payment",
            entity_id=payment.id,
            before_state={
                "bill": {
                    "id": bill.id,
                    "paid_amount": old_paid_amount
                }
            },
            after_state={
                "payment_id": payment.id,
                "bill_paid_amount": float(bill.paid_amount)
            },
            operator_id=operator_id
        )

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def adjust_bill(self, data: BillAdjustment, operator_id: int) -> Bill:
        """
        调整账单金额（需要人类确认 - HITL）
        仅经理有权限操作
        """
        bill = self.get_bill(data.bill_id)
        if not bill:
            raise ValueError("账单不存在")

        bill.adjustment_amount = data.adjustment_amount
        bill.adjustment_reason = data.reason

        # 重新检查结清状态
        balance = bill.total_amount + bill.adjustment_amount - bill.paid_amount
        bill.is_settled = (balance <= 0)

        self.db.commit()
        self.db.refresh(bill)
        return bill

    def get_bill_detail(self, bill_id: int) -> dict:
        """获取账单详情"""
        bill = self.get_bill(bill_id)
        if not bill:
            return None

        payments = []
        for p in bill.payments:
            payments.append({
                'id': p.id,
                'amount': p.amount,
                'method': p.method,
                'payment_time': p.payment_time,
                'remark': p.remark,
                'operator_name': p.operator.name if p.operator else None
            })

        balance = bill.total_amount + bill.adjustment_amount - bill.paid_amount

        return {
            'id': bill.id,
            'stay_record_id': bill.stay_record_id,
            'total_amount': bill.total_amount,
            'paid_amount': bill.paid_amount,
            'adjustment_amount': bill.adjustment_amount,
            'adjustment_reason': bill.adjustment_reason,
            'balance': balance,
            'is_settled': bill.is_settled,
            'payments': payments
        }

    def get_payments_by_date(self, start_date, end_date) -> List[Payment]:
        """获取指定日期范围的支付记录"""
        return self.db.query(Payment).filter(
            Payment.payment_time >= start_date,
            Payment.payment_time < end_date
        ).all()

    def calculate_daily_revenue(self, target_date) -> dict:
        """计算指定日期的营收"""
        from datetime import datetime, timedelta

        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        payments = self.get_payments_by_date(start, end)

        total = sum(p.amount for p in payments)
        cash = sum(p.amount for p in payments if p.method == PaymentMethod.CASH)
        card = sum(p.amount for p in payments if p.method == PaymentMethod.CARD)

        return {
            'date': target_date,
            'total': total,
            'cash': cash,
            'card': card,
            'count': len(payments)
        }
