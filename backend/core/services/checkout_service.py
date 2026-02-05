"""
core/services/checkout_service.py

退房服务适配器 - 桥接 core/services/ 与 app/services/
"""
from typing import Dict, Any
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

try:
    from app.services.checkout_service import CheckOutService as AppCheckOutService
    APP_CHECKOUT_SERVICE_AVAILABLE = True
except ImportError:
    APP_CHECKOUT_SERVICE_AVAILABLE = False


class CheckOutServiceV2:
    """退房服务 V2 - 服务适配器"""

    def __init__(self, db: Session):
        self.db = db
        if APP_CHECKOUT_SERVICE_AVAILABLE:
            self._app_service = AppCheckOutService(db)
        else:
            self._app_service = None

    def checkout(self, stay_record_id):
        if self._app_service:
            return self._app_service.checkout(stay_record_id)
        raise NotImplementedError()

    def can_checkout(self, stay_record_id):
        if self._app_service:
            return self._app_service.can_checkout(stay_record_id)
        return False, "退房服务不可用"

    def get_expected_checkouts(self, target_date):
        if self._app_service:
            return self._app_service.get_expected_checkouts(target_date)
        return []

    def get_overdue_checkouts(self):
        if self._app_service:
            return self._app_service.get_overdue_checkouts()
        return []


def get_checkout_service_v2(db: Session):
    return CheckOutServiceV2(db)


__all__ = ["CheckOutServiceV2", "get_checkout_service_v2"]
