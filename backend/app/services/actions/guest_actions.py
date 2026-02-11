"""
app/services/actions/guest_actions.py

Guest-related action handlers using ActionRegistry.
"""
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, Guest
from app.services.param_parser_service import ParamParserService, ParseResult
from app.services.actions.base import WalkInCheckInParams, UpdateGuestParams, CreateGuestParams, UpdateGuestSmartParams

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


    @registry.register(
        name="create_guest",
        entity="Guest",
        description="创建新客人记录。记录客人姓名、手机号、证件信息等。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["creates_guest"],
        search_keywords=["创建客人", "新增客人", "登记客人", "create guest"]
    )
    def handle_create_guest(
        params: CreateGuestParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """创建新客人"""
        from app.models.schemas import GuestCreate
        from app.services.guest_service import GuestService

        try:
            # Check for existing guest with same phone
            if params.phone:
                existing = db.query(Guest).filter(
                    Guest.phone == params.phone
                ).first()
                if existing:
                    return {
                        "success": False,
                        "message": f"手机号 {params.phone} 已被客人「{existing.name}」使用",
                        "error": "duplicate"
                    }

            create_data = GuestCreate(
                name=params.name,
                phone=params.phone,
                id_type=params.id_type,
                id_number=params.id_number,
                email=params.email
            )
            service = GuestService(db)
            guest = service.create_guest(create_data)

            return {
                "success": True,
                "message": f"客人「{guest.name}」已创建",
                "guest_id": guest.id,
                "guest_name": guest.name,
                "phone": guest.phone
            }
        except Exception as e:
            logger.error(f"Error in create_guest: {e}")
            return {
                "success": False,
                "message": f"创建客人失败: {str(e)}",
                "error": "execution_error"
            }


    @registry.register(
        name="update_guest_smart",
        entity="Guest",
        description="智能更新客人信息。支持自然语言式的部分修改指令，例如：'把电话号码后两位改为77'、'将邮箱改为新邮箱@qq.com'。会自动解析修改意图并应用到当前值。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["updates_guest"],
        search_keywords=["修改电话", "改号码", "更新信息", "智能修改", "部分修改"],
    )
    def handle_update_guest_smart(
        params: UpdateGuestSmartParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """
        智能更新客人信息 - 使用 LLM 解析部分修改指令

        处理流程:
        1. 查找客人（通过ID或姓名）
        2. 使用 LLM 解析修改意图
        3. 获取当前值并应用修改
        4. 执行更新
        """
        from app.models.schemas import GuestUpdate
        from app.services.guest_service import GuestService
        from app.services.llm_service import LLMService

        guest_service = GuestService(db)

        # 1. 查找客人
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

        # 2. 构建 LLM 提示来解析修改指令
        current_info = {
            "name": guest.name,
            "phone": guest.phone or "无",
            "email": guest.email or "无",
        }

        # 3. 使用 LLM 解析修改意图
        llm_service = LLMService()

        prompt = f"""你是酒店管理系统的修改意图解析器。

当前客人信息：
- 姓名: {current_info['name']}
- 电话: {current_info['phone']}
- 邮箱: {current_info['email']}

用户的修改指令：
{params.instructions}

请根据修改指令计算出新值。特别注意：
1. "后两位改为77" 意味着保留前9位，将最后两位改为77
2. "电话号码改为13800138000" 意味着完全替换
3. 如果当前值为"无"，则直接使用新值

只返回JSON格式：
{{
    "new_name": "新姓名（如果不修改则为null）",
    "new_phone": "新电话号码（必须是11位数字，如果不修改则为null）",
    "new_email": "新邮箱（如果不修改则为null）",
    "explanation": "修改说明"
}}

如果某个字段没有对应的修改指令，设为null。"""

        try:
            if not llm_service.is_enabled():
                return {
                    "success": False,
                    "message": "LLM 服务未启用，无法解析复杂修改指令。请使用 update_guest 动作直接提供完整的新值。",
                    "error": "llm_disabled"
                }

            # 使用 LLM 解析
            response = llm_service.client.chat.completions.create(
                model=llm_service.model,
                messages=[
                    {"role": "system", "content": "你是精确的数据修改解析器，只返回纯JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            update_fields = {}
            changes = []

            if result.get("new_name"):
                update_fields["name"] = result["new_name"]
                changes.append(f"姓名: {guest.name} → {result['new_name']}")

            if result.get("new_phone"):
                update_fields["phone"] = result["new_phone"]
                if guest.phone:
                    changes.append(f"手机号: {guest.phone} → {result['new_phone']}")
                else:
                    changes.append(f"手机号: 设置为 {result['new_phone']}")

            if result.get("new_email"):
                update_fields["email"] = result["new_email"]
                if guest.email:
                    changes.append(f"邮箱: {guest.email} → {result['new_email']}")
                else:
                    changes.append(f"邮箱: 设置为 {result['new_email']}")

            # 4. 执行更新
            if not update_fields:
                return {
                    "success": False,
                    "message": "LLM 未解析出任何需要修改的字段",
                    "error": "no_updates"
                }

            update_data = GuestUpdate(**update_fields)
            updated_guest = guest_service.update_guest(guest.id, update_data)

            return {
                "success": True,
                "message": f"已更新客人「{guest.name}」的信息：{'；'.join(changes)}",
                "guest_id": updated_guest.id,
                "guest_name": updated_guest.name,
                "updated_fields": update_fields,
                "changes": changes,
                "explanation": result.get("explanation", "")
            }

        except Exception as e:
            logger.error(f"Error in update_guest_smart: {e}")
            return {
                "success": False,
                "message": f"处理修改指令时出错: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_guest_actions"]
