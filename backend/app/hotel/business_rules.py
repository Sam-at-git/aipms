"""
app/hotel/business_rules.py

酒店领域业务规则 - 从 core/ontology/business_rules.py 提取的领域特定规则
"""
from core.ontology.business_rules import (
    BusinessRule,
    BusinessRuleRegistry,
    RuleType,
    business_rules,
)


def init_hotel_business_rules() -> None:
    """
    初始化酒店领域业务规则

    从 OntologyRegistry 读取元数据，自动生成业务规则。
    """
    from core.ontology.registry import OntologyRegistry

    registry = OntologyRegistry()

    # ========== Room 实体规则 ==========

    # 规则1: 空闲房间查询扩展
    business_rules.register(BusinessRule(
        id="vacant_room_expansion",
        name="空闲房间查询扩展",
        rule_type=RuleType.QUERY_EXPANSION,
        entity="Room",
        trigger_keywords=["空闲", "可住", "可用", "空房", "空闲房间"],
        condition={
            "field": "status",
            "operator": "in",
            "value": ["vacant_clean", "vacant_dirty"]
        },
        description="查询空闲房间时，应包含净房和脏房两种状态"
    ))

    # 规则2: 房间状态别名
    room_status_metadata = registry.get_entity("Room")
    if room_status_metadata:
        for prop_name, prop in room_status_metadata.properties.items():
            if prop_name == "status":
                status_aliases = {}
                for enum_val in prop.enum_values or []:
                    if enum_val == "vacant_clean":
                        status_aliases["净房"] = enum_val
                        status_aliases["空净房"] = enum_val
                    elif enum_val == "vacant_dirty":
                        status_aliases["脏房"] = enum_val
                        status_aliases["空脏房"] = enum_val
                    elif enum_val == "occupied":
                        status_aliases["已入住"] = enum_val
                        status_aliases["入住"] = enum_val
                    elif enum_val == "out_of_order":
                        status_aliases["维修中"] = enum_val
                        status_aliases["停用"] = enum_val

                if status_aliases:
                    business_rules.register(BusinessRule(
                        id="room_status_aliases",
                        name="房间状态别名",
                        rule_type=RuleType.ALIAS_DEFINITION,
                        entity="Room",
                        alias_mapping=status_aliases,
                        description="房间状态的中英文别名映射"
                    ))

    # ========== Guest 实体规则 ==========

    business_rules.register(BusinessRule(
        id="guest_name_aliases",
        name="客人姓名字段别名",
        rule_type=RuleType.ALIAS_DEFINITION,
        entity="Guest",
        alias_mapping={
            "客人": "name",
            "姓名": "name",
            "房客": "name",
            "住客": "name",
            "旅客": "name"
        },
        description="客人姓名的各种别名"
    ))

    # ========== Reservation 实体规则 ==========

    business_rules.register(BusinessRule(
        id="reservation_status_aliases",
        name="预订状态别名",
        rule_type=RuleType.ALIAS_DEFINITION,
        entity="Reservation",
        alias_mapping={
            "已确认": "confirmed",
            "待确认": "pending",
            "已取消": "cancelled",
            "已入住": "checked_in",
            "已离店": "checked_out"
        },
        description="预订状态的中英文别名映射"
    ))
