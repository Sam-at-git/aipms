"""
core/ontology/link.py

对象链接抽象 - Palantir 式架构的关系层
定义对象之间的链接关系，支持延迟加载和类型安全
"""
from typing import TYPE_CHECKING, Optional, Generic, TypeVar, Any

if TYPE_CHECKING:
    from core.ontology.base import BaseEntity

T = TypeVar("T", bound="BaseEntity")


class Link(Generic[T]):
    """
    对象链接 - 延迟加载的实体引用

    Link 表示对另一个实体的引用，支持延迟加载和类型安全。
    这是 Palantir 式架构中对象关系的核心抽象。

    Example:
        >>> class Room(BaseEntity):
        ...     room_type: Link[RoomType] = Link()
        ...
        >>> room = Room(id=1)
        >>> room.room_type.set(target_type)
        >>> room_type = room.room_type.get()

    Attributes:
        _target: 目标实体对象
        _target_type: 目标实体类型
    """

    def __init__(self, target: Optional["BaseEntity"] = None):
        """
        初始化链接

        Args:
            target: 目标实体，如果为 None 则为空链接
        """
        self._target: Optional["BaseEntity"] = target

    def get(self) -> Optional[T]:
        """
        获取目标实体

        Returns:
            目标实体，如果未设置则返回 None
        """
        return self._target

    def set(self, target: "BaseEntity") -> None:
        """
        设置目标实体

        Args:
            target: 目标实体
        """
        self._target = target

    def is_loaded(self) -> bool:
        """
        检查链接是否已加载

        Returns:
            如果目标实体已设置则返回 True
        """
        return self._target is not None

    def clear(self) -> None:
        """清除链接"""
        self._target = None

    def __repr__(self) -> str:
        """字符串表示"""
        if self._target is not None:
            return f"Link({repr(self._target)})"
        return "Link(None)"


class LinkCollection(Generic[T]):
    """
    链接集合 - 表示一对多关系

    LinkCollection 是多个实体引用的集合，支持延迟加载。

    Example:
        >>> class RoomType(BaseEntity):
        ...     rooms: LinkCollection[Room] = LinkCollection()
        ...
        >>> room_type = RoomType(id=1)
        >>> room_type.rooms.add(room1)
        >>> room_type.rooms.add(room2)
        >>> for room in room_type.rooms:
        ...     print(room.room_number)

    Attributes:
        _items: 目标实体列表
    """

    def __init__(self, items: Optional[list["BaseEntity"]] = None):
        """
        初始化链接集合

        Args:
            items: 初始实体列表
        """
        self._items: list["BaseEntity"] = list(items) if items else []

    def add(self, item: "BaseEntity") -> None:
        """
        添加实体到集合

        Args:
            item: 要添加的实体
        """
        if item not in self._items:
            self._items.append(item)

    def remove(self, item: "BaseEntity") -> None:
        """
        从集合中移除实体

        Args:
            item: 要移除的实体

        Raises:
            ValueError: 如果实体不在集合中
        """
        self._items.remove(item)

    def clear(self) -> None:
        """清空集合"""
        self._items.clear()

    def all(self) -> list[T]:
        """
        获取所有实体

        Returns:
            实体列表
        """
        return list(self._items)

    def __iter__(self):
        """支持迭代"""
        return iter(self._items)

    def __len__(self) -> int:
        """支持 len()"""
        return len(self._items)

    def __contains__(self, item: "BaseEntity") -> bool:
        """支持 in 操作符"""
        return item in self._items

    def __repr__(self) -> str:
        """字符串表示"""
        return f"LinkCollection({len(self._items)} items)"


# 导出
__all__ = ["Link", "LinkCollection"]
