"""Payment entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import EntityMetadata


def get_registration() -> EntityRegistration:
    from app.models.ontology import Payment

    metadata = EntityMetadata(
        name="Payment",
        description="支付记录 - 账单的支付明细，记录每笔支付的金额、方式和时间。",
        table_name="payments", category="transactional",
        extensions={
            "business_purpose": "支付流水与对账",
            "key_attributes": ["bill_id", "amount", "method", "payment_time"],
        },
    )

    return EntityRegistration(
        metadata=metadata,
        model_class=Payment,
    )
