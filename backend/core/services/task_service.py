"""
core/services/task_service.py

任务服务适配器 - 桥接 core/services/ 与 app/services/
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

try:
    from app.services.task_service import TaskService as AppTaskService
    APP_TASK_SERVICE_AVAILABLE = True
except ImportError:
    APP_TASK_SERVICE_AVAILABLE = False


class TaskServiceV2:
    """任务服务 V2 - 服务适配器"""

    def __init__(self, db: Session):
        self.db = db
        if APP_TASK_SERVICE_AVAILABLE:
            self._app_service = AppTaskService(db)
        else:
            self._app_service = None

    def get_tasks(self, room_id=None, task_type=None, status=None, assigned_to=None):
        if self._app_service:
            return self._app_service.get_tasks(
                room_id, task_type, status, assigned_to
            )
        return []

    def get_task(self, task_id):
        if self._app_service:
            return self._app_service.get_task(task_id)
        return None

    def get_pending_tasks(self):
        if self._app_service:
            return self._app_service.get_pending_tasks()
        return []

    def create_task(self, room_id, task_type, priority="normal", notes="", due_date=None):
        if self._app_service:
            return self._app_service.create_task(
                room_id, task_type, priority, notes, due_date
            )
        raise NotImplementedError()

    def assign_task(self, task_id, assignee_id):
        if self._app_service:
            return self._app_service.assign_task(task_id, assignee_id)
        raise NotImplementedError()

    def start_task(self, task_id):
        if self._app_service:
            return self._app_service.start_task(task_id)
        raise NotImplementedError()

    def complete_task(self, task_id, notes="", completed_at=None):
        if self._app_service:
            return self._app_service.complete_task(task_id, notes, completed_at)
        raise NotImplementedError()

    def get_task_statistics(self):
        if self._app_service:
            return self._app_service.get_task_statistics()
        return {"pending": 0, "in_progress": 0, "completed": 0}


def get_task_service_v2(db: Session):
    return TaskServiceV2(db)


__all__ = ["TaskServiceV2", "get_task_service_v2"]
