"""
app/services/actions/guest_actions.py

Guest-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.param_parser_service import ParamParserService, ParseResult
from app.services.actions.base import WalkInCheckInParams

import logging

logger = logging.getLogger(__name__)


def register_guest_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all guest-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="walkin_checkin",
        entity="Guest",
        description="处理无预订客人的直接入住。支持散客入住、临时入住等场景。自动创建客人记录、住宿记录和账单。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=True,
        side_effects=["creates_guest", "creates_stay_record", "creates_bill", "updates_room_status"],
        search_keywords=["散客", "直接入住", "无预订", "临时入住", "walk-in"],
        semantic_category="checkin_type",
        category_description="入住方式（预订入住 vs 直接入住）",
        glossary_examples=[
            {"correct": '"散客入住，王六儿..." → guest_name="王六儿"（散客是入住方式，不是客人姓名）',
             "incorrect": '"散客入住，王六儿..." → guest_name="散客"（错误地将入住方式当作参数值）'},
        ]
    )
    def handle_walkin_checkin(
        params: WalkInCheckInParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService
    ) -> Dict[str, Any]:
        """
        Execute walk-in guest check-in.

        This handler:
        1. Parses the room parameter (accepts both ID and room number)
        2. Validates the room is available
        3. Creates or updates the guest record
        4. Creates the stay record
        5. Creates the bill
        6. Updates room status to OCCUPIED

        Args:
            params: Validated walk-in check-in parameters
            db: Database session
            user: Current user (employee)
            param_parser: Parameter parser service for room resolution

        Returns:
            Result dict with success status and message
        """
        from app.models.schemas import WalkInCheckIn as WalkInCheckInRequest
        from app.services.checkin_service import CheckInService

        # Debug logging
        logger.info(f"[DEBUG] walkin_checkin called with params: {params.model_dump()}")

        # Parse room (support room number string)
        room_result = param_parser.parse_room(params.room_id)
        logger.info(f"[DEBUG] room_result: confidence={room_result.confidence}, value={room_result.value}")

        if room_result.confidence < 0.7:
            # Low confidence - return candidates for user selection
            return {
                "success": False,
                "requires_confirmation": True,
                "action": "select_room",
                "message": f'请确认房间："{room_result.raw_input}"',
                "candidates": room_result.candidates or [],
                "raw_input": room_result.raw_input
            }

        room_id = int(room_result.value)

        # Build service request
        request = WalkInCheckInRequest(
            guest_name=params.guest_name,
            guest_phone=params.guest_phone,
            guest_id_type=params.guest_id_type,
            guest_id_number=params.guest_id_number,
            room_id=room_id,
            expected_check_out=params.expected_check_out,
            deposit_amount=params.deposit_amount
        )

        # Execute check-in
        try:
            service = CheckInService(db)
            stay = service.walk_in_check_in(request, user.id)

            return {
                "success": True,
                "message": f"散客入住成功！{stay.guest.name} 已入住 {stay.room.room_number}号房。",
                "stay_record_id": stay.id,
                "guest_id": stay.guest_id,
                "room_id": stay.room_id,
                "room_number": stay.room.room_number,
                "check_in_time": stay.check_in_time.isoformat(),
                "expected_check_out": stay.expected_check_out.isoformat()
            }
        except ValidationError as e:
            logger.error(f"Validation error in walkin_checkin: {e}")
            return {
                "success": False,
                "message": f"参数验证失败: {str(e)}",
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in walkin_checkin: {e}")
            return {
                "success": False,
                "message": f"入住失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_guest_actions"]
