"""
app/hotel/security — Hotel domain role permissions

Defines hotel-specific role→permission mappings, injected into
core.security.checker at startup via register_role_permissions().
"""
from typing import Dict, List

from core.security.checker import Permission


HOTEL_ROLE_PERMISSIONS: Dict[str, List[Permission]] = {
    "manager": [Permission("*", "*")],

    "receptionist": [
        Permission("room", "read"),
        Permission("room", "update_status"),
        Permission("guest", "read"),
        Permission("guest", "write"),
        Permission("reservation", "read"),
        Permission("reservation", "write"),
        Permission("reservation", "create"),
        Permission("checkin", "*"),
        Permission("checkout", "read"),
        Permission("bill", "read"),
        Permission("task", "read"),
        Permission("task", "assign"),
    ],

    "cleaner": [
        Permission("room", "read"),
        Permission("task", "read"),
        Permission("task", "update"),
        Permission("task", "complete"),
    ],
}


def register_hotel_role_permissions() -> None:
    """Register all hotel role permissions into the global PermissionChecker."""
    from core.security.checker import permission_checker

    for role, permissions in HOTEL_ROLE_PERMISSIONS.items():
        permission_checker.register_role_permissions(role, permissions)
