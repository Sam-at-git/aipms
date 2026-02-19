"""
app/services/actions/price_actions.py

Price-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, RoomType
from app.services.param_parser_service import ParamParserService
from app.services.actions.base import (
    UpdatePriceParams,
    CreateRatePlanParams
)

import logging

logger = logging.getLogger(__name__)


def register_price_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all price-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="update_price",
        entity="RatePlan",
        description="更新房型价格。支持调整基础价格或创建价格策略。",
        category="pricing",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=True,
        side_effects=["updates_price"],
        search_keywords=["更新价格", "调整价格", "修改价格", "update price", "adjust price"],
        risk_level="medium",
        is_financial=True,
    )
    def handle_update_price(
        params: UpdatePriceParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService
    ) -> Dict[str, Any]:
        """
        Execute price update.

        This handler:
        1. Parses the room_type parameter
        2. Updates the base price or creates a rate plan
        3. Returns confirmation

        Args:
            params: Validated update price parameters
            db: Database session
            user: Current user (employee)
            param_parser: Parameter parser service for room type resolution

        Returns:
            Result dict with success status and message
        """
        from app.services.room_service import RoomService
        from app.services.price_service import PriceService

        # Parse room type
        room_type_result = param_parser.parse_room_type(params.room_type)

        if room_type_result.confidence < 0.7:
            return {
                "success": False,
                "requires_confirmation": True,
                "action": "select_room_type",
                "message": f'请确认房型："{room_type_result.raw_input}"',
                "candidates": room_type_result.candidates or [],
                "raw_input": room_type_result.raw_input
            }

        room_type_id = int(room_type_result.value)
        room_service = RoomService(db)
        price_service = PriceService(db)

        room_type = room_service.get_room_type(room_type_id)
        if not room_type:
            return {
                "success": False,
                "message": f"房型 ID {room_type_id} 不存在"
            }

        # If updating base price directly
        if params.update_type == "base_price":
            from app.models.schemas import RoomTypeUpdate
            update_data = RoomTypeUpdate(base_price=params.price)
            updated = room_service.update_room_type(room_type_id, update_data)

            return {
                "success": True,
                "message": f"{room_type.name}的基础价格已调整为¥{params.price}/晚",
                "room_type_id": room_type_id,
                "room_type_name": room_type.name,
                "new_price": str(params.price)
            }

        # If creating/updating a rate plan
        from app.models.schemas import RatePlanCreate, RatePlanUpdate

        # Check if weekend plan exists
        from app.models.ontology import RatePlan
        existing_plan = db.query(RatePlan).filter(
            RatePlan.room_type_id == room_type_id,
            RatePlan.is_weekend == (params.price_type == "weekend"),
            RatePlan.is_active == True
        ).first()

        if existing_plan:
            # Update existing plan
            update_data = RatePlanUpdate(price=params.price)
            updated = price_service.update_rate_plan(existing_plan.id, update_data)
            price_type_name = "周末" if params.price_type == "weekend" else "平日"
            return {
                "success": True,
                "message": f"{room_type.name}的{price_type_name}价格策略已更新为¥{params.price}/晚",
                "rate_plan_id": existing_plan.id,
                "room_type_id": room_type_id,
                "room_type_name": room_type.name,
                "new_price": str(params.price)
            }
        else:
            # Create new rate plan
            from datetime import timedelta
            start_date = params.start_date or date.today()
            end_date = params.end_date or (date.today() + timedelta(days=365))

            create_data = RatePlanCreate(
                name=f"{room_type.name} {'周末' if params.price_type == 'weekend' else '平日'}价格",
                room_type_id=room_type_id,
                start_date=start_date,
                end_date=end_date,
                price=params.price,
                is_weekend=(params.price_type == "weekend"),
                priority=2
            )
            new_plan = price_service.create_rate_plan(create_data, user.id)

            price_type_name = "周末" if params.price_type == "weekend" else "平日"
            return {
                "success": True,
                "message": f"已为{room_type.name}创建{price_type_name}价格策略：¥{params.price}/晚",
                "rate_plan_id": new_plan.id,
                "room_type_id": room_type_id,
                "room_type_name": room_type.name,
                "new_price": str(params.price)
            }

    @registry.register(
        name="create_rate_plan",
        entity="RatePlan",
        description="创建价格策略。支持为指定房型创建特定时间段的价格策略。",
        category="pricing",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=True,
        side_effects=["creates_rate_plan"],
        search_keywords=["创建价格策略", "新建价格", "create rate plan"],
        risk_level="medium",
        is_financial=True,
    )
    def handle_create_rate_plan(
        params: CreateRatePlanParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService
    ) -> Dict[str, Any]:
        """
        Execute rate plan creation.

        Args:
            params: Validated create rate plan parameters
            db: Database session
            user: Current user (employee)
            param_parser: Parameter parser service

        Returns:
            Result dict with success status and message
        """
        from app.services.room_service import RoomService
        from app.services.price_service import PriceService
        from app.models.schemas import RatePlanCreate

        room_service = RoomService(db)
        price_service = PriceService(db)

        room_type_result = param_parser.parse_room_type(params.room_type)

        if room_type_result.confidence < 0.7:
            return {
                "success": False,
                "requires_confirmation": True,
                "action": "select_room_type",
                "message": f'请确认房型："{room_type_result.raw_input}"',
                "candidates": room_type_result.candidates or [],
                "raw_input": room_type_result.raw_input
            }

        room_type_id = int(room_type_result.value)
        room_type = room_service.get_room_type(room_type_id)

        if not room_type:
            return {
                "success": False,
                "message": f"房型 ID {room_type_id} 不存在"
            }

        create_data = RatePlanCreate(
            name=params.name or f"{room_type.name}价格策略",
            room_type_id=room_type_id,
            start_date=params.start_date,
            end_date=params.end_date,
            price=params.price,
            priority=params.priority,
            is_weekend=params.is_weekend
        )

        try:
            new_plan = price_service.create_rate_plan(create_data, user.id)

            return {
                "success": True,
                "message": f"已创建价格策略：{new_plan.name}，价格¥{params.price}/晚",
                "rate_plan_id": new_plan.id,
                "room_type_id": room_type_id,
                "room_type_name": room_type.name
            }
        except ValueError as e:
            return {
                "success": False,
                "message": f"创建价格策略失败: {str(e)}",
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in create_rate_plan: {e}")
            return {
                "success": False,
                "message": f"创建价格策略失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_price_actions"]
