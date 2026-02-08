"""
app/services/actions/stay_actions.py

StayRecord-related action handlers using ActionRegistry.
"""
from typing import Dict, Any, TYPE_CHECKING, Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import CheckoutParams
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


__all__ = ["register_stay_actions"]
