"""
core/services/billing_service.py

账单服务适配器 - 桥接 core/services/ 与 app/services/
"""
from typing import Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

try:
    from app.services.billing_service import BillingService as AppBillingService
    APP_BILLING_SERVICE_AVAILABLE = True
except ImportError:
    APP_BILLING_SERVICE_AVAILABLE = False


class BillingServiceV2:
    """账单服务 V2 - 服务适配器"""

    def __init__(self, db: Session):
        self.db = db
        if APP_BILLING_SERVICE_AVAILABLE:
            self._app_service = AppBillingService(db)
        else:
            self._app_service = None

    def get_bill_by_stay(self, stay_record_id):
        if self._app_service:
            return self._app_service.get_bill_by_stay(stay_record_id)
        return None

    def get_bill(self, bill_id):
        if self._app_service:
            return self._app_service.get_bill(bill_id)
        return None

    def get_unpaid_bills(self):
        if self._app_service:
            return self._app_service.get_unpaid_bills()
        return []

    def add_payment(self, bill_id, amount, method, processed_by, remark=""):
        if self._app_service:
            return self._app_service.add_payment(
                bill_id, amount, method, processed_by, remark
            )
        raise NotImplementedError()

    def adjust_bill(self, bill_id, adjustment_amount, reason, adjusted_by):
        if self._app_service:
            return self._app_service.adjust_bill(
                bill_id, adjustment_amount, reason, adjusted_by
            )
        raise NotImplementedError()


def get_billing_service_v2(db: Session):
    return BillingServiceV2(db)


__all__ = ["BillingServiceV2", "get_billing_service_v2"]
