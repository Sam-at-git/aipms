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
from app.security.auth import get_current_user, require_manager
from app.services.ontology_metadata_service import OntologyMetadataService

router = APIRouter(prefix="/ontology", tags=["本体视图"])


@router.get("/schema")
async def get_ontology_schema(
    current_user: Employee = Depends(require_manager)
):
    """获取本体结构定义"""
    return {
        "entities": [
            {
                "name": "RoomType",
                "description": "房间类型",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "name", "type": "string"},
                    {"name": "base_price", "type": "decimal"},
                    {"name": "max_occupancy", "type": "integer"}
                ]
            },
            {
                "name": "Room",
                "description": "房间",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "room_number", "type": "string"},
                    {"name": "floor", "type": "integer"},
                    {"name": "status", "type": "enum", "values": ["vacant_clean", "occupied", "vacant_dirty", "out_of_order"]}
                ]
            },
            {
                "name": "Guest",
                "description": "客人",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "name", "type": "string"},
                    {"name": "phone", "type": "string"},
                    {"name": "id_type", "type": "string"},
                    {"name": "id_number", "type": "string"},
                    {"name": "tier", "type": "enum", "values": ["normal", "silver", "gold", "platinum"]}
                ]
            },
            {
                "name": "Reservation",
                "description": "预订",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "status", "type": "enum", "values": ["confirmed", "checked_in", "completed", "cancelled", "no_show"]},
                    {"name": "check_in_date", "type": "date"},
                    {"name": "check_out_date", "type": "date"},
                    {"name": "total_amount", "type": "decimal"}
                ]
            },
            {
                "name": "StayRecord",
                "description": "住宿记录",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "status", "type": "enum", "values": ["active", "checked_out"]},
                    {"name": "check_in_time", "type": "datetime"},
                    {"name": "expected_check_out", "type": "datetime"},
                    {"name": "check_out_time", "type": "datetime"}
                ]
            },
            {
                "name": "Bill",
                "description": "账单",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "total_amount", "type": "decimal"},
                    {"name": "paid_amount", "type": "decimal"},
                    {"name": "is_settled", "type": "boolean"}
                ]
            },
            {
                "name": "Task",
                "description": "任务",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "task_type", "type": "enum", "values": ["cleaning", "maintenance"]},
                    {"name": "status", "type": "enum", "values": ["pending", "assigned", "in_progress", "completed"]},
                    {"name": "priority", "type": "integer"}
                ]
            },
            {
                "name": "Employee",
                "description": "员工",
                "attributes": [
                    {"name": "id", "type": "integer", "primary": True},
                    {"name": "name", "type": "string"},
                    {"name": "username", "type": "string"},
                    {"name": "role", "type": "enum", "values": ["manager", "receptionist", "cleaner"]}
                ]
            }
        ],
        "relationships": [
            {"from": "Room", "to": "RoomType", "type": "belongs_to", "label": "属于"},
            {"from": "Reservation", "to": "Guest", "type": "belongs_to", "label": "预订人"},
            {"from": "Reservation", "to": "RoomType", "type": "belongs_to", "label": "房型"},
            {"from": "StayRecord", "to": "Guest", "type": "belongs_to", "label": "入住人"},
            {"from": "StayRecord", "to": "Room", "type": "belongs_to", "label": "入住房间"},
            {"from": "StayRecord", "to": "Reservation", "type": "belongs_to", "label": "来源预订"},
            {"from": "Bill", "to": "StayRecord", "type": "belongs_to", "label": "住宿账单"},
            {"from": "Task", "to": "Room", "type": "belongs_to", "label": "目标房间"},
            {"from": "Task", "to": "Employee", "type": "belongs_to", "label": "执行人"}
        ]
    }


@router.get("/statistics")
async def get_ontology_statistics(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """获取各实体的统计数据"""
    return {
        "entities": {
            "RoomType": {
                "total": db.query(RoomType).count()
            },
            "Room": {
                "total": db.query(Room).count(),
                "by_status": {
                    "vacant_clean": db.query(Room).filter(Room.status == RoomStatus.VACANT_CLEAN).count(),
                    "occupied": db.query(Room).filter(Room.status == RoomStatus.OCCUPIED).count(),
                    "vacant_dirty": db.query(Room).filter(Room.status == RoomStatus.VACANT_DIRTY).count(),
                    "out_of_order": db.query(Room).filter(Room.status == RoomStatus.OUT_OF_ORDER).count()
                }
            },
            "Guest": {
                "total": db.query(Guest).count(),
                "by_tier": {
                    "normal": db.query(Guest).filter(Guest.tier == "normal").count(),
                    "silver": db.query(Guest).filter(Guest.tier == "silver").count(),
                    "gold": db.query(Guest).filter(Guest.tier == "gold").count(),
                    "platinum": db.query(Guest).filter(Guest.tier == "platinum").count()
                }
            },
            "Reservation": {
                "total": db.query(Reservation).count(),
                "by_status": {
                    "confirmed": db.query(Reservation).filter(Reservation.status == ReservationStatus.CONFIRMED).count(),
                    "checked_in": db.query(Reservation).filter(Reservation.status == ReservationStatus.CHECKED_IN).count(),
                    "completed": db.query(Reservation).filter(Reservation.status == ReservationStatus.COMPLETED).count(),
                    "cancelled": db.query(Reservation).filter(Reservation.status == ReservationStatus.CANCELLED).count()
                }
            },
            "StayRecord": {
                "total": db.query(StayRecord).count(),
                "active": db.query(StayRecord).filter(StayRecord.status == StayRecordStatus.ACTIVE).count()
            },
            "Bill": {
                "total": db.query(Bill).count(),
                "settled": db.query(Bill).filter(Bill.is_settled == True).count(),
                "unsettled": db.query(Bill).filter(Bill.is_settled == False).count()
            },
            "Task": {
                "total": db.query(Task).count(),
                "by_status": {
                    "pending": db.query(Task).filter(Task.status == TaskStatus.PENDING).count(),
                    "assigned": db.query(Task).filter(Task.status == TaskStatus.ASSIGNED).count(),
                    "in_progress": db.query(Task).filter(Task.status == TaskStatus.IN_PROGRESS).count(),
                    "completed": db.query(Task).filter(Task.status == TaskStatus.COMPLETED).count()
                }
            },
            "Employee": {
                "total": db.query(Employee).count(),
                "by_role": {
                    "manager": db.query(Employee).filter(Employee.role == EmployeeRole.MANAGER).count(),
                    "receptionist": db.query(Employee).filter(Employee.role == EmployeeRole.RECEPTIONIST).count(),
                    "cleaner": db.query(Employee).filter(Employee.role == EmployeeRole.CLEANER).count()
                }
            }
        }
    }


@router.get("/instance-graph")
async def get_instance_graph(
    center_entity: Optional[str] = Query(None, description="中心实体类型"),
    center_id: Optional[int] = Query(None, description="中心实体ID"),
    depth: int = Query(2, ge=1, le=3, description="关系深度"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
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
        entity_positions = {
            "RoomType": (200, 100),
            "Room": (400, 100),
            "Guest": (100, 300),
            "Reservation": (300, 300),
            "StayRecord": (500, 300),
            "Bill": (700, 300),
            "Task": (600, 100),
            "Employee": (800, 100)
        }

        # 获取统计数据
        stats = {
            "RoomType": db.query(RoomType).count(),
            "Room": db.query(Room).count(),
            "Guest": db.query(Guest).count(),
            "Reservation": db.query(Reservation).count(),
            "StayRecord": db.query(StayRecord).count(),
            "Bill": db.query(Bill).count(),
            "Task": db.query(Task).count(),
            "Employee": db.query(Employee).count()
        }

        entity_labels = {
            "RoomType": "房间类型",
            "Room": "房间",
            "Guest": "客人",
            "Reservation": "预订",
            "StayRecord": "住宿记录",
            "Bill": "账单",
            "Task": "任务",
            "Employee": "员工"
        }

        for entity_name, pos in entity_positions.items():
            nodes.append({
                "id": entity_name,
                "type": "entity",
                "label": entity_labels[entity_name],
                "data": {
                    "name": entity_name,
                    "total": stats.get(entity_name, 0)
                },
                "position": {"x": pos[0], "y": pos[1]}
            })

        # 关系边
        relationships = [
            ("Room", "RoomType", "属于"),
            ("Reservation", "Guest", "预订人"),
            ("Reservation", "RoomType", "房型"),
            ("StayRecord", "Guest", "入住人"),
            ("StayRecord", "Room", "入住房间"),
            ("StayRecord", "Reservation", "来源预订"),
            ("Bill", "StayRecord", "住宿账单"),
            ("Task", "Room", "目标房间"),
            ("Task", "Employee", "执行人")
        ]

        for i, (source, target, label) in enumerate(relationships):
            edges.append({
                "id": f"edge-{i}",
                "source": source,
                "target": target,
                "label": label
            })

    return {"nodes": nodes, "edges": edges}


# ============== 语义层 (Semantic) - 实体属性和关系 ==============

@router.get("/semantic")
async def get_semantic_metadata(
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
):
    """
    获取动态层元数据
    包含状态机、权限矩阵、业务规则
    """
    service = OntologyMetadataService()
    return service.get_dynamic_metadata()


@router.get("/dynamic/state-machines")
async def get_state_machines(
    current_user: Employee = Depends(require_manager)
):
    """获取所有状态机定义"""
    service = OntologyMetadataService()
    dynamic = service.get_dynamic_metadata()
    return dynamic["state_machines"]


@router.get("/dynamic/state-machines/{entity_name}")
async def get_entity_state_machine(
    entity_name: str,
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
):
    """获取权限矩阵"""
    service = OntologyMetadataService()
    dynamic = service.get_dynamic_metadata()
    return dynamic["permission_matrix"]


@router.get("/dynamic/business-rules")
async def get_business_rules(
    entity: Optional[str] = Query(None, description="筛选实体"),
    current_user: Employee = Depends(require_manager)
):
    """获取业务规则列表"""
    service = OntologyMetadataService()
    rules = service._get_business_rules()

    if entity:
        rules = [r for r in rules if r["entity"] == entity]

    return {"rules": rules}


# ============== 接口系统 (Interfaces) - Phase 2.5 ==============

@router.get("/interfaces")
async def get_interfaces(
    current_user: Employee = Depends(require_manager)
):
    """获取所有接口定义及其实现关系"""
    from core.ontology.registry import registry
    schema = registry.export_schema()
    return schema.get("interfaces", {})


@router.get("/interfaces/{interface_name}")
async def get_interface(
    interface_name: str,
    current_user: Employee = Depends(require_manager)
):
    """获取单个接口详情"""
    from core.ontology.registry import registry
    schema = registry.export_schema()
    interfaces = schema.get("interfaces", {})
    return interfaces.get(interface_name, {"error": "Interface not found"})


@router.get("/interfaces/{interface_name}/implementations")
async def get_interface_implementations(
    interface_name: str,
    current_user: Employee = Depends(require_manager)
):
    """获取实现指定接口的所有实体"""
    from core.ontology.registry import registry
    implementations = registry.get_implementations(interface_name)
    return {"interface": interface_name, "implementations": implementations}


@router.get("/entities/{entity_name}/interfaces")
async def get_entity_interfaces(
    entity_name: str,
    current_user: Employee = Depends(require_manager)
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
    current_user: Employee = Depends(require_manager)
):
    """
    导出完整本体 schema (JSON)
    用于版本快照、AI 上下文注入、API 文档生成
    """
    from core.ontology.registry import registry
    return registry.export_schema()
