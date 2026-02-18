"""
RBAC 种子数据 — 初始化角色、权限、角色-权限映射
"""
from sqlalchemy.orm import Session
from app.system.models.rbac import SysRole, SysPermission, SysRolePermission, SysUserRole
from app.hotel.models.ontology import Employee


# ========== Role Definitions ==========

SEED_ROLES = [
    {"code": "sysadmin", "name": "系统管理员", "description": "拥有所有权限", "data_scope": "ALL", "sort_order": 0, "is_system": True},
    {"code": "manager", "name": "经理", "description": "业务管理权限", "data_scope": "ALL", "sort_order": 1, "is_system": True},
    {"code": "receptionist", "name": "前台", "description": "前台操作权限", "data_scope": "DEPT", "sort_order": 2, "is_system": True},
    {"code": "cleaner", "name": "清洁员", "description": "清洁任务权限", "data_scope": "SELF", "sort_order": 3, "is_system": True},
]

# ========== Permission Definitions ==========

SEED_PERMISSIONS = [
    # Room
    {"code": "room:view", "name": "查看房间", "type": "api", "resource": "room", "action": "view", "sort_order": 10},
    {"code": "room:update", "name": "更新房间状态", "type": "api", "resource": "room", "action": "update", "sort_order": 11},
    {"code": "room:manage", "name": "管理房间/房型", "type": "api", "resource": "room", "action": "manage", "sort_order": 12},
    # Reservation
    {"code": "reservation:view", "name": "查看预订", "type": "api", "resource": "reservation", "action": "view", "sort_order": 20},
    {"code": "reservation:create", "name": "创建预订", "type": "api", "resource": "reservation", "action": "create", "sort_order": 21},
    {"code": "reservation:update", "name": "修改/取消预订", "type": "api", "resource": "reservation", "action": "update", "sort_order": 22},
    # Guest
    {"code": "guest:view", "name": "查看客人", "type": "api", "resource": "guest", "action": "view", "sort_order": 30},
    {"code": "guest:create", "name": "创建客人", "type": "api", "resource": "guest", "action": "create", "sort_order": 31},
    {"code": "guest:update", "name": "更新客人信息", "type": "api", "resource": "guest", "action": "update", "sort_order": 32},
    # Check-in/out
    {"code": "checkin:execute", "name": "办理入住", "type": "api", "resource": "checkin", "action": "execute", "sort_order": 40},
    {"code": "checkout:execute", "name": "办理退房", "type": "api", "resource": "checkout", "action": "execute", "sort_order": 41},
    # Task
    {"code": "task:view", "name": "查看任务", "type": "api", "resource": "task", "action": "view", "sort_order": 50},
    {"code": "task:create", "name": "创建任务", "type": "api", "resource": "task", "action": "create", "sort_order": 51},
    {"code": "task:assign", "name": "分配任务", "type": "api", "resource": "task", "action": "assign", "sort_order": 52},
    {"code": "task:complete", "name": "完成任务", "type": "api", "resource": "task", "action": "complete", "sort_order": 53},
    # Billing
    {"code": "billing:view", "name": "查看账单", "type": "api", "resource": "billing", "action": "view", "sort_order": 60},
    {"code": "billing:create", "name": "创建/收款", "type": "api", "resource": "billing", "action": "create", "sort_order": 61},
    {"code": "billing:manage", "name": "管理账单/退款", "type": "api", "resource": "billing", "action": "manage", "sort_order": 62},
    # Price
    {"code": "price:view", "name": "查看价格", "type": "api", "resource": "price", "action": "view", "sort_order": 70},
    {"code": "price:manage", "name": "管理价格", "type": "api", "resource": "price", "action": "manage", "sort_order": 71},
    # Employee
    {"code": "employee:view", "name": "查看员工", "type": "api", "resource": "employee", "action": "view", "sort_order": 80},
    {"code": "employee:manage", "name": "管理员工", "type": "api", "resource": "employee", "action": "manage", "sort_order": 81},
    # AI/Chat
    {"code": "ai:chat", "name": "使用AI对话", "type": "api", "resource": "ai", "action": "chat", "sort_order": 90},
    {"code": "ai:execute", "name": "执行AI操作", "type": "api", "resource": "ai", "action": "execute", "sort_order": 91},
    # System
    {"code": "system:view", "name": "查看系统设置", "type": "api", "resource": "system", "action": "view", "sort_order": 100},
    {"code": "system:manage", "name": "管理系统配置", "type": "api", "resource": "system", "action": "manage", "sort_order": 101},
    {"code": "system:admin", "name": "系统管理员操作", "type": "api", "resource": "system", "action": "admin", "sort_order": 102},
    # Debug
    {"code": "debug:view", "name": "查看调试面板", "type": "api", "resource": "debug", "action": "view", "sort_order": 110},
    {"code": "debug:manage", "name": "管理调试/回放", "type": "api", "resource": "debug", "action": "manage", "sort_order": 111},
    # Audit
    {"code": "audit:view", "name": "查看审计日志", "type": "api", "resource": "audit", "action": "view", "sort_order": 120},
    # Report
    {"code": "report:view", "name": "查看报表", "type": "api", "resource": "report", "action": "view", "sort_order": 130},
]

# ========== Role→Permission Mappings ==========

ROLE_PERMISSIONS = {
    "sysadmin": None,  # None = ALL permissions
    "manager": [
        "room:view", "room:update", "room:manage",
        "reservation:view", "reservation:create", "reservation:update",
        "guest:view", "guest:create", "guest:update",
        "checkin:execute", "checkout:execute",
        "task:view", "task:create", "task:assign", "task:complete",
        "billing:view", "billing:create", "billing:manage",
        "price:view", "price:manage",
        "employee:view", "employee:manage",
        "ai:chat", "ai:execute",
        "system:view",
        "report:view",
    ],
    "receptionist": [
        "room:view", "room:update",
        "reservation:view", "reservation:create", "reservation:update",
        "guest:view", "guest:create", "guest:update",
        "checkin:execute", "checkout:execute",
        "task:view", "task:create",
        "billing:view", "billing:create",
        "price:view",
        "ai:chat", "ai:execute",
    ],
    "cleaner": [
        "task:view", "task:complete",
        "ai:chat",
    ],
}


def seed_rbac_data(db: Session) -> dict:
    """Seed RBAC initial data. Idempotent — skips existing records.

    Returns dict with counts of created items.
    """
    stats = {"roles": 0, "permissions": 0, "mappings": 0, "user_roles": 0}

    # 1. Seed roles
    for role_data in SEED_ROLES:
        existing = db.query(SysRole).filter(SysRole.code == role_data["code"]).first()
        if not existing:
            db.add(SysRole(**role_data))
            stats["roles"] += 1

    db.flush()

    # 2. Seed permissions
    for perm_data in SEED_PERMISSIONS:
        existing = db.query(SysPermission).filter(SysPermission.code == perm_data["code"]).first()
        if not existing:
            db.add(SysPermission(**perm_data))
            stats["permissions"] += 1

    db.flush()

    # 3. Seed role→permission mappings
    perm_map = {p.code: p.id for p in db.query(SysPermission).all()}
    all_perm_ids = list(perm_map.values())

    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        role = db.query(SysRole).filter(SysRole.code == role_code).first()
        if not role:
            continue

        target_ids = all_perm_ids if perm_codes is None else [perm_map[c] for c in perm_codes if c in perm_map]

        for pid in target_ids:
            existing = db.query(SysRolePermission).filter(
                SysRolePermission.role_id == role.id,
                SysRolePermission.permission_id == pid
            ).first()
            if not existing:
                db.add(SysRolePermission(role_id=role.id, permission_id=pid))
                stats["mappings"] += 1

    db.flush()

    # 4. Seed user→role mappings from existing Employee.role field
    role_map = {r.code: r.id for r in db.query(SysRole).all()}
    employees = db.query(Employee).all()

    for emp in employees:
        role_code = emp.role.value if hasattr(emp.role, 'value') else str(emp.role)
        if role_code in role_map:
            existing = db.query(SysUserRole).filter(
                SysUserRole.user_id == emp.id,
                SysUserRole.role_id == role_map[role_code]
            ).first()
            if not existing:
                db.add(SysUserRole(user_id=emp.id, role_id=role_map[role_code]))
                stats["user_roles"] += 1

    db.commit()
    return stats
