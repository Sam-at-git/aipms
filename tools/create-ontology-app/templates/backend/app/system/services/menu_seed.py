"""
菜单种子数据 — 从现有硬编码 navItems 初始化
"""
from sqlalchemy.orm import Session
from app.system.models.menu import SysMenu


SEED_MENUS = [
    # Top-level menus (matching existing navItems from App.tsx)
    {"code": "dashboard", "name": "工作台", "path": "/", "icon": "LayoutDashboard", "menu_type": "menu", "sort_order": 0},
    {"code": "rooms", "name": "房态管理", "path": "/rooms", "icon": "BedDouble", "permission_code": "room:view", "menu_type": "menu", "sort_order": 10},
    {"code": "reservations", "name": "预订管理", "path": "/reservations", "icon": "CalendarCheck", "permission_code": "reservation:view", "menu_type": "menu", "sort_order": 20},
    {"code": "guests", "name": "在住客人", "path": "/guests", "icon": "Users", "permission_code": "guest:view", "menu_type": "menu", "sort_order": 30},
    {"code": "customers", "name": "客户管理", "path": "/customers", "icon": "UserCircle", "permission_code": "guest:view", "menu_type": "menu", "sort_order": 35},
    {"code": "tasks", "name": "任务管理", "path": "/tasks", "icon": "ClipboardList", "permission_code": "task:view", "menu_type": "menu", "sort_order": 40},
    {"code": "billing", "name": "账务管理", "path": "/billing", "icon": "DollarSign", "permission_code": "billing:view", "menu_type": "menu", "sort_order": 50},
    {"code": "prices", "name": "价格管理", "path": "/prices", "icon": "Tag", "permission_code": "price:view", "menu_type": "menu", "sort_order": 60},
    {"code": "employees", "name": "员工管理", "path": "/employees", "icon": "UserCog", "permission_code": "employee:view", "menu_type": "menu", "sort_order": 70},
    {"code": "reports", "name": "统计报表", "path": "/reports", "icon": "BarChart3", "permission_code": "report:view", "menu_type": "menu", "sort_order": 80},

    # System management directory
    {"code": "system", "name": "系统管理", "icon": "Shield", "menu_type": "directory", "permission_code": "system:view", "sort_order": 90},

    {"code": "chat", "name": "独立聊天", "path": "/chat", "icon": "MessageSquare", "permission_code": "ai:chat", "menu_type": "menu", "sort_order": 200},
]

# System sub-menus (parent_code → system)
SYSTEM_SUB_MENUS = [
    {"code": "system_audit", "name": "审计日志", "path": "/audit-logs", "icon": "FileText", "permission_code": "audit:view", "menu_type": "menu", "sort_order": 91},
    {"code": "system_ontology", "name": "本体视图", "path": "/ontology", "icon": "Database", "permission_code": "system:admin", "menu_type": "menu", "sort_order": 92},
    {"code": "system_security", "name": "安全管理", "path": "/security", "icon": "Shield", "permission_code": "system:admin", "menu_type": "menu", "sort_order": 93},
    {"code": "system_conversations", "name": "聊天管理", "path": "/conversation-admin", "icon": "MessageSquare", "permission_code": "system:admin", "menu_type": "menu", "sort_order": 94},
    {"code": "system_debug", "name": "调试面板", "path": "/debug", "icon": "Bug", "permission_code": "debug:view", "menu_type": "menu", "sort_order": 95},
    {"code": "system_benchmark", "name": "Benchmark", "path": "/benchmark", "icon": "FlaskConical", "permission_code": "debug:view", "menu_type": "menu", "sort_order": 95},
    {"code": "system_dicts", "name": "数据字典", "path": "/system/dicts", "icon": "BookOpen", "permission_code": "system:view", "menu_type": "menu", "sort_order": 96},
    {"code": "system_configs", "name": "系统配置", "path": "/system/configs", "icon": "Settings", "permission_code": "system:manage", "menu_type": "menu", "sort_order": 97},
    {"code": "system_rbac", "name": "权限管理", "path": "/system/rbac", "icon": "Shield", "permission_code": "system:admin", "menu_type": "menu", "sort_order": 98},
    {"code": "system_schedulers", "name": "定时任务", "path": "/system/schedulers", "icon": "Clock", "permission_code": "system:admin", "menu_type": "menu", "sort_order": 98},
    {"code": "system_settings", "name": "系统设置", "path": "/settings", "icon": "Settings", "permission_code": "system:manage", "menu_type": "menu", "sort_order": 99},
]


def seed_menu_data(db: Session) -> dict:
    """Seed menu initial data. Idempotent."""
    stats = {"menus": 0}

    # 1. Top-level menus
    for menu_data in SEED_MENUS:
        existing = db.query(SysMenu).filter(SysMenu.code == menu_data["code"]).first()
        if not existing:
            db.add(SysMenu(**menu_data))
            stats["menus"] += 1

    db.flush()

    # 2. System sub-menus
    system_menu = db.query(SysMenu).filter(SysMenu.code == "system").first()
    if system_menu:
        for sub_data in SYSTEM_SUB_MENUS:
            existing = db.query(SysMenu).filter(SysMenu.code == sub_data["code"]).first()
            if not existing:
                db.add(SysMenu(parent_id=system_menu.id, **sub_data))
                stats["menus"] += 1

    db.commit()
    return stats
