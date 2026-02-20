"""Bill entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import Bill

    metadata = EntityMetadata(
        name="Bill",
        description="账单 - 与住宿记录关联的财务记录。包含总金额、已付金额、调整金额，支持多种支付方式。",
        table_name="bills", category="transactional",
        data_scope_type="scoped", scope_column="branch_id",
        extensions={
            "business_purpose": "财务管理与结算",
            "key_attributes": ["stay_record_id", "total_amount", "paid_amount", "is_settled"],
            "invariants": ["支付不超过余额", "调整需要经理审批"],
        },
    )

    constraints = [
        ConstraintMetadata(
            id="payment_not_exceed_balance",
            name="支付不超过余额",
            description="单次支付金额不能超过账单未付余额",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Bill", action="add_payment",
            condition_text="payment.amount <= bill.outstanding_amount",
            condition_code="param.amount <= state.outstanding_amount",
            error_message="支付金额超过未付余额",
            suggestion_message="请确认支付金额"
        ),
        ConstraintMetadata(
            id="adjustment_requires_manager_approval",
            name="账单调整需要经理审批",
            description="账单调整（减免、折扣等）需要经理角色审批",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Bill", action="adjust_bill",
            condition_text="user.role in ('manager', 'sysadmin')",
            condition_code="user.role in ('manager', 'sysadmin')",
            error_message="账单调整需要经理或以上权限",
            suggestion_message="请联系经理进行账单调整"
        ),
        ConstraintMetadata(
            id="daily_charges_auto_post",
            name="每日自动计费",
            description="在住客人每日自动产生房费，计入账单",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.INFO,
            entity="Bill", action="",
            condition_text="daily charge posted for active stays",
            error_message="",
            suggestion_message="系统每日自动计算并记录房费"
        ),
    ]

    events = [
        EventMetadata(
            name="PAYMENT_RECEIVED",
            description="收到支付",
            entity="Bill",
            triggered_by=["add_payment"],
            payload_fields=["bill_id", "payment_id", "amount"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=Bill,
        constraints=constraints,
        events=events,
    )
