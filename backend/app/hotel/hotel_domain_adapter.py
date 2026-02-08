"""
app/hotel/hotel_domain_adapter.py

Hotel domain adapter - Registers hotel-specific ontology to the framework
Demonstrates how to implement IDomainAdapter for a real business domain
"""
from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry

from core.ontology.domain_adapter import IDomainAdapter
from core.ontology.metadata import (
    EntityMetadata,
    PropertyMetadata,
    ActionMetadata,
    ActionParam,
    ParamType,
    ConstraintMetadata,
    ConstraintType,
    ConstraintSeverity,
    ActionScope,
    ConfirmationLevel,
)


class HotelDomainAdapter(IDomainAdapter):
    """
    酒店领域适配器 - 框架与应用的桥梁

    将酒店管理系统的领域本体注册到框架中。
    """

    def get_domain_name(self) -> str:
        """获取领域名称"""
        return "Hotel Management System"

    def register_ontology(self, registry: "OntologyRegistry") -> None:
        """注册酒店领域本体到框架"""
        self._register_entities(registry)
        self._register_actions(registry)
        self._register_constraints(registry)
        # State machines will be registered in later SPECs

    def _register_entities(self, registry: "OntologyRegistry") -> None:
        """注册酒店实体"""

        # Room 实体
        registry.register_entity(
            EntityMetadata(
                name="Room",
                description="酒店房间，物理空间单位",
                table_name="rooms",
                category="master_data",
                is_aggregate_root=False,
                lifecycle_states=[
                    "VACANT_CLEAN", "VACANT_DIRTY",
                    "OCCUPIED", "OUT_OF_ORDER"
                ]
            )
            .add_property(PropertyMetadata(
                name="room_number",
                type="string",
                python_type="str",
                is_required=True,
                is_unique=True,
                description="房间号"
            ))
            .add_property(PropertyMetadata(
                name="status",
                type="enum",
                python_type="str",
                is_required=True,
                enum_values=["VACANT_CLEAN", "VACANT_DIRTY", "OCCUPIED", "OUT_OF_ORDER"],
                description="房间状态"
            ))
            .add_property(PropertyMetadata(
                name="floor",
                type="integer",
                python_type="int",
                description="所在楼层"
            ))
        )

        # Guest 实体
        registry.register_entity(
            EntityMetadata(
                name="Guest",
                description="客人信息",
                table_name="guests",
                category="master_data",
                is_aggregate_root=True,
                tags=["customer", "crm"]
            )
            .add_property(PropertyMetadata(
                name="name",
                type="string",
                python_type="str",
                is_required=True,
                description="客人姓名"
            ))
            .add_property(PropertyMetadata(
                name="phone",
                type="string",
                python_type="str",
                description="联系电话"
            ))
        )

        # Reservation 实体
        registry.register_entity(
            EntityMetadata(
                name="Reservation",
                description="预订信息",
                table_name="reservations",
                category="transactional",
                lifecycle_states=["CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED"]
            )
            .add_property(PropertyMetadata(
                name="check_in_date",
                type="date",
                python_type="date",
                is_required=True,
                description="入住日期"
            ))
            .add_property(PropertyMetadata(
                name="check_out_date",
                type="date",
                python_type="date",
                is_required=True,
                description="退房日期"
            ))
        )

        # StayRecord 实体
        registry.register_entity(
            EntityMetadata(
                name="StayRecord",
                description="住宿记录",
                table_name="stay_records",
                category="transactional",
                is_aggregate_root=True,
                lifecycle_states=["ACTIVE", "CHECKED_OUT"]
            )
        )

    def _register_actions(self, registry: "OntologyRegistry") -> None:
        """注册酒店操作"""

        # checkin 操作
        registry.register_action(
            "Room",
            ActionMetadata(
                action_type="checkin",
                entity="Room",
                method_name="checkin",
                description="为客人办理入住手续",
                scope=ActionScope.SINGLE,
                confirmation_level=ConfirmationLevel.MEDIUM,
                undoable=False,
                side_effects=[
                    "房间状态从 VACANT_CLEAN 变为 OCCUPIED",
                    "创建账单记录"
                ]
            )
            .add_parameter(ActionParam(
                name="room_id",
                type=ParamType.INTEGER,
                required=True,
                description="房间ID"
            ))
            .add_parameter(ActionParam(
                name="guest_id",
                type=ParamType.INTEGER,
                required=True,
                description="客人ID"
            ))
        )

        # checkout 操作
        registry.register_action(
            "StayRecord",
            ActionMetadata(
                action_type="checkout",
                entity="StayRecord",
                method_name="checkout",
                description="为客人办理退房手续",
                scope=ActionScope.SINGLE,
                confirmation_level=ConfirmationLevel.HIGH,
                undoable=True,
                side_effects=[
                    "房间状态从 OCCUPIED 变为 VACANT_DIRTY",
                    "自动创建清洁任务"
                ]
            )
            .add_parameter(ActionParam(
                name="stay_record_id",
                type=ParamType.INTEGER,
                required=True,
                description="住宿记录ID"
            ))
        )

        # create_reservation 操作
        registry.register_action(
            "Reservation",
            ActionMetadata(
                action_type="create_reservation",
                entity="Reservation",
                method_name="create_reservation",
                description="创建预订",
                scope=ActionScope.SINGLE,
                confirmation_level=ConfirmationLevel.MEDIUM
            )
            .add_parameter(ActionParam(
                name="guest_name",
                type=ParamType.STRING,
                required=True,
                description="客人姓名"
            ))
            .add_parameter(ActionParam(
                name="check_in_date",
                type=ParamType.DATE,
                required=True,
                description="入住日期"
            ))
            .add_parameter(ActionParam(
                name="check_out_date",
                type=ParamType.DATE,
                required=True,
                description="退房日期"
            ))
        )

    def _register_constraints(self, registry: "OntologyRegistry") -> None:
        """注册酒店约束"""

        # 入住约束：房间必须空闲
        registry.register_constraint(ConstraintMetadata(
            id="room_must_be_vacant_for_checkin",
            name="入住时房间必须空闲",
            description="只有 VACANT_CLEAN 状态的房间才能办理入住",
            constraint_type=ConstraintType.STATE,
            severity=ConstraintSeverity.ERROR,
            entity="Room",
            action="checkin",
            condition_text="room.status == 'VACANT_CLEAN'",
            error_message="房间状态不是空闲可住，无法入住",
            suggestion_message="请选择状态为 VACANT_CLEAN 的房间"
        ))

        # 退房约束：账单必须结清
        registry.register_constraint(ConstraintMetadata(
            id="bill_must_be_settled_for_checkout",
            name="退房前必须结清账单",
            description="客人退房时账单必须已结清",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="StayRecord",
            action="checkout",
            condition_text="stay.bill.outstanding_amount <= 0",
            error_message="账单未结清，无法退房",
            suggestion_message="请先收取未结清金额"
        ))

        # 日期约束：退房日期必须晚于入住日期
        registry.register_constraint(ConstraintMetadata(
            id="checkout_date_must_be_after_checkin",
            name="退房日期必须晚于入住日期",
            description="预订时退房日期必须晚于入住日期",
            constraint_type=ConstraintType.BUSINESS_RULE,
            severity=ConstraintSeverity.ERROR,
            entity="Reservation",
            action="create_reservation",
            condition_text="check_out_date > check_in_date",
            error_message="退房日期不能早于或等于入住日期",
            suggestion_message="请选择正确的入住和退房日期"
        ))

    def get_current_state(self) -> Dict[str, Any]:
        """获取当前系统状态"""
        # 简化实现，返回示例状态
        return {
            "total_rooms": 100,
            "occupied_rooms": 65,
            "vacant_clean_rooms": 30,
            "vacant_dirty_rooms": 5,
            "occupancy_rate": "65%",
            "today_checkins": 12,
            "today_checkouts": 8,
            "pending_checkouts": 3
        }

    def execute_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行酒店特定的操作

        注意：这是简化实现，完整实现将在 SPEC-16 中完成。
        当前版本仅返回操作信息，实际业务逻辑委托给具体的 service。
        """
        # TODO: 在 SPEC-16 中实现完整的 action 执行逻辑
        return {
            "success": False,
            "error": "Not implemented yet - will be implemented in SPEC-16",
            "action_type": action_type,
            "params": params
        }

    def get_llm_system_prompt_additions(self) -> str:
        """获取酒店领域的特定提示词"""
        return """
## 酒店业务特定规则

1. 房间编号格式: 楼层+房号 (如 201, 202, 301)
2. 入住时间通常为 14:00 后，退房时间为 12:00 前
3. 同一房间同一天只能有一组客人
4. VIP 客人的特殊需求需要优先处理
"""

    def get_entity_display_name(self, entity_type: str, entity_id: Any) -> str:
        """获取实体的显示名称"""
        # 简化实现，可以根据 entity_type 查询数据库获取实际名称
        if entity_type == "Room":
            return f"房间 {entity_id}"
        elif entity_type == "Guest":
            return f"客人 {entity_id}"
        elif entity_type == "Reservation":
            return f"预订 #{entity_id}"
        elif entity_type == "StayRecord":
            return f"住宿记录 #{entity_id}"
        return f"{entity_type}:{entity_id}"


# Export
__all__ = ["HotelDomainAdapter"]
