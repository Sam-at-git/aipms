"""
app/services/actions/task_actions.py

Task-related action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, TaskType
from app.services.param_parser_service import ParamParserService
from app.services.actions.base import CreateTaskParams

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
        search_keywords=["创建任务", "清洁任务", "维修任务", "打扫", "create task"]
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
        from app.models.schemas import TaskCreate
        from app.services.task_service import TaskService

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


__all__ = ["register_task_actions"]
