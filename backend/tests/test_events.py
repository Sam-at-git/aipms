"""
领域事件单元测试
"""
import pytest
from datetime import datetime

from app.models.events import (
    EventType, BaseEventData, GuestCheckedInData, GuestCheckedOutData,
    TaskCreatedData, TaskCompletedData, RoomStatusChangedData,
    StayExtendedData, RoomChangedData, EVENT_DATA_CLASSES
)


class TestEventType:
    """事件类型枚举测试"""

    def test_event_type_values(self):
        """测试事件类型值"""
        assert EventType.GUEST_CHECKED_IN == "guest.checked_in"
        assert EventType.GUEST_CHECKED_OUT == "guest.checked_out"
        assert EventType.ROOM_STATUS_CHANGED == "room.status_changed"
        assert EventType.TASK_CREATED == "task.created"
        assert EventType.TASK_COMPLETED == "task.completed"

    def test_event_type_is_string(self):
        """测试事件类型是字符串"""
        assert isinstance(EventType.GUEST_CHECKED_IN.value, str)


class TestBaseEventData:
    """事件数据基类测试"""

    def test_default_timestamp(self):
        """测试默认时间戳"""
        data = BaseEventData()
        assert data.timestamp is not None
        assert isinstance(data.timestamp, datetime)

    def test_to_dict(self):
        """测试转换为字典"""
        data = BaseEventData()
        result = data.to_dict()
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)


class TestGuestCheckedInData:
    """入住事件数据测试"""

    def test_create_event_data(self):
        """测试创建入住事件数据"""
        data = GuestCheckedInData(
            stay_record_id=1,
            guest_id=1,
            guest_name="张三",
            room_id=101,
            room_number="101",
            check_in_time=datetime.now(),
            expected_check_out="2024-01-15",
            operator_id=1,
            is_walkin=False
        )

        assert data.stay_record_id == 1
        assert data.guest_name == "张三"
        assert data.is_walkin == False

    def test_to_dict_serialization(self):
        """测试序列化"""
        data = GuestCheckedInData(
            stay_record_id=1,
            guest_id=1,
            guest_name="张三",
            room_id=101,
            room_number="101",
            check_in_time=datetime.now(),
            expected_check_out="2024-01-15",
            operator_id=1
        )

        result = data.to_dict()
        assert isinstance(result, dict)
        assert result["guest_name"] == "张三"
        assert "check_in_time" in result


class TestGuestCheckedOutData:
    """退房事件数据测试"""

    def test_create_checkout_data(self):
        """测试创建退房事件数据"""
        data = GuestCheckedOutData(
            stay_record_id=1,
            guest_id=1,
            guest_name="张三",
            room_id=101,
            room_number="101",
            check_out_time=datetime.now(),
            total_amount=576.00,
            paid_amount=576.00,
            operator_id=1
        )

        assert data.total_amount == 576.00
        assert data.paid_amount == 576.00


class TestTaskCreatedData:
    """任务创建事件数据测试"""

    def test_create_task_data(self):
        """测试创建任务事件数据"""
        data = TaskCreatedData(
            task_id=1,
            task_type="cleaning",
            room_id=101,
            room_number="101",
            priority=2,
            notes="退房清洁",
            created_by=1,
            trigger="auto_checkout"
        )

        assert data.task_type == "cleaning"
        assert data.trigger == "auto_checkout"


class TestTaskCompletedData:
    """任务完成事件数据测试"""

    def test_create_completion_data(self):
        """测试创建任务完成事件数据"""
        data = TaskCompletedData(
            task_id=1,
            task_type="cleaning",
            room_id=101,
            room_number="101",
            completed_by=2,
            completed_by_name="清洁员小李",
            completion_time=datetime.now()
        )

        assert data.completed_by_name == "清洁员小李"


class TestRoomStatusChangedData:
    """房间状态变更事件数据测试"""

    def test_create_status_change_data(self):
        """测试创建房间状态变更事件数据"""
        data = RoomStatusChangedData(
            room_id=101,
            room_number="101",
            old_status="occupied",
            new_status="vacant_dirty",
            changed_by=1,
            reason="退房"
        )

        assert data.old_status == "occupied"
        assert data.new_status == "vacant_dirty"


class TestStayExtendedData:
    """续住事件数据测试"""

    def test_create_extend_data(self):
        """测试创建续住事件数据"""
        data = StayExtendedData(
            stay_record_id=1,
            guest_id=1,
            guest_name="张三",
            room_id=101,
            room_number="101",
            old_check_out="2024-01-15",
            new_check_out="2024-01-17",
            operator_id=1
        )

        assert data.old_check_out == "2024-01-15"
        assert data.new_check_out == "2024-01-17"


class TestRoomChangedData:
    """换房事件数据测试"""

    def test_create_room_change_data(self):
        """测试创建换房事件数据"""
        data = RoomChangedData(
            stay_record_id=1,
            guest_id=1,
            guest_name="张三",
            old_room_id=101,
            old_room_number="101",
            new_room_id=102,
            new_room_number="102",
            operator_id=1
        )

        assert data.old_room_number == "101"
        assert data.new_room_number == "102"


class TestEventDataClasses:
    """事件数据类映射测试"""

    def test_mapping_exists(self):
        """测试映射存在"""
        assert EventType.GUEST_CHECKED_IN in EVENT_DATA_CLASSES
        assert EventType.GUEST_CHECKED_OUT in EVENT_DATA_CLASSES
        assert EventType.TASK_COMPLETED in EVENT_DATA_CLASSES

    def test_mapping_correct_class(self):
        """测试映射正确的类"""
        assert EVENT_DATA_CLASSES[EventType.GUEST_CHECKED_IN] == GuestCheckedInData
        assert EVENT_DATA_CLASSES[EventType.GUEST_CHECKED_OUT] == GuestCheckedOutData
        assert EVENT_DATA_CLASSES[EventType.TASK_COMPLETED] == TaskCompletedData
