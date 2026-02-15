"""
app/services/actions/reservation_actions.py

Reservation-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.param_parser_service import ParamParserService
from app.services.actions.base import (
    CreateReservationParams, CancelReservationParams, ModifyReservationParams,
)
from app.services.reservation_service import ReservationService
from app.services.room_service import RoomService

import logging

logger = logging.getLogger(__name__)


def register_reservation_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all reservation-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="create_reservation",
        entity="Reservation",
        description="创建新的客房预订。支持指定房型、入住/退房日期、客人信息等。自动计算总价并创建预订记录。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["creates_reservation", "may_create_guest"],
        search_keywords=["预订", "创建预订", "订房", "reservation", "book room"],
        ui_required_fields=["guest_name", "guest_phone", "room_type_id", "check_in_date", "check_out_date"],
    )
    def handle_create_reservation(
        params: CreateReservationParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService
    ) -> Dict[str, Any]:
        """
        Execute reservation creation.

        This handler:
        1. Parses the room_type parameter (accepts both ID and name)
        2. Validates dates are valid
        3. Creates or updates the guest record
        4. Calculates total price
        5. Creates the reservation in CONFIRMED status

        Args:
            params: Validated create reservation parameters
            db: Database session
            user: Current user (employee)
            param_parser: Parameter parser service for room type resolution

        Returns:
            Result dict with success status and message
        """
        from app.models.schemas import ReservationCreate

        # Parse room type (support both ID and name)
        room_type_result = param_parser.parse_room_type(params.room_type_id)

        if room_type_result.confidence < 0.7:
            # Low confidence - return candidates for user selection
            room_service = RoomService(db)
            room_types = room_service.get_room_types()
            candidates = [
                {'id': rt.id, 'name': rt.name, 'price': float(rt.base_price)}
                for rt in room_types
            ]
            return {
                "success": False,
                "requires_confirmation": True,
                "action": "select_room_type",
                "message": f'请确认房型："{room_type_result.raw_input}"',
                "candidates": room_type_result.candidates or candidates,
                "raw_input": room_type_result.raw_input
            }

        room_type_id = int(room_type_result.value)

        # Ensure dates are date objects
        check_in = params.check_in_date
        check_out = params.check_out_date

        # Additional date validation
        if isinstance(check_in, date) and isinstance(check_out, date):
            if check_out <= check_in:
                return {
                    "success": False,
                    "message": "退房日期必须晚于入住日期",
                    "error": "validation_error"
                }

        # Build service request
        request = ReservationCreate(
            guest_name=params.guest_name,
            guest_phone=params.guest_phone,
            guest_id_number=params.guest_id_number,
            room_type_id=room_type_id,
            check_in_date=check_in,
            check_out_date=check_out,
            adult_count=params.adult_count,
            child_count=params.child_count,
            room_count=params.room_count,
            special_requests=params.special_requests
        )

        # Execute reservation creation
        try:
            service = ReservationService(db)
            reservation = service.create_reservation(request, created_by=user.id)

            return {
                "success": True,
                "message": f"预订创建成功！预订号：{reservation.reservation_no}，"
                          f"{reservation.guest.name} 预订了 {reservation.room_count} 间 "
                          f"{reservation.room_type.name}。",
                "reservation_id": reservation.id,
                "reservation_no": reservation.reservation_no,
                "guest_id": reservation.guest_id,
                "guest_name": reservation.guest.name,
                "room_type_id": reservation.room_type_id,
                "room_type_name": reservation.room_type.name,
                "check_in_date": reservation.check_in_date.isoformat(),
                "check_out_date": reservation.check_out_date.isoformat(),
                "total_amount": float(reservation.total_amount) if reservation.total_amount else 0,
                "status": reservation.status.value
            }
        except ValidationError as e:
            logger.error(f"Validation error in create_reservation: {e}")
            return {
                "success": False,
                "message": f"参数验证失败: {str(e)}",
                "error": "validation_error"
            }
        except ValueError as e:
            logger.error(f"Business logic error in create_reservation: {e}")
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in create_reservation: {e}")
            return {
                "success": False,
                "message": f"创建预订失败: {str(e)}",
                "error": "execution_error"
            }


    @registry.register(
        name="cancel_reservation",
        entity="Reservation",
        description="取消预订。仅已确认状态的预订可以取消。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["cancels_reservation"],
        search_keywords=["取消预订", "退订", "cancel reservation"]
    )
    def handle_cancel_reservation(
        params: CancelReservationParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """取消预订"""
        from app.models.schemas import ReservationCancel
        from app.models.ontology import Reservation

        try:
            # Resolve reservation by ID or number
            reservation = None
            if params.reservation_id:
                reservation = db.query(Reservation).filter(
                    Reservation.id == params.reservation_id
                ).first()
            elif params.reservation_no:
                reservation = db.query(Reservation).filter(
                    Reservation.reservation_no == params.reservation_no
                ).first()

            if not reservation:
                return {
                    "success": False,
                    "message": "预订不存在，请提供有效的预订ID或预订号",
                    "error": "not_found"
                }

            cancel_data = ReservationCancel(
                cancel_reason=params.reason or "客人要求取消"
            )
            service = ReservationService(db)
            reservation = service.cancel_reservation(reservation.id, cancel_data)

            return {
                "success": True,
                "message": f"预订 {reservation.reservation_no} 已取消",
                "reservation_id": reservation.id,
                "reservation_no": reservation.reservation_no,
                "status": reservation.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in cancel_reservation: {e}")
            return {
                "success": False,
                "message": f"取消预订失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="modify_reservation",
        entity="Reservation",
        description="修改预订信息。可修改入住/退房日期、房型、人数、特殊要求等。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["modifies_reservation"],
        search_keywords=["修改预订", "更改预订", "调整预订", "modify reservation"]
    )
    def handle_modify_reservation(
        params: ModifyReservationParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """修改预订"""
        from app.models.schemas import ReservationUpdate
        from app.models.ontology import Reservation

        try:
            # Resolve reservation
            reservation = None
            if params.reservation_id:
                reservation = db.query(Reservation).filter(
                    Reservation.id == params.reservation_id
                ).first()
            elif params.reservation_no:
                reservation = db.query(Reservation).filter(
                    Reservation.reservation_no == params.reservation_no
                ).first()

            if not reservation:
                return {
                    "success": False,
                    "message": "预订不存在，请提供有效的预订ID或预订号",
                    "error": "not_found"
                }

            # Build update dict from non-None fields
            update_fields = {}
            if params.check_in_date is not None:
                update_fields['check_in_date'] = params.check_in_date
            if params.check_out_date is not None:
                update_fields['check_out_date'] = params.check_out_date
            if params.room_type_id is not None:
                update_fields['room_type_id'] = params.room_type_id
            if params.adult_count is not None:
                update_fields['adult_count'] = params.adult_count
            if params.special_requests is not None:
                update_fields['special_requests'] = params.special_requests

            if not update_fields:
                return {
                    "success": False,
                    "message": "没有需要修改的字段",
                    "error": "no_updates"
                }

            update_data = ReservationUpdate(**update_fields)
            service = ReservationService(db)
            reservation = service.update_reservation(reservation.id, update_data)

            return {
                "success": True,
                "message": f"预订 {reservation.reservation_no} 已更新",
                "reservation_id": reservation.id,
                "reservation_no": reservation.reservation_no,
                "check_in_date": str(reservation.check_in_date),
                "check_out_date": str(reservation.check_out_date),
                "status": reservation.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in modify_reservation: {e}")
            return {
                "success": False,
                "message": f"修改预订失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_reservation_actions"]
