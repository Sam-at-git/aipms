"""
事件处理器单元测试
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from app.services.event_bus import Event, EventBus
from app.services.event_handlers import EventHandlers
from app.models.events import EventType
from app.models.ontology import Task, TaskType, TaskStatus, Room, RoomStatus


class TestEventHandlers:
    """事件处理器测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.close = MagicMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_db_session):
        """创建模拟会话工厂"""
        return lambda: mock_db_session

    @pytest.fixture
    def event_handlers(self, mock_session_factory):
        """创建事件处理器实例"""
        return EventHandlers(db_session_factory=mock_session_factory)

    def test_handle_guest_checked_out_creates_task(self, event_handlers, mock_db_session):
        """测试退房事件创建清洁任务"""
        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                "stay_record_id": 1,
                "guest_id": 1,
                "guest_name": "张三",
                "room_id": 101,
                "room_number": "101",
                "operator_id": 1
            },
            source="checkout_service"
        )

        event_handlers.handle_guest_checked_out(event)

        # 验证添加了任务
        mock_db_session.add.assert_called_once()
        added_task = mock_db_session.add.call_args[0][0]
        assert isinstance(added_task, Task)
        assert added_task.task_type == TaskType.CLEANING
        assert added_task.room_id == 101
        assert added_task.status == TaskStatus.PENDING

        # 验证提交了事务
        mock_db_session.commit.assert_called_once()

    def test_handle_guest_checked_out_missing_room_id(self, event_handlers, mock_db_session):
        """测试退房事件缺少房间ID"""
        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                "guest_name": "张三"
                # 缺少 room_id
            },
            source="checkout_service"
        )

        event_handlers.handle_guest_checked_out(event)

        # 不应该添加任务
        mock_db_session.add.assert_not_called()

    def test_handle_task_completed_updates_room_status(self, event_handlers, mock_db_session):
        """测试任务完成更新房间状态"""
        # 模拟房间查询
        mock_room = MagicMock(spec=Room)
        mock_room.status = RoomStatus.VACANT_DIRTY
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_id": 1,
                "task_type": "cleaning",
                "room_id": 101,
                "room_number": "101",
                "completed_by": 2
            },
            source="task_service"
        )

        event_handlers.handle_task_completed(event)

        # 验证房间状态被更新
        assert mock_room.status == RoomStatus.VACANT_CLEAN
        mock_db_session.commit.assert_called_once()

    def test_handle_task_completed_non_cleaning_task(self, event_handlers, mock_db_session):
        """测试非清洁任务完成不更新房间状态"""
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_id": 1,
                "task_type": "maintenance",  # 维修任务
                "room_id": 101,
                "room_number": "101"
            },
            source="task_service"
        )

        event_handlers.handle_task_completed(event)

        # 不应该查询房间
        mock_db_session.query.assert_not_called()

    def test_handle_room_changed_creates_cleaning_task(self, event_handlers, mock_db_session):
        """测试换房事件创建清洁任务"""
        event = Event(
            event_type=EventType.ROOM_CHANGED,
            timestamp=datetime.now(),
            data={
                "stay_record_id": 1,
                "guest_name": "张三",
                "old_room_id": 101,
                "old_room_number": "101",
                "new_room_id": 102,
                "new_room_number": "102",
                "operator_id": 1
            },
            source="checkin_service"
        )

        event_handlers.handle_room_changed(event)

        # 验证为原房间添加了清洁任务
        mock_db_session.add.assert_called_once()
        added_task = mock_db_session.add.call_args[0][0]
        assert isinstance(added_task, Task)
        assert added_task.room_id == 101  # 原房间
        assert added_task.task_type == TaskType.CLEANING

    def test_register_handlers(self, event_handlers):
        """测试注册处理器"""
        mock_bus = MagicMock(spec=EventBus)

        event_handlers.register_handlers(mock_bus)

        # 验证订阅了正确的事件
        assert mock_bus.subscribe.call_count == 3
        event_types = [call[0][0] for call in mock_bus.subscribe.call_args_list]
        assert EventType.GUEST_CHECKED_OUT in event_types
        assert EventType.TASK_COMPLETED in event_types
        assert EventType.ROOM_CHANGED in event_types

    def test_unregister_handlers(self, event_handlers):
        """测试取消注册处理器"""
        mock_bus = MagicMock(spec=EventBus)

        event_handlers.register_handlers(mock_bus)
        event_handlers.unregister_handlers(mock_bus)

        # 验证取消了订阅
        assert mock_bus.unsubscribe.call_count == 3

    def test_handler_exception_does_not_propagate(self, event_handlers, mock_db_session):
        """测试处理器异常不会传播"""
        mock_db_session.add.side_effect = Exception("Database error")

        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                "room_id": 101,
                "guest_name": "张三",
                "operator_id": 1
            },
            source="checkout_service"
        )

        # 不应该抛出异常
        event_handlers.handle_guest_checked_out(event)

        # 应该回滚事务
        mock_db_session.rollback.assert_called_once()


class TestEventHandlersIntegration:
    """事件处理器集成测试"""

    def test_checkout_event_creates_task(self, db_session, sample_room, sample_employee):
        """测试退房事件创建清洁任务（集成测试）"""
        from app.services.event_handlers import EventHandlers

        # 保存房间ID（避免会话问题）
        room_id = sample_room.id
        room_number = sample_room.room_number
        employee_id = sample_employee.id

        handlers = EventHandlers(db_session_factory=lambda: db_session)

        event = Event(
            event_type=EventType.GUEST_CHECKED_OUT,
            timestamp=datetime.now(),
            data={
                "stay_record_id": 1,
                "guest_id": 1,
                "guest_name": "张三",
                "room_id": room_id,
                "room_number": room_number,
                "operator_id": employee_id
            },
            source="checkout_service"
        )

        handlers.handle_guest_checked_out(event)

        # 验证任务被创建
        task = db_session.query(Task).filter(Task.room_id == room_id).first()
        assert task is not None
        assert task.task_type == TaskType.CLEANING
        assert task.status == TaskStatus.PENDING

    def test_task_completed_updates_room(self, db_session, sample_room, sample_cleaner):
        """测试任务完成更新房间状态（集成测试）"""
        from app.services.event_handlers import EventHandlers

        # 保存ID（避免会话问题）
        room_id = sample_room.id
        room_number = sample_room.room_number
        cleaner_id = sample_cleaner.id

        # 设置房间为脏房状态
        sample_room.status = RoomStatus.VACANT_DIRTY
        db_session.commit()

        handlers = EventHandlers(db_session_factory=lambda: db_session)

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_id": 1,
                "task_type": "cleaning",
                "room_id": room_id,
                "room_number": room_number,
                "completed_by": cleaner_id
            },
            source="task_service"
        )

        handlers.handle_task_completed(event)

        # 重新查询房间
        room = db_session.query(Room).filter(Room.id == room_id).first()

        # 验证房间状态更新
        assert room.status == RoomStatus.VACANT_CLEAN
