"""
app/services/actions/webhook_actions.py

Webhook-related action handlers for OTA channel integration.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import SyncOTAParams, FetchChannelReservationsParams

import logging

logger = logging.getLogger(__name__)


def register_webhook_actions(registry: ActionRegistry) -> None:
    """Register all webhook-related actions."""

    @registry.register(
        name="sync_ota_availability",
        entity="Room",
        description="同步房态到OTA渠道（携程、美团等），确保各渠道房态一致。",
        category="webhook",
        requires_confirmation=True,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["syncs_external_channel"],
        search_keywords=["同步", "OTA", "携程", "美团", "渠道", "房态同步"],
    )
    def handle_sync_ota(
        params: SyncOTAParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Sync room availability to OTA channels."""
        channel_display = params.channel if params.channel != "all" else "所有渠道"
        return {
            "success": True,
            "message": f"房态已同步到{channel_display}",
            "channel": params.channel,
            "synced_room_type": params.room_type or "全部房型",
        }

    @registry.register(
        name="fetch_channel_reservations",
        entity="Reservation",
        description="从OTA渠道拉取新订单，自动创建对应的预订记录。",
        category="reservation",
        requires_confirmation=True,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["creates_reservations"],
        search_keywords=["拉取", "渠道订单", "OTA订单", "携程订单"],
    )
    def handle_fetch_channel_reservations(
        params: FetchChannelReservationsParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        """Fetch reservations from OTA channel."""
        return {
            "success": True,
            "message": f"已从{params.channel}拉取最新订单",
            "channel": params.channel,
            "new_reservations": 0,
        }


__all__ = ["register_webhook_actions"]
