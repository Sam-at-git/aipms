"""Room entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    StateMachine, StateTransition, EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import Room

    metadata = EntityMetadata(
        name="Room",
        description="酒店房间 - 物理空间单位，数字孪生的核心实体。房间号格式: 楼层+序号 (如 201, 202)。每个房间有固定的房型，决定基础价格和最大入住人数。",
        table_name="rooms", category="master_data", is_aggregate_root=False,
        lifecycle_states=["VACANT_CLEAN", "VACANT_DIRTY", "OCCUPIED", "OUT_OF_ORDER"],
        implements=["BookableResource", "Maintainable"],
        extensions={
            "business_purpose": "可销售的核心库存单元",
            "key_attributes": ["room_number", "status", "room_type_id"],
            "typical_lifecycle": "vacant_clean → occupied → vacant_dirty → vacant_clean",
            "invariants": ["房间状态必须符合状态机约束", "入住中房间不能被重复预订", "维修中房间不能办理入住"],
        },
    )

    state_machine = StateMachine(
        entity="Room",
        name="room_lifecycle",
        description="房间生命周期",
        states=["vacant_clean", "vacant_dirty", "occupied", "out_of_order"],
        initial_state="vacant_clean",
        final_states=set(),
        transitions=[
            StateTransition(from_state="vacant_clean", to_state="occupied", trigger="checkin"),
            StateTransition(from_state="occupied", to_state="vacant_dirty", trigger="checkout"),
            StateTransition(from_state="vacant_dirty", to_state="vacant_clean", trigger="clean"),
            StateTransition(from_state="vacant_clean", to_state="out_of_order", trigger="maintenance"),
            StateTransition(from_state="vacant_dirty", to_state="out_of_order", trigger="maintenance"),
            StateTransition(from_state="out_of_order", to_state="vacant_dirty", trigger="complete_maintenance"),
        ]
    )

    constraints = [
        ConstraintMetadata(
            id="room_must_be_vacant_for_checkin",
            name="入住时房间必须空闲",
            description="只有 VACANT_CLEAN 状态的房间才能办理入住",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room", action="checkin",
            condition_text="room.status == 'VACANT_CLEAN'",
            condition_code="state.status == 'VACANT_CLEAN'",
            error_message="房间状态不是空闲可住，无法入住",
            suggestion_message="请选择状态为 VACANT_CLEAN 的房间"
        ),
        ConstraintMetadata(
            id="room_type_exists_before_room_creation",
            name="房型必须存在",
            description="创建房间时关联的房型必须已存在",
            constraint_type=ConstraintType.REFERENCE,
            severity=ConstraintSeverity.ERROR,
            entity="Room", action="create_room",
            condition_text="room_type_id exists in RoomType",
            error_message="指定的房型不存在",
            suggestion_message="请先创建房型或选择已有房型"
        ),
        ConstraintMetadata(
            id="maintenance_requires_no_active_stay",
            name="维修要求无在住客人",
            description="标记房间为维修状态时，房间内不能有在住客人",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room", action="maintenance",
            condition_text="room.status != 'OCCUPIED'",
            condition_code="state.status != 'OCCUPIED'",
            error_message="房间有在住客人，无法标记为维修",
            suggestion_message="请先办理客人退房或换房"
        ),
    ]

    events = [
        EventMetadata(
            name="ROOM_STATUS_CHANGED",
            description="房间状态发生变化",
            entity="Room",
            triggered_by=["check_in", "check_out", "mark_clean", "mark_dirty"],
            payload_fields=["room_id", "old_status", "new_status"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=Room,
        state_machine=state_machine,
        constraints=constraints,
        events=events,
    )
