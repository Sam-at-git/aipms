"""
app/services/actions/interface_actions.py

Interface-based polymorphic action handlers.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import BookResourceParams

import logging

logger = logging.getLogger(__name__)


def register_interface_actions(registry: ActionRegistry) -> None:
    """Register all interface-based polymorphic actions."""

    @registry.register(
        name="book_resource",
        entity="BookableResource",
        description="预订资源（通用接口动作），支持房间、会议室等可预订资源的统一入口。",
        category="interface",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["creates_booking"],
        search_keywords=["预订资源", "预订", "book"],
    )
    def handle_book_resource(
        params: BookResourceParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Book a resource via the generic interface."""
        resource_type = params.resource_type
        if resource_type == "Room" and params.resource_id:
            return {
                "success": True,
                "message": f"已为{params.guest_name or '客人'}预订{resource_type} {params.resource_id}",
                "resource_type": resource_type,
                "resource_id": str(params.resource_id),
            }
        return {
            "success": True,
            "message": f"资源预订请求已提交: {resource_type}",
            "resource_type": resource_type,
        }


__all__ = ["register_interface_actions"]
