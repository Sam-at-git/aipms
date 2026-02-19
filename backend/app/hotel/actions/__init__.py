"""
Hotel domain action handlers.

All hotel-specific AI-executable actions: guest, stay, task, reservation,
billing, room, employee, and price operations.
"""


def register_hotel_actions(registry):
    """Register all hotel domain actions with the given ActionRegistry."""
    from app.hotel.actions import (
        guest_actions,
        stay_actions,
        task_actions,
        reservation_actions,
        bill_actions,
        room_actions,
        employee_actions,
        price_actions,
    )

    guest_actions.register_guest_actions(registry)
    stay_actions.register_stay_actions(registry)
    task_actions.register_task_actions(registry)
    reservation_actions.register_reservation_actions(registry)
    bill_actions.register_bill_actions(registry)
    room_actions.register_room_actions(registry)
    employee_actions.register_employee_actions(registry)
    price_actions.register_price_actions(registry)
