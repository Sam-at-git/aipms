"""
core/services/checkin_service.py

入住服务适配器 - 桥接 core/services/ 与 app/services/
"""
from typing import Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session

try:
    from app.services.checkin_service import CheckInService as AppCheckInService
    APP_CHECKIN_SERVICE_AVAILABLE = True
except ImportError:
    APP_CHECKIN_SERVICE_AVAILABLE = False


class CheckInServiceV2:
    """入住服务 V2 - 服务适配器"""

    def __init__(self, db: Session):
        self.db = db
        if APP_CHECKIN_SERVICE_AVAILABLE:
            self._app_service = AppCheckInService(db)
        else:
            self._app_service = None

    def checkin_from_reservation(self, reservation_id, room_id, actual_check_in=None):
        if self._app_service:
            return self._app_service.checkin_from_reservation(
                reservation_id, room_id, actual_check_in
            )
        raise NotImplementedError()

    def walkin_checkin(self, room_id, guest_name, guest_phone, expected_check_out,
                       adult_count=1, child_count=0, deposit_amount=None):
        if self._app_service:
            return self._app_service.walkin_checkin(
                room_id, guest_name, guest_phone, expected_check_out,
                adult_count, child_count, deposit_amount
            )
        raise NotImplementedError()

    def validate_checkin(self, reservation_id, room_id):
        if self._app_service:
            return self._app_service.validate_checkin(reservation_id, room_id)
        return False, "入住服务不可用", []

    def can_checkin(self, reservation_id):
        if self._app_service:
            return self._app_service.can_checkin(reservation_id)
        return False, "入住服务不可用"


def get_checkin_service_v2(db: Session):
    return CheckInServiceV2(db)


__all__ = ["CheckInServiceV2", "get_checkin_service_v2"]
