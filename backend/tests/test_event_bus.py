"""
事件总线单元测试
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.services.event_bus import EventBus, Event


class TestEventBus:
    """事件总线测试"""

    @pytest.fixture
    def event_bus(self):
        """创建新的事件总线实例"""
        bus = EventBus()
        bus.clear_subscribers()
        bus.clear_history()
        return bus

    @pytest.fixture
    def sample_event(self):
        """创建示例事件"""
        return Event(
            event_type="test.event",
            timestamp=datetime.now(),
            data={"key": "value"},
            source="test"
        )

    def test_subscribe_and_publish(self, event_bus, sample_event):
        """测试订阅和发布"""
        received_events = []

        def handler(event):
            received_events.append(event)

        event_bus.subscribe("test.event", handler)
        event_bus.publish(sample_event)

        assert len(received_events) == 1
        assert received_events[0].event_type == "test.event"
        assert received_events[0].data["key"] == "value"

    def test_multiple_handlers(self, event_bus, sample_event):
        """测试多个处理器"""
        call_count = [0, 0]

        def handler1(event):
            call_count[0] += 1

        def handler2(event):
            call_count[1] += 1

        event_bus.subscribe("test.event", handler1)
        event_bus.subscribe("test.event", handler2)
        event_bus.publish(sample_event)

        assert call_count[0] == 1
        assert call_count[1] == 1

    def test_unsubscribe(self, event_bus, sample_event):
        """测试取消订阅"""
        received_events = []

        def handler(event):
            received_events.append(event)

        event_bus.subscribe("test.event", handler)
        event_bus.unsubscribe("test.event", handler)
        event_bus.publish(sample_event)

        assert len(received_events) == 0

    def test_handler_exception_isolation(self, event_bus, sample_event):
        """测试处理器异常隔离"""
        successful_calls = []

        def failing_handler(event):
            raise ValueError("Test error")

        def successful_handler(event):
            successful_calls.append(event)

        event_bus.subscribe("test.event", failing_handler)
        event_bus.subscribe("test.event", successful_handler)

        # 不应该抛出异常
        event_bus.publish(sample_event)

        # 成功的处理器应该被调用
        assert len(successful_calls) == 1

    def test_event_history(self, event_bus):
        """测试事件历史"""
        for i in range(5):
            event = Event(
                event_type="test.event",
                timestamp=datetime.now(),
                data={"index": i},
                source="test"
            )
            event_bus.publish(event)

        history = event_bus.get_history()
        assert len(history) == 5

        # 最新的在前
        assert history[0].data["index"] == 4

    def test_event_history_filter(self, event_bus):
        """测试事件历史筛选"""
        event_bus.publish(Event(
            event_type="type.a",
            timestamp=datetime.now(),
            data={},
            source="test"
        ))
        event_bus.publish(Event(
            event_type="type.b",
            timestamp=datetime.now(),
            data={},
            source="test"
        ))

        history_a = event_bus.get_history(event_type="type.a")
        assert len(history_a) == 1
        assert history_a[0].event_type == "type.a"

    def test_event_history_limit(self, event_bus):
        """测试事件历史数量限制"""
        # 发布超过限制的事件
        for i in range(150):
            event_bus.publish(Event(
                event_type="test.event",
                timestamp=datetime.now(),
                data={"index": i},
                source="test"
            ))

        history = event_bus.get_history(limit=100)
        # 只保留最近100条
        assert len(history) <= 100

    def test_no_handlers_for_event_type(self, event_bus, sample_event):
        """测试没有处理器的事件类型"""
        # 不应该抛出异常
        event_bus.publish(sample_event)

    def test_get_subscribers(self, event_bus):
        """测试获取订阅者信息"""
        def handler1(event):
            pass

        def handler2(event):
            pass

        event_bus.subscribe("type.a", handler1)
        event_bus.subscribe("type.a", handler2)
        event_bus.subscribe("type.b", handler1)

        subscribers = event_bus.get_subscribers()
        assert "type.a" in subscribers
        assert len(subscribers["type.a"]) == 2
        assert "type.b" in subscribers
        assert len(subscribers["type.b"]) == 1

    def test_duplicate_subscription(self, event_bus, sample_event):
        """测试重复订阅"""
        call_count = [0]

        def handler(event):
            call_count[0] += 1

        event_bus.subscribe("test.event", handler)
        event_bus.subscribe("test.event", handler)  # 重复订阅
        event_bus.publish(sample_event)

        # 应该只调用一次
        assert call_count[0] == 1

    def test_publish_many(self, event_bus):
        """测试批量发布"""
        received_events = []

        def handler(event):
            received_events.append(event)

        event_bus.subscribe("test.event", handler)

        events = [
            Event(event_type="test.event", timestamp=datetime.now(), data={"i": i}, source="test")
            for i in range(3)
        ]
        event_bus.publish_many(events)

        assert len(received_events) == 3

    def test_clear_subscribers(self, event_bus, sample_event):
        """测试清空订阅者"""
        received_events = []

        def handler(event):
            received_events.append(event)

        event_bus.subscribe("test.event", handler)
        event_bus.clear_subscribers()
        event_bus.publish(sample_event)

        assert len(received_events) == 0

    def test_singleton_pattern(self):
        """测试单例模式"""
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2
