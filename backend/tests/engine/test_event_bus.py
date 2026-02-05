"""
测试 core.engine.event_bus 事件总线
"""
import pytest
from datetime import datetime
from core.engine.event_bus import (
    Event,
    PublishResult,
    EventBusStatistics,
    EventBus,
    event_bus,
)


def test_event_creation():
    """测试事件创建"""
    event = Event(event_type="test", timestamp=datetime.now(), data={"key": "value"})
    assert event.event_type == "test"
    assert event.data == {"key": "value"}
    assert event.event_id is not None
    assert len(event.event_id) > 0


def test_event_with_correlation():
    """测试事件关联ID"""
    parent = Event(event_type="parent", timestamp=datetime.now(), data={})
    child = Event(event_type="child", timestamp=datetime.now(), data={})
    child.with_correlation(parent.event_id)

    assert child.correlation_id == parent.event_id


def test_event_source_default():
    """测试事件默认来源"""
    event = Event(event_type="test", timestamp=datetime.now(), data={})
    assert event.source == ""


def test_event_source_custom():
    """测试自定义事件来源"""
    event = Event(event_type="test", timestamp=datetime.now(), data={}, source="test_service")
    assert event.source == "test_service"


def test_event_bus_singleton():
    """测试事件总线单例模式"""
    bus1 = EventBus()
    bus2 = EventBus()
    assert bus1 is bus2


def test_global_event_bus_is_singleton():
    """测试全局事件总线是单例"""
    bus = EventBus()
    assert event_bus is bus


def test_subscribe_and_publish():
    """测试订阅和发布"""
    bus = EventBus()
    bus.clear()  # 清空之前的状态

    received = []

    def handler(event):
        received.append(event)

    bus.subscribe("test", handler)
    event = Event(event_type="test", timestamp=datetime.now(), data={"msg": "hello"})
    result = bus.publish(event)

    assert len(received) == 1
    assert received[0] is event
    assert result.success_count == 1
    assert result.failure_count == 0
    assert result.subscriber_count == 1


def test_subscribe_same_handler_once():
    """测试同一处理器只订阅一次"""
    bus = EventBus()
    bus.clear()

    count = 0

    def handler(event):
        nonlocal count
        count += 1

    bus.subscribe("test", handler)
    bus.subscribe("test", handler)  # 重复订阅

    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    assert count == 1  # 应该只被调用一次


def test_unsubscribe():
    """测试取消订阅"""
    bus = EventBus()
    bus.clear()

    count = 0

    def handler(event):
        nonlocal count
        count += 1

    bus.subscribe("test", handler)
    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))
    assert count == 1

    bus.unsubscribe("test", handler)
    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))
    assert count == 1  # 不应该再被调用


def test_publish_with_no_subscribers():
    """测试发布到无订阅者的事件"""
    bus = EventBus()
    bus.clear()

    result = bus.publish(Event(event_type="no_subs", timestamp=datetime.now(), data={}))

    assert result.subscriber_count == 0
    assert result.success_count == 0
    assert result.failure_count == 0


def test_publish_with_error_handler():
    """测试处理器异常处理"""
    bus = EventBus()
    bus.clear()

    class CustomError(Exception):
        pass

    def failing_handler(event):
        raise CustomError("Test error")

    bus.subscribe("test", failing_handler)
    result = bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    assert result.failure_count == 1
    assert result.success_count == 0
    assert len(result.errors) == 1
    assert isinstance(result.errors[0][1], CustomError)


def test_publish_multiple_handlers():
    """测试发布到多个处理器"""
    bus = EventBus()
    bus.clear()

    results = []

    def handler1(event):
        results.append("h1")

    def handler2(event):
        results.append("h2")

    bus.subscribe("test", handler1)
    bus.subscribe("test", handler2)

    result = bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    assert len(results) == 2
    assert result.success_count == 2


def test_publish_mixed_success_failure():
    """测试混合成功和失败的处理器"""
    bus = EventBus()
    bus.clear()

    def success_handler(event):
        pass

    def failing_handler(event):
        raise ValueError("Error")

    bus.subscribe("test", success_handler)
    bus.subscribe("test", failing_handler)

    result = bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    assert result.success_count == 1
    assert result.failure_count == 1


def test_publish_many():
    """测试批量发布"""
    bus = EventBus()
    bus.clear()

    results = []

    def handler(event):
        results.append(event.event_type)

    bus.subscribe("test", handler)

    events = [
        Event(event_type="test", timestamp=datetime.now(), data={"id": 1}),
        Event(event_type="test", timestamp=datetime.now(), data={"id": 2}),
    ]

    publish_results = bus.publish_many(events)

    assert len(publish_results) == 2
    assert len(results) == 2
    assert all(r.success_count == 1 for r in publish_results)


def test_event_history():
    """测试事件历史记录"""
    bus = EventBus(history_size=10)
    bus.clear()

    events = [
        Event(event_type="e1", timestamp=datetime.now(), data={"id": i}) for i in range(5)
    ]

    for e in events:
        bus.publish(e)

    history = bus.get_history()
    assert len(history) == 5
    # 最新的在前
    assert history[0].data["id"] == 4
    assert history[-1].data["id"] == 0


def test_event_history_filtered():
    """测试按类型筛选事件历史"""
    bus = EventBus()
    bus.clear()

    bus.publish(Event(event_type="type_a", timestamp=datetime.now(), data={}))
    bus.publish(Event(event_type="type_b", timestamp=datetime.now(), data={}))
    bus.publish(Event(event_type="type_a", timestamp=datetime.now(), data={}))

    history_a = bus.get_history(event_type="type_a")
    assert len(history_a) == 2

    history_b = bus.get_history(event_type="type_b")
    assert len(history_b) == 1


def test_event_history_limit():
    """测试历史记录数量限制"""
    bus = EventBus()
    bus.clear()
    bus.set_history_size(3)  # 设置历史大小为3

    for i in range(5):
        bus.publish(Event(event_type=f"e{i}", timestamp=datetime.now(), data={"id": i}))

    history = bus.get_history(limit=10)
    assert len(history) == 3  # 只保留最新的3条


def test_get_subscribers():
    """测试获取订阅者信息"""
    bus = EventBus()
    bus.clear()

    def handler1(event):
        pass

    def handler2(event):
        pass

    bus.subscribe("type_a", handler1)
    bus.subscribe("type_a", handler2)
    bus.subscribe("type_b", handler1)

    subs = bus.get_subscribers()
    assert "type_a" in subs
    assert "type_b" in subs
    assert len(subs["type_a"]) == 2
    assert len(subs["type_b"]) == 1


def test_get_subscribers_filtered():
    """测试按类型获取订阅者"""
    bus = EventBus()
    bus.clear()

    def handler(event):
        pass

    bus.subscribe("type_a", handler)
    bus.subscribe("type_b", handler)

    subs_a = bus.get_subscribers(event_type="type_a")
    assert "type_a" in subs_a
    assert "type_b" not in subs_a
    assert len(subs_a["type_a"]) == 1


def test_statistics():
    """测试统计信息"""
    bus = EventBus()
    bus.clear()
    bus.reset_statistics()

    events = [
        Event(event_type="e1", timestamp=datetime.now(), data={}),
        Event(event_type="e2", timestamp=datetime.now(), data={}),
    ]

    def handler(event):
        pass

    def failing_handler(event):
        raise ValueError("Error")

    bus.subscribe("e1", handler)
    bus.subscribe("e2", handler)
    bus.subscribe("e2", failing_handler)

    bus.publish_many(events)

    stats = bus.get_statistics()
    assert stats.total_published == 2
    assert stats.total_processed == 2  # e1: 1, e2: 1
    assert stats.total_failed == 1  # e2: 1 failure
    assert stats.subscriber_count["e1"] == 1
    assert stats.subscriber_count["e2"] == 2


def test_clear_subscribers():
    """测试清空订阅者"""
    bus = EventBus()

    def handler(event):
        pass

    bus.subscribe("test", handler)
    assert len(bus.get_subscribers()) > 0

    bus.clear_subscribers()
    assert len(bus.get_subscribers()) == 0


def test_clear_history():
    """测试清空历史"""
    bus = EventBus()
    bus.clear()

    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))
    assert len(bus.get_history()) > 0

    bus.clear_history()
    assert len(bus.get_history()) == 0


def test_reset_statistics():
    """测试重置统计"""
    bus = EventBus()
    bus.clear()
    bus.reset_statistics()

    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    stats = bus.get_statistics()
    assert stats.total_published == 1

    bus.reset_statistics()
    stats = bus.get_statistics()
    assert stats.total_published == 0


def test_clear_all():
    """测试完全清空"""
    bus = EventBus()

    def handler(event):
        pass

    bus.subscribe("test", handler)
    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    assert len(bus.get_subscribers()) > 0
    assert len(bus.get_history()) > 0

    bus.clear()

    assert len(bus.get_subscribers()) == 0
    assert len(bus.get_history()) == 0
    assert bus.get_statistics().total_published == 0


def test_publish_result_attributes():
    """测试发布结果属性"""
    result = PublishResult(
        event_type="test",
        subscriber_count=5,
        success_count=4,
        failure_count=1,
    )

    assert result.event_type == "test"
    assert result.subscriber_count == 5
    assert result.success_count == 4
    assert result.failure_count == 1
    assert result.errors == []


def test_statistics_defaults():
    """测试统计信息默认值"""
    stats = EventBusStatistics()
    assert stats.total_published == 0
    assert stats.total_processed == 0
    assert stats.total_failed == 0
    assert stats.subscriber_count == {}


def test_event_data_mutation():
    """测试事件数据可以被修改"""
    event = Event(event_type="test", timestamp=datetime.now(), data={"count": 0})
    event.data["count"] = 10
    assert event.data["count"] == 10


def test_multiple_event_buses_independent():
    """测试多个独立的事件总线实例"""
    # 注意：EventBus 是单例，所以这里只验证全局实例的行为
    bus = EventBus()
    bus.clear()

    received_global = []

    def handler(event):
        received_global.append(event)

    event_bus.subscribe("test", handler)
    bus.publish(Event(event_type="test", timestamp=datetime.now(), data={}))

    # 由于是单例，event_bus 和 bus 是同一个实例
    assert len(received_global) == 1
