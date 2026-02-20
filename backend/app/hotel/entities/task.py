"""Task entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    StateMachine, StateTransition, EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import Task

    metadata = EntityMetadata(
        name="Task",
        description="任务 - 清洁和维修任务管理。支持任务创建、分配、执行、完成的完整工作流。退房自动创建清洁任务，任务完成自动更新房间状态。",
        table_name="tasks", category="transactional",
        lifecycle_states=["PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
        data_scope_type="scoped", scope_column="branch_id",
        extensions={
            "business_purpose": "运营任务管理与工作流",
            "key_attributes": ["room_id", "task_type", "assignee_id", "status"],
            "invariants": ["退房自动创建清洁任务", "任务完成更新房间状态"],
        },
    )

    state_machine = StateMachine(
        entity="Task",
        name="task_lifecycle",
        description="任务生命周期",
        states=["pending", "assigned", "in_progress", "completed", "cancelled"],
        initial_state="pending",
        final_states={"completed", "cancelled"},
        transitions=[
            StateTransition(from_state="pending", to_state="assigned", trigger="assign"),
            StateTransition(from_state="pending", to_state="in_progress", trigger="start"),
            StateTransition(from_state="pending", to_state="cancelled", trigger="cancel"),
            StateTransition(from_state="assigned", to_state="in_progress", trigger="start"),
            StateTransition(from_state="assigned", to_state="completed", trigger="complete"),
            StateTransition(from_state="assigned", to_state="cancelled", trigger="cancel"),
            StateTransition(from_state="in_progress", to_state="completed", trigger="complete"),
            StateTransition(from_state="in_progress", to_state="cancelled", trigger="cancel"),
        ]
    )

    constraints = [
        ConstraintMetadata(
            id="cleaning_task_created_on_checkout",
            name="退房自动创建清洁任务",
            description="客人退房后系统自动为该房间创建清洁任务",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.INFO,
            entity="Task", action="checkout",
            condition_text="auto create cleaning task on checkout",
            error_message="",
            suggestion_message="退房后系统会自动创建清洁任务"
        ),
        ConstraintMetadata(
            id="task_auto_assign_by_role",
            name="任务按角色自动分配",
            description="清洁任务自动分配给清洁工角色的空闲员工",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.INFO,
            entity="Task", action="create_task",
            condition_text="auto assign to available cleaner",
            error_message="",
            suggestion_message="系统可自动分配任务给空闲清洁工"
        ),
        ConstraintMetadata(
            id="task_completion_updates_room_status",
            name="任务完成更新房间状态",
            description="清洁任务完成后自动将房间状态更新为 VACANT_CLEAN",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.INFO,
            entity="Task", action="complete_task",
            condition_text="on task complete: room.status = 'VACANT_CLEAN'",
            error_message="",
            suggestion_message="任务完成后房间状态会自动更新"
        ),
    ]

    events = [
        EventMetadata(
            name="TASK_CREATED",
            description="创建新任务",
            entity="Task",
            triggered_by=["create_task"],
            payload_fields=["task_id", "room_id", "task_type"],
        ),
        EventMetadata(
            name="TASK_COMPLETED",
            description="任务完成",
            entity="Task",
            triggered_by=["complete_task"],
            payload_fields=["task_id", "assignee_id"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=Task,
        state_machine=state_machine,
        constraints=constraints,
        events=events,
    )
