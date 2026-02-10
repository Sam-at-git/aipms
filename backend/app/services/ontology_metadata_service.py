"""
本体元数据服务
在运行时通过反射提取本体元数据（语义、动力、动态）
"""
from typing import Dict, List, Optional, Any
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.models.ontology import (
    Room, RoomType, Guest, Reservation, StayRecord, Bill,
    Task, Employee, RatePlan, Payment,
    RoomStatus, ReservationStatus, StayRecordStatus, TaskStatus, EmployeeRole,
    GuestTier, PaymentMethod
)
from app.models.schemas import (
    RoomCreate, RoomUpdate, RoomStatusUpdate,
    RoomTypeCreate, RoomTypeUpdate,
    GuestCreate, GuestUpdate,
    ReservationCreate, ReservationUpdate, ReservationCancel,
    CheckInFromReservation, WalkInCheckIn, ExtendStay, ChangeRoom,
    CheckOutRequest,
    TaskCreate, TaskAssign, TaskUpdate,
    PaymentCreate, BillAdjustment
)
from app.services.metadata import (
    get_model_attributes, get_entity_relationships,
    AttributeMetadata, ActionMetadata, StateTransition, BusinessRule
)
from core.ontology.registry import OntologyRegistry


class OntologyMetadataService:
    """本体元数据服务 - 提取语义、动力、动态三个维度的元数据"""

    # Fallback model mapping (used when registry is not yet populated)
    _FALLBACK_MODELS = {
        "RoomType": RoomType,
        "Room": Room,
        "Guest": Guest,
        "Reservation": Reservation,
        "StayRecord": StayRecord,
        "Bill": Bill,
        "Task": Task,
        "Employee": Employee,
        "RatePlan": RatePlan,
        "Payment": Payment,
    }

    # Fallback descriptions (used when registry is not yet populated)
    _FALLBACK_DESCRIPTIONS = {
        "RoomType": "房型 - 定义房间类型和基础价格",
        "Room": "房间 - 酒店物理房间，数字孪生核心实体",
        "Guest": "客人 - 客户信息管理",
        "Reservation": "预订 - 预订阶段的聚合根",
        "StayRecord": "住宿记录 - 住宿期间的聚合根",
        "Bill": "账单 - 属于 StayRecord 的账单对象",
        "Task": "任务 - 清洁和维修任务管理",
        "Employee": "员工 - 系统用户",
        "RatePlan": "价格策略 - 动态定价管理",
        "Payment": "支付记录 - 账单支付记录",
    }

    # Fallback aggregate roots
    _FALLBACK_AGGREGATE_ROOTS = {"Reservation", "StayRecord"}

    # Fallback relationships
    _FALLBACK_RELATIONSHIPS = {
        "RoomType": ["Room", "RatePlan"],
        "Room": ["RoomType", "StayRecord", "Task"],
        "Guest": ["Reservation", "StayRecord"],
        "Reservation": ["Guest", "RoomType", "StayRecord"],
        "StayRecord": ["Guest", "Room", "Reservation", "Bill"],
        "Bill": ["StayRecord", "Payment"],
        "Task": ["Room", "Employee"],
        "Employee": ["Task"],
        "RatePlan": ["RoomType"],
        "Payment": ["Bill"],
    }

    @property
    def MODELS(self):
        """Get models from OntologyRegistry, falling back to hardcoded."""
        registry = OntologyRegistry()
        model_map = registry.get_model_map()
        if model_map:
            return model_map
        return self._FALLBACK_MODELS

    @property
    def ENTITY_DESCRIPTIONS(self):
        """Get entity descriptions from OntologyRegistry, falling back to hardcoded."""
        registry = OntologyRegistry()
        descriptions = {}
        for entity in registry.get_entities():
            descriptions[entity.name] = entity.description
        if descriptions:
            # Merge with fallbacks for entities not in registry
            merged = dict(self._FALLBACK_DESCRIPTIONS)
            merged.update(descriptions)
            return merged
        return self._FALLBACK_DESCRIPTIONS

    @property
    def AGGREGATE_ROOTS(self):
        """Get aggregate roots from OntologyRegistry, falling back to hardcoded."""
        registry = OntologyRegistry()
        roots = set()
        for entity in registry.get_entities():
            if entity.is_aggregate_root:
                roots.add(entity.name)
        if roots:
            return roots
        return self._FALLBACK_AGGREGATE_ROOTS

    @property
    def ENTITY_RELATIONSHIPS(self):
        """Get entity relationships from OntologyRegistry, falling back to hardcoded."""
        registry = OntologyRegistry()
        result = {}
        entities = registry.get_entities()
        if entities:
            for entity in entities:
                rels = registry.get_relationships(entity.name)
                result[entity.name] = list({r.target_entity for r in rels})
            # Merge with fallbacks for entities not in registry
            merged = dict(self._FALLBACK_RELATIONSHIPS)
            merged.update(result)
            return merged
        return self._FALLBACK_RELATIONSHIPS

    def __init__(self, db: Session = None):
        self.db = db

    # ============== 语义层 (Semantic) ==============

    def get_semantic_metadata(self) -> Dict[str, Any]:
        """
        获取语义层元数据 - 实体定义、属性、关系

        Returns:
            {
                "entities": [
                    {
                        "name": "Room",
                        "description": "...",
                        "table_name": "rooms",
                        "is_aggregate_root": false,
                        "attributes": [...],
                        "relationships": [...]
                    }
                ]
            }
        """
        entities = []

        for entity_name, model_class in self.MODELS.items():
            # 获取模型属性
            attributes = self._get_enriched_attributes(entity_name, model_class)

            # 获取关系
            relationships = self._get_enriched_relationships(entity_name)

            # Get enriched metadata from registry
            onto_registry = OntologyRegistry()
            entity_meta = onto_registry.get_entity(entity_name)

            entity_info = {
                "name": entity_name,
                "description": self.ENTITY_DESCRIPTIONS.get(entity_name, ""),
                "table_name": model_class.__tablename__,
                "is_aggregate_root": entity_name in self.AGGREGATE_ROOTS,
                "attributes": [self._serialize_attribute(attr) for attr in attributes],
                "relationships": relationships,
                "related_entities": self.ENTITY_RELATIONSHIPS.get(entity_name, []),
            }

            # Add enriched fields from registry
            if entity_meta:
                entity_info["category"] = getattr(entity_meta, "category", "")
                entity_info["implements"] = getattr(entity_meta, "implements", [])
                entity_info["lifecycle_states"] = getattr(entity_meta, "lifecycle_states", None)
                extensions = getattr(entity_meta, "extensions", {})
                if extensions:
                    entity_info["business_purpose"] = extensions.get("business_purpose", "")
                    entity_info["key_attributes"] = extensions.get("key_attributes", [])
                    entity_info["invariants"] = extensions.get("invariants", [])
            entities.append(entity_info)

        return {"entities": entities}

    def _get_enriched_attributes(self, entity_name: str, model_class) -> List[AttributeMetadata]:
        """获取增强的属性元数据"""
        attributes = get_model_attributes(model_class)

        # Try registry properties first
        onto_registry = OntologyRegistry()
        entity_meta = onto_registry.get_entity(entity_name)
        if entity_meta and entity_meta.properties:
            for attr in attributes:
                prop = entity_meta.properties.get(attr.name)
                if prop:
                    attr.description = prop.description or attr.description
                    attr.security_level = prop.security_level or "INTERNAL"
        else:
            # Fallback to hardcoded descriptions
            attr_descriptions = self._get_attribute_descriptions(entity_name)
            for attr in attributes:
                if attr.name in attr_descriptions:
                    attr.description = attr_descriptions[attr.name].get("description", attr.description)
                    attr.security_level = attr_descriptions[attr.name].get("security_level", "INTERNAL")

        return attributes

    def _get_attribute_descriptions(self, entity_name: str) -> Dict[str, Dict]:
        """获取属性描述"""
        descriptions = {
            "Room": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "room_number": {"description": "房间号", "security_level": "PUBLIC"},
                "floor": {"description": "楼层", "security_level": "PUBLIC"},
                "status": {"description": "房间状态", "security_level": "INTERNAL"},
                "room_type_id": {"description": "房型ID", "security_level": "INTERNAL"},
                "features": {"description": "特征描述（如海景）", "security_level": "INTERNAL"},
                "is_active": {"description": "是否启用", "security_level": "INTERNAL"},
            },
            "Guest": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "name": {"description": "姓名", "security_level": "INTERNAL"},
                "id_type": {"description": "证件类型", "security_level": "CONFIDENTIAL"},
                "id_number": {"description": "证件号码", "security_level": "RESTRICTED"},
                "phone": {"description": "手机号", "security_level": "CONFIDENTIAL"},
                "email": {"description": "邮箱", "security_level": "CONFIDENTIAL"},
                "tier": {"description": "客户等级", "security_level": "INTERNAL"},
                "total_stays": {"description": "累计入住次数", "security_level": "INTERNAL"},
                "total_amount": {"description": "累计消费金额", "security_level": "CONFIDENTIAL"},
                "is_blacklisted": {"description": "是否黑名单", "security_level": "INTERNAL"},
            },
            "Reservation": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "reservation_no": {"description": "预订号", "security_level": "PUBLIC"},
                "guest_id": {"description": "客人ID", "security_level": "INTERNAL"},
                "room_type_id": {"description": "房型ID", "security_level": "INTERNAL"},
                "status": {"description": "预订状态", "security_level": "INTERNAL"},
                "check_in_date": {"description": "入住日期", "security_level": "INTERNAL"},
                "check_out_date": {"description": "离店日期", "security_level": "INTERNAL"},
                "total_amount": {"description": "预估总价", "security_level": "CONFIDENTIAL"},
                "prepaid_amount": {"description": "预付金额", "security_level": "CONFIDENTIAL"},
            },
            "StayRecord": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "guest_id": {"description": "客人ID", "security_level": "INTERNAL"},
                "room_id": {"description": "房间ID", "security_level": "INTERNAL"},
                "reservation_id": {"description": "来源预订ID", "security_level": "INTERNAL"},
                "status": {"description": "住宿状态", "security_level": "INTERNAL"},
                "check_in_time": {"description": "实际入住时间", "security_level": "INTERNAL"},
                "check_out_time": {"description": "实际退房时间", "security_level": "INTERNAL"},
                "expected_check_out": {"description": "预计离店日期", "security_level": "INTERNAL"},
                "deposit_amount": {"description": "押金", "security_level": "CONFIDENTIAL"},
            },
            "Bill": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "stay_record_id": {"description": "住宿记录ID", "security_level": "INTERNAL"},
                "total_amount": {"description": "总金额", "security_level": "CONFIDENTIAL"},
                "paid_amount": {"description": "已付金额", "security_level": "CONFIDENTIAL"},
                "adjustment_amount": {"description": "调整金额", "security_level": "CONFIDENTIAL"},
                "is_settled": {"description": "是否结清", "security_level": "INTERNAL"},
            },
            "Task": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "room_id": {"description": "房间ID", "security_level": "INTERNAL"},
                "task_type": {"description": "任务类型", "security_level": "INTERNAL"},
                "status": {"description": "任务状态", "security_level": "INTERNAL"},
                "assignee_id": {"description": "执行人ID", "security_level": "INTERNAL"},
                "priority": {"description": "优先级", "security_level": "INTERNAL"},
            },
            "Employee": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "username": {"description": "登录账号", "security_level": "INTERNAL"},
                "password_hash": {"description": "密码哈希", "security_level": "RESTRICTED"},
                "name": {"description": "姓名", "security_level": "PUBLIC"},
                "phone": {"description": "手机号", "security_level": "CONFIDENTIAL"},
                "role": {"description": "角色", "security_level": "INTERNAL"},
                "is_active": {"description": "是否启用", "security_level": "INTERNAL"},
            },
            "RoomType": {
                "id": {"description": "主键", "security_level": "INTERNAL"},
                "name": {"description": "房型名称", "security_level": "PUBLIC"},
                "description": {"description": "描述", "security_level": "PUBLIC"},
                "base_price": {"description": "基础价格", "security_level": "INTERNAL"},
                "max_occupancy": {"description": "最大入住人数", "security_level": "PUBLIC"},
                "amenities": {"description": "设施列表", "security_level": "PUBLIC"},
            },
        }
        return descriptions.get(entity_name, {})

    def _serialize_attribute(self, attr: AttributeMetadata) -> Dict:
        """序列化属性元数据"""
        return {
            "name": attr.name,
            "type": attr.type,
            "python_type": attr.python_type,
            "is_primary_key": attr.is_primary_key,
            "is_foreign_key": attr.is_foreign_key,
            "is_required": attr.is_required,
            "is_nullable": attr.is_nullable,
            "is_unique": attr.is_unique,
            "default_value": str(attr.default_value) if attr.default_value is not None else None,
            "max_length": attr.max_length,
            "enum_values": attr.enum_values,
            "description": attr.description,
            "security_level": attr.security_level,
            "foreign_key_target": attr.foreign_key_target,
        }

    def _get_enriched_relationships(self, entity_name: str) -> List[Dict]:
        """获取增强的关系"""
        model_class = self.MODELS.get(entity_name)
        if not model_class:
            return []

        relationships = []

        # Try registry relationships for labels
        onto_registry = OntologyRegistry()
        registry_rels = onto_registry.get_relationships(entity_name)
        registry_labels = {}
        for r in registry_rels:
            if r.description:
                registry_labels[r.target_entity] = r.description

        # Fallback labels
        _fallback_labels = {
            "RoomType": {
                "Room": "包含多个房间",
                "RatePlan": "关联价格策略",
            },
            "Room": {
                "RoomType": "属于房型",
                "StayRecord": "住宿记录",
                "Task": "关联任务",
            },
            "Guest": {
                "Reservation": "拥有预订",
                "StayRecord": "住宿记录",
            },
            "Reservation": {
                "Guest": "预订人",
                "RoomType": "预订房型",
                "StayRecord": "产生住宿记录",
            },
            "StayRecord": {
                "Guest": "入住人",
                "Room": "入住房间",
                "Reservation": "来源预订",
                "Bill": "拥有账单",
            },
            "Bill": {
                "StayRecord": "属于住宿记录",
                "Payment": "包含支付记录",
            },
            "Task": {
                "Room": "目标房间",
                "Employee": "执行人",
            },
            "Employee": {
                "Task": "分配的任务",
            },
            "RatePlan": {
                "RoomType": "应用于房型",
            },
            "Payment": {
                "Bill": "支付账单",
            },
        }

        base_relationships = get_entity_relationships(model_class)
        fallback_rels = _fallback_labels.get(entity_name, {})

        for rel in base_relationships:
            # Registry labels take priority, then fallback
            rel["label"] = registry_labels.get(rel["target"], fallback_rels.get(rel["target"], rel["name"]))
            relationships.append(rel)

        return relationships

    # ============== 动力层 (Kinetic) ==============

    def get_kinetic_metadata(self) -> Dict[str, Any]:
        """
        获取动力层元数据 - 按实体分组的可执行操作

        Returns:
            {
                "entities": [
                    {
                        "name": "Room",
                        "description": "...",
                        "actions": [
                            {
                                "action_type": "update_status",
                                "description": "更新房间状态",
                                "params": [...],
                                "requires_confirmation": true,
                                "allowed_roles": [...],
                                "writeback": true,
                                "undoable": true
                            }
                        ]
                    }
                ]
            }
        """
        # 从 OntologyRegistry 获取已注册的动作
        onto_registry = OntologyRegistry()
        registered_actions = onto_registry.get_actions()

        # 预定义动作（当注册表为空时使用）
        predefined_actions = self._get_predefined_actions()

        # 合并注册表和预定义动作
        all_actions = {**predefined_actions}

        for action in registered_actions:
            if action.entity not in all_actions:
                all_actions[action.entity] = []
            all_actions[action.entity].append(self._serialize_action(action))

        # 构建响应
        entities = []
        for entity_name, entity_actions in all_actions.items():
            entities.append({
                "name": entity_name,
                "description": self.ENTITY_DESCRIPTIONS.get(entity_name, ""),
                "actions": entity_actions
            })

        return {"entities": entities}

    def _get_predefined_actions(self) -> Dict[str, List[Dict]]:
        """获取预定义的动作定义"""
        return {
            "Room": [
                {
                    "action_type": "create_room",
                    "description": "创建新房间",
                    "params": [
                        {"name": "room_number", "type": "string", "required": True, "description": "房间号"},
                        {"name": "floor", "type": "integer", "required": True, "description": "楼层"},
                        {"name": "room_type_id", "type": "integer", "required": True, "description": "房型ID"},
                        {"name": "features", "type": "string", "required": False, "description": "特征描述"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "update_room_status",
                    "description": "更新房间状态",
                    "params": [
                        {"name": "room_id", "type": "integer", "required": True, "description": "房间ID"},
                        {"name": "status", "type": "enum", "required": True, "description": "新状态",
                         "enum_values": ["vacant_clean", "occupied", "vacant_dirty", "out_of_order"]},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": True,
                },
                {
                    "action_type": "get_available_rooms",
                    "description": "查询可用房间",
                    "params": [
                        {"name": "check_in_date", "type": "date", "required": True, "description": "入住日期"},
                        {"name": "check_out_date", "type": "date", "required": True, "description": "离店日期"},
                        {"name": "room_type_id", "type": "integer", "required": False, "description": "房型ID"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist", "cleaner"],
                    "writeback": False,
                    "undoable": False,
                },
            ],
            "RoomType": [
                {
                    "action_type": "create_room_type",
                    "description": "创建房型",
                    "params": [
                        {"name": "name", "type": "string", "required": True, "description": "房型名称"},
                        {"name": "description", "type": "string", "required": False, "description": "描述"},
                        {"name": "base_price", "type": "number", "required": True, "description": "基础价格"},
                        {"name": "max_occupancy", "type": "integer", "required": False, "description": "最大入住人数"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "update_room_type",
                    "description": "更新房型",
                    "params": [
                        {"name": "room_type_id", "type": "integer", "required": True, "description": "房型ID"},
                        {"name": "name", "type": "string", "required": False, "description": "房型名称"},
                        {"name": "base_price", "type": "number", "required": False, "description": "基础价格"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "delete_room_type",
                    "description": "删除房型",
                    "params": [
                        {"name": "room_type_id", "type": "integer", "required": True, "description": "房型ID"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
            ],
            "Guest": [
                {
                    "action_type": "create_guest",
                    "description": "创建客人档案",
                    "params": [
                        {"name": "name", "type": "string", "required": True, "description": "姓名"},
                        {"name": "phone", "type": "string", "required": False, "description": "手机号"},
                        {"name": "id_type", "type": "string", "required": False, "description": "证件类型"},
                        {"name": "id_number", "type": "string", "required": False, "description": "证件号码"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "update_guest",
                    "description": "更新客人信息，包括联系方式、姓名、证件信息、客户等级、黑名单状态等",
                    "params": [
                        {"name": "guest_id", "type": "integer", "required": False, "description": "客人ID（与guest_name二选一）"},
                        {"name": "guest_name", "type": "string", "required": False, "description": "客人姓名（用于查找客人，与guest_id二选一）"},
                        {"name": "name", "type": "string", "required": False, "description": "新姓名"},
                        {"name": "phone", "type": "string", "required": False, "description": "新手机号"},
                        {"name": "email", "type": "string", "required": False, "description": "新邮箱"},
                        {"name": "id_type", "type": "string", "required": False, "description": "证件类型"},
                        {"name": "id_number", "type": "string", "required": False, "description": "证件号码"},
                        {"name": "tier", "type": "enum", "required": False, "description": "客户等级",
                         "enum_values": ["normal", "silver", "gold", "platinum"]},
                        {"name": "is_blacklisted", "type": "boolean", "required": False, "description": "是否黑名单"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
            ],
            "Reservation": [
                {
                    "action_type": "create_reservation",
                    "description": "创建预订",
                    "params": [
                        {"name": "guest_name", "type": "string", "required": True, "description": "客人姓名"},
                        {"name": "guest_phone", "type": "string", "required": True, "description": "客人手机"},
                        {"name": "room_type_id", "type": "integer", "required": True, "description": "房型ID"},
                        {"name": "check_in_date", "type": "date", "required": True, "description": "入住日期"},
                        {"name": "check_out_date", "type": "date", "required": True, "description": "离店日期"},
                        {"name": "adult_count", "type": "integer", "required": False, "description": "成人数"},
                        {"name": "child_count", "type": "integer", "required": False, "description": "儿童数"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "cancel_reservation",
                    "description": "取消预订",
                    "params": [
                        {"name": "reservation_id", "type": "integer", "required": True, "description": "预订ID"},
                        {"name": "cancel_reason", "type": "string", "required": True, "description": "取消原因"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
            ],
            "StayRecord": [
                {
                    "action_type": "checkin",
                    "description": "预订入住",
                    "params": [
                        {"name": "reservation_id", "type": "integer", "required": True, "description": "预订ID"},
                        {"name": "room_id", "type": "integer", "required": True, "description": "房间ID"},
                        {"name": "deposit_amount", "type": "number", "required": False, "description": "押金"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "walkin_checkin",
                    "description": "散客入住",
                    "params": [
                        {"name": "guest_name", "type": "string", "required": True, "description": "客人姓名"},
                        {"name": "guest_phone", "type": "string", "required": True, "description": "客人手机"},
                        {"name": "room_id", "type": "integer", "required": True, "description": "房间ID"},
                        {"name": "expected_check_out", "type": "date", "required": True, "description": "预计离店日期"},
                        {"name": "deposit_amount", "type": "number", "required": False, "description": "押金"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "extend_stay",
                    "description": "延长住宿",
                    "params": [
                        {"name": "stay_record_id", "type": "integer", "required": True, "description": "住宿记录ID"},
                        {"name": "new_check_out_date", "type": "date", "required": True, "description": "新的离店日期"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": True,
                },
                {
                    "action_type": "change_room",
                    "description": "换房",
                    "params": [
                        {"name": "stay_record_id", "type": "integer", "required": True, "description": "住宿记录ID"},
                        {"name": "new_room_id", "type": "integer", "required": True, "description": "新房间ID"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": True,
                },
                {
                    "action_type": "checkout",
                    "description": "退房",
                    "params": [
                        {"name": "stay_record_id", "type": "integer", "required": True, "description": "住宿记录ID"},
                        {"name": "refund_deposit", "type": "number", "required": False, "description": "退还押金"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": True,
                },
            ],
            "Bill": [
                {
                    "action_type": "add_payment",
                    "description": "添加支付",
                    "params": [
                        {"name": "bill_id", "type": "integer", "required": True, "description": "账单ID"},
                        {"name": "amount", "type": "number", "required": True, "description": "支付金额"},
                        {"name": "method", "type": "enum", "required": True, "description": "支付方式",
                         "enum_values": ["cash", "card"]},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": True,
                },
                {
                    "action_type": "adjust_bill",
                    "description": "调整账单",
                    "params": [
                        {"name": "bill_id", "type": "integer", "required": True, "description": "账单ID"},
                        {"name": "adjustment_amount", "type": "number", "required": True, "description": "调整金额"},
                        {"name": "reason", "type": "string", "required": True, "description": "调整原因"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": True,
                },
            ],
            "Task": [
                {
                    "action_type": "create_task",
                    "description": "创建任务",
                    "params": [
                        {"name": "room_id", "type": "integer", "required": True, "description": "房间ID"},
                        {"name": "task_type", "type": "enum", "required": True, "description": "任务类型",
                         "enum_values": ["cleaning", "maintenance"]},
                        {"name": "priority", "type": "integer", "required": False, "description": "优先级(1-5)"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "assign_task",
                    "description": "分配任务",
                    "params": [
                        {"name": "task_id", "type": "integer", "required": True, "description": "任务ID"},
                        {"name": "assignee_id", "type": "integer", "required": True, "description": "执行人ID"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "start_task",
                    "description": "开始任务",
                    "params": [
                        {"name": "task_id", "type": "integer", "required": True, "description": "任务ID"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager", "receptionist", "cleaner"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "complete_task",
                    "description": "完成任务",
                    "params": [
                        {"name": "task_id", "type": "integer", "required": True, "description": "任务ID"},
                    ],
                    "requires_confirmation": True,
                    "allowed_roles": ["manager", "receptionist", "cleaner"],
                    "writeback": True,
                    "undoable": True,
                },
            ],
            "Employee": [
                {
                    "action_type": "create_employee",
                    "description": "创建员工",
                    "params": [
                        {"name": "username", "type": "string", "required": True, "description": "登录账号"},
                        {"name": "password", "type": "string", "required": True, "description": "密码"},
                        {"name": "name", "type": "string", "required": True, "description": "姓名"},
                        {"name": "role", "type": "enum", "required": True, "description": "角色",
                         "enum_values": ["manager", "receptionist", "cleaner"]},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
                {
                    "action_type": "update_employee",
                    "description": "更新员工",
                    "params": [
                        {"name": "employee_id", "type": "integer", "required": True, "description": "员工ID"},
                        {"name": "role", "type": "enum", "required": False, "description": "角色",
                         "enum_values": ["manager", "receptionist", "cleaner"]},
                        {"name": "is_active", "type": "boolean", "required": False, "description": "是否启用"},
                    ],
                    "requires_confirmation": False,
                    "allowed_roles": ["manager"],
                    "writeback": True,
                    "undoable": False,
                },
            ],
        }

    def _serialize_action(self, action: ActionMetadata) -> Dict:
        """序列化动作元数据"""
        return {
            "action_type": action.action_type,
            "description": action.description,
            "params": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "required": p.required,
                    "description": p.description,
                    "enum_values": p.enum_values,
                    "format": p.format,
                }
                for p in action.params
            ],
            "requires_confirmation": action.requires_confirmation,
            "allowed_roles": list(action.allowed_roles),
            "writeback": action.writeback,
            "undoable": action.undoable,
        }

    # ============== 动态层 (Dynamic) ==============

    def get_dynamic_metadata(self) -> Dict[str, Any]:
        """
        获取动态层元数据 - 状态机、权限矩阵、业务规则

        Returns:
            {
                "state_machines": [...],
                "permission_matrix": {...},
                "business_rules": [...]
            }
        """
        return {
            "state_machines": self._get_state_machines(),
            "permission_matrix": self._get_permission_matrix(),
            "business_rules": self._get_business_rules(),
        }

    def _get_state_machines(self) -> List[Dict]:
        """获取状态机定义"""
        state_machines = [
            {
                "entity": "Room",
                "description": "房间状态机",
                "states": [
                    {"value": "vacant_clean", "label": "空闲已清洁", "color": "green"},
                    {"value": "occupied", "label": "入住中", "color": "red"},
                    {"value": "vacant_dirty", "label": "空闲待清洁", "color": "yellow"},
                    {"value": "out_of_order", "label": "维修中", "color": "gray"},
                ],
                "initial_state": "vacant_clean",
                "transitions": [
                    {
                        "from": "vacant_clean",
                        "to": "occupied",
                        "trigger": "check_in",
                        "trigger_action": "入住",
                        "condition": None,
                        "side_effects": [],
                    },
                    {
                        "from": "occupied",
                        "to": "vacant_dirty",
                        "trigger": "check_out",
                        "trigger_action": "退房",
                        "condition": None,
                        "side_effects": ["create_cleaning_task"],
                    },
                    {
                        "from": "vacant_dirty",
                        "to": "vacant_clean",
                        "trigger": "task_complete",
                        "trigger_action": "清洁任务完成",
                        "condition": "task_type == 'cleaning'",
                        "side_effects": [],
                    },
                    {
                        "from": "vacant_clean",
                        "to": "out_of_order",
                        "trigger": "mark_out_of_order",
                        "trigger_action": "标记维修",
                        "condition": None,
                        "side_effects": [],
                    },
                    {
                        "from": "out_of_order",
                        "to": "vacant_clean",
                        "trigger": "mark_available",
                        "trigger_action": "标记可用",
                        "condition": None,
                        "side_effects": [],
                    },
                ],
            },
            {
                "entity": "Reservation",
                "description": "预订状态机",
                "states": [
                    {"value": "confirmed", "label": "已确认", "color": "blue"},
                    {"value": "checked_in", "label": "已入住", "color": "green"},
                    {"value": "completed", "label": "已完成", "color": "gray"},
                    {"value": "cancelled", "label": "已取消", "color": "red"},
                    {"value": "no_show", "label": "未到店", "color": "orange"},
                ],
                "initial_state": "confirmed",
                "transitions": [
                    {
                        "from": "confirmed",
                        "to": "checked_in",
                        "trigger": "check_in",
                        "trigger_action": "办理入住",
                        "condition": None,
                        "side_effects": ["create_stay_record"],
                    },
                    {
                        "from": "confirmed",
                        "to": "cancelled",
                        "trigger": "cancel",
                        "trigger_action": "取消预订",
                        "condition": None,
                        "side_effects": [],
                    },
                    {
                        "from": "confirmed",
                        "to": "no_show",
                        "trigger": "mark_no_show",
                        "trigger_action": "标记未到店",
                        "condition": "check_in_date < today",
                        "side_effects": [],
                    },
                    {
                        "from": "checked_in",
                        "to": "completed",
                        "trigger": "check_out",
                        "trigger_action": "退房",
                        "condition": None,
                        "side_effects": [],
                    },
                ],
            },
            {
                "entity": "StayRecord",
                "description": "住宿记录状态机",
                "states": [
                    {"value": "active", "label": "在住", "color": "green"},
                    {"value": "checked_out", "label": "已退房", "color": "gray"},
                ],
                "initial_state": "active",
                "transitions": [
                    {
                        "from": "active",
                        "to": "checked_out",
                        "trigger": "check_out",
                        "trigger_action": "退房",
                        "condition": None,
                        "side_effects": ["update_room_status", "create_cleaning_task"],
                    },
                ],
            },
            {
                "entity": "Task",
                "description": "任务状态机",
                "states": [
                    {"value": "pending", "label": "待分配", "color": "gray"},
                    {"value": "assigned", "label": "已分配", "color": "blue"},
                    {"value": "in_progress", "label": "进行中", "color": "yellow"},
                    {"value": "completed", "label": "已完成", "color": "green"},
                ],
                "initial_state": "pending",
                "transitions": [
                    {
                        "from": "pending",
                        "to": "assigned",
                        "trigger": "assign",
                        "trigger_action": "分配任务",
                        "condition": "assignee_id is not null",
                        "side_effects": [],
                    },
                    {
                        "from": "assigned",
                        "to": "in_progress",
                        "trigger": "start",
                        "trigger_action": "开始任务",
                        "condition": None,
                        "side_effects": ["set_started_at"],
                    },
                    {
                        "from": "in_progress",
                        "to": "completed",
                        "trigger": "complete",
                        "trigger_action": "完成任务",
                        "condition": None,
                        "side_effects": ["set_completed_at", "update_room_status_if_cleaning"],
                    },
                    {
                        "from": "pending",
                        "to": "in_progress",
                        "trigger": "start",
                        "trigger_action": "直接开始",
                        "condition": "assignee_id is not null",
                        "side_effects": ["set_started_at"],
                    },
                ],
            },
        ]

        # 合并 OntologyRegistry 中的状态机
        onto_registry = OntologyRegistry()
        for entity_name in ["Room", "Reservation", "StayRecord", "Task"]:
            registered_sm = onto_registry.get_state_machine(entity_name)
            if registered_sm:
                # 如果有注册的状态机，替换预定义的
                for i, sm in enumerate(state_machines):
                    if sm["entity"] == entity_name:
                        state_machines[i] = self._serialize_state_machine(registered_sm)
                        break
                else:
                    state_machines.append(self._serialize_state_machine(registered_sm))

        return state_machines

    # State presentation mapping: value → {label, color}
    STATE_PRESENTATION = {
        # Room states
        "vacant_clean": {"label": "空闲已清洁", "color": "green"},
        "occupied": {"label": "入住中", "color": "red"},
        "vacant_dirty": {"label": "空闲待清洁", "color": "yellow"},
        "out_of_order": {"label": "维修中", "color": "gray"},
        # Reservation states
        "confirmed": {"label": "已确认", "color": "blue"},
        "checked_in": {"label": "已入住", "color": "green"},
        "completed": {"label": "已完成", "color": "gray"},
        "cancelled": {"label": "已取消", "color": "red"},
        "no_show": {"label": "未到店", "color": "orange"},
        # StayRecord states
        "active": {"label": "在住", "color": "green"},
        "checked_out": {"label": "已退房", "color": "gray"},
        # Task states
        "pending": {"label": "待分配", "color": "gray"},
        "assigned": {"label": "已分配", "color": "blue"},
        "in_progress": {"label": "进行中", "color": "yellow"},
        # "completed" already defined above
    }

    # Trigger action display names
    TRIGGER_ACTIONS = {
        "check_in": "入住",
        "check_out": "退房",
        "task_complete": "清洁任务完成",
        "mark_out_of_order": "标记维修",
        "mark_available": "标记可用",
        "cancel": "取消预订",
        "mark_no_show": "标记未到店",
        "assign": "分配任务",
        "start": "开始任务",
        "complete": "完成任务",
    }

    def _serialize_state_machine(self, sm) -> Dict:
        """序列化状态机，输出 {value, label, color} 格式的 states"""
        states = []
        for s in sm.states:
            pres = self.STATE_PRESENTATION.get(s, {})
            states.append({
                "value": s,
                "label": pres.get("label", s),
                "color": pres.get("color", "gray"),
            })

        transitions = []
        for t in sm.transitions:
            transitions.append({
                "from": t.from_state,
                "to": t.to_state,
                "trigger": t.trigger,
                "trigger_action": self.TRIGGER_ACTIONS.get(t.trigger, t.trigger),
                "condition": t.condition,
                "side_effects": t.side_effects,
            })

        return {
            "entity": sm.entity,
            "description": f"{sm.entity}状态机",
            "states": states,
            "initial_state": sm.initial_state,
            "transitions": transitions,
        }

    def _get_permission_matrix(self) -> Dict:
        """
        获取权限矩阵

        Returns:
            {
                "roles": ["manager", "receptionist", "cleaner"],
                "actions": [
                    {"action_type": "update_room_status", "roles": ["manager", "receptionist"]},
                    ...
                ]
            }
        """
        roles = ["manager", "receptionist", "cleaner"]

        # 从 OntologyRegistry 获取权限
        onto_registry = OntologyRegistry()
        registered_permissions = onto_registry.get_permissions()

        # 预定义权限
        action_permissions = [
            # Room actions
            {"action_type": "create_room", "entity": "Room", "roles": ["manager"]},
            {"action_type": "update_room", "entity": "Room", "roles": ["manager"]},
            {"action_type": "update_room_status", "entity": "Room", "roles": ["manager", "receptionist"]},
            {"action_type": "delete_room", "entity": "Room", "roles": ["manager"]},
            # RoomType actions
            {"action_type": "create_room_type", "entity": "RoomType", "roles": ["manager"]},
            {"action_type": "update_room_type", "entity": "RoomType", "roles": ["manager"]},
            {"action_type": "delete_room_type", "entity": "RoomType", "roles": ["manager"]},
            # Guest actions
            {"action_type": "create_guest", "entity": "Guest", "roles": ["manager", "receptionist"]},
            {"action_type": "update_guest", "entity": "Guest", "roles": ["manager", "receptionist"]},
            {"action_type": "blacklist_guest", "entity": "Guest", "roles": ["manager"]},
            # Reservation actions
            {"action_type": "create_reservation", "entity": "Reservation", "roles": ["manager", "receptionist"]},
            {"action_type": "update_reservation", "entity": "Reservation", "roles": ["manager", "receptionist"]},
            {"action_type": "cancel_reservation", "entity": "Reservation", "roles": ["manager", "receptionist"]},
            # StayRecord actions
            {"action_type": "checkin", "entity": "StayRecord", "roles": ["manager", "receptionist"]},
            {"action_type": "walkin_checkin", "entity": "StayRecord", "roles": ["manager", "receptionist"]},
            {"action_type": "checkout", "entity": "StayRecord", "roles": ["manager", "receptionist"]},
            {"action_type": "extend_stay", "entity": "StayRecord", "roles": ["manager", "receptionist"]},
            {"action_type": "change_room", "entity": "StayRecord", "roles": ["manager", "receptionist"]},
            # Bill actions
            {"action_type": "add_payment", "entity": "Bill", "roles": ["manager", "receptionist"]},
            {"action_type": "adjust_bill", "entity": "Bill", "roles": ["manager"]},
            # Task actions
            {"action_type": "create_task", "entity": "Task", "roles": ["manager", "receptionist"]},
            {"action_type": "assign_task", "entity": "Task", "roles": ["manager", "receptionist"]},
            {"action_type": "start_task", "entity": "Task", "roles": ["manager", "receptionist", "cleaner"]},
            {"action_type": "complete_task", "entity": "Task", "roles": ["manager", "receptionist", "cleaner"]},
            # Employee actions
            {"action_type": "create_employee", "entity": "Employee", "roles": ["manager"]},
            {"action_type": "update_employee", "entity": "Employee", "roles": ["manager"]},
            {"action_type": "delete_employee", "entity": "Employee", "roles": ["manager"]},
        ]

        return {
            "roles": roles,
            "actions": action_permissions,
        }

    def _get_business_rules(self) -> List[Dict]:
        """
        获取业务规则

        Returns:
            [
                {
                    "rule_id": "...",
                    "entity": "...",
                    "rule_name": "...",
                    "description": "...",
                    "condition": "...",
                    "action": "...",
                    "severity": "error"
                },
                ...
            ]
        """
        business_rules = [
            {
                "rule_id": "room_occupied_no_manual_change",
                "entity": "Room",
                "rule_name": "入住中房间禁止手动改状态",
                "description": "当房间状态为入住中时，不能手动更改状态，必须通过退房操作",
                "condition": "room.status == 'occupied'",
                "action": "raise ValueError('入住中的房间不能手动更改状态，请通过退房操作')",
                "severity": "error",
            },
            {
                "rule_id": "room_type_has_rooms_no_delete",
                "entity": "RoomType",
                "rule_name": "有房间的房型不能删除",
                "description": "如果房型下有关联的房间，则不能删除该房型",
                "condition": "room_type.rooms.count() > 0",
                "action": "raise ValueError('该房型下有房间，无法删除')",
                "severity": "error",
            },
            {
                "rule_id": "checkout_must_settle_bill",
                "entity": "Bill",
                "rule_name": "退房前必须结清账单",
                "description": "退房时账单必须已结清，除非允许未结清退房",
                "condition": "not bill.is_settled and not allow_unsettled",
                "action": "raise ValueError('账单未结清，请先结清账单')",
                "severity": "error",
            },
            {
                "rule_id": "only_active_employee_can_assign_task",
                "entity": "Employee",
                "rule_name": "只有激活员工才能分配任务",
                "description": "只有 is_active=True 的员工才能被分配任务",
                "condition": "not employee.is_active",
                "action": "raise ValueError('该员工已停用，无法分配任务')",
                "severity": "error",
            },
            {
                "rule_id": "guest_tier_auto_upgrade",
                "entity": "Guest",
                "rule_name": "客人等级自动升级",
                "description": "当客人累计消费金额达到阈值时，自动升级客户等级",
                "condition": "guest.total_amount >= 10000 and guest.tier == 'normal'",
                "action": "guest.tier = 'silver'",
                "severity": "info",
            },
            {
                "rule_id": "checkout_creates_cleaning_task",
                "entity": "Task",
                "rule_name": "退房自动创建清洁任务",
                "description": "客人退房后，自动为该房间创建清洁任务",
                "condition": "event == 'guest_checked_out'",
                "action": "create_cleaning_task(room_id)",
                "severity": "info",
            },
            {
                "rule_id": "cleaning_task_complete_updates_room",
                "entity": "Room",
                "rule_name": "清洁任务完成更新房间状态",
                "description": "清洁任务完成后，房间状态自动变为空闲已清洁",
                "condition": "task.type == 'cleaning' and task.status == 'completed'",
                "action": "room.status = 'vacant_clean'",
                "severity": "info",
            },
            {
                "rule_id": "stay_active_requires_vacant_room",
                "entity": "StayRecord",
                "rule_name": "入住需要空闲房间",
                "description": "办理入住时，房间必须处于空闲状态",
                "condition": "room.status not in ['vacant_clean', 'vacant_dirty']",
                "action": "raise ValueError('房间状态不是空闲，无法入住')",
                "severity": "error",
            },
            {
                "rule_id": "bill_adjustment_manager_only",
                "entity": "Bill",
                "rule_name": "账单调整仅限经理",
                "description": "只有经理角色可以调整账单金额",
                "condition": "employee.role != 'manager'",
                "action": "raise PermissionError('只有经理可以调整账单')",
                "severity": "error",
            },
            {
                "rule_id": "task_complete_only_by_assignee",
                "entity": "Task",
                "rule_name": "任务只能由执行人完成",
                "description": "任务只能被分配给该任务的员工或经理完成",
                "condition": "employee.id != task.assignee_id and employee.role != 'manager'",
                "action": "raise PermissionError('只有任务执行人或经理可以完成任务')",
                "severity": "error",
            },
        ]

        # 合并 OntologyRegistry 中的业务规则
        onto_registry = OntologyRegistry()
        for entity_name in ["Room", "Guest", "Bill", "Task", "StayRecord"]:
            registered_rules = onto_registry.get_business_rules(entity_name)
            for rule in registered_rules:
                business_rules.append({
                    "rule_id": rule.rule_id,
                    "entity": rule.entity,
                    "rule_name": rule.rule_name,
                    "description": rule.description,
                    "condition": rule.condition,
                    "action": rule.action,
                    "severity": rule.severity,
                })

        return business_rules

    def get_events(self) -> List[Dict]:
        """获取所有已注册的领域事件"""
        onto_registry = OntologyRegistry()
        events = onto_registry.get_events()
        return [
            {
                "name": e.name,
                "description": e.description,
                "entity": e.entity,
                "triggered_by": e.triggered_by,
                "payload_fields": e.payload_fields,
                "subscribers": e.subscribers,
            }
            for e in events
        ]
