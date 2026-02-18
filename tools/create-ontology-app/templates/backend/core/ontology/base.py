"""
core/ontology/base.py

本体质心基类定义 - Palantir 式架构的基础
所有领域实体继承此基类以获得元数据支持和通用行为
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING, List

from core.ontology.security import SecurityLevel
from core.ontology.metadata import PIIType

if TYPE_CHECKING:
    from core.ontology.metadata import EntityMetadata, PropertyMetadata, StateMachine
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

    def _get_property_metadata(self, name: str) -> Optional["PropertyMetadata"]:
        """
        获取属性的 PropertyMetadata

        Args:
            name: 属性名称

        Returns:
            PropertyMetadata 对象，如果未找到则返回 None
        """
        cache = object.__getattribute__(self, "_metadata_cache")
        if name in cache:
            return cache[name]

        entity = object.__getattribute__(self, "_entity")
        entity_cls = type(entity)
        metadata = getattr(entity_cls, "_ontology_metadata", None)
        if metadata is None:
            cache[name] = None
            return None

        properties = getattr(metadata, "properties", None)
        if not properties:
            cache[name] = None
            return None

        prop_meta = properties.get(name)
        cache[name] = prop_meta
        return prop_meta

    @staticmethod
    def _mask_pii(value: Any, pii_type: "PIIType") -> Any:
        """
        根据 PII 类型对值进行脱敏

        Args:
            value: 原始值
            pii_type: PII 类型

        Returns:
            脱敏后的值
        """
        if not isinstance(value, str) or not value:
            return value

        if pii_type == PIIType.PHONE:
            # 138****1234: keep first 3, mask middle with ****, keep last 4
            if len(value) <= 7:
                return "*" * len(value)
            return value[:3] + "****" + value[-4:]

        if pii_type == PIIType.ID_NUMBER:
            # 310***1234: keep first 3, mask middle with ***, keep last 4
            if len(value) <= 7:
                return "*" * len(value)
            middle_len = len(value) - 3 - 4
            return value[:3] + "*" * middle_len + value[-4:]

        if pii_type == PIIType.NAME:
            # 张*: keep first char, replace rest with *
            if len(value) <= 1:
                return value
            return value[0] + "*" * (len(value) - 1)

        if pii_type == PIIType.EMAIL:
            # a***@example.com: keep first char of local, mask rest, keep domain
            if "@" not in value:
                return "*" * len(value)
            local, domain = value.split("@", 1)
            if len(local) <= 1:
                masked_local = local
            else:
                masked_local = local[0] + "***"
            return f"{masked_local}@{domain}"

        # For other PII types (ADDRESS, FINANCIAL, HEALTH), apply full masking
        return "*" * len(value)

    def __getattr__(self, name: str) -> Any:
        """
        拦截属性读取

        实现属性级访问控制和 PII 脱敏:
        1. 检查 PropertyMetadata.security_level，如果高于用户权限则拒绝访问
        2. 检查 PropertyMetadata.pii_type，如果需要脱敏则自动脱敏

        Args:
            name: 属性名称

        Returns:
            属性值（可能经过脱敏处理）

        Raises:
            AttributeError: 属性不存在
            PermissionError: 安全级别不足
        """
        entity = object.__getattribute__(self, "_entity")

        # 检查属性是否存在
        if not hasattr(entity, name):
            entity_name = entity.get_entity_name()
            raise AttributeError(f"'{entity_name}' has no attribute '{name}'")

        # 获取属性值
        value = getattr(entity, name)

        # 获取属性元数据
        prop_meta = self._get_property_metadata(name)
        if prop_meta is None:
            return value

        context = object.__getattribute__(self, "_context")

        # 安全级别检查
        prop_security_str = getattr(prop_meta, "security_level", "PUBLIC")
        try:
            prop_security = SecurityLevel.from_string(prop_security_str)
        except (ValueError, AttributeError):
            prop_security = SecurityLevel.PUBLIC

        if prop_security != SecurityLevel.PUBLIC and context is not None:
            if not context.has_clearance(prop_security):
                raise PermissionError(
                    f"Access denied to '{name}': requires {prop_security.name} clearance"
                )

        # PII 脱敏检查
        pii_type = getattr(prop_meta, "pii_type", PIIType.NONE)
        if pii_type != PIIType.NONE:
            should_mask = False
            if context is None:
                # 无上下文时，脱敏所有 PII 数据
                should_mask = True
            elif getattr(context, "should_mask_pii", False):
                # 上下文明确要求脱敏
                should_mask = True
            elif not context.has_clearance(SecurityLevel.CONFIDENTIAL):
                # 安全级别低于 CONFIDENTIAL 时自动脱敏
                should_mask = True

            if should_mask:
                value = self._mask_pii(value, pii_type)

        return value

    def __setattr__(self, name: str, value: Any) -> None:
        """
        拦截属性写入

        实现属性级写入访问控制:
        检查 PropertyMetadata.security_level，如果高于用户权限则拒绝写入

        Args:
            name: 属性名称
            value: 新值

        Raises:
            PermissionError: 安全级别不足
        """
        # 内部属性（__slots__ 中定义的）直接设置
        # 使用 object.__setattr__ 避免递归
        if name in ObjectProxy.__slots__:
            object.__setattr__(self, name, value)
            return

        entity = object.__getattribute__(self, "_entity")

        # 安全级别检查
        prop_meta = self._get_property_metadata(name)
        if prop_meta is not None:
            context = object.__getattribute__(self, "_context")
            prop_security_str = getattr(prop_meta, "security_level", "PUBLIC")
            try:
                prop_security = SecurityLevel.from_string(prop_security_str)
            except (ValueError, AttributeError):
                prop_security = SecurityLevel.PUBLIC

            if prop_security != SecurityLevel.PUBLIC and context is not None:
                if not context.has_clearance(prop_security):
                    raise PermissionError(
                        f"Write access denied to '{name}': requires {prop_security.name} clearance"
                    )

        # 设置到实体（包括以 _ 开头的属性）
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
