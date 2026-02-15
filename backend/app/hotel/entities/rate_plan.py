"""RatePlan entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import EntityMetadata


def get_registration() -> EntityRegistration:
    from app.models.ontology import RatePlan

    metadata = EntityMetadata(
        name="RatePlan",
        description="价格方案 - 动态定价管理，支持按日期范围、周末/平日区分的灵活价格策略。",
        table_name="rate_plans", category="dimension",
        extensions={
            "business_purpose": "动态定价与收益管理",
            "key_attributes": ["room_type_id", "price", "start_date", "end_date"],
        },
    )

    return EntityRegistration(
        metadata=metadata,
        model_class=RatePlan,
    )
