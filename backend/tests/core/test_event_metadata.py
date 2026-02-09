"""
测试 SPEC-23: EventMetadata - 领域事件元数据
"""
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import EventMetadata


@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前清空注册表"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


def test_event_metadata_creation():
    """测试 EventMetadata 数据类创建"""
    event = EventMetadata(
        name="ROOM_STATUS_CHANGED",
        description="房间状态发生变化",
        entity="Room",
        triggered_by=["check_in", "check_out"],
        payload_fields=["room_id", "old_status", "new_status"],
        subscribers=["TaskService", "NotificationService"],
    )

    assert event.name == "ROOM_STATUS_CHANGED"
    assert event.description == "房间状态发生变化"
    assert event.entity == "Room"
    assert event.triggered_by == ["check_in", "check_out"]
    assert event.payload_fields == ["room_id", "old_status", "new_status"]
    assert event.subscribers == ["TaskService", "NotificationService"]


def test_event_metadata_defaults():
    """测试 EventMetadata 默认值"""
    event = EventMetadata(name="TEST_EVENT")

    assert event.name == "TEST_EVENT"
    assert event.description == ""
    assert event.entity == ""
    assert event.triggered_by == []
    assert event.payload_fields == []
    assert event.subscribers == []


def test_register_event(clean_registry):
    """测试注册事件到 registry"""
    reg = clean_registry

    event = EventMetadata(
        name="GUEST_CHECKED_IN",
        description="客人办理入住",
        entity="Guest",
        triggered_by=["walkin_checkin", "checkin"],
        payload_fields=["guest_id", "room_id", "stay_record_id"],
    )

    result = reg.register_event(event)

    # 流式 API 返回 self
    assert result is reg

    retrieved = reg.get_event("GUEST_CHECKED_IN")
    assert retrieved is event
    assert retrieved.name == "GUEST_CHECKED_IN"


def test_get_events_all(clean_registry):
    """测试获取所有事件"""
    reg = clean_registry

    reg.register_event(EventMetadata(name="EVENT_A", entity="Room"))
    reg.register_event(EventMetadata(name="EVENT_B", entity="Guest"))
    reg.register_event(EventMetadata(name="EVENT_C", entity="Task"))

    events = reg.get_events()
    assert len(events) == 3
    event_names = {e.name for e in events}
    assert event_names == {"EVENT_A", "EVENT_B", "EVENT_C"}


def test_get_events_by_entity(clean_registry):
    """测试按实体过滤事件"""
    reg = clean_registry

    reg.register_event(EventMetadata(name="ROOM_STATUS_CHANGED", entity="Room"))
    reg.register_event(EventMetadata(name="GUEST_CHECKED_IN", entity="Guest"))
    reg.register_event(EventMetadata(name="GUEST_CHECKED_OUT", entity="Guest"))
    reg.register_event(EventMetadata(name="TASK_COMPLETED", entity="Task"))

    room_events = reg.get_events(entity="Room")
    assert len(room_events) == 1
    assert room_events[0].name == "ROOM_STATUS_CHANGED"

    guest_events = reg.get_events(entity="Guest")
    assert len(guest_events) == 2
    guest_event_names = {e.name for e in guest_events}
    assert guest_event_names == {"GUEST_CHECKED_IN", "GUEST_CHECKED_OUT"}

    # 不存在的实体返回空列表
    empty_events = reg.get_events(entity="NonExistent")
    assert empty_events == []


def test_get_event_by_name(clean_registry):
    """测试按名称获取单个事件"""
    reg = clean_registry

    event = EventMetadata(
        name="TASK_COMPLETED",
        description="任务完成",
        entity="Task",
        triggered_by=["complete_task"],
        payload_fields=["task_id", "assignee_id"],
    )
    reg.register_event(event)

    retrieved = reg.get_event("TASK_COMPLETED")
    assert retrieved is event

    # 不存在的事件返回 None
    assert reg.get_event("NON_EXISTENT") is None


def test_event_in_export_schema(clean_registry):
    """测试事件包含在 export_schema 输出中"""
    reg = clean_registry

    reg.register_event(EventMetadata(
        name="PAYMENT_RECEIVED",
        description="收到支付",
        entity="Bill",
        triggered_by=["add_payment"],
        payload_fields=["bill_id", "payment_id", "amount"],
        subscribers=["AccountingService"],
    ))

    schema = reg.export_schema()

    assert "events" in schema
    assert "PAYMENT_RECEIVED" in schema["events"]

    event_data = schema["events"]["PAYMENT_RECEIVED"]
    assert event_data["name"] == "PAYMENT_RECEIVED"
    assert event_data["description"] == "收到支付"
    assert event_data["entity"] == "Bill"
    assert event_data["triggered_by"] == ["add_payment"]
    assert event_data["payload_fields"] == ["bill_id", "payment_id", "amount"]
    assert event_data["subscribers"] == ["AccountingService"]


def test_clear_clears_events(clean_registry):
    """测试 clear() 清空事件"""
    reg = clean_registry

    reg.register_event(EventMetadata(name="EVENT_A", entity="Room"))
    reg.register_event(EventMetadata(name="EVENT_B", entity="Guest"))

    assert len(reg.get_events()) == 2

    reg.clear()

    assert len(reg.get_events()) == 0
    assert reg.get_event("EVENT_A") is None
    assert reg.get_event("EVENT_B") is None


def test_register_duplicate_event_overwrites(clean_registry):
    """测试注册同名事件会覆盖"""
    reg = clean_registry

    event1 = EventMetadata(
        name="ROOM_STATUS_CHANGED",
        description="旧描述",
        entity="Room",
    )
    event2 = EventMetadata(
        name="ROOM_STATUS_CHANGED",
        description="新描述",
        entity="Room",
        triggered_by=["check_in"],
    )

    reg.register_event(event1)
    reg.register_event(event2)

    # 应该只有一个事件
    events = reg.get_events()
    assert len(events) == 1

    retrieved = reg.get_event("ROOM_STATUS_CHANGED")
    assert retrieved is event2
    assert retrieved.description == "新描述"
    assert retrieved.triggered_by == ["check_in"]
