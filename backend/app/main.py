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
        from core.domain.room import RoomEntity
        from core.domain.guest import GuestEntity
        from core.domain.reservation import ReservationEntity
        from core.domain.stay_record import StayRecordEntity
        from core.domain.bill import BillEntity
        from core.domain.task import TaskEntity
        from core.domain.employee import EmployeeEntity
        from core.domain.relationships import relationship_registry

        # 导入业务规则
        from core.domain.rules import register_all_rules

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
