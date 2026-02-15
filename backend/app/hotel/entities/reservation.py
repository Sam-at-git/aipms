"""Reservation entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    StateMachine, StateTransition, EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import Reservation

    metadata = EntityMetadata(
        name="Reservation",
        description="预订信息 - 预订阶段的聚合根。管理从创建到入住或取消的完整预订生命周期，包括渠道来源、押金、特殊要求等。",
        table_name="reservations", category="transactional",
        lifecycle_states=["CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED", "NO_SHOW"],
        extensions={
            "business_purpose": "预订管理与渠道分销",
            "key_attributes": ["reservation_no", "guest_id", "check_in_date", "check_out_date", "status"],
            "invariants": ["禁止重复预订同一房间同一时段", "入住日期必须是未来日期"],
        },
    )

    state_machine = StateMachine(
        entity="Reservation",
        name="reservation_lifecycle",
        description="预订生命周期",
        states=["confirmed", "checked_in", "completed", "cancelled", "no_show"],
        initial_state="confirmed",
        final_states={"completed", "cancelled", "no_show"},
        transitions=[
            StateTransition(from_state="confirmed", to_state="checked_in", trigger="checkin"),
            StateTransition(from_state="checked_in", to_state="completed", trigger="checkout"),
            StateTransition(from_state="confirmed", to_state="cancelled", trigger="cancel"),
            StateTransition(from_state="confirmed", to_state="no_show", trigger="no_show"),
        ]
    )

    constraints = [
        ConstraintMetadata(
            id="checkout_date_must_be_after_checkin",
            name="退房日期必须晚于入住日期",
            description="预订时退房日期必须晚于入住日期",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Reservation", action="create_reservation",
            condition_text="check_out_date > check_in_date",
            error_message="退房日期不能早于或等于入住日期",
            suggestion_message="请选择正确的入住和退房日期"
        ),
        ConstraintMetadata(
            id="no_double_booking_same_room",
            name="禁止重复预订同一房间",
            description="同一房间在同一时间段内不能被多次预订",
            constraint_type=ConstraintType.CARDINALITY,
            severity=ConstraintSeverity.ERROR,
            entity="Reservation", action="create_reservation",
            condition_text="no overlapping reservations for same room and date range",
            error_message="该房间在指定日期已有预订",
            suggestion_message="请选择其他房间或日期"
        ),
        ConstraintMetadata(
            id="checkin_requires_future_date",
            name="入住日期必须是未来",
            description="创建预订时入住日期不能是过去的日期",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Reservation", action="create_reservation",
            condition_text="check_in_date >= today",
            error_message="入住日期不能是过去的日期",
            suggestion_message="请选择今天或之后的日期"
        ),
        ConstraintMetadata(
            id="no_show_auto_cancel_after_24h",
            name="未到店24小时自动取消",
            description="客人未在预订入住日期后24小时内到达，预订自动标记为No Show",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.WARNING,
            entity="Reservation", action="",
            condition_text="now() - check_in_date > 24 hours AND status == 'CONFIRMED'",
            error_message="客人超时未到店",
            suggestion_message="系统将自动标记为 No Show"
        ),
        ConstraintMetadata(
            id="deposit_required_for_confirmed",
            name="确认预订需要押金",
            description="预订确认时需收取押金",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.WARNING,
            entity="Reservation", action="create_reservation",
            condition_text="prepaid_amount > 0 for confirmed reservations",
            error_message="建议收取押金以确保预订",
            suggestion_message="建议收取首晚房费作为押金"
        ),
    ]

    events = [
        EventMetadata(
            name="RESERVATION_CREATED",
            description="创建新预订",
            entity="Reservation",
            triggered_by=["create_reservation"],
            payload_fields=["reservation_id", "guest_id", "room_type_id"],
        ),
        EventMetadata(
            name="RESERVATION_CANCELLED",
            description="取消预订",
            entity="Reservation",
            triggered_by=["cancel_reservation"],
            payload_fields=["reservation_id", "reason"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=Reservation,
        state_machine=state_machine,
        constraints=constraints,
        events=events,
    )
