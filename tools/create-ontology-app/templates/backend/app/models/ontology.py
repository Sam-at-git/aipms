"""
Ontology Objects — generic framework types.

SecurityLevel is a generic framework type used by core/security.
Hotel-specific ORM models are in app.hotel.models.ontology.
"""
from enum import Enum


class SecurityLevel(int, Enum):
    """安全等级 - 用于属性级访问控制"""
    PUBLIC = 1         # 公开
    INTERNAL = 2       # 内部
    CONFIDENTIAL = 3   # 机密
    RESTRICTED = 4     # 受限
