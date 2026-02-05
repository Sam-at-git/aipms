"""
Core Services Module - 服务层适配器

本模块提供使用新领域层的服务适配器，同时保持与现有 API 的兼容性。
"""

from core.services.room_service import RoomServiceV2, get_room_service_v2
from core.services.guest_service import GuestServiceV2, get_guest_service_v2

__all__ = [
    "RoomServiceV2",
    "get_room_service_v2",
    "GuestServiceV2",
    "get_guest_service_v2",
]
