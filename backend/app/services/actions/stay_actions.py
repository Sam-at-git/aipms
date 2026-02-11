"""
app/services/actions/stay_actions.py

StayRecord-related action handlers using ActionRegistry.
"""
from typing import Dict, Any, TYPE_CHECKING, Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import CheckoutParams, CheckinParams, ExtendStayParams, ChangeRoomParams
from app.services.param_parser_service import ParamParserService

import logging

logger = logging.getLogger(__name__)


def register_stay_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all stay-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="checkout",
        entity="StayRecord",
        description="办理客人退房手续。结算账单、退还押金、更新房间状态为待清洁。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["settles_bill", "updates_room_status", "creates_cleaning_task"],
        search_keywords=["退房", "结算", "离店", "checkout"]
    )
    def handle_checkout(
        params: CheckoutParams,
        db: Session,
        user: Employee,
        param_parser: Optional[ParamParserService] = None
    ) -> Dict[str, Any]:
        """
        Execute guest checkout.

        This handler:
        1. Validates the stay record exists
        2. Calculates final bill
        3. Processes refund if applicable
        4. Updates room status to VACANT_DIRTY
        5. Marks stay record as COMPLETED

        Args:
            params: Validated checkout parameters
            db: Database session
            user: Current user (employee)

        Returns:
            Result dict with success status and message
        """
        from app.models.schemas import CheckOutRequest
        from app.services.checkout_service import CheckOutService

        # Build service request
        request = CheckOutRequest(
            stay_record_id=params.stay_record_id,
            refund_deposit=params.refund_deposit,
            allow_unsettled=params.allow_unsettled,
            unsettled_reason=params.unsettled_reason
        )

        # Execute checkout
        try:
            service = CheckOutService(db)
            stay = service.check_out(request, user.id)

            message = f"退房成功！房间 {stay.room.room_number} 已变为待清洁状态。"
            if stay.bill:
                balance = (
                    stay.bill.total_amount +
                    stay.bill.adjustment_amount -
                    stay.bill.paid_amount
                )
                if balance > 0:
                    message += f" 账单余额：¥{balance}"

            return {
                "success": True,
                "message": message,
                "stay_record_id": stay.id,
                "room_id": stay.room_id,
                "room_number": stay.room.room_number,
                "check_out_time": stay.check_out_time.isoformat() if stay.check_out_time else None,
                "bill_id": stay.bill.id if stay.bill else None,
                "guest_name": stay.guest.name
            }
        except ValidationError as e:
            logger.error(f"Validation error in checkout: {e}")
            return {
                "success": False,
                "message": f"参数验证失败: {str(e)}",
                "error": "validation_error"
            }
        except ValueError as e:
            logger.error(f"Business logic error in checkout: {e}")
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in checkout: {e}")
            return {
                "success": False,
                "message": f"退房失败: {str(e)}",
                "error": "execution_error"
            }


    @registry.register(
        name="checkin",
        entity="StayRecord",
        description="预订入住。根据预订号或预订ID办理入住，创建住宿记录和账单。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["creates_stay_record", "creates_bill", "updates_room_status"],
        search_keywords=["入住", "预订入住", "办理入住", "checkin", "check in"]
    )
    def handle_checkin(
        params: CheckinParams,
        db: Session,
        user: Employee,
        param_parser: Optional[ParamParserService] = None
    ) -> Dict[str, Any]:
        """预订入住"""
        from app.models.schemas import CheckInFromReservation
        from app.services.checkin_service import CheckInService
        from app.models.ontology import Reservation, Room

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

            # Resolve room: use provided room_number or find available room of matching type
            room = None
            if params.room_number:
                room = db.query(Room).filter(
                    Room.room_number == params.room_number
                ).first()
                if not room:
                    return {
                        "success": False,
                        "message": f"房间 {params.room_number} 不存在",
                        "error": "not_found"
                    }
            else:
                # Find first available room of the right type
                from app.models.ontology import RoomStatus
                room = db.query(Room).filter(
                    Room.room_type_id == reservation.room_type_id,
                    Room.status.in_([RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]),
                    Room.is_active == True
                ).first()
                if not room:
                    return {
                        "success": False,
                        "message": "没有可用的同房型房间",
                        "error": "no_available_room"
                    }

            request = CheckInFromReservation(
                reservation_id=reservation.id,
                room_id=room.id
            )

            service = CheckInService(db)
            stay = service.check_in_from_reservation(request, user.id)

            return {
                "success": True,
                "message": f"入住成功！{stay.guest.name} 已入住 {stay.room.room_number}号房",
                "stay_record_id": stay.id,
                "guest_name": stay.guest.name,
                "room_number": stay.room.room_number,
                "reservation_no": reservation.reservation_no,
                "check_in_time": stay.check_in_time.isoformat()
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in checkin: {e}")
            return {
                "success": False,
                "message": f"入住失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="extend_stay",
        entity="StayRecord",
        description="续住。延长客人的退房日期，自动重新计算房费。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["updates_stay_record", "updates_bill"],
        search_keywords=["续住", "延住", "延长入住", "extend stay"]
    )
    def handle_extend_stay(
        params: ExtendStayParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """续住"""
        from app.models.schemas import ExtendStay
        from app.services.checkin_service import CheckInService

        try:
            request = ExtendStay(new_check_out_date=params.new_check_out_date)
            service = CheckInService(db)
            stay = service.extend_stay(params.stay_record_id, request, operator_id=user.id)

            return {
                "success": True,
                "message": f"续住成功！{stay.guest.name} 新退房日期为 {stay.expected_check_out}",
                "stay_record_id": stay.id,
                "guest_name": stay.guest.name,
                "room_number": stay.room.room_number,
                "new_check_out_date": str(stay.expected_check_out)
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in extend_stay: {e}")
            return {
                "success": False,
                "message": f"续住失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="change_room",
        entity="StayRecord",
        description="换房。将客人从当前房间换到新房间，原房间变为待清洁。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["updates_stay_record", "updates_room_status"],
        search_keywords=["换房", "转房", "调房", "change room"]
    )
    def handle_change_room(
        params: ChangeRoomParams,
        db: Session,
        user: Employee,
        param_parser: Optional[ParamParserService] = None
    ) -> Dict[str, Any]:
        """换房"""
        from app.models.schemas import ChangeRoom
        from app.services.checkin_service import CheckInService
        from app.models.ontology import Room

        try:
            # Resolve new room by number
            new_room = db.query(Room).filter(
                Room.room_number == params.new_room_number
            ).first()
            if not new_room:
                return {
                    "success": False,
                    "message": f"房间 {params.new_room_number} 不存在",
                    "error": "not_found"
                }

            request = ChangeRoom(new_room_id=new_room.id)
            service = CheckInService(db)
            stay = service.change_room(params.stay_record_id, request, operator_id=user.id)

            return {
                "success": True,
                "message": f"换房成功！{stay.guest.name} 已换至 {stay.room.room_number}号房",
                "stay_record_id": stay.id,
                "guest_name": stay.guest.name,
                "new_room_number": stay.room.room_number
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in change_room: {e}")
            return {
                "success": False,
                "message": f"换房失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_stay_actions"]
