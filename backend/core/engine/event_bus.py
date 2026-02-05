"""
core/engine/event_bus.py

框架级事件总线 - 内存级发布/订阅模式
实现轻量级事件驱动架构，支持同步处理器和错误追踪
"""
from typing import Callable, Dict, List, Any, Optional, Protocol, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

# 类型别名
EventId = str
CorrelationId = str


def _generate_event_id() -> EventId:
    """生成唯一事件ID"""
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


class EventHandler(Protocol):
    """事件处理器协议"""

    def __call__(self, event: "Event") -> None:
        """处理事件"""
        ...


@dataclass
class Event:
    """
    事件基类

    Attributes:
        event_type: 事件类型（如 "room.status_changed"）
        timestamp: 事件时间戳
        data: 事件数据
        source: 触发来源（服务名）
        event_id: 唯一事件ID
        correlation_id: 关联ID（用于事件链追踪）
    """

    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str = ""
    event_id: EventId = field(default_factory=_generate_event_id)
    correlation_id: Optional[CorrelationId] = None

    def with_correlation(self, parent_id: EventId) -> "Event":
        """
        创建带关联ID的新事件

        Args:
            parent_id: 父事件ID

        Returns:
            新的事件对象，correlation_id 设置为 parent_id
        """
        self.correlation_id = parent_id
        return self


@dataclass
class PublishResult:
    """
    事件发布结果

    Attributes:
        event_type: 事件类型
        subscriber_count: 订阅者数量
        success_count: 成功处理的处理器数量
        failure_count: 失败的处理器数量
        errors: 处理器错误列表 (handler, exception) 元组
    """

    event_type: str
    subscriber_count: int
    success_count: int
    failure_count: int
    errors: List[Tuple[Callable, Exception]] = field(default_factory=list)


@dataclass
class EventBusStatistics:
    """
    事件总线统计

    Attributes:
        total_published: 总发布事件数
        total_processed: 总处理成功数
        total_failed: 总处理失败数
        subscriber_count: 各事件类型的订阅者数量
    """

    total_published: int = 0
    total_processed: int = 0
    total_failed: int = 0
    subscriber_count: Dict[str, int] = field(default_factory=dict)


class EventBus:
    """
    框架级事件总线 - 线程安全单例模式

    特性：
    - 内存级发布/订阅模式
    - 线程安全的订阅管理
    - 事件历史记录（可配置大小）
    - 处理器异常隔离
    - 统计信息收集

    Example:
        >>> bus = EventBus()
        >>> def handler(event):
        ...     print(f"Received: {event.event_type}")
        >>> bus.subscribe("test.event", handler)
        >>> bus.publish(Event(event_type="test.event", timestamp=datetime.now(), data={}))

    Thread Safety:
        所有公共方法都是线程安全的。
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls, history_size: int = 100) -> "EventBus":
        """单例模式 - 确保全局唯一实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, history_size: int = 100):
        """
        初始化事件总线

        Args:
            history_size: 事件历史记录最大条数
        """
        if self._initialized:
            return

        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._event_history: deque[Event] = deque(maxlen=history_size)
        self._subscriber_lock = threading.RLock()

        # 统计信息
        self._stats = EventBusStatistics()
        self._stats_lock = threading.Lock()

        self._history_size = history_size
        self._initialized = True
        logger.info("EventBus initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型（如 "room.status_changed"）
            handler: 处理函数，接收 Event 对象作为参数

        Example:
            >>> def my_handler(event: Event) -> None:
            ...     print(event.data)
            >>> bus.subscribe("my.event", my_handler)
        """
        with self._subscriber_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.info(f"Handler {handler.__name__} subscribed to {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 要取消的处理函数
        """
        with self._subscriber_lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.info(f"Handler {handler.__name__} unsubscribed from {event_type}")

    def publish(self, event: Event) -> PublishResult:
        """
        发布事件（同步执行所有处理器）

        处理器异常不会影响其他处理器的执行。
        返回处理结果统计。

        Args:
            event: 要发布的事件对象

        Returns:
            PublishResult 对象，包含处理统计
        """
        # 记录事件
        self._event_history.append(event)

        # 获取处理器（在锁内复制，避免长时间持锁）
        with self._subscriber_lock:
            handlers = self._subscribers.get(event.event_type, []).copy()

        # 更新统计
        with self._stats_lock:
            self._stats.total_published += 1

        result = PublishResult(
            event_type=event.event_type,
            subscriber_count=len(handlers),
            success_count=0,
            failure_count=0,
            errors=[],
        )

        if handlers:
            logger.info(f"Publishing {event.event_type} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(event)
                result.success_count += 1
                with self._stats_lock:
                    self._stats.total_processed += 1
            except Exception as e:
                result.failure_count += 1
                result.errors.append((handler, e))
                with self._stats_lock:
                    self._stats.total_failed += 1
                logger.error(
                    f"Event handler {handler.__name__} error for {event.event_type}: {e}",
                    exc_info=True,
                )

        return result

    def publish_many(self, events: List[Event]) -> List[PublishResult]:
        """
        批量发布事件

        Args:
            events: 事件列表

        Returns:
            每个事件的 PublishResult 列表

        Example:
            >>> events = [
            ...     Event(event_type="e1", timestamp=datetime.now(), data={}),
            ...     Event(event_type="e2", timestamp=datetime.now(), data={}),
            ... ]
            >>> results = bus.publish_many(events)
            >>> for r in results:
            ...     print(f"{r.event_type}: {r.success_count} successes")
        """
        return [self.publish(event) for event in events]

    def get_history(
        self, event_type: Optional[str] = None, limit: int = 50
    ) -> List[Event]:
        """
        获取事件历史（用于调试）

        Args:
            event_type: 可选，筛选特定类型的事件
            limit: 返回数量限制

        Returns:
            事件列表（最新的在前）
        """
        history = list(self._event_history)
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return list(reversed(history))[:limit]

    def get_subscribers(
        self, event_type: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        获取订阅者信息（用于调试）

        Args:
            event_type: 可选，筛选特定类型

        Returns:
            事件类型到处理器名称列表的映射
        """
        with self._subscriber_lock:
            if event_type:
                handlers = self._subscribers.get(event_type, [])
                return {event_type: [h.__name__ for h in handlers]}
            return {
                et: [h.__name__ for h in handlers]
                for et, handlers in self._subscribers.items()
            }

    def get_statistics(self) -> EventBusStatistics:
        """
        获取事件总线统计

        Returns:
            EventBusStatistics 对象的副本
        """
        with self._stats_lock:
            stats = EventBusStatistics(
                total_published=self._stats.total_published,
                total_processed=self._stats.total_processed,
                total_failed=self._stats.total_failed,
            )

        with self._subscriber_lock:
            stats.subscriber_count = {
                et: len(handlers) for et, handlers in self._subscribers.items()
            }

        return stats

    def clear_subscribers(self) -> None:
        """
        清空所有订阅（用于测试）

        Warning:
            此方法会清空所有订阅，仅应在测试环境中使用。
        """
        with self._subscriber_lock:
            self._subscribers.clear()
        logger.info("All subscribers cleared")

    def clear_history(self) -> None:
        """清空事件历史"""
        self._event_history.clear()

    def set_history_size(self, size: int) -> None:
        """
        设置历史记录大小（会清空现有历史）

        Args:
            size: 新的历史记录大小
        """
        self._history_size = size
        self._event_history = deque(maxlen=size)

    def reset_statistics(self) -> None:
        """
        重置统计信息（用于测试）

        Warning:
            此方法会重置所有统计，仅应在测试环境中使用。
        """
        with self._stats_lock:
            self._stats = EventBusStatistics()

    def clear(self) -> None:
        """
        完全清空事件总线（用于测试）

        Warning:
            此方法会清空所有数据，仅应在测试环境中使用。
        """
        self.clear_subscribers()
        self.clear_history()
        self.reset_statistics()


# 全局事件总线实例
event_bus = EventBus()


# 导出
__all__ = [
    "EventId",
    "CorrelationId",
    "EventHandler",
    "Event",
    "PublishResult",
    "EventBusStatistics",
    "EventBus",
    "event_bus",
]
