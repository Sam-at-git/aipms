"""
AIPMS 主应用入口
基于 Palantir 架构思想的酒店管理系统
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, rooms, reservations, checkin, checkout, tasks, billing, employees, reports, ai, prices, settings, audit_logs, guests, conversations, undo, ontology, security, debug
from app.system.routers import dict_router, config_router, rbac_router, menu_router, org_router, message_router, scheduler_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    SPEC-64: 初始化本体注册中心和业务规则
    """
    # 启动时执行
    # 初始化数据库
    init_db()

    # 注册事件处理器
    from app.services.event_handlers import register_event_handlers
    register_event_handlers()

    # 注册告警处理器
    from app.services.alert_service import register_alert_handlers
    register_alert_handlers()

    # ========== SPEC-64: 初始化本体注册中心 ==========
    try:
        # 导入本体注册中心
        from core.ontology import registry

        # 导入并注册领域本体
        from app.hotel.domain import (
            RoomEntity, GuestEntity, ReservationEntity,
            StayRecordEntity, BillEntity, TaskEntity, EmployeeEntity,
        )
        from core.domain.relationships import relationship_registry
        from app.hotel.domain.relationships import register_hotel_relationships
        register_hotel_relationships(relationship_registry)

        # 导入业务规则
        from app.hotel.domain.rules import register_all_rules

        # 注册业务规则（这会注册规则到规则引擎）
        from core.engine.rule_engine import rule_engine
        register_all_rules(rule_engine)

        print("本体注册中心初始化完成")

        # ========== SPEC-R01: Bootstrap HotelDomainAdapter ==========
        from core.ontology.registry import OntologyRegistry
        from app.hotel.hotel_domain_adapter import HotelDomainAdapter

        ont_registry = OntologyRegistry()
        adapter = HotelDomainAdapter()
        adapter.register_ontology(ont_registry)
        print(f"✓ 酒店领域本体已注册 ({len(ont_registry.get_entities())} entities)")

        # ========== Configure embedding service ==========
        from core.ai import configure_embedding_service
        from app.config import settings
        embed_api_key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
        configure_embedding_service(
            api_key=embed_api_key,
            base_url=settings.EMBEDDING_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            cache_size=settings.EMBEDDING_CACHE_SIZE,
            enabled=settings.ENABLE_LLM and settings.EMBEDDING_ENABLED and bool(embed_api_key),
        )

        # ========== Configure admin roles for SecurityContext ==========
        from core.security.context import SecurityContext
        SecurityContext.set_admin_roles({"sysadmin", "manager"})

        # ========== Register hotel role permissions (SPEC-1) ==========
        from app.hotel.security import register_hotel_role_permissions
        register_hotel_role_permissions()
        print("✓ 酒店角色权限已注册")

        # ========== Register hotel domain ACL permissions ==========
        from core.security.attribute_acl import AttributeACL, AttributePermission, SecurityLevel
        acl = AttributeACL()
        acl.register_domain_permissions([
            AttributePermission("Guest", "phone", SecurityLevel.CONFIDENTIAL),
            AttributePermission("Guest", "id_card", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "blacklist_reason", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "tier", SecurityLevel.INTERNAL),
            AttributePermission("Room", "price", SecurityLevel.INTERNAL),
            AttributePermission("Employee", "salary", SecurityLevel.RESTRICTED, allow_write=False),
            AttributePermission("Employee", "password_hash", SecurityLevel.RESTRICTED, allow_read=False),
            AttributePermission("Bill", "total_amount", SecurityLevel.INTERNAL),
        ])

        # ========== SPEC-5: Initialize hotel business rules (domain layer) ==========
        from app.hotel.business_rules import init_hotel_business_rules
        init_hotel_business_rules()
        print("✓ 酒店业务规则已初始化")

        # ========== SPEC-R11: Sync ActionRegistry to OntologyRegistry ==========
        from app.services.actions import get_action_registry, register_smart_updates
        action_registry = get_action_registry()
        action_registry.set_ontology_registry(ont_registry)

        # Register smart update actions (requires populated OntologyRegistry)
        register_smart_updates(ont_registry)
        print(f"✓ ActionRegistry 已同步到 OntologyRegistry ({len(action_registry.list_actions())} actions)")

        # ========== System Domain: Register system entities to OntologyRegistry ==========
        from app.system.system_domain_adapter import SystemDomainAdapter
        sys_adapter = SystemDomainAdapter()
        sys_adapter.register_ontology(ont_registry)
        print(f"✓ 系统管理域本体已注册 ({len([e for e in ont_registry.get_entities() if getattr(e, 'category', '') == 'system'])} system entities)")

        # ========== RBAC: Register permission provider ==========
        from core.security.permission import permission_provider_registry
        from app.system.services.permission_provider import RBACPermissionProvider
        from app.database import SessionLocal
        provider = RBACPermissionProvider(SessionLocal)
        permission_provider_registry.set_provider(provider)
        print("✓ RBAC PermissionProvider 已注册")

        # ========== RBAC: Seed initial data ==========
        from app.system.services.rbac_seed import seed_rbac_data
        from app.system.services.menu_seed import seed_menu_data
        from app.system.services.config_seed import seed_config_data
        seed_db = SessionLocal()
        try:
            seed_stats = seed_rbac_data(seed_db)
            if any(seed_stats.values()):
                print(f"✓ RBAC 种子数据已初始化: {seed_stats}")
            menu_stats = seed_menu_data(seed_db)
            if any(menu_stats.values()):
                print(f"✓ 菜单种子数据已初始化: {menu_stats}")
            config_stats = seed_config_data(seed_db)
            if any(config_stats.values()):
                print(f"✓ 系统配置种子数据已初始化: {config_stats}")
        finally:
            seed_db.close()

    except Exception as e:
        print(f"本体注册中心初始化警告: {e}")

    # ========== 可选：初始化语义搜索索引 ==========
    # 通过环境变量 AUTO_BUILD_SCHEMA_INDEX 控制是否自动构建
    if os.getenv("AUTO_BUILD_SCHEMA_INDEX", "false").lower() == "true":
        try:
            from app.services.schema_index_service import SchemaIndexService

            print("正在构建语义搜索索引...")
            service = SchemaIndexService()
            service.build_index()

            stats = service.get_stats()
            print(f"✓ 语义搜索索引构建完成！共 {stats['total_items']} 项")

        except Exception as e:
            print(f"语义搜索索引构建警告: {e}")

    yield

    # 关闭时执行（如果需要清理资源）
    pass


# 创建应用
app = FastAPI(
    title="AIPMS - 智能酒店管理系统",
    description="基于 Palantir 架构思想的本体运行时酒店管理系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(guests.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(checkin.router)
app.include_router(checkout.router)
app.include_router(tasks.router)
app.include_router(billing.router)
app.include_router(employees.router)
app.include_router(reports.router)
app.include_router(prices.router)
app.include_router(audit_logs.router)
app.include_router(ai.router)
app.include_router(conversations.router)
app.include_router(settings.router)
app.include_router(undo.router)
app.include_router(ontology.router)
app.include_router(security.router)
app.include_router(debug.router)
app.include_router(dict_router.router)
app.include_router(config_router.router)
app.include_router(rbac_router.role_router)
app.include_router(rbac_router.permission_router)
app.include_router(rbac_router.user_role_router)
app.include_router(menu_router.router)
app.include_router(org_router.dept_router)
app.include_router(org_router.pos_router)
app.include_router(message_router.msg_router)
app.include_router(message_router.tpl_router)
app.include_router(message_router.ann_router)
app.include_router(scheduler_router.router)


@app.get("/")
def root():
    """根路径"""
    return {
        "name": "AIPMS - 智能酒店管理系统",
        "version": "1.0.0",
        "description": "基于 Palantir 架构思想的本体运行时"
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}
