"""
core/ontology/base.py

本体质心基类定义 - Palantir 式架构的基础
所有领域实体继承此基类以获得元数据支持和通用行为
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING, List

if TYPE_CHECKING:
    from core.ontology.metadata import EntityMetadata, StateMachine
    from core.security.context import SecurityContext


class BaseEntity(ABC):
    """
    本体实体基类 - 通用业务对象抽象

    提供以下功能：
    - 实体名称获取
    - 元数据访问（由装饰器填充）
    - 状态机访问（由装饰器填充）
    - 字典序列化
    """

    # 类属性：由 @ontology_entity 装饰器填充
    _ontology_metadata: Optional["EntityMetadata"] = None
    _state_machine: Optional["StateMachine"] = None

    @classmethod
    def get_entity_name(cls) -> str:
        """
        获取实体名称

        Returns:
            实体名称（如 "Room", "Guest"）

        Example:
            >>> Room.get_entity_name()
            'Room'
        """
        return cls.__name__

    @classmethod
    def get_metadata(cls) -> Optional["EntityMetadata"]:
        """
        获取本体元数据

        Returns:
            EntityMetadata 对象，如果未通过装饰器注册则返回 None
        """
        return cls._ontology_metadata

    @classmethod
    def get_state_machine(cls) -> Optional["StateMachine"]:
        """
        获取状态机定义

        Returns:
            StateMachine 对象，如果未定义状态机则返回 None
        """
        return cls._state_machine

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示

        Returns:
            包含所有属性的字典

        Note:
            默认实现使用 vars() 获取实例属性。
            子类可以覆盖此方法以提供自定义序列化逻辑。
        """
        # 过滤掉内部属性（以 _ 开头）
        return {
            k: v for k, v in vars(self).items()
            if not k.startswith("_")
        }

    def __repr__(self) -> str:
        """
        友好的字符串表示

        Returns:
            格式如 "Room(id=1, room_number='101')"
        """
        cls_name = self.get_entity_name()
        # 尝试获取 id 属性
        entity_id = getattr(self, "id", "?")
        return f"{cls_name}(id={entity_id})"


class ObjectProxy:
    """
    对象代理 - 属性级拦截实现

    Palantir 式架构的核心组件，提供：
    - 属性级访问控制
    - 敏感数据脱敏
    - 审计日志记录
    - 业务规则触发

    使用 __slots__ 优化内存使用，避免创建 __dict__。
    """

    __slots__ = ("_entity", "_context", "_metadata_cache")

    def __init__(self, entity: "BaseEntity", context: Optional["SecurityContext"] = None):
        """
        初始化代理

        Args:
            entity: 被代理的实体对象
            context: 安全上下文（可选，用于权限控制）

        Example:
            >>> room = Room(id=1, room_number="101")
            >>> proxy = ObjectProxy(room, user_context)
            >>> proxy.room_number  # 通过代理访问
            '101'
        """
        object.__setattr__(self, "_entity", entity)
        object.__setattr__(self, "_context", context)
        object.__setattr__(self, "_metadata_cache", {})

    def __getattr__(self, name: str) -> Any:
        """
        拦截属性读取

        Args:
            name: 属性名称

        Returns:
            属性值

        Raises:
            AttributeError: 属性不存在

        Note:
            当前版本直接返回属性值。
            后续版本将实现权限检查和脱敏处理（SPEC-17, SPEC-18）。
        """
        entity = object.__getattribute__(self, "_entity")

        # 检查属性是否存在
        if not hasattr(entity, name):
            entity_name = entity.get_entity_name()
            raise AttributeError(f"'{entity_name}' has no attribute '{name}'")

        # 获取属性值
        value = getattr(entity, name)

        # TODO: 后续实现权限检查和脱敏
        # context = object.__getattribute__(self, "_context")
        # if context and self._is_sensitive(name):
        #     if not context.can_read(name):
        #         raise PermissionError(f"Access denied to '{name}'")
        #     return self._mask_value(value, name)

        return value

    def __setattr__(self, name: str, value: Any) -> None:
        """
        拦截属性写入

        Args:
            name: 属性名称
            value: 新值

        Note:
            当前版本直接写入属性值。
            后续版本将实现权限检查、审计日志、规则触发（SPEC-17, SPEC-18）。
        """
        # 内部属性（__slots__ 中定义的）直接设置
        # 使用 object.__setattr__ 避免递归
        if name in ObjectProxy.__slots__:
            object.__setattr__(self, name, value)
            return

        entity = object.__getattribute__(self, "_entity")

        # TODO: 后续实现权限检查、审计日志、规则触发
        # context = object.__getattribute__(self, "_context")
        # if context and self._is_sensitive(name):
        #     if not context.can_write(name):
        #         raise PermissionError(f"Write access denied to '{name}'")

        # 直接设置到实体（包括以 _ 开头的属性）
        setattr(entity, name, value)

    def __repr__(self) -> str:
        """
        代理对象的字符串表示

        Returns:
            格式如 "Proxy(Room(id=1))"
        """
        entity = object.__getattribute__(self, "_entity")
        return f"Proxy({repr(entity)})"

    def __dir__(self) -> List[str]:
        """
        支持 dir() 和 IDE 自动完成

        Returns:
            实体对象的属性列表
        """
        entity = object.__getattribute__(self, "_entity")
        return dir(entity)

    def unwrap(self) -> "BaseEntity":
        """
        获取原始实体对象

        Returns:
            被代理的原始实体

        Example:
            >>> room = Room(id=1, room_number="101")
            >>> proxy = ObjectProxy(room)
            >>> proxy.unwrap() is room
            True
        """
        return object.__getattribute__(self, "_entity")

    def get_context(self) -> Optional["SecurityContext"]:
        """
        获取安全上下文

        Returns:
            SecurityContext 对象，如果未设置则返回 None
        """
        return object.__getattribute__(self, "_context")


# 导出
__all__ = ["BaseEntity", "ObjectProxy"]
