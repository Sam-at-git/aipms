"""
app/hotel/hotel_domain_adapter.py

Hotel domain adapter - Registers hotel-specific ontology to the framework
Demonstrates how to implement IDomainAdapter for a real business domain
"""
import re
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import date, datetime, timedelta

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry
    from sqlalchemy.orm import Session

from core.ontology.domain_adapter import IDomainAdapter
from core.ontology.metadata import (
    EntityMetadata,
    PropertyMetadata,
)

logger = logging.getLogger(__name__)


class HotelDomainAdapter(IDomainAdapter):
    """
    酒店领域适配器 - 框架与应用的桥梁

    将酒店管理系统的领域本体注册到框架中。
    Implements OODA orchestrator support methods for hotel domain.
    """

    def __init__(self, db: "Session" = None):
        self._db = db
        self._room_service = None
        self._reservation_service = None
        self._checkin_service = None
        self._checkout_service = None
        self._task_service = None
        self._billing_service = None
        self._report_service = None
        self._param_parser = None

    def _ensure_services(self):
        """Lazy-initialize hotel services (only when db is available)."""
        if self._db is None:
            return
        if self._room_service is not None:
            return
        from app.services.room_service import RoomService
        from app.services.reservation_service import ReservationService
        from app.services.checkin_service import CheckInService
        from app.services.checkout_service import CheckOutService
        from app.services.task_service import TaskService
        from app.services.billing_service import BillingService
        from app.services.report_service import ReportService
        from app.services.param_parser_service import ParamParserService
        self._room_service = RoomService(self._db)
        self._reservation_service = ReservationService(self._db)
        self._checkin_service = CheckInService(self._db)
        self._checkout_service = CheckOutService(self._db)
        self._task_service = TaskService(self._db)
        self._billing_service = BillingService(self._db)
        self._report_service = ReportService(self._db)
        self._param_parser = ParamParserService(self._db)

    @property
    def room_service(self):
        self._ensure_services()
        return self._room_service

    @property
    def reservation_service(self):
        self._ensure_services()
        return self._reservation_service

    @property
    def checkin_service(self):
        self._ensure_services()
        return self._checkin_service

    @property
    def task_service(self):
        self._ensure_services()
        return self._task_service

    @property
    def param_parser(self):
        self._ensure_services()
        return self._param_parser

    @property
    def report_service(self):
        self._ensure_services()
        return self._report_service

    def get_domain_name(self) -> str:
        """获取领域名称"""
        return "Hotel Management System"

    def register_ontology(self, registry: "OntologyRegistry") -> None:
        """注册酒店领域本体到框架

        Note: Actions are no longer registered here. SPEC-R11 unified action
        registration via ActionRegistry.set_ontology_registry() which auto-syncs
        all ActionDefinitions to OntologyRegistry as ActionMetadata.

        Entity metadata, state machines, constraints, events, and relationships
        are sourced from app/hotel/entities/ module (SPEC-4/5).
        """
        self._register_models(registry)
        self._register_entities(registry)
        self._register_relationships(registry)

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
        """注册酒店实体、状态机、约束、事件 (sourced from entities/ module)."""
        from app.hotel.entities import get_all_entity_registrations
        from core.reasoning.constraint_engine import PhoneFormatValidator, FieldUniquenessValidator

        # OAG: 实例化验证器用于属性级别约束
        _phone_format_validator = PhoneFormatValidator()
        _phone_uniqueness_validator = FieldUniquenessValidator(entity_name="Guest", field_name="phone")

        for reg in get_all_entity_registrations():
            entity_meta = reg.metadata
            model_cls = reg.model_class
            self._auto_register_properties(entity_meta, model_cls)

            # ========== OAG: Guest.phone 属性增强 ==========
            if entity_meta.name == "Guest":
                phone_metadata = entity_meta.get_property("phone")
                if phone_metadata:
                    phone_metadata.format_regex = r'^1[3-9]\d{9}$'
                    phone_metadata.sensitive = True
                    phone_metadata.requires_reason = False
                    phone_metadata.update_validation_rules.extend([
                        _phone_format_validator,
                        _phone_uniqueness_validator,
                    ])

            registry.register_entity(entity_meta)

            # Register state machine if defined
            if reg.state_machine:
                registry.register_state_machine(reg.state_machine)

            # Register constraints
            for constraint in reg.constraints:
                registry.register_constraint(constraint)

            # Register events
            for event in reg.events:
                registry.register_event(event)

    def _register_relationships(self, registry: "OntologyRegistry") -> None:
        """注册实体间关系 (sourced from entities/ module)."""
        from app.hotel.entities import get_all_relationships
        for entity_name, rel_meta in get_all_relationships():
            registry.register_relationship(entity_name, rel_meta)

    # _register_state_machines: removed — now handled by EntityRegistration in _register_entities()
    # _register_constraints: removed — now handled by EntityRegistration in _register_entities()
    # _register_events: removed — now handled by EntityRegistration in _register_entities()

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


    # ========== OODA Orchestrator Support Methods ==========

    def build_llm_context(self, db) -> Dict[str, Any]:
        """Build hotel-specific LLM context: room summary, room types, active stays, tasks.

        数据自动受当前 SecurityContext 的 branch_id 过滤。
        """
        self._ensure_services()
        context = {}

        # 获取当前分店上下文（用于提示 LLM）
        branch_id = None
        branch_name = None
        try:
            from app.services.branch_utils import get_current_branch_id
            branch_id = get_current_branch_id()
            if branch_id:
                from app.system.models.org import SysDepartment
                branch = db.query(SysDepartment).filter(SysDepartment.id == branch_id).first()
                if branch:
                    branch_name = branch.name
        except Exception:
            pass
        if branch_name:
            context["current_branch"] = branch_name

        # Room status summary
        summary = self.room_service.get_room_status_summary()
        context["room_summary"] = summary

        # Available room types (so LLM can suggest during reservations)
        room_types = self.room_service.get_room_types()
        context["room_types"] = [
            {"id": rt.id, "name": rt.name, "price": float(rt.base_price)}
            for rt in room_types
        ]

        # Active stays (most recent 20)
        active_stays = self.checkin_service.get_active_stays()
        context["active_stays"] = [
            {
                "id": s.id,
                "room_number": s.room.room_number,
                "guest_name": s.guest.name,
                "expected_check_out": str(s.expected_check_out),
            }
            for s in active_stays[:20]
        ]

        # Pending tasks
        pending_tasks = self.task_service.get_pending_tasks()
        context["pending_tasks"] = [
            {
                "id": t.id,
                "room_number": t.room.room_number,
                "task_type": t.task_type.value,
            }
            for t in pending_tasks[:20]
        ]

        return context

    def enhance_action_params(self, action_type: str, params: Dict[str, Any],
                              message: str, db) -> Dict[str, Any]:
        """Enhance LLM-extracted params with hotel DB lookups and fuzzy matching."""
        self._ensure_services()

        # --- Room type parsing (multiple key names) ---
        if "room_type_id" in params or "room_type_name" in params or "room_type" in params:
            room_type_input = params.get("room_type_id") or params.get("room_type_name") or params.get("room_type")
            if room_type_input:
                parse_result = self.param_parser.parse_room_type(room_type_input)
                if parse_result.confidence >= 0.7:
                    params["room_type_id"] = parse_result.value
                    room_type = self.room_service.get_room_type(parse_result.value)
                    if room_type:
                        params["room_type_name"] = room_type.name

        # --- Room parsing ---
        if "room_id" in params or "room_number" in params:
            room_input = params.get("room_id") or params.get("room_number")
            if room_input:
                parse_result = self.param_parser.parse_room(room_input)
                if parse_result.confidence >= 0.7:
                    params["room_id"] = parse_result.value
                    if "room_number" not in params and isinstance(parse_result.raw_input, str):
                        params["room_number"] = parse_result.raw_input

        # --- New room (change room scenario) ---
        if "new_room_id" in params or "new_room_number" in params:
            room_input = params.get("new_room_id") or params.get("new_room_number")
            if room_input:
                parse_result = self.param_parser.parse_room(room_input)
                if parse_result.confidence >= 0.7:
                    params["new_room_id"] = parse_result.value

        # --- Employee parsing (task assignment) ---
        if "assignee_id" in params or "assignee_name" in params:
            assignee_input = params.get("assignee_id") or params.get("assignee_name")
            if assignee_input:
                parse_result = self.param_parser.parse_employee(assignee_input)
                if parse_result.confidence >= 0.7:
                    params["assignee_id"] = parse_result.value

        # --- Room status parsing ---
        if "status" in params:
            status_result = self.param_parser.parse_room_status(params["status"])
            if status_result.confidence >= 0.7:
                params["status"] = status_result.value

        # --- Task type parsing (Chinese: 维修, 清洁) ---
        if "task_type" in params:
            task_type_result = self.param_parser.parse_task_type(params["task_type"])
            if task_type_result.confidence >= 0.7:
                params["task_type"] = task_type_result.value.value

        # --- Price type parsing ---
        if "price_type" in params:
            price_type_input = str(params["price_type"]).lower().strip()
            price_type_aliases = {
                'weekend': ['周末', '周末价', 'weekend', '周六日', '星期六日'],
                'standard': ['平日', '标准', 'standard', '工作日', '平时'],
            }
            for ptype, aliases in price_type_aliases.items():
                if price_type_input in [a.lower() for a in aliases]:
                    params["price_type"] = ptype
                    break

        # --- Fallback DB lookups ---
        if "room_number" in params and "room_id" not in params:
            room = self.room_service.get_room_by_number(params["room_number"])
            if room:
                params["room_id"] = room.id

        if "reservation_no" in params and "reservation_id" not in params:
            reservation = self.reservation_service.get_reservation_by_no(params["reservation_no"])
            if reservation:
                params["reservation_id"] = reservation.id

        # --- Date parsing ---
        for date_field in ["expected_check_out", "new_check_out_date", "check_in_date", "check_out_date"]:
            if date_field in params:
                parse_result = self.param_parser.parse_date(params[date_field])
                if parse_result.confidence > 0:
                    val = parse_result.value
                    params[date_field] = val.isoformat() if isinstance(val, date) else str(val)
                else:
                    parsed_date = self._parse_relative_date(params[date_field])
                    if parsed_date:
                        params[date_field] = parsed_date.isoformat() if isinstance(parsed_date, date) else str(parsed_date)

        return params

    def enhance_single_action_params(self, action_type: str, params: Dict[str, Any],
                                     db) -> Dict[str, Any]:
        """Simplified param enhancement for follow-up mode."""
        self._ensure_services()
        enhanced = params.copy()

        if "room_type" in params and params["room_type"]:
            parse_result = self.param_parser.parse_room_type(str(params["room_type"]))
            if parse_result.confidence >= 0.7:
                enhanced["room_type_id"] = parse_result.value
                room_type = self.room_service.get_room_type(parse_result.value)
                if room_type:
                    enhanced["room_type_name"] = room_type.name

        if "room_number" in params and params["room_number"]:
            parse_result = self.param_parser.parse_room(str(params["room_number"]))
            if parse_result.confidence >= 0.7:
                enhanced["room_id"] = parse_result.value

        if "new_room_number" in params and params["new_room_number"]:
            parse_result = self.param_parser.parse_room(str(params["new_room_number"]))
            if parse_result.confidence >= 0.7:
                enhanced["new_room_id"] = parse_result.value

        return enhanced

    def get_field_definition(self, param_name: str, action_type: str,
                             current_params: Dict[str, Any], db) -> Optional[Any]:
        """Get UI field definition for a missing parameter."""
        self._ensure_services()
        from app.hotel.field_definitions import HotelFieldDefinitionProvider
        provider = HotelFieldDefinitionProvider(
            db=self._db,
            room_service=self.room_service,
            checkin_service=self.checkin_service,
            reservation_service=self.reservation_service,
        )
        return provider.get_field_definition(param_name, action_type, current_params)

    def get_report_data(self, db) -> Dict[str, Any]:
        """Get hotel dashboard stats."""
        self._ensure_services()
        stats = self.report_service.get_dashboard_stats()
        message = "**今日运营概览：**\n\n"
        message += f"- 入住率：**{stats['occupancy_rate']}%**\n"
        message += f"- 今日入住：{stats['today_checkins']} 间\n"
        message += f"- 今日退房：{stats['today_checkouts']} 间\n"
        message += f"- 今日营收：**¥{stats['today_revenue']}**\n"
        return {"message": message, "stats": stats}

    def get_help_text(self, language: str = "zh") -> str:
        """Get hotel-specific help text."""
        return (
            '您好！我是酒店智能助手，可以帮您：\n\n'
            '**查询类：**\n'
            '- 查看房态 / 有多少空房\n'
            '- 查询今日预抵\n'
            '- 查看在住客人\n'
            '- 查看清洁任务\n'
            '- 今日入住率\n\n'
            '**操作类：**\n'
            '- 帮王五办理入住\n'
            '- 301房退房\n'
            '- 预订一间大床房\n\n'
            '请问有什么可以帮您？'
        )

    def get_display_names(self) -> Dict[str, str]:
        """Get hotel field name → display name mapping."""
        return {
            'guest_name': '客人',
            'guest_phone': '电话',
            'room_type': '房型',
            'room_type_id': '房型',
            'room_number': '房间号',
            'check_in_date': '入住日期',
            'check_out_date': '离店日期',
            'expected_check_out': '预计离店',
            'reservation_id': '预订号',
            'stay_record_id': '住宿记录',
            'new_room_number': '新房间号',
            'new_check_out_date': '新离店日期',
            'task_type': '任务类型',
            'assignee_id': '执行人',
        }

    # ========== SPEC-04: Classification & HITL Support ==========

    def get_admin_roles(self) -> List[str]:
        """Return hotel admin role names."""
        return ["sysadmin", "manager"]

    def get_query_examples(self) -> List[Dict[str, Any]]:
        """Return hotel-specific query examples for LLM prompts."""
        return [
            {
                "description": "查询在住客人",
                "query": {
                    "root_object": "Guest",
                    "fields": ["name", "phone"],
                    "filters": [{"path": "stays.status", "operator": "eq", "value": "ACTIVE"}],
                },
            },
            {
                "description": "查询空闲房间",
                "query": {
                    "root_object": "Room",
                    "fields": ["room_number", "room_type.name", "status"],
                    "filters": [{"path": "status", "operator": "eq", "value": "VACANT_CLEAN"}],
                },
            },
        ]

    def get_context_summary(self, db, additional_context: Dict[str, Any]) -> List[str]:
        """Format hotel business context as user message lines."""
        lines = []
        if additional_context.get("room_summary"):
            rs = additional_context["room_summary"]
            lines.append(
                f"- 总房间: {rs.get('total', 'N/A')}, "
                f"空闲: {rs.get('vacant_clean', 'N/A')}, "
                f"入住: {rs.get('occupied', 'N/A')}"
            )
        if additional_context.get("room_types"):
            rt_list = additional_context["room_types"]
            if isinstance(rt_list, list):
                for rt in rt_list:
                    name = rt.get("name", "")
                    price = rt.get("base_price", "")
                    if name:
                        lines.append(f"  - {name}: ¥{price}")
        return lines

    def get_hitl_risk_overrides(self) -> Dict[str, Any]:
        """Return hotel HITL risk overrides — use ActionMetadata defaults."""
        return {}

    def get_hitl_custom_rules(self) -> list:
        """Return hotel-specific HITL custom rules."""
        def check_high_amount_adjustment(action_type, params, **kwargs):
            if action_type == "adjust_bill":
                amount = params.get("adjustment_amount", 0)
                try:
                    if abs(float(amount)) > 1000:
                        from core.ontology.metadata import ConfirmationLevel
                        return ConfirmationLevel.HIGH
                except (ValueError, TypeError):
                    pass
            return None
        return [check_high_amount_adjustment]

    @staticmethod
    def _parse_relative_date(date_input) -> Optional[date]:
        """Parse relative date strings (今天, 明天, 后天, etc.) to date objects."""
        if isinstance(date_input, date):
            return date_input
        if not isinstance(date_input, str):
            return None

        date_str = date_input.strip()

        if date_str in ["今天", "今日", "今日内"]:
            return date.today()
        if date_str in ["明天", "明日", "明晚", "明早"]:
            return date.today() + timedelta(days=1)
        if date_str == "明":
            return date.today() + timedelta(days=1)
        if date_str in ["后天", "后日"]:
            return date.today() + timedelta(days=2)
        if date_str in ["大后天"]:
            return date.today() + timedelta(days=3)

        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        week_match = re.match(r'下?(周|星期)([一二三四五六日天])', date_str)
        if week_match:
            target_weekday = weekday_map.get(week_match.group(2))
            if target_weekday is not None:
                today = date.today()
                days_ahead = target_weekday - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                if week_match.group(1) == "周":
                    days_ahead += 7
                return today + timedelta(days=days_ahead)

        try:
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            pass

        for fmt in ["%Y/%m/%d", "%Y.%m.%d", "%m/%d", "%m.%d"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if "%Y" not in fmt:
                    if parsed.month < date.today().month:
                        parsed = parsed.replace(year=date.today().year + 1)
                    else:
                        parsed = parsed.replace(year=date.today().year)
                return parsed.date()
            except ValueError:
                continue

        return None


# Export
__all__ = ["HotelDomainAdapter"]
