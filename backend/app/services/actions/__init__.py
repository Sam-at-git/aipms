"""
app/services/actions

Action handler modules using ActionRegistry.

This package contains all AI-executable actions migrated from the
monolithic execute_action() method in ai_service.py.

Each action is:
1. Defined with a Pydantic parameter model in base.py
2. Implemented as a handler function in a domain-specific module
3. Registered using the @registry.register decorator
4. Executed via ActionRegistry.dispatch()

Usage:
    from app.services.actions import get_action_registry

    registry = get_action_registry()
    result = registry.dispatch(
        "walkin_checkin",
        {"guest_name": "张三", "room_id": 101},
        {"db": db, "user": user, "param_parser": parser}
    )
"""
from core.ai.actions import ActionRegistry
from app.services.param_parser_service import ParamParserService

import logging

logger = logging.getLogger(__name__)

# Global action registry instance
_action_registry: ActionRegistry = None


def _create_action_registry() -> ActionRegistry:
    """
    Create and initialize the global action registry.

    Imports all action modules and registers their actions.
    """
    registry = ActionRegistry()

    # Import and register all actions
    from app.services.actions import (
        guest_actions,
        stay_actions,
        task_actions,
        reservation_actions,
        query_actions,
        price_actions,
        webhook_actions,
        notification_actions,
        interface_actions,
        bill_actions,
        room_actions,
        employee_actions,
    )

    guest_actions.register_guest_actions(registry)
    stay_actions.register_stay_actions(registry)
    task_actions.register_task_actions(registry)
    reservation_actions.register_reservation_actions(registry)
    query_actions.register_query_actions(registry)
    price_actions.register_price_actions(registry)
    webhook_actions.register_webhook_actions(registry)
    notification_actions.register_notification_actions(registry)
    interface_actions.register_interface_actions(registry)
    bill_actions.register_bill_actions(registry)
    room_actions.register_room_actions(registry)
    employee_actions.register_employee_actions(registry)

    logger.info(f"ActionRegistry initialized with {len(registry.list_actions())} actions")

    return registry


def get_action_registry() -> ActionRegistry:
    """
    Get the global action registry instance.

    Creates the registry on first call (lazy initialization).

    Returns:
        The global ActionRegistry instance
    """
    global _action_registry
    if _action_registry is None:
        _action_registry = _create_action_registry()
    return _action_registry


def reset_action_registry() -> None:
    """
    Reset the global action registry.

    Useful for testing to ensure clean state.
    """
    global _action_registry
    _action_registry = None


# Export the main accessor
__all__ = [
    "get_action_registry",
    "reset_action_registry",
]
