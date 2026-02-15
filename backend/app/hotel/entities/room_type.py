"""RoomType entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import EntityMetadata


def get_registration() -> EntityRegistration:
    from app.models.ontology import RoomType

    metadata = EntityMetadata(
        name="RoomType",
        description="房型定义 - 定义房间类型（如标准间、豪华大床房、套房等），包括基础价格、最大入住人数和设施信息。",
        table_name="room_types", category="dimension",
        extensions={
            "business_purpose": "产品定义与定价基准",
            "key_attributes": ["name", "base_price", "max_occupancy"],
            "smart_update": {
                "enabled": True,
                "identifier_fields": {"name_column": "name"},
                "editable_fields": ["name", "description", "base_price", "max_occupancy", "amenities"],
                "update_schema": "RoomTypeUpdate",
                "service_class": "app.services.room_service.RoomService",
                "service_method": "update_room_type",
                "allowed_roles": {"manager"},
                "display_name": "房型",
            },
        },
    )

    return EntityRegistration(
        metadata=metadata,
        model_class=RoomType,
    )
