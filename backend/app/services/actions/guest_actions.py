"""
app/services/actions/guest_actions.py

Guest-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, Guest
from app.services.param_parser_service import ParamParserService, ParseResult
from app.services.actions.base import WalkInCheckInParams, UpdateGuestParams

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


    @registry.register(
        name="update_guest",
        entity="Guest",
        description="更新客人信息，包括联系方式（手机号、邮箱）、姓名、证件信息、客户等级、黑名单状态等。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["updates_guest"],
    )
    def handle_update_guest(
        params: UpdateGuestParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """
        Execute guest information update.

        Supports locating guest by guest_id or guest_name.
        Updates only the fields that are provided (non-None).
        """
        from app.models.schemas import GuestUpdate
        from app.services.guest_service import GuestService
        from sqlalchemy import func

        guest_service = GuestService(db)

        # Resolve guest: by ID or by name
        guest = None
        if params.guest_id:
            guest = guest_service.get_guest(params.guest_id)
            if not guest:
                return {
                    "success": False,
                    "message": f"未找到ID为 {params.guest_id} 的客人",
                    "error": "not_found"
                }
        elif params.guest_name:
            # Search by exact name first, then fuzzy
            candidates = db.query(Guest).filter(
                Guest.name == params.guest_name
            ).all()

            if not candidates:
                candidates = db.query(Guest).filter(
                    Guest.name.like(f"%{params.guest_name}%")
                ).all()

            if len(candidates) == 0:
                return {
                    "success": False,
                    "message": f"未找到名为「{params.guest_name}」的客人",
                    "error": "not_found"
                }
            elif len(candidates) > 1:
                candidate_list = [
                    {"id": g.id, "name": g.name, "phone": g.phone or ""}
                    for g in candidates
                ]
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "action": "select_guest",
                    "message": f"找到多个名为「{params.guest_name}」的客人，请确认：",
                    "candidates": candidate_list
                }
            else:
                guest = candidates[0]
        else:
            return {
                "success": False,
                "message": "请提供客人ID或客人姓名",
                "error": "missing_identifier"
            }

        # Build update data (only non-None fields)
        update_fields = {}
        for field_name in ["name", "phone", "email", "id_type", "id_number",
                           "tier", "is_blacklisted", "blacklist_reason", "notes"]:
            value = getattr(params, field_name, None)
            if value is not None:
                update_fields[field_name] = value

        if not update_fields:
            return {
                "success": False,
                "message": "没有需要更新的字段",
                "error": "no_updates"
            }

        # Execute update
        try:
            update_data = GuestUpdate(**update_fields)
            updated_guest = guest_service.update_guest(guest.id, update_data)

            # Build response with changed fields
            changes = []
            for k, v in update_fields.items():
                field_labels = {
                    "name": "姓名", "phone": "手机号", "email": "邮箱",
                    "id_type": "证件类型", "id_number": "证件号码",
                    "tier": "客户等级", "is_blacklisted": "黑名单",
                    "blacklist_reason": "黑名单原因", "notes": "备注"
                }
                changes.append(f"{field_labels.get(k, k)}: {v}")

            return {
                "success": True,
                "message": f"已更新客人「{updated_guest.name}」的信息：{'、'.join(changes)}",
                "guest_id": updated_guest.id,
                "guest_name": updated_guest.name,
                "updated_fields": update_fields
            }
        except Exception as e:
            logger.error(f"Error in update_guest: {e}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_guest_actions"]
