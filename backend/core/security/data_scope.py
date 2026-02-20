"""
core/security/data_scope.py

数据作用域 — 领域无关的数据隔离抽象

定义实体的数据作用域类型和用户的可见范围级别。
app 层通过实现 IDataScopeResolver 注入具体的隔离语义（如分店隔离）。
"""
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Set, Optional


class DataScopeType(str, Enum):
    """实体的数据作用域类型"""
    GLOBAL = "global"       # 全局共享（如 Guest）
    SCOPED = "scoped"       # 按作用域隔离（如 Room, Reservation）


class DataScopeLevel(str, Enum):
    """用户的数据可见范围级别"""
    ALL = "all"                         # 看到所有数据（集团管理员）
    SCOPE_AND_BELOW = "scope_and_below" # 本作用域及下级
    SCOPE_ONLY = "scope_only"           # 仅本作用域
    SELF_ONLY = "self_only"             # 仅自己的数据


@dataclass
class DataScopeContext:
    """当前用户的数据作用域上下文"""
    level: DataScopeLevel = DataScopeLevel.ALL
    scope_ids: Set[int] = field(default_factory=set)
    user_id: Optional[int] = None
    owner_column: str = "created_by"


class IDataScopeResolver(ABC):
    """数据作用域解析器接口 — app 层实现"""

    @abstractmethod
    def resolve_scope(self, user_id: int, role_data_scope: str, **kwargs) -> DataScopeContext:
        """根据用户和角色的 data_scope 配置，解析出可见范围"""
        ...

    @abstractmethod
    def get_entity_scope_column(self, entity_name: str) -> Optional[str]:
        """获取实体的作用域列名，返回 None 表示 GLOBAL 实体"""
        ...


__all__ = [
    "DataScopeType",
    "DataScopeLevel",
    "DataScopeContext",
    "IDataScopeResolver",
]
