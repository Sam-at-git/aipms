"""
core/ontology/interface.py

本体接口多态系统 - Palantir 式接口抽象

提供接口定义和实现验证机制：
- OntologyInterface: 接口基类，定义契约
- implements(): 装饰器，声明实体实现指定接口

设计意图（对标 Foundry Interface）:
- 不同实体可实现相同接口（如 Room, MeetingRoom 都实现 BookableResource）
- 工作流面向接口编程，不关心具体类型
- 新增类型自动兼容已有工作流
"""
from typing import Dict, List, Type, ClassVar, Any, TYPE_CHECKING

from core.ontology.metadata import ParamType

if TYPE_CHECKING:
    from core.ontology.base import BaseEntity


class OntologyInterface:
    """
    本体接口基类

    用法:
        class BookableResource(OntologyInterface):
            required_properties = {
                "name": ParamType.STRING,
                "status": ParamType.STRING,
                "capacity": ParamType.INTEGER,
            }
            required_actions = ["check_availability", "book"]
    """
    __is_ontology_interface__: ClassVar[bool] = True

    # 接口契约：实现类必须包含这些属性
    required_properties: ClassVar[Dict[str, ParamType]] = {}

    # 接口契约：实现类必须包含这些链接类型
    required_links: ClassVar[Dict[str, str]] = {}

    # 接口契约：实现类必须支持这些 Action
    required_actions: ClassVar[List[str]] = []

    @classmethod
    def validate_implementation(cls, entity_cls: Type) -> List[str]:
        """
        验证一个实体类是否满足接口契约

        检查实体类是否具有接口要求的属性和动作。
        属性检查基于 __ontology_properties__ 或类的实际属性/property。
        动作检查基于 __ontology_actions__ 或注册到 metadata registry 的动作。

        Args:
            entity_cls: 要验证的实体类

        Returns:
            不满足项列表（空列表 = 验证通过）
        """
        errors = []

        # 获取实体的属性集合
        entity_props = _get_entity_properties(entity_cls)

        # 验证必需属性
        for prop_name, prop_type in cls.required_properties.items():
            if prop_name not in entity_props:
                errors.append(f"Missing required property: '{prop_name}' (type: {prop_type.value})")

        # 验证必需动作
        entity_actions = _get_entity_actions(entity_cls)
        for action in cls.required_actions:
            if action not in entity_actions:
                errors.append(f"Missing required action: '{action}'")

        return errors


def _get_entity_properties(entity_cls: Type) -> set:
    """
    获取实体类的属性名集合

    支持多种属性声明方式：
    1. __ontology_properties__ 显式声明
    2. Python property 描述符
    3. 类型注解
    """
    props = set()

    # 方式1: 显式声明的本体属性
    if hasattr(entity_cls, '__ontology_properties__'):
        ontology_props = entity_cls.__ontology_properties__
        if isinstance(ontology_props, dict):
            props.update(ontology_props.keys())
        elif isinstance(ontology_props, (list, set)):
            props.update(ontology_props)

    # 方式2: Python property 描述符
    for name in dir(entity_cls):
        if name.startswith('_'):
            continue
        attr = getattr(entity_cls, name, None)
        if isinstance(attr, property):
            props.add(name)

    # 方式3: 类型注解
    annotations = getattr(entity_cls, '__annotations__', {})
    for name in annotations:
        if not name.startswith('_'):
            props.add(name)

    return props


def _get_entity_actions(entity_cls: Type) -> set:
    """
    获取实体类的动作名集合

    支持多种动作声明方式：
    1. __ontology_actions__ 显式声明
    2. 带 _ontology_action 标记的方法（由 @ontology_action 装饰器设置）
    """
    actions = set()

    # 方式1: 显式声明的本体动作
    if hasattr(entity_cls, '__ontology_actions__'):
        ontology_actions = entity_cls.__ontology_actions__
        if isinstance(ontology_actions, (list, set)):
            actions.update(ontology_actions)

    # 方式2: 带 _ontology_action 标记的方法
    for name in dir(entity_cls):
        if name.startswith('_'):
            continue
        attr = getattr(entity_cls, name, None)
        if callable(attr) and hasattr(attr, '_ontology_action'):
            action_meta = attr._ontology_action
            actions.add(action_meta.action_type)

    return actions


def implements(*interfaces: Type[OntologyInterface]):
    """
    装饰器：声明一个实体类实现指定接口

    自动验证实体是否满足接口契约，并将实现关系注册到注册中心。

    用法:
        @implements(BookableResource, Maintainable)
        class RoomEntity(BaseEntity):
            ...

    Args:
        interfaces: 接口类列表

    Returns:
        装饰器函数

    Raises:
        TypeError: 如果实体类不满足接口契约
    """
    def decorator(cls: Type) -> Type:
        from core.ontology.registry import registry

        errors = []
        implemented_interfaces = []

        for iface in interfaces:
            iface_errors = iface.validate_implementation(cls)
            if iface_errors:
                errors.extend([f"[{iface.__name__}] {e}" for e in iface_errors])
            else:
                implemented_interfaces.append(iface.__name__)

        if errors:
            raise TypeError(
                f"{cls.__name__} does not satisfy interface contracts:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

        # 注册接口实现关系到注册中心
        for iface in interfaces:
            registry.register_interface(iface)
            registry.register_interface_implementation(
                iface.__name__, cls.__name__
            )

        # 在类上记录实现的接口
        if not hasattr(cls, '__implements_interfaces__'):
            cls.__implements_interfaces__ = []
        cls.__implements_interfaces__.extend(interfaces)

        return cls

    return decorator


# 导出
__all__ = [
    "OntologyInterface",
    "implements",
]
