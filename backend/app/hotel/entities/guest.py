"""Guest entity registration."""
from app.hotel.entities import EntityRegistration
from core.ontology.metadata import (
    EntityMetadata, ConstraintMetadata, ConstraintType, ConstraintSeverity,
    EventMetadata,
)


def get_registration() -> EntityRegistration:
    from app.models.ontology import Guest

    metadata = EntityMetadata(
        name="Guest",
        description="客人信息 - 客户关系管理的核心实体。支持会员等级体系 (normal/silver/gold/platinum)，黑名单管理，以及完整的入住历史追踪。",
        table_name="guests", category="master_data", is_aggregate_root=True,
        tags=["customer", "crm"],
        extensions={
            "business_purpose": "客户关系管理与画像",
            "key_attributes": ["name", "phone", "id_number", "tier"],
            "invariants": ["身份证号唯一", "黑名单客人禁止入住"],
            "smart_update": {
                "enabled": True,
                "identifier_fields": {"name_column": "name"},
                "editable_fields": ["name", "phone", "email"],
                "update_schema": "GuestUpdate",
                "service_class": "app.services.guest_service.GuestService",
                "service_method": "update_guest",
                "allowed_roles": {"receptionist", "manager"},
                "display_name": "客人",
                "action_description": "智能修改客人信息。当用户描述的是相对修改、部分修改等无法直接得出完整新值的指令时使用此操作（例如：'手机号后两位改为88'、'名字最后一个字改为华'、'邮箱前缀改为abc'）。注意：如果用户提供了完整的新值（如'电话改成13912345678'），应使用 update_guest 而非此操作。",
                "glossary_examples": [
                    {"correct": '"张三的手机号后三位改为888" → update_guest_smart（需要基于当前值计算新值）',
                     "incorrect": '"张三的手机号后三位改为888" → update_guest（无法直接得出完整新手机号）'},
                    {"correct": '"把张三的电话改成13912345678" → update_guest（已提供完整新值）',
                     "incorrect": '"把张三的电话改成13912345678" → update_guest_smart（已有完整值，不需要智能解析）'},
                ],
            },
        },
    )

    constraints = [
        ConstraintMetadata(
            id="guest_unique_by_id_number",
            name="身份证号唯一",
            description="同一身份证号不能重复注册",
            constraint_type=ConstraintType.CARDINALITY,
            severity=ConstraintSeverity.ERROR,
            entity="Guest", action="create_guest",
            condition_text="id_number is unique across Guest",
            error_message="该身份证号已注册",
            suggestion_message="请检查是否已有该客人记录"
        ),
        ConstraintMetadata(
            id="blacklist_prevents_checkin",
            name="黑名单客人禁止入住",
            description="在黑名单中的客人不允许办理入住",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Guest", action="checkin",
            condition_text="guest.is_blacklisted == False",
            condition_code="state.is_blacklisted == False",
            error_message="该客人在黑名单中，禁止入住",
            suggestion_message="如需解除黑名单，请联系经理审批"
        ),
    ]

    events = [
        EventMetadata(
            name="GUEST_CHECKED_IN",
            description="客人办理入住",
            entity="Guest",
            triggered_by=["walkin_checkin", "checkin"],
            payload_fields=["guest_id", "room_id", "stay_record_id"],
        ),
        EventMetadata(
            name="GUEST_CHECKED_OUT",
            description="客人办理退房",
            entity="Guest",
            triggered_by=["checkout"],
            payload_fields=["guest_id", "room_id", "stay_record_id", "bill_id"],
        ),
    ]

    return EntityRegistration(
        metadata=metadata,
        model_class=Guest,
        constraints=constraints,
        events=events,
    )
