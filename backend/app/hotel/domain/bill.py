"""
core/domain/bill.py

Bill 领域实体 - 账单管理
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
import logging

from core.ontology.base import BaseEntity

if TYPE_CHECKING:
    from app.models.ontology import Bill

logger = logging.getLogger(__name__)


class BillEntity(BaseEntity):
    def __init__(self, orm_model: "Bill"):
        self._orm_model = orm_model

    @property
    def id(self) -> int:
        return self._orm_model.id

    @property
    def stay_record_id(self) -> int:
        return self._orm_model.stay_record_id

    @property
    def total_amount(self) -> Decimal:
        return self._orm_model.total_amount or Decimal("0")

    @property
    def paid_amount(self) -> Decimal:
        return self._orm_model.paid_amount or Decimal("0")

    @property
    def adjustment_amount(self) -> Decimal:
        return self._orm_model.adjustment_amount or Decimal("0")

    @property
    def adjustment_reason(self) -> Optional[str]:
        return self._orm_model.adjustment_reason

    @property
    def is_settled(self) -> bool:
        return self._orm_model.is_settled

    @property
    def created_at(self) -> datetime:
        return self._orm_model.created_at

    @property
    def outstanding_balance(self) -> Decimal:
        return self.total_amount + self.adjustment_amount - self.paid_amount

    def add_payment(self, amount: float, method: str) -> None:
        self._orm_model.paid_amount = (self._orm_model.paid_amount or Decimal("0")) + Decimal(str(amount))
        if self.outstanding_balance <= 0:
            self._orm_model.is_settled = True
        logger.info(f"Bill {self.id} payment added: {amount}, method={method}")

    def apply_discount(self, discount_amount: float, reason: str) -> None:
        self._orm_model.adjustment_amount = (self._orm_model.adjustment_amount or Decimal("0")) - Decimal(str(discount_amount))
        self._orm_model.adjustment_reason = reason
        logger.info(f"Bill {self.id} discount applied: {discount_amount}, reason={reason}")

    def is_fully_paid(self) -> bool:
        return self.is_settled or self.outstanding_balance <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "stay_record_id": self.stay_record_id,
            "total_amount": float(self.total_amount),
            "paid_amount": float(self.paid_amount),
            "adjustment_amount": float(self.adjustment_amount),
            "adjustment_reason": self.adjustment_reason,
            "is_settled": self.is_settled,
            "outstanding_balance": float(self.outstanding_balance),
            "is_fully_paid": self.is_fully_paid(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BillRepository:
    def __init__(self, db_session):
        self._db = db_session

    def get_by_id(self, bill_id: int) -> Optional[BillEntity]:
        from app.models.ontology import Bill
        orm_model = self._db.query(Bill).filter(Bill.id == bill_id).first()
        if orm_model is None:
            return None
        return BillEntity(orm_model)

    def get_by_stay_record(self, stay_record_id: int) -> Optional[BillEntity]:
        from app.models.ontology import Bill
        orm_model = self._db.query(Bill).filter(Bill.stay_record_id == stay_record_id).first()
        if orm_model is None:
            return None
        return BillEntity(orm_model)

    def find_unpaid(self) -> List[BillEntity]:
        from app.models.ontology import Bill
        orm_models = self._db.query(Bill).filter(Bill.is_settled == False).all()
        return [BillEntity(m) for m in orm_models]

    def save(self, bill: BillEntity) -> None:
        self._db.add(bill._orm_model)
        self._db.commit()

    def list_all(self) -> List[BillEntity]:
        from app.models.ontology import Bill
        orm_models = self._db.query(Bill).order_by(Bill.created_at.desc()).all()
        return [BillEntity(m) for m in orm_models]


__all__ = ["BillEntity", "BillRepository"]
