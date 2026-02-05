"""
core/services/reservation_service.py

预订服务适配器 - 桥接 core/services/ 与 app/services/
"""
from typing import List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session

try:
    from app.services.reservation_service import ReservationService as AppReservationService
    APP_RESERVATION_SERVICE_AVAILABLE = True
except ImportError:
    APP_RESERVATION_SERVICE_AVAILABLE = False


class ReservationServiceV2:
    """预订服务 V2 - 服务适配器"""

    def __init__(self, db: Session):
        self.db = db
        if APP_RESERVATION_SERVICE_AVAILABLE:
            self._app_service = AppReservationService(db)
        else:
            self._app_service = None

    def get_reservations(self, guest_id=None, room_type_id=None, status=None, check_in_date=None):
        if self._app_service:
            return self._app_service.get_reservations(
                guest_id, room_type_id, status, check_in_date
            )
        return []

    def get_reservation(self, reservation_id: int):
        if self._app_service:
            return self._app_service.get_reservation(reservation_id)
        return None

    def get_reservation_by_no(self, reservation_no: str):
        if self._app_service:
            return self._app_service.get_reservation_by_no(reservation_no)
        return None

    def create_reservation(self, data):
        if self._app_service:
            return self._app_service.create_reservation(data)
        raise NotImplementedError()

    def update_reservation(self, reservation_id: int, data):
        if self._app_service:
            return self._app_service.update_reservation(reservation_id, data)
        raise NotImplementedError()

    def cancel_reservation(self, reservation_id: int, reason: str = ""):
        if self._app_service:
            return self._app_service.cancel_reservation(reservation_id, reason)
        raise NotImplementedError()

    def confirm_reservation(self, reservation_id: int):
        if self._app_service:
            return self._app_service.confirm_reservation(reservation_id)
        raise NotImplementedError()

    def mark_no_show(self, reservation_id: int, reason: str = ""):
        if self._app_service:
            return self._app_service.mark_no_show(reservation_id, reason)
        raise NotImplementedError()

    def get_today_arrivals(self):
        if self._app_service:
            return self._app_service.get_today_arrivals()
        return []

    def get_today_expected_departures(self):
        if self._app_service:
            return self._app_service.get_today_expected_departures()
        return []

    def get_conflicting_reservations(self, room_type_id, check_in, check_out, exclude_id=None):
        if self._app_service:
            return self._app_service.get_conflicting_reservations(
                room_type_id, check_in, check_out, exclude_id
            )
        return []

    def is_room_type_available(self, room_type_id, check_in, check_out, exclude_id=None):
        if self._app_service:
            return self._app_service.is_room_type_available(
                room_type_id, check_in, check_out, exclude_id
            )
        return True


def get_reservation_service_v2(db: Session) -> ReservationServiceV2:
    return ReservationServiceV2(db)


__all__ = ["ReservationServiceV2", "get_reservation_service_v2"]
