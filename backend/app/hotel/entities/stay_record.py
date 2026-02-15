"""StayRecord entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    StateMachine, StateTransition, EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import StayRecord

    metadata = EntityMetadata(
        name="StayRecord",
        description="住宿记录 - 住宿期间的聚合根，代表一次完整的入住经历。关联客人、房间、账单，是营收管理的核心数据。",
        table_name="stay_records", category="transactional", is_aggregate_root=True,
        lifecycle_states=["ACTIVE", "CHECKED_OUT"],
        extensions={
            "business_purpose": "住宿过程管理与营收追踪",
            "key_attributes": ["guest_id", "room_id", "check_in_time", "expected_check_out", "status"],
            "invariants": ["最短入住1小时", "延住需要房间可用"],
        },
    )

    state_machine = StateMachine(
        entity="StayRecord",
        name="stay_lifecycle",
        description="住宿记录生命周期",
        states=["active", "checked_out"],
        initial_state="active",
        final_states={"checked_out"},
        transitions=[
            StateTransition(from_state="active", to_state="checked_out", trigger="checkout"),
        ]
    )

    constraints = [
        ConstraintMetadata(
            id="bill_must_be_settled_for_checkout",
            name="退房前必须结清账单",
            description="客人退房时账单必须已结清",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="StayRecord", action="checkout",
            condition_text="stay.bill.outstanding_amount <= 0",
            condition_code="state.outstanding_amount <= 0",
            error_message="账单未结清，无法退房",
            suggestion_message="请先收取未结清金额"
        ),
        ConstraintMetadata(
            id="stay_duration_minimum_1_hour",
            name="最短入住1小时",
            description="住宿时长不得少于1小时",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="StayRecord", action="checkout",
            condition_text="check_out_time - check_in_time >= 1 hour",
            error_message="入住时间不足1小时，请稍后再办理退房",
            suggestion_message="如需取消入住，请使用取消功能"
        ),
        ConstraintMetadata(
            id="extension_requires_availability",
            name="延住需要房间可用",
            description="延长住宿时需确认延住期间房间无其他预订",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="StayRecord", action="extend_stay",
            condition_text="no reservations for room during extended period",
            error_message="延住日期内该房间已有其他预订",
            suggestion_message="请选择其他日期或考虑换房"
        ),
        ConstraintMetadata(
            id="change_room_requires_vacant_target",
            name="换房目标必须空闲",
            description="换房时目标房间必须处于空闲可住状态",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="StayRecord", action="change_room",
            condition_text="target_room.status == 'VACANT_CLEAN'",
            condition_code="state.target_room_status == 'VACANT_CLEAN'",
            error_message="目标房间不可用，无法换房",
            suggestion_message="请选择状态为空闲已清洁的房间"
        ),
    ]

    events = [
        EventMetadata(
            name="STAY_EXTENDED",
            description="延长住宿",
            entity="StayRecord",
            triggered_by=["extend_stay"],
            payload_fields=["stay_record_id", "new_checkout_date"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=StayRecord,
        state_machine=state_machine,
        constraints=constraints,
        events=events,
    )
