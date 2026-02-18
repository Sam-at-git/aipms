"""
core/ontology/security.py

本体安全定义 - 属性级访问控制
定义安全等级枚举，用于属性安全标记
"""
from enum import IntEnum


class SecurityLevel(IntEnum):
    """
    安全等级枚举 - 用于属性级访问控制

    等级定义：
    - PUBLIC (1): 公开数据，任何人可访问
    - INTERNAL (2): 内部数据，仅内部员工可访问
    - CONFIDENTIAL (3): 机密数据，仅授权人员可访问
    - RESTRICTED (4): 受限数据，仅特定角色可访问

    Example:
        >>> class Room(BaseEntity):
        ...     room_number: str = secure_field(SecurityLevel.PUBLIC)
        ...     price: Decimal = secure_field(SecurityLevel.CONFIDENTIAL)
    """

    PUBLIC = 1  # 公开
    INTERNAL = 2  # 内部
    CONFIDENTIAL = 3  # 机密
    RESTRICTED = 4  # 受限

    def __str__(self) -> str:
        """返回字符串表示"""
        return self.name

    @classmethod
    def from_string(cls, value: str) -> "SecurityLevel":
        """
        从字符串创建安全等级

        Args:
            value: 字符串值（如 "PUBLIC", "INTERNAL"）

        Returns:
            SecurityLevel 枚举值

        Raises:
            ValueError: 如果字符串值无效
        """
        try:
            return cls[value.upper()]
        except KeyError as e:
            valid_values = [level.name for level in cls]
            raise ValueError(
                f"Invalid security level: {value}. Valid values are: {valid_values}"
            ) from e


# 导出
__all__ = ["SecurityLevel"]
