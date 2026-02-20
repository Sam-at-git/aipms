"""
本体关系可视化路由
提供本体结构定义、实体统计和关系图数据
支持三个维度：语义(Semantic)、动力(Kinetic)、动态(Dynamic)
"""
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import (
    Room, Guest, Reservation, StayRecord, Task, Employee, RoomType, Bill,
    RoomStatus, ReservationStatus, StayRecordStatus, TaskStatus, EmployeeRole, GuestTier
)
from app.security.auth import get_current_user, require_permission
from app.security.permissions import ONTOLOGY_READ
from app.services.ontology_metadata_service import OntologyMetadataService
from core.ontology.registry import OntologyRegistry

router = APIRouter(prefix="/ontology", tags=["本体视图"])


@router.get("/schema")
async def get_ontology_schema(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取本体结构定义"""
    onto_registry = OntologyRegistry()
    entities = onto_registry.get_entities()

    if not entities:
        # Fallback if registry not populated
        return {"entities": [], "relationships": []}

    # Build entities list from registry
    entity_list = []
    for entity in entities:
        attrs = []
        for prop_name, prop in entity.properties.items():
            attr = {"name": prop_name, "type": prop.type}
            if prop.is_primary_key:
                attr["primary"] = True
            if prop.enum_values:
                attr["type"] = "enum"
                attr["values"] = prop.enum_values
            attrs.append(attr)
        entity_list.append({
            "name": entity.name,
            "description": entity.description,
            "category": entity.category or "business",
            "attributes": attrs,
        })

    # Build relationships from registry
    rel_list = []
    for entity in entities:
        rels = onto_registry.get_relationships(entity.name)
        for rel in rels:
            if rel.cardinality in ("many_to_one", "one_to_one"):
                rel_list.append({
                    "from": entity.name,
                    "to": rel.target_entity,
                    "type": "belongs_to",
                    "label": rel.description or rel.name,
                })

    return {"entities": entity_list, "relationships": rel_list}


@router.get("/statistics")
async def get_ontology_statistics(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取各实体的统计数据"""
    onto_registry = OntologyRegistry()
    result = {}

    # Generic total counts from registry model map
    model_map = onto_registry.get_model_map()
    for entity_name, model_cls in model_map.items():
        result[entity_name] = {"total": db.query(model_cls).count()}

    # Entity-specific breakdowns (presentation layer knowledge)
    if "Room" in result:
        result["Room"]["by_status"] = {
            s.value: db.query(Room).filter(Room.status == s).count()
            for s in RoomStatus
        }
    if "Guest" in result:
        result["Guest"]["by_tier"] = {
            t.value: db.query(Guest).filter(Guest.tier == t.value).count()
            for t in GuestTier
        }
    if "Reservation" in result:
        result["Reservation"]["by_status"] = {
            s.value: db.query(Reservation).filter(Reservation.status == s).count()
            for s in ReservationStatus
        }
    if "StayRecord" in result:
        result["StayRecord"]["active"] = db.query(StayRecord).filter(
            StayRecord.status == StayRecordStatus.ACTIVE
        ).count()
    if "Bill" in result:
        result["Bill"]["settled"] = db.query(Bill).filter(Bill.is_settled == True).count()
        result["Bill"]["unsettled"] = db.query(Bill).filter(Bill.is_settled == False).count()
    if "Task" in result:
        result["Task"]["by_status"] = {
            s.value: db.query(Task).filter(Task.status == s).count()
            for s in TaskStatus
        }
    if "Employee" in result:
        result["Employee"]["by_role"] = {
            r.value: db.query(Employee).filter(Employee.role == r).count()
            for r in EmployeeRole
        }

    return {"entities": result}


@router.get("/instance-graph")
async def get_instance_graph(
    center_entity: Optional[str] = Query(None, description="中心实体类型"),
    center_id: Optional[int] = Query(None, description="中心实体ID"),
    depth: int = Query(2, ge=1, le=3, description="关系深度"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取以指定实体为中心的关系图数据"""
    nodes = []
    edges = []

    if center_entity and center_id:
        # 从指定实体出发，获取关联数据
        if center_entity == "StayRecord":
            stay_record = db.query(StayRecord).filter(StayRecord.id == center_id).first()
            if stay_record:
                # 中心节点
                nodes.append({
                    "id": f"StayRecord-{stay_record.id}",
                    "type": "StayRecord",
                    "label": f"住宿记录 #{stay_record.id}",
                    "data": {
                        "status": stay_record.status.value if stay_record.status else None,
                        "check_in_time": str(stay_record.check_in_time) if stay_record.check_in_time else None
                    }
                })

                # 关联的Guest
                if stay_record.guest:
                    nodes.append({
                        "id": f"Guest-{stay_record.guest.id}",
                        "type": "Guest",
                        "label": stay_record.guest.name,
                        "data": {"tier": stay_record.guest.tier}
                    })
                    edges.append({
                        "source": f"StayRecord-{stay_record.id}",
                        "target": f"Guest-{stay_record.guest.id}",
                        "label": "入住人"
                    })

                # 关联的Room
                if stay_record.room:
                    nodes.append({
                        "id": f"Room-{stay_record.room.id}",
                        "type": "Room",
                        "label": f"房间 {stay_record.room.room_number}",
                        "data": {"status": stay_record.room.status.value if stay_record.room.status else None}
                    })
                    edges.append({
                        "source": f"StayRecord-{stay_record.id}",
                        "target": f"Room-{stay_record.room.id}",
                        "label": "入住房间"
                    })

                    # Room的RoomType
                    if stay_record.room.room_type:
                        nodes.append({
                            "id": f"RoomType-{stay_record.room.room_type.id}",
                            "type": "RoomType",
                            "label": stay_record.room.room_type.name,
                            "data": {"base_price": float(stay_record.room.room_type.base_price)}
                        })
                        edges.append({
                            "source": f"Room-{stay_record.room.id}",
                            "target": f"RoomType-{stay_record.room.room_type.id}",
                            "label": "房型"
                        })

                # 关联的Bill
                if stay_record.bill:
                    nodes.append({
                        "id": f"Bill-{stay_record.bill.id}",
                        "type": "Bill",
                        "label": f"账单 #{stay_record.bill.id}",
                        "data": {
                            "total_amount": float(stay_record.bill.total_amount) if stay_record.bill.total_amount else 0,
                            "is_settled": stay_record.bill.is_settled
                        }
                    })
                    edges.append({
                        "source": f"StayRecord-{stay_record.id}",
                        "target": f"Bill-{stay_record.bill.id}",
                        "label": "账单"
                    })

                # 关联的Reservation
                if stay_record.reservation:
                    nodes.append({
                        "id": f"Reservation-{stay_record.reservation.id}",
                        "type": "Reservation",
                        "label": f"预订 {stay_record.reservation.reservation_no}",
                        "data": {"status": stay_record.reservation.status.value if stay_record.reservation.status else None}
                    })
                    edges.append({
                        "source": f"StayRecord-{stay_record.id}",
                        "target": f"Reservation-{stay_record.reservation.id}",
                        "label": "来源预订"
                    })

        elif center_entity == "Room":
            room = db.query(Room).filter(Room.id == center_id).first()
            if room:
                nodes.append({
                    "id": f"Room-{room.id}",
                    "type": "Room",
                    "label": f"房间 {room.room_number}",
                    "data": {"status": room.status.value if room.status else None, "floor": room.floor}
                })

                # RoomType
                if room.room_type:
                    nodes.append({
                        "id": f"RoomType-{room.room_type.id}",
                        "type": "RoomType",
                        "label": room.room_type.name,
                        "data": {"base_price": float(room.room_type.base_price)}
                    })
                    edges.append({
                        "source": f"Room-{room.id}",
                        "target": f"RoomType-{room.room_type.id}",
                        "label": "房型"
                    })

                # Active StayRecords
                active_stays = [sr for sr in room.stay_records if sr.status == StayRecordStatus.ACTIVE]
                for stay in active_stays[:3]:  # 限制数量
                    nodes.append({
                        "id": f"StayRecord-{stay.id}",
                        "type": "StayRecord",
                        "label": f"住宿 #{stay.id}",
                        "data": {"status": stay.status.value if stay.status else None}
                    })
                    edges.append({
                        "source": f"Room-{room.id}",
                        "target": f"StayRecord-{stay.id}",
                        "label": "当前住宿"
                    })

                # Tasks
                pending_tasks = [t for t in room.tasks if t.status != TaskStatus.COMPLETED]
                for task in pending_tasks[:3]:
                    nodes.append({
                        "id": f"Task-{task.id}",
                        "type": "Task",
                        "label": f"任务 #{task.id}",
                        "data": {"type": task.task_type.value if task.task_type else None, "status": task.status.value if task.status else None}
                    })
                    edges.append({
                        "source": f"Room-{room.id}",
                        "target": f"Task-{task.id}",
                        "label": "任务"
                    })

        elif center_entity == "Guest":
            guest = db.query(Guest).filter(Guest.id == center_id).first()
            if guest:
                nodes.append({
                    "id": f"Guest-{guest.id}",
                    "type": "Guest",
                    "label": guest.name,
                    "data": {"tier": guest.tier, "phone": guest.phone}
                })

                # Reservations
                for res in guest.reservations[:5]:
                    nodes.append({
                        "id": f"Reservation-{res.id}",
                        "type": "Reservation",
                        "label": f"预订 {res.reservation_no}",
                        "data": {"status": res.status.value if res.status else None}
                    })
                    edges.append({
                        "source": f"Guest-{guest.id}",
                        "target": f"Reservation-{res.id}",
                        "label": "预订"
                    })

                # StayRecords
                for stay in guest.stay_records[:5]:
                    nodes.append({
                        "id": f"StayRecord-{stay.id}",
                        "type": "StayRecord",
                        "label": f"住宿 #{stay.id}",
                        "data": {"status": stay.status.value if stay.status else None}
                    })
                    edges.append({
                        "source": f"Guest-{guest.id}",
                        "target": f"StayRecord-{stay.id}",
                        "label": "住宿记录"
                    })
    else:
        # 返回系统概览图（各实体类型作为节点）
        onto_registry = OntologyRegistry()
        model_map = onto_registry.get_model_map()

        # Default positions for known entities (presentation concern)
        entity_positions = {
            "RoomType": (200, 100),
            "Room": (400, 100),
            "Guest": (100, 300),
            "Reservation": (300, 300),
            "StayRecord": (500, 300),
            "Bill": (700, 300),
            "Task": (600, 100),
            "Employee": (800, 100),
            "RatePlan": (200, 200),
            "Payment": (700, 200),
        }

        # Build nodes from registry entities
        for entity in onto_registry.get_entities():
            name = entity.name
            model_cls = model_map.get(name)
            total = db.query(model_cls).count() if model_cls else 0
            pos = entity_positions.get(name, (500, 200))
            nodes.append({
                "id": name,
                "type": "entity",
                "label": entity.description.split(" - ")[0] if " - " in entity.description else entity.description,
                "data": {
                    "name": name,
                    "total": total,
                },
                "position": {"x": pos[0], "y": pos[1]},
            })

        # Build edges from registry relationships (belongs_to only)
        edge_i = 0
        for entity in onto_registry.get_entities():
            for rel in onto_registry.get_relationships(entity.name):
                if rel.cardinality in ("many_to_one", "one_to_one"):
                    edges.append({
                        "id": f"edge-{edge_i}",
                        "source": entity.name,
                        "target": rel.target_entity,
                        "label": rel.description or rel.name,
                    })
                    edge_i += 1

    return {"nodes": nodes, "edges": edges}


# ============== 语义层 (Semantic) - 实体属性和关系 ==============

@router.get("/semantic")
async def get_semantic_metadata(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """
    获取语义层元数据
    展示所有实体的属性定义、类型、约束等详细信息
    """
    service = OntologyMetadataService()
    return service.get_semantic_metadata()


@router.get("/semantic/{entity_name}")
async def get_entity_semantic(
    entity_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取单个实体的语义元数据"""
    service = OntologyMetadataService()
    all_semantic = service.get_semantic_metadata()

    for entity in all_semantic["entities"]:
        if entity["name"] == entity_name:
            return entity

    return {"error": "Entity not found"}


# ============== 动力层 (Kinetic) - 可执行操作 ==============

@router.get("/kinetic")
async def get_kinetic_metadata(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """
    获取动力层元数据
    按实体分组展示所有可执行的操作（Actions）
    """
    service = OntologyMetadataService()
    return service.get_kinetic_metadata()


@router.get("/kinetic/{entity_name}")
async def get_entity_kinetic(
    entity_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取单个实体的动力元数据（可执行操作）"""
    service = OntologyMetadataService()
    all_kinetic = service.get_kinetic_metadata()

    for entity in all_kinetic["entities"]:
        if entity["name"] == entity_name:
            return entity

    return {"error": "Entity not found"}


# ============== 动态层 (Dynamic) - 状态机、权限、业务规则 ==============

@router.get("/dynamic")
async def get_dynamic_metadata(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """
    获取动态层元数据
    包含状态机、权限矩阵、业务规则
    """
    service = OntologyMetadataService()
    return service.get_dynamic_metadata()


@router.get("/dynamic/state-machines")
async def get_state_machines(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取所有状态机定义"""
    service = OntologyMetadataService()
    dynamic = service.get_dynamic_metadata()
    return dynamic["state_machines"]


@router.get("/dynamic/state-machines/{entity_name}")
async def get_entity_state_machine(
    entity_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取单个实体的状态机定义"""
    service = OntologyMetadataService()
    state_machines = service._get_state_machines()

    for sm in state_machines:
        if sm["entity"] == entity_name:
            return sm

    return {"error": "State machine not found"}


@router.get("/dynamic/permission-matrix")
async def get_permission_matrix(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取权限矩阵"""
    service = OntologyMetadataService()
    dynamic = service.get_dynamic_metadata()
    return dynamic["permission_matrix"]


@router.get("/dynamic/events")
async def get_events(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取所有已注册的领域事件"""
    service = OntologyMetadataService()
    return {"events": service.get_events()}


@router.get("/dynamic/business-rules")
async def get_business_rules(
    entity: Optional[str] = Query(None, description="筛选实体"),
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取业务规则列表"""
    service = OntologyMetadataService()
    rules = service._get_business_rules()

    if entity:
        rules = [r for r in rules if r["entity"] == entity]

    return {"rules": rules}


# ============== SPEC-6: Reasoning Transparency APIs ==============

@router.get("/dynamic/state-transitions/{entity_name}")
async def get_state_transitions(
    entity_name: str,
    current_state: Optional[str] = Query(None, description="当前状态"),
    current_user: Employee = Depends(get_current_user)
):
    """获取实体的有效状态转换列表

    给定实体和当前状态，返回可达的下一状态及所需角色。
    如果不指定 current_state，返回所有状态的转换。
    """
    from core.ontology.registry import registry
    state_machine = registry.get_state_machine(entity_name)
    if not state_machine:
        return {"entity": entity_name, "transitions": [], "error": "No state machine registered"}

    transitions = []
    for t in state_machine.transitions:
        if current_state and t.from_state.lower() != current_state.lower():
            continue
        transition_info = {
            "from_state": t.from_state,
            "to_state": t.to_state,
            "trigger": t.trigger,
        }
        if hasattr(t, "condition") and t.condition:
            transition_info["condition"] = t.condition
        if hasattr(t, "side_effects") and t.side_effects:
            transition_info["side_effects"] = t.side_effects
        transitions.append(transition_info)

    return {
        "entity": entity_name,
        "current_state": current_state,
        "transitions": transitions,
    }


@router.post("/dynamic/constraints/validate")
async def validate_constraints(
    body: dict,
    current_user: Employee = Depends(get_current_user)
):
    """校验操作约束

    给定 action_type 和 entity_type，检查该操作的所有注册约束。
    可选提供 params 和 entity_state 来评估可执行约束。

    Request body:
    {
        "entity_type": "Room",
        "action_type": "checkin",
        "params": {},
        "entity_state": {}
    }
    """
    from core.ontology.registry import registry

    entity_type = body.get("entity_type", "")
    action_type = body.get("action_type", "")
    params = body.get("params", {})
    entity_state = body.get("entity_state", {})

    # Get registered constraints
    constraints = registry.get_constraints_for_entity_action(entity_type, action_type)

    constraint_list = []
    for c in constraints:
        info = {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
            "has_executable_code": bool(c.condition_code) if hasattr(c, "condition_code") else False,
        }
        constraint_list.append(info)

    # If we have a GuardExecutor and entity_state, run evaluation
    violations = []
    warnings = []
    try:
        from core.ontology.guard_executor import GuardExecutor
        guard = GuardExecutor(ontology_registry=registry)
        result = guard.check(entity_type, action_type, params, {
            "entity_state": entity_state,
            "user_context": {"role": current_user.role.value},
        })
        for v in result.violations:
            violations.append({
                "constraint_id": v.constraint_id,
                "message": v.message,
                "severity": v.severity,
            })
        for w in result.warnings:
            warnings.append({
                "constraint_id": w.constraint_id,
                "message": w.message,
                "severity": w.severity,
            })
    except Exception:
        pass  # GuardExecutor evaluation is optional

    return {
        "entity_type": entity_type,
        "action_type": action_type,
        "constraints": constraint_list,
        "violations": violations,
        "warnings": warnings,
    }


# ============== 接口系统 (Interfaces) - Phase 2.5 ==============

@router.get("/interfaces")
async def get_interfaces(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取所有接口定义及其实现关系"""
    from core.ontology.registry import registry
    schema = registry.export_schema()
    return schema.get("interfaces", {})


@router.get("/interfaces/{interface_name}")
async def get_interface(
    interface_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取单个接口详情"""
    from core.ontology.registry import registry
    schema = registry.export_schema()
    interfaces = schema.get("interfaces", {})
    return interfaces.get(interface_name, {"error": "Interface not found"})


@router.get("/interfaces/{interface_name}/implementations")
async def get_interface_implementations(
    interface_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取实现指定接口的所有实体"""
    from core.ontology.registry import registry
    implementations = registry.get_implementations(interface_name)
    return {"interface": interface_name, "implementations": implementations}


@router.get("/entities/{entity_name}/interfaces")
async def get_entity_interfaces(
    entity_name: str,
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """获取实体实现的所有接口"""
    from core.ontology.registry import registry
    schema = registry.export_schema()
    entity = schema.get("entity_types", {}).get(entity_name, {})
    return {
        "entity": entity_name,
        "interfaces": entity.get("interfaces", [])
    }


# ============== Schema 导出 (Schema Export) - Phase 2.5 ==============

@router.get("/schema/export")
async def export_schema(
    current_user: Employee = Depends(require_permission(ONTOLOGY_READ))
):
    """
    导出完整本体 schema (JSON)
    用于版本快照、AI 上下文注入、API 文档生成
    """
    from core.ontology.registry import registry
    return registry.export_schema()
