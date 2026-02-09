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
    ConstraintMetadata,
    ConstraintType,
    ConstraintSeverity,
    RelationshipMetadata,
    StateMachine,
    StateTransition,
    EventMetadata,
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
        """注册酒店领域本体到框架

        Note: Actions are no longer registered here. SPEC-R11 unified action
        registration via ActionRegistry.set_ontology_registry() which auto-syncs
        all ActionDefinitions to OntologyRegistry as ActionMetadata.
        """
        self._register_models(registry)
        self._register_entities(registry)
        self._register_relationships(registry)
        self._register_state_machines(registry)
        self._register_constraints(registry)
        self._register_events(registry)

    def _register_models(self, registry: "OntologyRegistry") -> None:
        """SPEC-R02: Register ORM model classes for registry-driven queries."""
        from app.models.ontology import (
            Room, Guest, Reservation, StayRecord, Bill,
            Payment, Task, Employee, RoomType, RatePlan,
        )
        models = {
            "Room": Room, "Guest": Guest, "Reservation": Reservation,
            "StayRecord": StayRecord, "Bill": Bill, "Payment": Payment,
            "Task": Task, "Employee": Employee, "RoomType": RoomType,
            "RatePlan": RatePlan,
        }
        for name, cls in models.items():
            registry.register_model(name, cls)

    # ========== SPEC-R03: Display name and security overrides ==========

    _DISPLAY_NAMES = {
        "id": "主键", "room_number": "房间号", "floor": "楼层",
        "status": "状态", "room_type_id": "房型ID", "features": "特征描述",
        "is_active": "是否启用", "name": "姓名", "id_type": "证件类型",
        "id_number": "证件号码", "phone": "手机号", "email": "邮箱",
        "preferences": "偏好", "tier": "客户等级", "total_stays": "累计入住次数",
        "total_amount": "总金额", "is_blacklisted": "是否黑名单",
        "blacklist_reason": "黑名单原因", "notes": "备注",
        "reservation_no": "预订号", "guest_id": "客人ID",
        "check_in_date": "入住日期", "check_out_date": "离店日期",
        "room_count": "房间数", "adult_count": "成人数", "child_count": "儿童数",
        "prepaid_amount": "预付金额", "special_requests": "特殊要求",
        "estimated_arrival": "预计到达时间", "cancel_reason": "取消原因",
        "created_by": "创建人", "reservation_id": "预订ID", "room_id": "房间ID",
        "check_in_time": "入住时间", "check_out_time": "退房时间",
        "expected_check_out": "预计离店日期", "deposit_amount": "押金",
        "task_type": "任务类型", "assignee_id": "执行人ID", "priority": "优先级",
        "stay_record_id": "住宿记录ID", "paid_amount": "已付金额",
        "adjustment_amount": "调整金额", "adjustment_reason": "调整原因",
        "is_settled": "是否结清", "bill_id": "账单ID", "amount": "金额",
        "method": "支付方式", "payment_time": "支付时间", "remark": "备注",
        "username": "登录账号", "password_hash": "密码哈希", "role": "角色",
        "description": "描述", "base_price": "基础价格",
        "max_occupancy": "最大入住人数", "amenities": "设施列表",
        "discount_rate": "折扣率", "start_date": "开始日期", "end_date": "结束日期",
        "price": "价格", "is_weekend": "是否周末",
        "created_at": "创建时间", "updated_at": "更新时间",
        "started_at": "开始时间", "completed_at": "完成时间",
    }

    _SECURITY_OVERRIDES = {
        "password_hash": "RESTRICTED",
        "id_number": "RESTRICTED",
        "phone": "CONFIDENTIAL",
        "email": "CONFIDENTIAL",
        "id_type": "CONFIDENTIAL",
        "deposit_amount": "CONFIDENTIAL",
        "total_amount": "CONFIDENTIAL",
        "paid_amount": "CONFIDENTIAL",
        "prepaid_amount": "CONFIDENTIAL",
        "adjustment_amount": "CONFIDENTIAL",
    }

    _PII_TYPES = {
        "phone": "PHONE",
        "id_number": "ID_NUMBER",
        "name": "NAME",
        "email": "EMAIL",
    }

    def _auto_register_properties(self, entity_meta: EntityMetadata, model_class) -> EntityMetadata:
        """SPEC-R03: Auto-discover ORM columns and register as PropertyMetadata."""
        from sqlalchemy import inspect as sa_inspect, String, Integer, Float, Numeric, Boolean, Text, Date, DateTime, Enum as SAEnum
        mapper = sa_inspect(model_class)
        for col in mapper.columns:
            col_name = col.key
            # Skip if already registered (manual override takes precedence)
            if col_name in entity_meta.properties:
                continue

            # Determine type
            col_type = type(col.type)
            if col_type in (String, Text) or issubclass(col_type, String):
                prop_type, py_type = "string", "str"
            elif col_type in (Integer,) or issubclass(col_type, Integer):
                prop_type, py_type = "integer", "int"
            elif col_type in (Float, Numeric) or issubclass(col_type, (Float, Numeric)):
                prop_type, py_type = "number", "float"
            elif col_type in (Boolean,) or issubclass(col_type, Boolean):
                prop_type, py_type = "boolean", "bool"
            elif col_type in (Date,):
                prop_type, py_type = "date", "date"
            elif col_type in (DateTime,) or issubclass(col_type, DateTime):
                prop_type, py_type = "datetime", "datetime"
            else:
                prop_type, py_type = "string", "str"

            # Detect enum
            enum_values = None
            if hasattr(col.type, 'enums'):
                enum_values = list(col.type.enums)
                prop_type = "enum"
            elif hasattr(col.type, 'enum_class'):
                enum_values = [e.value for e in col.type.enum_class]
                prop_type = "enum"

            # FK detection
            is_fk = bool(col.foreign_keys)
            fk_target = None
            if is_fk and col.foreign_keys:
                fk_target = list(col.foreign_keys)[0].target_fullname.split(".")[0]

            entity_meta.add_property(PropertyMetadata(
                name=col_name,
                type=prop_type,
                python_type=py_type,
                is_primary_key=col.primary_key,
                is_foreign_key=is_fk,
                foreign_key_target=fk_target,
                is_required=not col.nullable and not col.primary_key,
                is_unique=col.unique or False,
                is_nullable=col.nullable if col.nullable is not None else True,
                enum_values=enum_values,
                description=self._DISPLAY_NAMES.get(col_name, col_name),
                display_name=self._DISPLAY_NAMES.get(col_name, ""),
                security_level=self._SECURITY_OVERRIDES.get(col_name, "INTERNAL"),
            ))
        return entity_meta

    def _register_entities(self, registry: "OntologyRegistry") -> None:
        """注册酒店实体 (SPEC-R03: auto-discover properties from ORM)"""
        from app.models.ontology import (
            Room, Guest, Reservation, StayRecord, Bill,
            Payment, Task, Employee, RoomType, RatePlan,
        )

        entity_defs = [
            (EntityMetadata(name="Room", description="酒店房间，物理空间单位",
                table_name="rooms", category="master_data", is_aggregate_root=False,
                lifecycle_states=["VACANT_CLEAN", "VACANT_DIRTY", "OCCUPIED", "OUT_OF_ORDER"]),
             Room),
            (EntityMetadata(name="Guest", description="客人信息",
                table_name="guests", category="master_data", is_aggregate_root=True,
                tags=["customer", "crm"]),
             Guest),
            (EntityMetadata(name="Reservation", description="预订信息",
                table_name="reservations", category="transactional",
                lifecycle_states=["CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED"]),
             Reservation),
            (EntityMetadata(name="StayRecord", description="住宿记录",
                table_name="stay_records", category="transactional", is_aggregate_root=True,
                lifecycle_states=["ACTIVE", "CHECKED_OUT"]),
             StayRecord),
            (EntityMetadata(name="Task", description="任务（清洁、维修等）",
                table_name="tasks", category="transactional",
                lifecycle_states=["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"]),
             Task),
            (EntityMetadata(name="Bill", description="账单",
                table_name="bills", category="transactional"),
             Bill),
            (EntityMetadata(name="Payment", description="支付记录",
                table_name="payments", category="transactional"),
             Payment),
            (EntityMetadata(name="Employee", description="员工",
                table_name="employees", category="master_data"),
             Employee),
            (EntityMetadata(name="RoomType", description="房型定义",
                table_name="room_types", category="dimension"),
             RoomType),
            (EntityMetadata(name="RatePlan", description="价格方案",
                table_name="rate_plans", category="dimension"),
             RatePlan),
        ]

        for entity_meta, model_cls in entity_defs:
            self._auto_register_properties(entity_meta, model_cls)
            registry.register_entity(entity_meta)

    def _register_relationships(self, registry: "OntologyRegistry") -> None:
        """注册实体间关系 (SPEC-07)"""
        # Guest ↔ StayRecord
        registry.register_relationship("Guest", RelationshipMetadata(
            name="stays", target_entity="StayRecord", cardinality="one_to_many",
            foreign_key="guest_id", foreign_key_entity="StayRecord", inverse_name="guest",
        ))
        registry.register_relationship("StayRecord", RelationshipMetadata(
            name="guest", target_entity="Guest", cardinality="many_to_one",
            foreign_key="guest_id", foreign_key_entity="StayRecord", inverse_name="stays",
        ))
        # Guest ↔ Reservation
        registry.register_relationship("Guest", RelationshipMetadata(
            name="reservations", target_entity="Reservation", cardinality="one_to_many",
            foreign_key="guest_id", foreign_key_entity="Reservation", inverse_name="guest",
        ))
        registry.register_relationship("Reservation", RelationshipMetadata(
            name="guest", target_entity="Guest", cardinality="many_to_one",
            foreign_key="guest_id", foreign_key_entity="Reservation", inverse_name="reservations",
        ))
        # Room ↔ StayRecord
        registry.register_relationship("Room", RelationshipMetadata(
            name="stay_records", target_entity="StayRecord", cardinality="one_to_many",
            foreign_key="room_id", foreign_key_entity="StayRecord", inverse_name="room",
        ))
        registry.register_relationship("StayRecord", RelationshipMetadata(
            name="room", target_entity="Room", cardinality="many_to_one",
            foreign_key="room_id", foreign_key_entity="StayRecord", inverse_name="stay_records",
        ))
        # Room ↔ Task
        registry.register_relationship("Room", RelationshipMetadata(
            name="tasks", target_entity="Task", cardinality="one_to_many",
            foreign_key="room_id", foreign_key_entity="Task", inverse_name="room",
        ))
        registry.register_relationship("Task", RelationshipMetadata(
            name="room", target_entity="Room", cardinality="many_to_one",
            foreign_key="room_id", foreign_key_entity="Task", inverse_name="tasks",
        ))
        # Room → RoomType
        registry.register_relationship("Room", RelationshipMetadata(
            name="room_type", target_entity="RoomType", cardinality="many_to_one",
            foreign_key="room_type_id", foreign_key_entity="Room",
        ))
        # StayRecord → Bill
        registry.register_relationship("StayRecord", RelationshipMetadata(
            name="bill", target_entity="Bill", cardinality="one_to_one",
            foreign_key="stay_record_id", foreign_key_entity="Bill", inverse_name="stay_record",
        ))
        registry.register_relationship("Bill", RelationshipMetadata(
            name="stay_record", target_entity="StayRecord", cardinality="one_to_one",
            foreign_key="stay_record_id", foreign_key_entity="Bill", inverse_name="bill",
        ))
        # Bill ↔ Payment
        registry.register_relationship("Bill", RelationshipMetadata(
            name="payments", target_entity="Payment", cardinality="one_to_many",
            foreign_key="bill_id", foreign_key_entity="Payment", inverse_name="bill",
        ))
        registry.register_relationship("Payment", RelationshipMetadata(
            name="bill", target_entity="Bill", cardinality="many_to_one",
            foreign_key="bill_id", foreign_key_entity="Payment", inverse_name="payments",
        ))
        # Task → Employee
        registry.register_relationship("Task", RelationshipMetadata(
            name="assignee", target_entity="Employee", cardinality="many_to_one",
            foreign_key="assignee_id", foreign_key_entity="Task",
        ))
        # Reservation → RoomType
        registry.register_relationship("Reservation", RelationshipMetadata(
            name="room_type", target_entity="RoomType", cardinality="many_to_one",
            foreign_key="room_type_id", foreign_key_entity="Reservation",
        ))

    def _register_state_machines(self, registry: "OntologyRegistry") -> None:
        """注册状态机 (SPEC-08)"""
        # Room 状态机 (lowercase to match ORM RoomStatus enum values)
        registry.register_state_machine(StateMachine(
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
        ))
        # Reservation 状态机
        registry.register_state_machine(StateMachine(
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
        ))
        # StayRecord 状态机
        registry.register_state_machine(StateMachine(
            entity="StayRecord",
            name="stay_lifecycle",
            description="住宿记录生命周期",
            states=["active", "checked_out"],
            initial_state="active",
            final_states={"checked_out"},
            transitions=[
                StateTransition(from_state="active", to_state="checked_out", trigger="checkout"),
            ]
        ))
        # Task 状态机 (includes "assigned" state used by TaskService)
        registry.register_state_machine(StateMachine(
            entity="Task",
            name="task_lifecycle",
            description="任务生命周期",
            states=["pending", "assigned", "in_progress", "completed", "cancelled"],
            initial_state="pending",
            final_states={"completed", "cancelled"},
            transitions=[
                StateTransition(from_state="pending", to_state="assigned", trigger="assign"),
                StateTransition(from_state="pending", to_state="in_progress", trigger="start"),
                StateTransition(from_state="pending", to_state="cancelled", trigger="cancel"),
                StateTransition(from_state="assigned", to_state="in_progress", trigger="start"),
                StateTransition(from_state="assigned", to_state="completed", trigger="complete"),
                StateTransition(from_state="assigned", to_state="cancelled", trigger="cancel"),
                StateTransition(from_state="in_progress", to_state="completed", trigger="complete"),
                StateTransition(from_state="in_progress", to_state="cancelled", trigger="cancel"),
            ]
        ))

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

    def _register_events(self, registry: "OntologyRegistry") -> None:
        """注册领域事件 (SPEC-23)"""

        registry.register_event(EventMetadata(
            name="ROOM_STATUS_CHANGED",
            description="房间状态发生变化",
            entity="Room",
            triggered_by=["check_in", "check_out", "mark_clean", "mark_dirty"],
            payload_fields=["room_id", "old_status", "new_status"],
        ))

        registry.register_event(EventMetadata(
            name="GUEST_CHECKED_IN",
            description="客人办理入住",
            entity="Guest",
            triggered_by=["walkin_checkin", "checkin"],
            payload_fields=["guest_id", "room_id", "stay_record_id"],
        ))

        registry.register_event(EventMetadata(
            name="GUEST_CHECKED_OUT",
            description="客人办理退房",
            entity="Guest",
            triggered_by=["checkout"],
            payload_fields=["guest_id", "room_id", "stay_record_id", "bill_id"],
        ))

        registry.register_event(EventMetadata(
            name="RESERVATION_CREATED",
            description="创建新预订",
            entity="Reservation",
            triggered_by=["create_reservation"],
            payload_fields=["reservation_id", "guest_id", "room_type_id"],
        ))

        registry.register_event(EventMetadata(
            name="RESERVATION_CANCELLED",
            description="取消预订",
            entity="Reservation",
            triggered_by=["cancel_reservation"],
            payload_fields=["reservation_id", "reason"],
        ))

        registry.register_event(EventMetadata(
            name="TASK_CREATED",
            description="创建新任务",
            entity="Task",
            triggered_by=["create_task"],
            payload_fields=["task_id", "room_id", "task_type"],
        ))

        registry.register_event(EventMetadata(
            name="TASK_COMPLETED",
            description="任务完成",
            entity="Task",
            triggered_by=["complete_task"],
            payload_fields=["task_id", "assignee_id"],
        ))

        registry.register_event(EventMetadata(
            name="PAYMENT_RECEIVED",
            description="收到支付",
            entity="Bill",
            triggered_by=["add_payment"],
            payload_fields=["bill_id", "payment_id", "amount"],
        ))

        registry.register_event(EventMetadata(
            name="STAY_EXTENDED",
            description="延长住宿",
            entity="StayRecord",
            triggered_by=["extend_stay"],
            payload_fields=["stay_record_id", "new_checkout_date"],
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

        SPEC-R12: Delegates to ActionRegistry.dispatch() for unified action execution.
        """
        from app.services.actions import get_action_registry

        action_registry = get_action_registry()
        try:
            return action_registry.dispatch(action_type, params, context)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "action_type": action_type,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Action execution failed: {str(e)}",
                "action_type": action_type,
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
