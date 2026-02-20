"""
任务服务 - 本体操作层
支持事件驱动：任务完成发布事件，由事件处理器更新房间状态
支持操作撤销：关键操作创建快照
SPEC-R13: State machine validation before status changes
"""
from typing import List, Optional, Callable
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from app.models.ontology import Task, TaskType, TaskStatus, Room, RoomStatus, Employee, EmployeeRole
from app.models.schemas import TaskCreate, TaskAssign, TaskUpdate
from app.services.event_bus import event_bus, Event
from app.models.events import (
    EventType, TaskCreatedData, TaskAssignedData,
    TaskStartedData, TaskCompletedData
)
from app.models.snapshots import OperationType

logger = logging.getLogger(__name__)


def _validate_state_transition(entity_type: str, current_state: str, target_state: str) -> None:
    """SPEC-R13: Validate state transition against registry state machine."""
    try:
        from core.ontology.state_machine_executor import StateMachineExecutor
        executor = StateMachineExecutor()
        result = executor.validate_transition(entity_type, current_state, target_state)
        if not result.allowed:
            logger.warning(
                f"State transition validation: {entity_type} "
                f"'{current_state}' → '{target_state}': {result.reason}"
            )
    except Exception as e:
        logger.debug(f"State machine validation skipped: {e}")


class TaskService:
    """任务服务"""

    def __init__(self, db: Session, event_publisher: Callable[[Event], None] = None):
        self.db = db
        # 支持依赖注入事件发布器，便于测试
        self._publish_event = event_publisher or event_bus.publish

    def get_tasks(self, task_type: Optional[TaskType] = None,
                  status: Optional[TaskStatus] = None,
                  assignee_id: Optional[int] = None,
                  room_id: Optional[int] = None) -> List[Task]:
        """获取任务列表"""
        query = self.db.query(Task)

        if task_type:
            query = query.filter(Task.task_type == task_type)
        if status:
            query = query.filter(Task.status == status)
        if assignee_id:
            query = query.filter(Task.assignee_id == assignee_id)
        if room_id:
            query = query.filter(Task.room_id == room_id)

        return query.order_by(Task.priority.desc(), Task.created_at.desc()).all()

    def get_task(self, task_id: int) -> Optional[Task]:
        """获取单个任务"""
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_my_tasks(self, employee_id: int) -> List[Task]:
        """获取我的任务（清洁员视图）"""
        return self.db.query(Task).filter(
            Task.assignee_id == employee_id,
            Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
        ).order_by(Task.priority.desc(), Task.created_at).all()

    def get_pending_tasks(self) -> List[Task]:
        """获取待分配任务"""
        return self.db.query(Task).filter(
            Task.status == TaskStatus.PENDING
        ).order_by(Task.priority.desc(), Task.created_at).all()

    def create_task(self, data: TaskCreate, created_by: int) -> Task:
        """创建任务"""
        room = self.db.query(Room).filter(Room.id == data.room_id).first()
        if not room:
            raise ValueError("房间不存在")

        # 验证负责人
        if data.assignee_id:
            assignee = self.db.query(Employee).filter(
                Employee.id == data.assignee_id,
                Employee.role == EmployeeRole.CLEANER,
                Employee.is_active == True
            ).first()
            if not assignee:
                raise ValueError("指定的清洁员不存在或已停用")
            status = TaskStatus.ASSIGNED
        else:
            status = TaskStatus.PENDING

        task = Task(
            room_id=data.room_id,
            task_type=data.task_type,
            status=status,
            assignee_id=data.assignee_id,
            priority=data.priority,
            notes=data.notes,
            created_by=created_by
        )
        from app.services.branch_utils import inject_branch_id
        inject_branch_id(task)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # 发布任务创建事件
        self._publish_event(Event(
            event_type=EventType.TASK_CREATED,
            timestamp=datetime.now(),
            data=TaskCreatedData(
                task_id=task.id,
                task_type=task.task_type.value,
                room_id=task.room_id,
                room_number=room.room_number,
                priority=task.priority,
                notes=task.notes or "",
                created_by=created_by,
                trigger="manual"
            ).to_dict(),
            source="task_service"
        ))

        return task

    def assign_task(self, task_id: int, data: TaskAssign, assigned_by: int = None) -> Task:
        """分配任务"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        if task.status not in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
            raise ValueError(f"状态为 {task.status.value} 的任务无法分配")

        # 验证负责人
        assignee = self.db.query(Employee).filter(
            Employee.id == data.assignee_id,
            Employee.role == EmployeeRole.CLEANER,
            Employee.is_active == True
        ).first()
        if not assignee:
            raise ValueError("指定的清洁员不存在或已停用")

        task.assignee_id = data.assignee_id
        _validate_state_transition("Task", task.status.value, TaskStatus.ASSIGNED.value)
        task.status = TaskStatus.ASSIGNED

        self.db.commit()
        self.db.refresh(task)

        # 发布任务分配事件
        self._publish_event(Event(
            event_type=EventType.TASK_ASSIGNED,
            timestamp=datetime.now(),
            data=TaskAssignedData(
                task_id=task.id,
                task_type=task.task_type.value,
                room_id=task.room_id,
                room_number=task.room.room_number,
                assignee_id=assignee.id,
                assignee_name=assignee.name,
                assigned_by=assigned_by or 0
            ).to_dict(),
            source="task_service"
        ))

        return task

    def start_task(self, task_id: int, employee_id: int) -> Task:
        """开始任务"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        if task.assignee_id != employee_id:
            raise ValueError("只能开始分配给自己的任务")

        if task.status != TaskStatus.ASSIGNED:
            raise ValueError(f"状态为 {task.status.value} 的任务无法开始")

        _validate_state_transition("Task", task.status.value, TaskStatus.IN_PROGRESS.value)
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        self.db.commit()
        self.db.refresh(task)

        # 发布任务开始事件
        self._publish_event(Event(
            event_type=EventType.TASK_STARTED,
            timestamp=datetime.now(),
            data=TaskStartedData(
                task_id=task.id,
                task_type=task.task_type.value,
                room_id=task.room_id,
                room_number=task.room.room_number,
                started_by=employee_id,
                started_by_name=task.assignee.name if task.assignee else ""
            ).to_dict(),
            source="task_service"
        ))

        return task

    def complete_task(self, task_id: int, employee_id: int, notes: Optional[str] = None) -> Task:
        """
        完成任务
        业务联动：清洁任务完成后，房间状态自动变为空闲
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        if task.assignee_id != employee_id:
            raise ValueError("只能完成分配给自己的任务")

        if task.status not in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
            raise ValueError(f"状态为 {task.status.value} 的任务无法完成")

        # 保存快照所需的旧状态
        old_status = task.status.value
        room = task.room
        old_room_status = room.status.value if room else None

        _validate_state_transition("Task", task.status.value, TaskStatus.COMPLETED.value)
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        if notes:
            task.notes = (task.notes or '') + f'\n完成备注: {notes}'

        # 保存信息用于事件
        room_id = task.room_id
        room_number = task.room.room_number
        task_type = task.task_type.value
        assignee_name = task.assignee.name if task.assignee else ""

        # 创建操作快照（用于撤销）- 仅清洁任务
        if task.task_type == TaskType.CLEANING:
            from app.services.undo_service import UndoService
            undo_service = UndoService(self.db)
            undo_service.create_snapshot(
                operation_type=OperationType.COMPLETE_TASK,
                entity_type="task",
                entity_id=task.id,
                before_state={
                    "task": {
                        "id": task.id,
                        "status": old_status
                    },
                    "room": {
                        "id": room_id,
                        "room_number": room_number,
                        "status": old_room_status
                    } if room else None
                },
                after_state={
                    "task_status": TaskStatus.COMPLETED.value,
                    "room_status": RoomStatus.VACANT_CLEAN.value
                },
                operator_id=employee_id
            )

        self.db.commit()
        self.db.refresh(task)

        # 发布任务完成事件（事件处理器会更新房间状态）
        self._publish_event(Event(
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(),
            data=TaskCompletedData(
                task_id=task.id,
                task_type=task_type,
                room_id=room_id,
                room_number=room_number,
                completed_by=employee_id,
                completed_by_name=assignee_name,
                completion_time=task.completed_at
            ).to_dict(),
            source="task_service"
        ))

        return task

    def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        """更新任务（管理员操作）"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(task, key, value)

        self.db.commit()
        self.db.refresh(task)
        return task

    def get_cleaners(self) -> List[Employee]:
        """获取所有清洁员"""
        return self.db.query(Employee).filter(
            Employee.role == EmployeeRole.CLEANER,
            Employee.is_active == True
        ).all()

    def get_task_detail(self, task_id: int) -> dict:
        """获取任务详情"""
        task = self.get_task(task_id)
        if not task:
            return None

        return {
            'id': task.id,
            'room_id': task.room_id,
            'room_number': task.room.room_number,
            'task_type': task.task_type,
            'status': task.status,
            'assignee_id': task.assignee_id,
            'assignee_name': task.assignee.name if task.assignee else None,
            'priority': task.priority,
            'notes': task.notes,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'branch_name': task.branch.name if getattr(task, 'branch', None) else None
        }

    def delete_task(self, task_id: int) -> Task:
        """删除单个任务（仅允许删除 pending/assigned 状态）"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")

        if task.status not in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
            raise ValueError(f"状态为 {task.status.value} 的任务无法删除，仅可删除待分配或已分配的任务")

        self.db.delete(task)
        self.db.commit()
        return task

    def batch_delete_tasks(self, status: Optional[TaskStatus] = None,
                           task_type: Optional[TaskType] = None,
                           room_id: Optional[int] = None) -> int:
        """按条件批量删除任务，返回删除数量。仅删除 pending/assigned 状态的任务。"""
        query = self.db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.ASSIGNED])
        )

        if status:
            query = query.filter(Task.status == status)
        if task_type:
            query = query.filter(Task.task_type == task_type)
        if room_id:
            query = query.filter(Task.room_id == room_id)

        tasks = query.all()
        count = len(tasks)
        for task in tasks:
            self.db.delete(task)
        self.db.commit()
        return count

    def get_task_summary(self) -> dict:
        """获取任务统计"""
        tasks = self.db.query(Task).filter(
            Task.status != TaskStatus.COMPLETED
        ).all()

        return {
            'pending': len([t for t in tasks if t.status == TaskStatus.PENDING]),
            'assigned': len([t for t in tasks if t.status == TaskStatus.ASSIGNED]),
            'in_progress': len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
        }
