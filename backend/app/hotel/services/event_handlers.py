"""
事件处理器 - 事件驱动架构的核心
订阅领域事件并执行相应的业务逻辑
"""
from datetime import datetime
from typing import Callable, List
import logging

from app.services.event_bus import event_bus, Event
from app.models.events import EventType
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class EventHandlers:
    """
    事件处理器集合

    支持依赖注入以便于测试：
    - db_session_factory: 数据库会话工厂
    - task_service_factory: 任务服务工厂
    - room_service_factory: 房间服务工厂
    """

    def __init__(
        self,
        db_session_factory: Callable = None,
        task_service_factory: Callable = None,
        room_service_factory: Callable = None
    ):
        self._db_session_factory = db_session_factory or SessionLocal
        self._task_service_factory = task_service_factory
        self._room_service_factory = room_service_factory
        self._registered = False

    def _get_db(self):
        """获取数据库会话"""
        return self._db_session_factory()

    def _get_task_service(self, db):
        """获取任务服务"""
        if self._task_service_factory:
            return self._task_service_factory(db)
        from app.hotel.services.task_service import TaskService
        return TaskService(db)

    def _get_room_service(self, db):
        """获取房间服务"""
        if self._room_service_factory:
            return self._room_service_factory(db)
        from app.hotel.services.room_service import RoomService
        return RoomService(db)

    def handle_guest_checked_out(self, event: Event) -> None:
        """
        处理退房事件：自动创建清洁任务

        触发条件：客人退房
        业务逻辑：为退房的房间创建清洁任务
        """
        from app.hotel.models.ontology import Task, TaskType, TaskStatus

        db = self._get_db()
        try:
            data = event.data
            room_id = data.get('room_id')
            guest_name = data.get('guest_name', '')
            operator_id = data.get('operator_id')

            if not room_id:
                logger.warning(f"Invalid checkout event: missing room_id")
                return

            # 创建清洁任务
            cleaning_task = Task(
                room_id=room_id,
                task_type=TaskType.CLEANING,
                status=TaskStatus.PENDING,
                priority=2,  # 退房清洁优先级较高
                notes=f"退房清洁 - 原住客: {guest_name}",
                created_by=operator_id
            )
            db.add(cleaning_task)
            db.commit()

            logger.info(
                f"Auto-created cleaning task {cleaning_task.id} for room {data.get('room_number')}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create cleaning task: {e}", exc_info=True)
        finally:
            db.close()

    def handle_task_completed(self, event: Event) -> None:
        """
        处理任务完成事件：更新房间状态

        触发条件：清洁任务完成
        业务逻辑：将房间状态从脏房变为干净
        """
        from app.hotel.models.ontology import Room, RoomStatus

        db = self._get_db()
        try:
            data = event.data
            task_type = data.get('task_type')
            room_id = data.get('room_id')

            if task_type != 'cleaning':
                return

            if not room_id:
                logger.warning(f"Invalid task completed event: missing room_id")
                return

            room = db.query(Room).filter(Room.id == room_id).first()
            if room and room.status == RoomStatus.VACANT_DIRTY:
                room.status = RoomStatus.VACANT_CLEAN
                db.commit()
                logger.info(
                    f"Room {data.get('room_number')} status updated to vacant_clean"
                )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update room status: {e}", exc_info=True)
        finally:
            db.close()

    def handle_room_changed(self, event: Event) -> None:
        """
        处理换房事件：为原房间创建清洁任务

        触发条件：客人换房
        业务逻辑：为原房间创建清洁任务
        """
        from app.hotel.models.ontology import Task, TaskType, TaskStatus

        db = self._get_db()
        try:
            data = event.data
            old_room_id = data.get('old_room_id')
            guest_name = data.get('guest_name', '')
            operator_id = data.get('operator_id')

            if not old_room_id:
                return

            # 创建清洁任务
            cleaning_task = Task(
                room_id=old_room_id,
                task_type=TaskType.CLEANING,
                status=TaskStatus.PENDING,
                priority=1,  # 换房清洁优先级一般
                notes=f"换房清洁 - 原住客: {guest_name}",
                created_by=operator_id
            )
            db.add(cleaning_task)
            db.commit()

            logger.info(
                f"Auto-created cleaning task for room change, old room: {data.get('old_room_number')}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create cleaning task for room change: {e}", exc_info=True)
        finally:
            db.close()

    def register_handlers(self, event_bus_instance=None) -> None:
        """注册所有事件处理器"""
        if self._registered:
            return

        bus = event_bus_instance or event_bus

        bus.subscribe(EventType.GUEST_CHECKED_OUT, self.handle_guest_checked_out)
        bus.subscribe(EventType.TASK_COMPLETED, self.handle_task_completed)
        bus.subscribe(EventType.ROOM_CHANGED, self.handle_room_changed)

        self._registered = True
        logger.info("Event handlers registered successfully")

    def unregister_handlers(self, event_bus_instance=None) -> None:
        """取消注册所有事件处理器（用于测试）"""
        bus = event_bus_instance or event_bus

        bus.unsubscribe(EventType.GUEST_CHECKED_OUT, self.handle_guest_checked_out)
        bus.unsubscribe(EventType.TASK_COMPLETED, self.handle_task_completed)
        bus.unsubscribe(EventType.ROOM_CHANGED, self.handle_room_changed)

        self._registered = False
        logger.info("Event handlers unregistered")


# 全局事件处理器实例
event_handlers = EventHandlers()


def register_event_handlers():
    """注册所有事件处理器（应用启动时调用）"""
    event_handlers.register_handlers()
