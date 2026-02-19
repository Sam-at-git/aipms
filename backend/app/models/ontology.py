"""
本体对象定义 (Re-export Shim)

All hotel ORM models and enums are now defined in app/hotel/models/ontology.py.
This module keeps SecurityLevel and re-exports everything else for backward compatibility.
"""
from enum import Enum


class SecurityLevel(int, Enum):
    """安全等级 - 用于属性级访问控制"""
    PUBLIC = 1         # 公开
    INTERNAL = 2       # 内部
    CONFIDENTIAL = 3   # 机密
    RESTRICTED = 4     # 受限


# Re-export all hotel ORM models and enums for backward compatibility
from app.hotel.models.ontology import *  # noqa: F401, F403, E402
