"""
事件总线 - 内存级发布/订阅模式
实现轻量级事件驱动架构，解耦业务模块
"""
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件基类"""
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str  # 触发来源（服务名）
    event_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))


class EventBus:
    """
    内存级事件总线（线程安全单例模式）

    使用方式：
    1. 订阅事件：event_bus.subscribe("room.status_changed", handler_func)
    2. 发布事件：event_bus.publish(Event(...))
    3. 取消订阅：event_bus.unsubscribe("room.status_changed", handler_func)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: deque = deque(maxlen=100)  # 保留最近100条用于调试
        self._subscriber_lock = threading.Lock()
        self._initialized = True
        logger.info("EventBus initialized")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型（如 "room.status_changed"）
            handler: 处理函数，接收 Event 对象作为参数
        """
        with self._subscriber_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.info(f"Handler {handler.__name__} subscribed to {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
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

    def publish(self, event: Event) -> None:
        """
        发布事件（同步执行所有处理器）

        处理器异常不会影响其他处理器的执行

        Args:
            event: 要发布的事件对象
        """
        self._event_history.append(event)

        with self._subscriber_lock:
            handlers = self._subscribers.get(event.event_type, []).copy()

        if handlers:
            logger.info(f"Publishing {event.event_type} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler {handler.__name__} error for {event.event_type}: {e}",
                    exc_info=True
                )

    def publish_many(self, events: List[Event]) -> None:
        """
        批量发布事件

        Args:
            events: 事件列表
        """
        for event in events:
            self.publish(event)

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[Event]:
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

    def get_subscribers(self, event_type: Optional[str] = None) -> Dict[str, List[str]]:
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

    def clear_subscribers(self) -> None:
        """清空所有订阅（用于测试）"""
        with self._subscriber_lock:
            self._subscribers.clear()
        logger.info("All subscribers cleared")

    def clear_history(self) -> None:
        """清空事件历史"""
        self._event_history.clear()


# 全局事件总线实例
event_bus = EventBus()
