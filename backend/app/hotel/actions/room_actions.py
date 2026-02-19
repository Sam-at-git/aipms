"""
app/services/actions/room_actions.py

Room and RoomType action handlers using ActionRegistry.
"""
from typing import Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.hotel.models.ontology import Employee, Room, RoomStatus
from app.hotel.actions.base import (
    UpdateRoomStatusParams, CreateRoomTypeParams, UpdateRoomTypeParams,
)

import logging

logger = logging.getLogger(__name__)


def register_room_actions(
    registry: ActionRegistry
) -> None:
    """Register all room-related actions."""

    @registry.register(
        name="update_room_status",
        entity="Room",
        description="更新房间状态。支持设置为空闲已清洁、空闲待清洁、维修中。入住中的房间不能手动改状态。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager", "cleaner"},
        undoable=False,
        side_effects=["updates_room_status"],
        search_keywords=["房间状态", "更新状态", "room status"]
    )
    def handle_update_room_status(
        params: UpdateRoomStatusParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """更新房间状态"""
        from app.hotel.services.room_service import RoomService

        try:
            room = db.query(Room).filter(
                Room.room_number == params.room_number
            ).first()
            if not room:
                return {
                    "success": False,
                    "message": f"房间 {params.room_number} 不存在",
                    "error": "not_found"
                }

            # Parse status
            status_map = {
                'vacant_clean': RoomStatus.VACANT_CLEAN,
                'vacant_dirty': RoomStatus.VACANT_DIRTY,
                'out_of_order': RoomStatus.OUT_OF_ORDER,
            }
            target_status = status_map.get(params.status.lower().strip())
            if not target_status:
                return {
                    "success": False,
                    "message": f"无效的状态: {params.status}. 支持: vacant_clean, vacant_dirty, out_of_order",
                    "error": "validation_error"
                }

            service = RoomService(db)
            room = service.update_room_status(
                room.id, target_status,
                changed_by=user.id, reason="手动更新"
            )

            status_labels = {
                'vacant_clean': '空闲已清洁',
                'vacant_dirty': '空闲待清洁',
                'out_of_order': '维修中',
            }
            return {
                "success": True,
                "message": f"房间 {room.room_number} 已更新为{status_labels.get(room.status.value, room.status.value)}",
                "room_id": room.id,
                "room_number": room.room_number,
                "status": room.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in update_room_status: {e}")
            return {
                "success": False,
                "message": f"更新房间状态失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="mark_room_clean",
        entity="Room",
        description="标记房间为已清洁（vacant_clean）。",
        category="mutation",
        requires_confirmation=False,
        allowed_roles={"cleaner", "receptionist", "manager"},
        undoable=False,
        side_effects=["updates_room_status"],
        search_keywords=["清洁完成", "打扫完成", "房间干净", "mark clean"]
    )
    def handle_mark_room_clean(
        params: UpdateRoomStatusParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """标记房间为已清洁"""
        from app.hotel.services.room_service import RoomService

        try:
            room = db.query(Room).filter(
                Room.room_number == params.room_number
            ).first()
            if not room:
                return {
                    "success": False,
                    "message": f"房间 {params.room_number} 不存在",
                    "error": "not_found"
                }

            service = RoomService(db)
            room = service.update_room_status(
                room.id, RoomStatus.VACANT_CLEAN,
                changed_by=user.id, reason="清洁完成"
            )

            return {
                "success": True,
                "message": f"房间 {room.room_number} 已标记为已清洁",
                "room_id": room.id,
                "room_number": room.room_number,
                "status": room.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in mark_room_clean: {e}")
            return {
                "success": False,
                "message": f"标记房间失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="mark_room_dirty",
        entity="Room",
        description="标记房间为待清洁（vacant_dirty）。",
        category="mutation",
        requires_confirmation=False,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["updates_room_status"],
        search_keywords=["需要清洁", "待打扫", "mark dirty"]
    )
    def handle_mark_room_dirty(
        params: UpdateRoomStatusParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """标记房间为待清洁"""
        from app.hotel.services.room_service import RoomService

        try:
            room = db.query(Room).filter(
                Room.room_number == params.room_number
            ).first()
            if not room:
                return {
                    "success": False,
                    "message": f"房间 {params.room_number} 不存在",
                    "error": "not_found"
                }

            service = RoomService(db)
            room = service.update_room_status(
                room.id, RoomStatus.VACANT_DIRTY,
                changed_by=user.id, reason="标记待清洁"
            )

            return {
                "success": True,
                "message": f"房间 {room.room_number} 已标记为待清洁",
                "room_id": room.id,
                "room_number": room.room_number,
                "status": room.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in mark_room_dirty: {e}")
            return {
                "success": False,
                "message": f"标记房间失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="create_room_type",
        entity="RoomType",
        description="创建新房型。需要提供名称和基础价格。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=False,
        side_effects=["creates_room_type"],
        search_keywords=["创建房型", "新增房型", "添加房型", "create room type"]
    )
    def handle_create_room_type(
        params: CreateRoomTypeParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """创建房型"""
        from app.hotel.models.schemas import RoomTypeCreate
        from app.hotel.services.room_service import RoomService

        try:
            create_data = RoomTypeCreate(
                name=params.name,
                base_price=params.base_price,
                description=params.description,
                max_occupancy=params.max_occupancy
            )
            service = RoomService(db)
            room_type = service.create_room_type(create_data)

            return {
                "success": True,
                "message": f"房型「{room_type.name}」已创建，基础价格 ¥{room_type.base_price}",
                "room_type_id": room_type.id,
                "name": room_type.name,
                "base_price": float(room_type.base_price)
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in create_room_type: {e}")
            return {
                "success": False,
                "message": f"创建房型失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="update_room_type",
        entity="RoomType",
        description="更新房型信息。可修改名称、价格、描述等。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=False,
        side_effects=["updates_room_type"],
        search_keywords=["修改房型", "更新房型", "update room type"]
    )
    def handle_update_room_type(
        params: UpdateRoomTypeParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """更新房型"""
        from app.hotel.models.schemas import RoomTypeUpdate
        from app.hotel.services.room_service import RoomService
        from app.hotel.models.ontology import RoomType

        try:
            # Resolve room type by ID or name
            room_type_id = params.room_type_id
            if not room_type_id and params.room_type_name:
                rt = db.query(RoomType).filter(
                    RoomType.name == params.room_type_name
                ).first()
                if not rt:
                    return {
                        "success": False,
                        "message": f"未找到房型「{params.room_type_name}」",
                        "error": "not_found"
                    }
                room_type_id = rt.id

            if not room_type_id:
                return {
                    "success": False,
                    "message": "请提供房型ID或房型名称",
                    "error": "missing_identifier"
                }

            # Build update fields
            update_fields = {}
            if params.name is not None:
                update_fields['name'] = params.name
            if params.base_price is not None:
                update_fields['base_price'] = params.base_price
            if params.description is not None:
                update_fields['description'] = params.description

            if not update_fields:
                return {
                    "success": False,
                    "message": "没有需要更新的字段",
                    "error": "no_updates"
                }

            update_data = RoomTypeUpdate(**update_fields)
            service = RoomService(db)
            room_type = service.update_room_type(room_type_id, update_data)

            return {
                "success": True,
                "message": f"房型「{room_type.name}」已更新",
                "room_type_id": room_type.id,
                "name": room_type.name,
                "base_price": float(room_type.base_price)
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in update_room_type: {e}")
            return {
                "success": False,
                "message": f"更新房型失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_room_actions"]
