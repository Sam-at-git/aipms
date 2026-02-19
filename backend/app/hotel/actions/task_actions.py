"""
app/services/actions/task_actions.py

Task-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.hotel.models.ontology import Employee, TaskType
from app.hotel.services.param_parser_service import ParamParserService
from app.hotel.actions.base import (
    CreateTaskParams, DeleteTaskParams, BatchDeleteTasksParams,
    AssignTaskParams, StartTaskParams, CompleteTaskParams,
)
from app.hotel.services.task_service import TaskService

import logging

logger = logging.getLogger(__name__)


def register_task_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all task-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="create_task",
        entity="Task",
        description="创建清洁或维修任务。支持为指定房间创建任务，任务将进入待分配状态。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager", "cleaner"},
        undoable=True,
        side_effects=["creates_task"],
        search_keywords=["创建任务", "清洁任务", "维修任务", "打扫", "create task"],
        ui_required_fields=["room_number", "task_type"],
    )
    def handle_create_task(
        params: CreateTaskParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService
    ) -> Dict[str, Any]:
        """
        Execute task creation.

        This handler:
        1. Parses the room parameter (accepts both ID and room number)
        2. Validates the task type
        3. Creates the task in PENDING status

        Args:
            params: Validated create task parameters
            db: Database session
            user: Current user (employee)
            param_parser: Parameter parser service for room resolution

        Returns:
            Result dict with success status and message
        """
        from app.hotel.models.schemas import TaskCreate

        # Parse room (support room number string)
        room_result = param_parser.parse_room(params.room_id)

        if room_result.confidence < 0.7:
            # Low confidence - return candidates for user selection
            return {
                "success": False,
                "requires_confirmation": True,
                "action": "select_room",
                "message": f'请确认房间："{room_result.raw_input}"',
                "candidates": room_result.candidates or [],
                "raw_input": room_result.raw_input
            }

        room_id = int(room_result.value)

        # Normalize task type to enum
        task_type = params.task_type
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                # Default to cleaning if invalid
                task_type = TaskType.CLEANING

        # Build service request
        request = TaskCreate(
            room_id=room_id,
            task_type=task_type
        )

        # Execute task creation
        try:
            service = TaskService(db)
            task = service.create_task(request, user.id)

            task_type_name = "清洁" if task_type == TaskType.CLEANING else "维修"

            return {
                "success": True,
                "message": f"{task_type_name}任务已创建，任务ID：{task.id}",
                "task_id": task.id,
                "room_id": task.room_id,
                "task_type": task.task_type.value,
                "status": task.status.value
            }
        except ValidationError as e:
            logger.error(f"Validation error in create_task: {e}")
            return {
                "success": False,
                "message": f"参数验证失败: {str(e)}",
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in create_task: {e}")
            return {
                "success": False,
                "message": f"创建任务失败: {str(e)}",
                "error": "execution_error"
            }


    @registry.register(
        name="delete_task",
        entity="Task",
        description="删除单个任务。仅可删除待分配(pending)或已分配(assigned)状态的任务。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["deletes_task"],
        search_keywords=["删除任务", "移除任务", "取消任务", "delete task", "remove task"]
    )
    def handle_delete_task(
        params: DeleteTaskParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """删除单个任务"""

        try:
            service = TaskService(db)
            task = service.delete_task(params.task_id)
            return {
                "success": True,
                "message": f"任务 {params.task_id} 已删除",
                "task_id": params.task_id
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in delete_task: {e}")
            return {
                "success": False,
                "message": f"删除任务失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="batch_delete_tasks",
        entity="Task",
        description="按条件批量删除任务。可按状态(pending/assigned)、类型(cleaning/maintenance)、房间过滤。仅删除未开始的任务。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"manager"},
        undoable=False,
        side_effects=["deletes_tasks"],
        search_keywords=["批量删除", "删除所有任务", "清除任务", "删除待分配任务",
                         "delete all tasks", "batch delete", "清理任务"]
    )
    def handle_batch_delete_tasks(
        params: BatchDeleteTasksParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService = None,
        **context
    ) -> Dict[str, Any]:
        """批量删除任务"""
        from app.hotel.models.ontology import TaskStatus, TaskType

        try:
            # Parse status filter
            status_filter = None
            if params.status:
                status_filter = TaskStatus(params.status)

            # Parse task_type filter
            type_filter = None
            if params.task_type:
                type_filter = TaskType(params.task_type)

            # Parse room_id filter
            room_id = None
            if params.room_id is not None and param_parser:
                room_result = param_parser.parse_room(params.room_id)
                if room_result.confidence >= 0.7:
                    room_id = int(room_result.value)
            elif params.room_id is not None:
                room_id = int(params.room_id)

            service = TaskService(db)
            count = service.batch_delete_tasks(
                status=status_filter,
                task_type=type_filter,
                room_id=room_id
            )

            # Build description of filters applied
            filter_desc = []
            if status_filter:
                filter_desc.append(f"状态={status_filter.value}")
            if type_filter:
                filter_desc.append(f"类型={type_filter.value}")
            if room_id:
                filter_desc.append(f"房间ID={room_id}")
            filter_text = "（" + "，".join(filter_desc) + "）" if filter_desc else ""

            return {
                "success": True,
                "message": f"已批量删除 {count} 条任务{filter_text}",
                "deleted_count": count
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in batch_delete_tasks: {e}")
            return {
                "success": False,
                "message": f"批量删除任务失败: {str(e)}",
                "error": "execution_error"
            }


    @registry.register(
        name="assign_task",
        entity="Task",
        description="分配任务给清洁员。支持通过清洁员ID或姓名指定。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"receptionist", "manager"},
        undoable=False,
        side_effects=["assigns_task"],
        search_keywords=["分配任务", "指派任务", "assign task"]
    )
    def handle_assign_task(
        params: AssignTaskParams,
        db: Session,
        user: Employee,
        param_parser: ParamParserService = None,
        **context
    ) -> Dict[str, Any]:
        """分配任务给清洁员"""
        from app.hotel.models.schemas import TaskAssign

        try:
            # Resolve assignee: by ID or by name
            assignee_id = params.assignee_id
            if not assignee_id and params.assignee_name:
                assignee = db.query(Employee).filter(
                    Employee.name.like(f"%{params.assignee_name}%"),
                    Employee.is_active == True
                ).first()
                if not assignee:
                    return {
                        "success": False,
                        "message": f"未找到名为「{params.assignee_name}」的员工",
                        "error": "not_found"
                    }
                assignee_id = assignee.id

            if not assignee_id:
                return {
                    "success": False,
                    "message": "请提供清洁员ID或姓名",
                    "error": "missing_assignee"
                }

            assign_data = TaskAssign(assignee_id=assignee_id)
            service = TaskService(db)
            task = service.assign_task(params.task_id, assign_data, assigned_by=user.id)

            return {
                "success": True,
                "message": f"任务 {task.id} 已分配给 {task.assignee.name}",
                "task_id": task.id,
                "assignee_id": task.assignee_id,
                "assignee_name": task.assignee.name,
                "status": task.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in assign_task: {e}")
            return {
                "success": False,
                "message": f"分配任务失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="start_task",
        entity="Task",
        description="开始执行任务。仅任务的负责人可以开始。",
        category="mutation",
        requires_confirmation=False,
        allowed_roles={"cleaner", "manager"},
        undoable=False,
        side_effects=["starts_task"],
        search_keywords=["开始任务", "执行任务", "start task"]
    )
    def handle_start_task(
        params: StartTaskParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """开始执行任务"""

        try:
            service = TaskService(db)
            task = service.start_task(params.task_id, user.id)

            return {
                "success": True,
                "message": f"任务 {task.id} 已开始执行",
                "task_id": task.id,
                "status": task.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in start_task: {e}")
            return {
                "success": False,
                "message": f"开始任务失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="complete_task",
        entity="Task",
        description="完成任务。清洁任务完成后房间自动变为空闲。仅任务负责人可完成。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"cleaner", "manager"},
        undoable=True,
        side_effects=["completes_task", "may_update_room_status"],
        search_keywords=["完成任务", "任务完成", "complete task"]
    )
    def handle_complete_task(
        params: CompleteTaskParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """完成任务"""

        try:
            service = TaskService(db)
            task = service.complete_task(params.task_id, user.id, notes=params.notes)

            return {
                "success": True,
                "message": f"任务 {task.id} 已完成",
                "task_id": task.id,
                "room_number": task.room.room_number,
                "status": task.status.value
            }
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "error": "business_error"
            }
        except Exception as e:
            logger.error(f"Error in complete_task: {e}")
            return {
                "success": False,
                "message": f"完成任务失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_task_actions"]
